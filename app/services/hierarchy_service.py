"""
Antarus PO Finder — Hierarchy Service
=======================================
Manages the standardized folder structure on the network disk.

Structure:
  {root}/
  ├── ПО/
  │   ├── ПЖ-КПЧ/
  │   │   ├── SMH4/
  │   │   │   ├── Инструкция/
  │   │   │   ├── Карта ВВ/
  │   │   │   └── 1.1.42.1.20260422_1348/
  │   │   └── ОПЦ/
  │   ├── ПЖ-ХП/
  │   └── ...
  ├── Параметры/
  │   ├── Неизвестные параметры/
  │   ├── УПП/
  │   │   └── {SubType}/
  │   │       └── {Manufacturer}/
  │   │           ├── Аналог/
  │   │           └── Дискрет/
  │   └── ПЧ-КПЧ/
  │       └── ...
  └── Конфиг/
"""

import os
import json
import logging
import shutil
from pathlib import Path
from typing import Optional

from app.domain.hierarchy import (
    EquipmentGroup, EquipmentSubType, ControllerModel,
    INSTRUCTIONS_FOLDER, IO_MAP_FOLDER, OPC_FOLDER,
    UNKNOWN_FW_FOLDER, UNKNOWN_PARAMS_FOLDER,
)
from app.infrastructure.database import Database

log = logging.getLogger(__name__)


def _scandir_safe(path: str) -> list:
    try:
        return list(os.scandir(path))
    except (OSError, PermissionError):
        return []


# Top-level folder names on the network disk
FOLDER_PO         = 'ПО'
FOLDER_PARAMS     = 'Параметры'
FOLDER_CONFIG     = 'Конфиг'
FOLDER_UPP        = 'УПП'
FOLDER_PCH        = 'ПЧ-КПЧ'
FOLDER_ANALOG     = 'Аналог'
FOLDER_DISCRETE   = 'Дискрет'


class HierarchyService:
    """Creates and validates the folder structure on the network disk."""

    def __init__(self, db: Database):
        self._db = db

    # ── Public API ────────────────────────────────────────────────────────────

    def ensure_structure(self, root_path: str) -> dict:
        """Create missing folders in the hierarchy. Returns summary.

        Structure:
          ПО/{group.name}/{sub.name}/{ctrl}/Инструкция + Карта ВВ
          ПО/{group.name}/{ctrl}/...          (for "—" subtypes)
          Параметры/{group.name}/{sub.name}/{manufacturer}/
          Конфиги/
        """
        if not root_path or not os.path.isdir(root_path):
            return {'ok': False, 'error': f'Диск недоступен: {root_path}'}

        created: list[str] = []
        errors:  list[str] = []

        def _mkdir(path: str):
            if not os.path.exists(path):
                try:
                    os.makedirs(path, exist_ok=True)
                    created.append(os.path.relpath(path, root_path))
                except OSError as e:
                    errors.append(str(e))

        groups      = self._db.get_all_equipment_groups()
        subtypes    = self._db.get_all_equipment_subtypes()
        controllers = self._db.get_all_controller_models()
        manufacturers = self._db.get_param_manufacturers()

        # Build lookup: group_id → group
        group_map = {g.id: g for g in groups}

        # ── ПО structure ──────────────────────────────────────────────────────
        po_root = os.path.join(root_path, FOLDER_PO)
        _mkdir(po_root)

        for grp in groups:
            grp_folder = os.path.join(po_root, grp.name)
            _mkdir(grp_folder)

            # Subtypes for this group
            grp_subs = [s for s in subtypes if s.group_id == grp.id]

            for sub in grp_subs:
                if sub.name == '—':
                    # No subtype level — controllers go directly under group
                    parent = grp_folder
                else:
                    parent = os.path.join(grp_folder, sub.name)
                    _mkdir(parent)

                for ctrl in controllers:
                    ctrl_folder = os.path.join(parent, ctrl.name)
                    _mkdir(ctrl_folder)
                    _mkdir(os.path.join(ctrl_folder, INSTRUCTIONS_FOLDER))
                    _mkdir(os.path.join(ctrl_folder, IO_MAP_FOLDER))

                _mkdir(os.path.join(parent, OPC_FOLDER))

        _mkdir(os.path.join(po_root, UNKNOWN_FW_FOLDER))

        # ── Параметры structure ───────────────────────────────────────────────
        params_root = os.path.join(root_path, FOLDER_PARAMS)
        _mkdir(params_root)
        _mkdir(os.path.join(params_root, UNKNOWN_PARAMS_FOLDER))

        for grp in groups:
            grp_folder = os.path.join(params_root, grp.name)
            _mkdir(grp_folder)

            grp_subs = [s for s in subtypes if s.group_id == grp.id]
            for sub in grp_subs:
                if sub.name == '—':
                    parent = grp_folder
                else:
                    parent = os.path.join(grp_folder, sub.name)
                    _mkdir(parent)

                for manuf in manufacturers:
                    _mkdir(os.path.join(parent, manuf))

        # ── Конфиги ──────────────────────────────────────────────────────────
        _mkdir(os.path.join(root_path, FOLDER_CONFIG))

        # Move obsolete folders to Неизвестное / Неизвестные параметры
        unknowns = self.collect_unknowns(root_path)

        return {
            'ok': True,
            'created': created,
            'errors': errors + unknowns['errors'],
            'created_count': len(created),
            'moved': unknowns['moved'],
            'moved_count': len(unknowns['moved']),
        }

    def collect_unknowns(self, root_path: str) -> dict:
        """Move folders/files that don't fit the hierarchy to Неизвестное / Неизвестные параметры."""
        if not root_path or not os.path.isdir(root_path):
            return {'moved': [], 'errors': []}

        moved: list[str] = []
        errors: list[str] = []

        groups       = self._db.get_all_equipment_groups()
        subtypes     = self._db.get_all_equipment_subtypes()
        controllers  = {c.name for c in self._db.get_all_controller_models()}
        manufacturers = set(self._db.get_param_manufacturers())

        group_names = {g.name for g in groups}
        subs_by_group: dict[int, list] = {g.id: [] for g in groups}
        for s in subtypes:
            if s.group_id in subs_by_group:
                subs_by_group[s.group_id].append(s)

        special = {OPC_FOLDER, INSTRUCTIONS_FOLDER, IO_MAP_FOLDER}

        # ── ПО ───────────────────────────────────────────────────────────────
        po_root     = os.path.join(root_path, FOLDER_PO)
        unknown_po  = os.path.join(po_root, UNKNOWN_FW_FOLDER)

        if os.path.isdir(po_root):
            for entry in _scandir_safe(po_root):
                if entry.name == UNKNOWN_FW_FOLDER:
                    continue
                if not entry.is_dir():
                    self._safe_move(entry.path, unknown_po, moved, errors)
                    continue
                if entry.name not in group_names:
                    self._safe_move(entry.path, unknown_po, moved, errors)
                    continue

                # Inside group: check subtypes / controllers
                grp = next(g for g in groups if g.name == entry.name)
                grp_subs = subs_by_group[grp.id]
                real_sub_names = {s.name for s in grp_subs if s.name != '—'}
                has_dash = any(s.name == '—' for s in grp_subs)

                valid = real_sub_names | special
                if has_dash:
                    valid |= controllers

                for sub_entry in _scandir_safe(entry.path):
                    if sub_entry.name not in valid:
                        self._safe_move(sub_entry.path, unknown_po, moved, errors)

        # ── Параметры ────────────────────────────────────────────────────────
        params_root    = os.path.join(root_path, FOLDER_PARAMS)
        unknown_params = os.path.join(params_root, UNKNOWN_PARAMS_FOLDER)

        if os.path.isdir(params_root):
            for entry in _scandir_safe(params_root):
                if entry.name == UNKNOWN_PARAMS_FOLDER:
                    continue
                if not entry.is_dir() or entry.name not in group_names:
                    self._safe_move(entry.path, unknown_params, moved, errors)
                    continue

                grp = next(g for g in groups if g.name == entry.name)
                grp_subs = subs_by_group[grp.id]
                real_sub_names = {s.name for s in grp_subs if s.name != '—'}
                has_dash = any(s.name == '—' for s in grp_subs)

                valid_at_grp = real_sub_names
                if has_dash:
                    valid_at_grp |= manufacturers

                for sub_entry in _scandir_safe(entry.path):
                    if sub_entry.name not in valid_at_grp:
                        self._safe_move(sub_entry.path, unknown_params, moved, errors)
                        continue
                    # Inside real subtype: check manufacturers
                    if sub_entry.name in real_sub_names and sub_entry.is_dir():
                        for mfr_entry in _scandir_safe(sub_entry.path):
                            if mfr_entry.name not in manufacturers:
                                self._safe_move(mfr_entry.path, unknown_params, moved, errors)

        return {'moved': moved, 'errors': errors}

    @staticmethod
    def _safe_move(src: str, dst_dir: str, moved: list, errors: list) -> None:
        """Move src into dst_dir, resolving name conflicts with numeric suffix."""
        try:
            os.makedirs(dst_dir, exist_ok=True)
            name = os.path.basename(src)
            dst  = os.path.join(dst_dir, name)
            i = 1
            while os.path.exists(dst):
                dst = os.path.join(dst_dir, f'{name}_{i}')
                i += 1
            shutil.move(src, dst)
            moved.append(dst)
            log.info(f'collect_unknowns: moved {src!r} → {dst!r}')
        except (OSError, shutil.Error) as e:
            errors.append(str(e))
            log.warning(f'collect_unknowns: failed to move {src!r}: {e}')

    def scan_unknown_files(self, root_path: str) -> list[dict]:
        """Find files/folders that don't fit the hierarchy (both ПО and Параметры)."""
        if not root_path or not os.path.isdir(root_path):
            return []

        unknown = []

        # ── ПО ───────────────────────────────────────────────────────────────
        po_root = os.path.join(root_path, FOLDER_PO)
        if os.path.isdir(po_root):
            groups_list  = self._db.get_all_equipment_groups()
            groups       = {g.name for g in groups_list}
            subtypes     = self._db.get_all_equipment_subtypes()
            sub_names    = {s.name for s in subtypes if s.name != '—'}
            controllers  = {c.name for c in self._db.get_all_controller_models()}
            known_eq     = groups | {UNKNOWN_FW_FOLDER}

            try:
                for entry in os.scandir(po_root):
                    if not entry.is_dir():
                        unknown.append({'path': entry.path, 'name': entry.name,
                                        'type': 'file', 'section': 'ПО'})
                        continue
                    if entry.name not in known_eq:
                        unknown.append({'path': entry.path, 'name': entry.name,
                                        'type': 'unknown_folder', 'section': 'ПО'})
                        continue
                    for sub_entry in os.scandir(entry.path):
                        if sub_entry.is_file():
                            unknown.append({'path': sub_entry.path, 'name': sub_entry.name,
                                            'type': 'orphan_file', 'section': 'ПО'})
                        elif sub_entry.name not in (
                            sub_names | controllers | {OPC_FOLDER, INSTRUCTIONS_FOLDER, IO_MAP_FOLDER}
                        ):
                            unknown.append({'path': sub_entry.path, 'name': sub_entry.name,
                                            'type': 'unknown_folder', 'section': 'ПО'})
            except (OSError, PermissionError) as e:
                log.warning(f'scan_unknown_files ПО error: {e}')

        # ── Параметры ────────────────────────────────────────────────────────
        params_root = os.path.join(root_path, FOLDER_PARAMS)
        if os.path.isdir(params_root):
            groups_list   = self._db.get_all_equipment_groups()
            group_names   = {g.name for g in groups_list}
            group_id_map  = {g.name: g.id for g in groups_list}
            subtypes      = self._db.get_all_equipment_subtypes()
            manufacturers = set(self._db.get_param_manufacturers())

            subs_by_group: dict[int, list] = {}
            for s in subtypes:
                subs_by_group.setdefault(s.group_id, []).append(s)

            try:
                for entry in os.scandir(params_root):
                    if entry.name == UNKNOWN_PARAMS_FOLDER:
                        continue
                    if not entry.is_dir() or entry.name not in group_names:
                        unknown.append({'path': entry.path, 'name': entry.name,
                                        'type': 'unknown_folder', 'section': 'Параметры'})
                        continue

                    grp_subs = subs_by_group.get(group_id_map[entry.name], [])
                    real_sub_names = {s.name for s in grp_subs if s.name != '—'}
                    has_dash = any(s.name == '—' for s in grp_subs)
                    valid_at_grp = real_sub_names | (manufacturers if has_dash else set())

                    for sub_entry in os.scandir(entry.path):
                        if sub_entry.name not in valid_at_grp:
                            unknown.append({'path': sub_entry.path, 'name': sub_entry.name,
                                            'type': 'unknown_folder', 'section': 'Параметры'})
                            continue
                        if sub_entry.name in real_sub_names and sub_entry.is_dir():
                            for mfr_entry in os.scandir(sub_entry.path):
                                if mfr_entry.name not in manufacturers:
                                    unknown.append({'path': mfr_entry.path, 'name': mfr_entry.name,
                                                    'type': 'unknown_folder', 'section': 'Параметры'})
            except (OSError, PermissionError) as e:
                log.warning(f'scan_unknown_files Параметры error: {e}')

        return unknown

    def _po_ctrl_folder(self, root_path: str, group_name: str,
                        sub_name: str, ctrl_or_opc: str) -> str:
        """Return path to the controller (or ОПЦ) folder under ПО."""
        if sub_name and sub_name != '—':
            return os.path.join(root_path, FOLDER_PO, group_name, sub_name, ctrl_or_opc)
        return os.path.join(root_path, FOLDER_PO, group_name, ctrl_or_opc)

    def fw_path(self, root_path: str, group_name: str, sub_name: str,
                controller: str, version_str: str, is_opc: bool = False) -> str:
        """Build expected path for a firmware version folder."""
        ctrl_or_opc = OPC_FOLDER if is_opc else controller
        return os.path.join(
            self._po_ctrl_folder(root_path, group_name, sub_name, ctrl_or_opc),
            version_str,
        )

    def instr_path(self, root_path: str, group_name: str,
                   sub_name: str, controller: str) -> str:
        return os.path.join(
            self._po_ctrl_folder(root_path, group_name, sub_name, controller),
            INSTRUCTIONS_FOLDER,
        )

    def io_map_path(self, root_path: str, group_name: str,
                    sub_name: str, controller: str) -> str:
        return os.path.join(
            self._po_ctrl_folder(root_path, group_name, sub_name, controller),
            IO_MAP_FOLDER,
        )

    def params_path(self, root_path: str, group_name: str,
                    sub_name: str, manufacturer: str) -> str:
        """Build path for parameter files: Параметры/{group}/{sub}/{manufacturer}/"""
        if sub_name and sub_name != '—':
            return os.path.join(root_path, FOLDER_PARAMS, group_name, sub_name, manufacturer)
        return os.path.join(root_path, FOLDER_PARAMS, group_name, manufacturer)
