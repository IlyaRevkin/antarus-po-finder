"""
Antarus PO Finder — SQLite Database
======================================
Single-file SQLite store for all persistent data.
Schema: rules, versions, templates, sync_queue, equipment_groups,
        equipment_subtypes, controller_models, fw_versions (new format).
"""

import sqlite3
import json
import os
from datetime import datetime
from pathlib import Path
from typing import Optional

from app.domain.models import (
    Rule, FirmwareVersion, Template, SyncQueueItem, Version
)
from app.domain.hierarchy import (
    EquipmentGroup, EquipmentSubType, ControllerModel, FWVersion,
    DEFAULT_EQUIPMENT_GROUPS, DEFAULT_SUB_TYPES, DEFAULT_CONTROLLERS,
)

_ISO = '%Y-%m-%d %H:%M:%S'


def _now() -> str:
    return datetime.now().strftime(_ISO)


def _dt(s: Optional[str]) -> Optional[datetime]:
    if not s:
        return None
    try:
        return datetime.strptime(s, _ISO)
    except Exception:
        return None


class Database:
    """Thread-safe SQLite wrapper with schema migrations."""

    def __init__(self, db_path: str):
        self._path = db_path
        os.makedirs(os.path.dirname(db_path), exist_ok=True)
        self._conn = sqlite3.connect(db_path, check_same_thread=False)
        self._conn.row_factory = sqlite3.Row
        self._conn.execute('PRAGMA journal_mode=WAL')
        self._conn.execute('PRAGMA foreign_keys=ON')
        self._migrate()

    # ── Schema ────────────────────────────────────────────────────────────────

    def _migrate(self):
        cur = self._conn.cursor()
        cur.executescript("""
        -- Hierarchy tables
        CREATE TABLE IF NOT EXISTS equipment_groups (
            id         INTEGER PRIMARY KEY AUTOINCREMENT,
            name       TEXT    UNIQUE NOT NULL,
            prefix     INTEGER NOT NULL DEFAULT 0,
            sort_order INTEGER NOT NULL DEFAULT 0
        );

        CREATE TABLE IF NOT EXISTS equipment_subtypes (
            id          INTEGER PRIMARY KEY AUTOINCREMENT,
            group_id    INTEGER NOT NULL REFERENCES equipment_groups(id) ON DELETE CASCADE,
            name        TEXT    NOT NULL,
            prefix      INTEGER NOT NULL DEFAULT 0,
            folder_name TEXT    NOT NULL,
            sort_order  INTEGER NOT NULL DEFAULT 0,
            UNIQUE(group_id, name)
        );

        CREATE TABLE IF NOT EXISTS controller_models (
            id         INTEGER PRIMARY KEY AUTOINCREMENT,
            name       TEXT    UNIQUE NOT NULL,
            sort_order INTEGER NOT NULL DEFAULT 0
        );

        -- New-format firmware versions
        CREATE TABLE IF NOT EXISTS fw_versions (
            id              INTEGER PRIMARY KEY AUTOINCREMENT,
            subtype_id      INTEGER REFERENCES equipment_subtypes(id),
            controller_id   INTEGER REFERENCES controller_models(id),
            eq_prefix       INTEGER NOT NULL DEFAULT 0,
            sub_prefix      INTEGER NOT NULL DEFAULT 0,
            hw_version      INTEGER NOT NULL DEFAULT 0,
            sw_version      INTEGER NOT NULL DEFAULT 0,
            dt_str          TEXT    NOT NULL DEFAULT '',
            version_raw     TEXT    NOT NULL DEFAULT '',
            filename        TEXT    NOT NULL DEFAULT '',
            disk_path       TEXT    NOT NULL DEFAULT '',
            local_path      TEXT    NOT NULL DEFAULT '',
            description     TEXT    NOT NULL DEFAULT '',
            changelog       TEXT    NOT NULL DEFAULT '',
            launch_types    TEXT    NOT NULL DEFAULT '[]',
            io_map_path     TEXT    NOT NULL DEFAULT '',
            instructions_path TEXT  NOT NULL DEFAULT '',
            is_opc          INTEGER NOT NULL DEFAULT 0,
            request_num     TEXT    NOT NULL DEFAULT '',
            archived        INTEGER NOT NULL DEFAULT 0,
            upload_date     TEXT    NOT NULL
        );

        -- Param manufacturers (for parameter search)
        CREATE TABLE IF NOT EXISTS param_manufacturers (
            id         INTEGER PRIMARY KEY AUTOINCREMENT,
            name       TEXT UNIQUE NOT NULL,
            sort_order INTEGER NOT NULL DEFAULT 0
        );

        -- Parameter files (ПЧ / УПП parameters)
        CREATE TABLE IF NOT EXISTS param_files (
            id           INTEGER PRIMARY KEY AUTOINCREMENT,
            subtype_id   INTEGER REFERENCES equipment_subtypes(id),
            manufacturer TEXT    NOT NULL DEFAULT '',
            filename     TEXT    NOT NULL,
            disk_path    TEXT    NOT NULL,
            description  TEXT    NOT NULL DEFAULT '',
            upload_date  TEXT    NOT NULL DEFAULT '',
            archived     INTEGER NOT NULL DEFAULT 0
        );
        """)
        self._conn.commit()

        # Seed defaults if tables are empty
        self._seed_hierarchy_defaults()

        # Original tables migration (existing schema)
        cur.executescript("""
        CREATE TABLE IF NOT EXISTS rules (
            id                INTEGER PRIMARY KEY AUTOINCREMENT,
            name              TEXT    UNIQUE NOT NULL,
            equipment_type    TEXT    NOT NULL DEFAULT '',
            work_type         TEXT    NOT NULL DEFAULT '',
            controller        TEXT    NOT NULL DEFAULT '',
            firmware_dir      TEXT    NOT NULL DEFAULT '',
            firmware_type     TEXT    NOT NULL DEFAULT 'plc',
            software_name     TEXT    NOT NULL DEFAULT '',
            keywords          TEXT    NOT NULL DEFAULT '[]',
            exclude_keywords  TEXT    NOT NULL DEFAULT '[]',
            kw_mode           TEXT    NOT NULL DEFAULT 'all',
            local_dir         TEXT    NOT NULL DEFAULT '',
            local_synced      INTEGER NOT NULL DEFAULT 0,
            disk_snapshot     TEXT    NOT NULL DEFAULT '{}',
            param_pch_dir     TEXT    NOT NULL DEFAULT '',
            param_upp_dir     TEXT    NOT NULL DEFAULT '',
            passport_dir      TEXT    NOT NULL DEFAULT '',
            io_map_path       TEXT    NOT NULL DEFAULT '',
            instructions_path TEXT    NOT NULL DEFAULT '',
            notes_file        TEXT    NOT NULL DEFAULT '',
            created_at        TEXT    NOT NULL,
            updated_at        TEXT    NOT NULL
        );

        CREATE TABLE IF NOT EXISTS versions (
            id          INTEGER PRIMARY KEY AUTOINCREMENT,
            rule_names  TEXT    NOT NULL DEFAULT '[]',
            version     TEXT    NOT NULL,
            filename    TEXT    NOT NULL DEFAULT '',
            local_path  TEXT    NOT NULL DEFAULT '',
            disk_path   TEXT    NOT NULL DEFAULT '',
            controller  TEXT    NOT NULL DEFAULT '',
            device_type TEXT    NOT NULL DEFAULT '',
            work_type   TEXT    NOT NULL DEFAULT '',
            extension   TEXT    NOT NULL DEFAULT '',
            description TEXT    NOT NULL DEFAULT '',
            changelog   TEXT    NOT NULL DEFAULT '',
            upload_date TEXT    NOT NULL,
            archived    INTEGER NOT NULL DEFAULT 0,
            io_map_path    TEXT NOT NULL DEFAULT '',
            param_pch_dir  TEXT NOT NULL DEFAULT '',
            param_upp_dir  TEXT NOT NULL DEFAULT ''
        );

        CREATE TABLE IF NOT EXISTS templates (
            id            INTEGER PRIMARY KEY AUTOINCREMENT,
            name          TEXT    UNIQUE NOT NULL,
            template_type TEXT    NOT NULL DEFAULT 'upp',
            path          TEXT    NOT NULL DEFAULT '',
            description   TEXT    NOT NULL DEFAULT '',
            rule_names    TEXT    NOT NULL DEFAULT '[]'
        );

        CREATE TABLE IF NOT EXISTS sync_queue (
            id         INTEGER PRIMARY KEY AUTOINCREMENT,
            action     TEXT    NOT NULL,
            payload    TEXT    NOT NULL DEFAULT '{}',
            created_at TEXT    NOT NULL,
            synced_at  TEXT,
            status     TEXT    NOT NULL DEFAULT 'pending',
            error      TEXT    NOT NULL DEFAULT ''
        );

        CREATE TABLE IF NOT EXISTS settings (
            key   TEXT PRIMARY KEY,
            value TEXT NOT NULL DEFAULT ''
        );
        """)
        self._conn.commit()

    def _seed_hierarchy_defaults(self):
        """Insert default hierarchy data if tables are empty."""
        if self._conn.execute('SELECT COUNT(*) FROM equipment_groups').fetchone()[0] > 0:
            return

        # Insert groups
        for g in DEFAULT_EQUIPMENT_GROUPS:
            self._conn.execute(
                'INSERT OR IGNORE INTO equipment_groups(name,prefix,sort_order) VALUES(?,?,?)',
                (g['name'], g['prefix'], g['sort_order'])
            )

        # Build name→id map
        groups_map: dict[str, int] = {}
        for row in self._conn.execute('SELECT id, name FROM equipment_groups'):
            groups_map[row['name']] = row['id']

        # Insert subtypes
        for s in DEFAULT_SUB_TYPES:
            gid = groups_map.get(s['group_name'])
            if gid:
                self._conn.execute(
                    'INSERT OR IGNORE INTO equipment_subtypes'
                    '(group_id,name,prefix,folder_name,sort_order) VALUES(?,?,?,?,?)',
                    (gid, s['name'], s['prefix'], s['folder_name'], s['sort_order'])
                )

        # Insert controllers
        for c in DEFAULT_CONTROLLERS:
            self._conn.execute(
                'INSERT OR IGNORE INTO controller_models(name,sort_order) VALUES(?,?)',
                (c['name'], c['sort_order'])
            )

        # Seed default manufacturers
        for i, m in enumerate(['VEDS', 'HERTZ', 'DANFOSS', 'ABB', 'SIEMENS', 'АЭП']):
            self._conn.execute(
                'INSERT OR IGNORE INTO param_manufacturers(name,sort_order) VALUES(?,?)',
                (m, i + 1)
            )

        self._conn.commit()

    # ── Equipment Groups ──────────────────────────────────────────────────────

    def get_all_equipment_groups(self) -> list[EquipmentGroup]:
        rows = self._conn.execute(
            'SELECT * FROM equipment_groups ORDER BY sort_order, name'
        ).fetchall()
        return [EquipmentGroup(id=r['id'], name=r['name'],
                               prefix=r['prefix'], sort_order=r['sort_order'])
                for r in rows]

    def upsert_equipment_group(self, g: EquipmentGroup) -> int:
        self._conn.execute(
            'INSERT INTO equipment_groups(name,prefix,sort_order) VALUES(?,?,?)'
            ' ON CONFLICT(name) DO UPDATE SET prefix=excluded.prefix, sort_order=excluded.sort_order',
            (g.name, g.prefix, g.sort_order)
        )
        self._conn.commit()
        row = self._conn.execute('SELECT id FROM equipment_groups WHERE name=?', (g.name,)).fetchone()
        return row['id'] if row else -1

    def delete_equipment_group(self, group_id: int):
        self._conn.execute('DELETE FROM equipment_groups WHERE id=?', (group_id,))
        self._conn.commit()

    # ── Equipment SubTypes ────────────────────────────────────────────────────

    def get_all_equipment_subtypes(self) -> list[EquipmentSubType]:
        rows = self._conn.execute(
            'SELECT * FROM equipment_subtypes ORDER BY group_id, sort_order, name'
        ).fetchall()
        return [EquipmentSubType(id=r['id'], group_id=r['group_id'], name=r['name'],
                                 prefix=r['prefix'], folder_name=r['folder_name'],
                                 sort_order=r['sort_order'])
                for r in rows]

    def get_subtypes_for_group(self, group_id: int) -> list[EquipmentSubType]:
        rows = self._conn.execute(
            'SELECT * FROM equipment_subtypes WHERE group_id=? ORDER BY sort_order, name',
            (group_id,)
        ).fetchall()
        return [EquipmentSubType(id=r['id'], group_id=r['group_id'], name=r['name'],
                                 prefix=r['prefix'], folder_name=r['folder_name'],
                                 sort_order=r['sort_order'])
                for r in rows]

    def upsert_equipment_subtype(self, s: EquipmentSubType) -> int:
        self._conn.execute(
            'INSERT INTO equipment_subtypes(group_id,name,prefix,folder_name,sort_order)'
            ' VALUES(?,?,?,?,?)'
            ' ON CONFLICT(group_id,name) DO UPDATE SET'
            ' prefix=excluded.prefix, folder_name=excluded.folder_name, sort_order=excluded.sort_order',
            (s.group_id, s.name, s.prefix, s.folder_name, s.sort_order)
        )
        self._conn.commit()
        row = self._conn.execute(
            'SELECT id FROM equipment_subtypes WHERE group_id=? AND name=?',
            (s.group_id, s.name)
        ).fetchone()
        return row['id'] if row else -1

    def delete_equipment_subtype(self, subtype_id: int):
        self._conn.execute('DELETE FROM equipment_subtypes WHERE id=?', (subtype_id,))
        self._conn.commit()

    # ── Controller Models ─────────────────────────────────────────────────────

    def get_all_controller_models(self) -> list[ControllerModel]:
        rows = self._conn.execute(
            'SELECT * FROM controller_models ORDER BY sort_order, name'
        ).fetchall()
        return [ControllerModel(id=r['id'], name=r['name'], sort_order=r['sort_order'])
                for r in rows]

    def upsert_controller_model(self, c: ControllerModel) -> int:
        self._conn.execute(
            'INSERT INTO controller_models(name,sort_order) VALUES(?,?)'
            ' ON CONFLICT(name) DO UPDATE SET sort_order=excluded.sort_order',
            (c.name, c.sort_order)
        )
        self._conn.commit()
        row = self._conn.execute('SELECT id FROM controller_models WHERE name=?', (c.name,)).fetchone()
        return row['id'] if row else -1

    def delete_controller_model(self, ctrl_id: int):
        self._conn.execute('DELETE FROM controller_models WHERE id=?', (ctrl_id,))
        self._conn.commit()

    # ── New FW Versions ───────────────────────────────────────────────────────

    def add_fw_version(self, v: dict) -> int:
        """Insert a new fw_version record. v is a dict with all fields."""
        cur = self._conn.execute(
            """INSERT INTO fw_versions
               (subtype_id,controller_id,eq_prefix,sub_prefix,hw_version,sw_version,
                dt_str,version_raw,filename,disk_path,local_path,description,changelog,
                launch_types,io_map_path,instructions_path,is_opc,request_num,archived,upload_date)
               VALUES(?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)""",
            (v.get('subtype_id'), v.get('controller_id'),
             v.get('eq_prefix', 0), v.get('sub_prefix', 0),
             v.get('hw_version', 0), v.get('sw_version', 0),
             v.get('dt_str', ''), v.get('version_raw', ''),
             v.get('filename', ''), v.get('disk_path', ''),
             v.get('local_path', ''), v.get('description', ''),
             v.get('changelog', ''),
             json.dumps(v.get('launch_types', []), ensure_ascii=False),
             v.get('io_map_path', ''), v.get('instructions_path', ''),
             int(v.get('is_opc', False)), v.get('request_num', ''),
             0, _now())
        )
        self._conn.commit()
        return cur.lastrowid

    def get_fw_versions(self, subtype_id: int | None = None,
                        controller_id: int | None = None,
                        include_archived: bool = False) -> list[dict]:
        q = 'SELECT * FROM fw_versions WHERE 1=1'
        params: list = []
        if subtype_id is not None:
            q += ' AND subtype_id=?'; params.append(subtype_id)
        if controller_id is not None:
            q += ' AND controller_id=?'; params.append(controller_id)
        if not include_archived:
            q += ' AND archived=0'
        q += ' ORDER BY dt_str DESC, hw_version DESC, sw_version DESC'
        rows = self._conn.execute(q, params).fetchall()
        return [self._fw_row_to_dict(r) for r in rows]

    def _fw_row_to_dict(self, row: sqlite3.Row) -> dict:
        d = dict(row)
        d['launch_types'] = json.loads(d.get('launch_types') or '[]')
        return d

    def get_latest_fw_version(self, subtype_id: int,
                               controller_id: int) -> dict | None:
        versions = self.get_fw_versions(subtype_id, controller_id)
        if not versions:
            return None
        def _key(v):
            fwv = FWVersion.parse(v['version_raw'])
            return fwv if fwv else FWVersion(raw='', eq_prefix=0, sub_prefix=0,
                                              hw_version=0, sw_version=0, dt_str='')
        return max(versions, key=_key)

    def search_fw_versions_by_tokens(self, tokens: list[str]) -> list[dict]:
        """Return latest fw_version per (subtype_id, controller_id) matching ALL tokens.
        Tokens are matched case-insensitively against group name, subtype name/folder, controller name.
        """
        rows = self._conn.execute('''
            SELECT fv.id, fv.subtype_id, fv.controller_id, fv.version_raw,
                   fv.hw_version, fv.sw_version, fv.description, fv.upload_date,
                   fv.disk_path, fv.filename, fv.io_map_path, fv.instructions_path,
                   fv.launch_types, fv.is_opc,
                   eg.name  AS group_name,
                   es.name  AS subtype_name,
                   es.folder_name AS subtype_folder,
                   cm.name  AS ctrl_name
            FROM fw_versions fv
            JOIN equipment_subtypes es ON fv.subtype_id  = es.id
            JOIN equipment_groups   eg ON es.group_id    = eg.id
            JOIN controller_models  cm ON fv.controller_id = cm.id
            WHERE fv.archived = 0
            ORDER BY fv.id DESC
        ''').fetchall()

        if not rows:
            return []

        toks_upper = [t.upper() for t in tokens if t]

        def _matches(row) -> bool:
            haystack = ' '.join([
                row['group_name']     or '',
                row['subtype_name']   or '',
                row['subtype_folder'] or '',
                row['ctrl_name']      or '',
            ]).upper()
            return all(t in haystack for t in toks_upper)

        seen: dict[tuple, dict] = {}
        for row in rows:
            if not _matches(row):
                continue
            key = (row['subtype_id'], row['controller_id'])
            if key not in seen:
                seen[key] = dict(row)

        return list(seen.values())

    def archive_fw_version(self, version_id: int):
        self._conn.execute('UPDATE fw_versions SET archived=1 WHERE id=?', (version_id,))
        self._conn.commit()

    def update_fw_io_map(self, version_id: int, io_map_path: str):
        self._conn.execute('UPDATE fw_versions SET io_map_path=? WHERE id=?',
                           (io_map_path, version_id))
        self._conn.commit()

    def update_fw_instructions(self, version_id: int, instructions_path: str):
        self._conn.execute('UPDATE fw_versions SET instructions_path=? WHERE id=?',
                           (instructions_path, version_id))
        self._conn.commit()

    # ── Param Manufacturers ───────────────────────────────────────────────────

    def get_param_manufacturers(self) -> list[str]:
        rows = self._conn.execute(
            'SELECT name FROM param_manufacturers ORDER BY sort_order, name'
        ).fetchall()
        return [r['name'] for r in rows]

    def add_param_manufacturer(self, name: str):
        self._conn.execute(
            'INSERT OR IGNORE INTO param_manufacturers(name) VALUES(?)', (name,)
        )
        self._conn.commit()

    def delete_param_manufacturer(self, name: str):
        self._conn.execute('DELETE FROM param_manufacturers WHERE name=?', (name,))
        self._conn.commit()

    # ── Param files ───────────────────────────────────────────────────────────

    def add_param_file(self, data: dict) -> int:
        cur = self._conn.execute(
            '''INSERT INTO param_files
               (subtype_id, manufacturer, filename, disk_path, description, upload_date)
               VALUES (:subtype_id, :manufacturer, :filename, :disk_path, :description, :upload_date)''',
            data,
        )
        self._conn.commit()
        return cur.lastrowid

    def get_param_files(self, subtype_id: int | None = None,
                        manufacturer: str | None = None) -> list[dict]:
        q = '''
            SELECT pf.*, es.name AS subtype_name, es.folder_name,
                   eg.name AS group_name
            FROM param_files pf
            LEFT JOIN equipment_subtypes es ON pf.subtype_id = es.id
            LEFT JOIN equipment_groups   eg ON es.group_id   = eg.id
            WHERE pf.archived = 0
        '''
        params: list = []
        if subtype_id is not None:
            q += ' AND pf.subtype_id = ?'
            params.append(subtype_id)
        if manufacturer:
            q += ' AND pf.manufacturer = ?'
            params.append(manufacturer)
        q += ' ORDER BY pf.upload_date DESC'
        rows = self._conn.execute(q, params).fetchall()
        return [dict(r) for r in rows]

    def delete_param_file(self, file_id: int):
        self._conn.execute('UPDATE param_files SET archived=1 WHERE id=?', (file_id,))
        self._conn.commit()

    # ── Settings ──────────────────────────────────────────────────────────────

    def get_setting(self, key: str, default: str = '') -> str:
        row = self._conn.execute(
            'SELECT value FROM settings WHERE key=?', (key,)
        ).fetchone()
        return row['value'] if row else default

    def set_setting(self, key: str, value: str):
        self._conn.execute(
            'INSERT INTO settings(key,value) VALUES(?,?) '
            'ON CONFLICT(key) DO UPDATE SET value=excluded.value',
            (key, value)
        )
        self._conn.commit()

    # ── Rules ─────────────────────────────────────────────────────────────────

    def upsert_rule(self, rule: Rule) -> int:
        now = _now()
        cur = self._conn.execute(
            """INSERT INTO rules
               (name,equipment_type,work_type,controller,firmware_dir,firmware_type,
                software_name,keywords,exclude_keywords,kw_mode,local_dir,local_synced,
                disk_snapshot,param_pch_dir,param_upp_dir,passport_dir,io_map_path,
                instructions_path,notes_file,created_at,updated_at)
               VALUES(?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)
               ON CONFLICT(name) DO UPDATE SET
                 equipment_type=excluded.equipment_type,
                 work_type=excluded.work_type,
                 controller=excluded.controller,
                 firmware_dir=excluded.firmware_dir,
                 firmware_type=excluded.firmware_type,
                 software_name=excluded.software_name,
                 keywords=excluded.keywords,
                 exclude_keywords=excluded.exclude_keywords,
                 kw_mode=excluded.kw_mode,
                 local_dir=excluded.local_dir,
                 local_synced=excluded.local_synced,
                 disk_snapshot=excluded.disk_snapshot,
                 param_pch_dir=excluded.param_pch_dir,
                 param_upp_dir=excluded.param_upp_dir,
                 passport_dir=excluded.passport_dir,
                 io_map_path=excluded.io_map_path,
                 instructions_path=excluded.instructions_path,
                 notes_file=excluded.notes_file,
                 updated_at=excluded.updated_at
            """,
            (rule.name, rule.equipment_type, rule.work_type, rule.controller,
             rule.firmware_dir, rule.firmware_type, rule.software_name,
             json.dumps(rule.keywords, ensure_ascii=False),
             json.dumps(rule.exclude_keywords, ensure_ascii=False),
             rule.kw_mode, rule.local_dir, int(rule.local_synced),
             json.dumps(rule.disk_snapshot, ensure_ascii=False),
             rule.param_pch_dir, rule.param_upp_dir, rule.passport_dir,
             rule.io_map_path, rule.instructions_path, rule.notes_file,
             now, now)
        )
        self._conn.commit()
        if rule.id:
            return rule.id
        row = self._conn.execute(
            'SELECT id FROM rules WHERE name=?', (rule.name,)
        ).fetchone()
        return row['id'] if row else -1

    def get_rule(self, name: str) -> Optional[Rule]:
        row = self._conn.execute(
            'SELECT * FROM rules WHERE name=?', (name,)
        ).fetchone()
        return self._row_to_rule(row) if row else None

    def get_all_rules(self) -> list[Rule]:
        rows = self._conn.execute('SELECT * FROM rules ORDER BY name').fetchall()
        return [self._row_to_rule(r) for r in rows]

    def delete_rule(self, rule_id: int):
        self._conn.execute('DELETE FROM rules WHERE id=?', (rule_id,))
        self._conn.commit()

    def _row_to_rule(self, row: sqlite3.Row) -> Rule:
        return Rule(
            id=row['id'],
            name=row['name'],
            equipment_type=row['equipment_type'],
            work_type=row['work_type'],
            controller=row['controller'],
            firmware_dir=row['firmware_dir'],
            firmware_type=row['firmware_type'],
            software_name=row['software_name'],
            keywords=json.loads(row['keywords'] or '[]'),
            exclude_keywords=json.loads(row['exclude_keywords'] or '[]'),
            kw_mode=row['kw_mode'],
            local_dir=row['local_dir'],
            local_synced=bool(row['local_synced']),
            disk_snapshot=json.loads(row['disk_snapshot'] or '{}'),
            param_pch_dir=row['param_pch_dir'],
            param_upp_dir=row['param_upp_dir'],
            passport_dir=row['passport_dir'],
            io_map_path=row['io_map_path'],
            instructions_path=row['instructions_path'],
            notes_file=row['notes_file'],
            created_at=_dt(row['created_at']) or datetime.now(),
            updated_at=_dt(row['updated_at']) or datetime.now(),
        )

    # ── Versions ──────────────────────────────────────────────────────────────

    def add_version(self, fv: FirmwareVersion) -> int:
        cur = self._conn.execute(
            """INSERT INTO versions
               (rule_names,version,filename,local_path,disk_path,controller,
                device_type,work_type,extension,description,changelog,
                upload_date,archived,io_map_path,param_pch_dir,param_upp_dir)
               VALUES(?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)
            """,
            (json.dumps(fv.rule_names, ensure_ascii=False),
             str(fv.version),
             fv.filename, fv.local_path, fv.disk_path,
             fv.controller, fv.device_type, fv.work_type, fv.extension,
             fv.description, fv.changelog,
             fv.upload_date.strftime(_ISO),
             int(fv.archived),
             fv.io_map_path, fv.param_pch_dir, fv.param_upp_dir)
        )
        self._conn.commit()
        return cur.lastrowid

    def get_versions_for_rule(self, rule_name: str,
                              include_archived: bool = False) -> list[FirmwareVersion]:
        rows = self._conn.execute(
            'SELECT * FROM versions ORDER BY upload_date DESC'
        ).fetchall()
        result = []
        for row in rows:
            names = json.loads(row['rule_names'] or '[]')
            if rule_name in names:
                if not include_archived and row['archived']:
                    continue
                fv = self._row_to_version(row)
                if fv:
                    result.append(fv)
        return result

    def get_latest_version(self, rule_name: str) -> Optional[FirmwareVersion]:
        versions = self.get_versions_for_rule(rule_name, include_archived=False)
        if not versions:
            return None
        # Sort by Version object
        def _key(fv: FirmwareVersion):
            v = Version.parse(str(fv.version))
            return v if v else Version(raw='', prefix=0, body=(0,), date=0)
        return max(versions, key=_key)

    def archive_version(self, version_id: int):
        self._conn.execute(
            'UPDATE versions SET archived=1 WHERE id=?', (version_id,)
        )
        self._conn.commit()

    def restore_version(self, version_id: int):
        self._conn.execute(
            'UPDATE versions SET archived=0 WHERE id=?', (version_id,)
        )
        self._conn.commit()

    def delete_version(self, version_id: int):
        self._conn.execute('DELETE FROM versions WHERE id=?', (version_id,))
        self._conn.commit()

    def get_all_versions(self) -> list[FirmwareVersion]:
        rows = self._conn.execute(
            'SELECT * FROM versions ORDER BY upload_date DESC'
        ).fetchall()
        return [v for r in rows if (v := self._row_to_version(r))]

    def _row_to_version(self, row: sqlite3.Row) -> Optional[FirmwareVersion]:
        ver = Version.parse(row['version'])
        if not ver:
            ver = Version(raw=row['version'], prefix=0, body=(0,), date=0)
        return FirmwareVersion(
            id=row['id'],
            rule_ids=[],
            rule_names=json.loads(row['rule_names'] or '[]'),
            version=ver,
            filename=row['filename'],
            local_path=row['local_path'],
            disk_path=row['disk_path'],
            controller=row['controller'],
            device_type=row['device_type'],
            work_type=row['work_type'],
            extension=row['extension'],
            description=row['description'],
            changelog=row['changelog'],
            upload_date=_dt(row['upload_date']) or datetime.now(),
            archived=bool(row['archived']),
            io_map_path=row['io_map_path'],
            param_pch_dir=row['param_pch_dir'],
            param_upp_dir=row['param_upp_dir'],
        )

    # ── Templates ─────────────────────────────────────────────────────────────

    def upsert_template(self, t: Template) -> int:
        self._conn.execute(
            """INSERT INTO templates(name,template_type,path,description,rule_names)
               VALUES(?,?,?,?,?)
               ON CONFLICT(name) DO UPDATE SET
                 template_type=excluded.template_type,
                 path=excluded.path,
                 description=excluded.description,
                 rule_names=excluded.rule_names
            """,
            (t.name, t.template_type, t.path, t.description,
             json.dumps(t.rule_names, ensure_ascii=False))
        )
        self._conn.commit()
        row = self._conn.execute(
            'SELECT id FROM templates WHERE name=?', (t.name,)
        ).fetchone()
        return row['id'] if row else -1

    def get_all_templates(self) -> list[Template]:
        rows = self._conn.execute(
            'SELECT * FROM templates ORDER BY name'
        ).fetchall()
        return [Template(
            id=r['id'], name=r['name'], template_type=r['template_type'],
            path=r['path'], description=r['description'],
            rule_names=json.loads(r['rule_names'] or '[]')
        ) for r in rows]

    def delete_template(self, template_id: int):
        self._conn.execute('DELETE FROM templates WHERE id=?', (template_id,))
        self._conn.commit()

    # ── Sync Queue ────────────────────────────────────────────────────────────

    def enqueue(self, action: str, payload: dict) -> int:
        cur = self._conn.execute(
            """INSERT INTO sync_queue(action,payload,created_at,status)
               VALUES(?,?,?,'pending')
            """,
            (action, json.dumps(payload, ensure_ascii=False), _now())
        )
        self._conn.commit()
        return cur.lastrowid

    def get_pending(self) -> list[SyncQueueItem]:
        rows = self._conn.execute(
            "SELECT * FROM sync_queue WHERE status='pending' ORDER BY created_at"
        ).fetchall()
        return [self._row_to_queue(r) for r in rows]

    def mark_synced(self, item_id: int):
        self._conn.execute(
            "UPDATE sync_queue SET status='synced', synced_at=? WHERE id=?",
            (_now(), item_id)
        )
        self._conn.commit()

    def mark_failed(self, item_id: int, error: str):
        self._conn.execute(
            "UPDATE sync_queue SET status='failed', error=? WHERE id=?",
            (error, item_id)
        )
        self._conn.commit()

    def _row_to_queue(self, row: sqlite3.Row) -> SyncQueueItem:
        return SyncQueueItem(
            id=row['id'],
            action=row['action'],
            payload=json.loads(row['payload'] or '{}'),
            created_at=_dt(row['created_at']) or datetime.now(),
            synced_at=_dt(row['synced_at']),
            status=row['status'],
            error=row['error'],
        )

    def close(self):
        self._conn.close()
