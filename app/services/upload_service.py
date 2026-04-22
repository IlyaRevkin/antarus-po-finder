"""
FirmwareFinder — Upload Service
==================================
Validates version, copies files into versioned folder structure,
writes CHANGELOG.md, updates DB. Works offline via sync queue.
"""

import os
import shutil
from datetime import datetime
from pathlib import Path
from typing import Optional

from app.domain.models import FirmwareVersion, Rule, Version
from app.domain.exceptions import (
    VersionConflictError, InvalidVersionError, FileOperationError
)
from app.infrastructure.database import Database
from app.infrastructure.filesystem import archive_old_files, parse_firmware_info
from app.infrastructure.archive import extract_all_in_dir
from app.services.config_service import ConfigService, LOCAL_FW


class UploadService:
    """Handles firmware upload: version validation, file copy, DB update."""

    def __init__(self, db: Database, cfg: ConfigService):
        self._db  = db
        self._cfg = cfg

    # ── Public API ────────────────────────────────────────────────────────────

    def auto_detect(self, path: str) -> dict:
        """Parse metadata from file/folder path. Returns dict of suggested fields."""
        filename = os.path.basename(path)
        info = parse_firmware_info(filename, path)

        # Suggest version based on last upload for detected device/controller
        suggested_ver = self._suggest_next_version(
            info.get('device_type', ''), info.get('controller', '')
        )
        if suggested_ver:
            info['suggested_version'] = str(suggested_ver)

        return info

    def validate_version(self, version_str: str,
                         rule_names: list[str]) -> list[str]:
        """Check version against existing uploads. Returns list of conflict messages."""
        ver = Version.parse(version_str)
        if not ver:
            raise InvalidVersionError(version_str)

        conflicts = []
        for rule_name in rule_names:
            existing = self._db.get_latest_version(rule_name)
            if not existing:
                continue
            ex_ver = existing.version
            if ex_ver >= ver:
                conflicts.append(
                    f'«{rule_name}»: существующая {ex_ver} ≥ новой {ver}'
                )
        return conflicts

    def upload(
        self,
        src_path:    str,
        version_str: str,
        rule_names:  list[str],
        controller:  str = '',
        device_type: str = '',
        work_type:   str = '',
        description: str = '',
        changelog:   str = '',
        io_map_path:   str = '',
        param_pch_dir: str = '',
        param_upp_dir: str = '',
        allow_equal:   bool = False,
    ) -> FirmwareVersion:
        """Full upload pipeline. Raises on version conflict or file error."""
        # 1. Parse & validate version
        ver = Version.parse(version_str)
        if not ver:
            raise InvalidVersionError(version_str)

        # 2. Version conflict check
        for rule_name in rule_names:
            existing = self._db.get_latest_version(rule_name)
            if existing:
                ex_ver = existing.version
                if ex_ver > ver or (ex_ver == ver and not allow_equal):
                    raise VersionConflictError(str(ex_ver), str(ver), rule_name)

        # 3. Copy files into <root_path>/<firmware_dir>/<version>/
        #    Falls back to LOCAL_FW if root_path not accessible.
        _orig_name = os.path.basename(src_path)
        _ext       = os.path.splitext(_orig_name)[1]
        _parts     = [p.replace(' ', '_') for p in [device_type, controller, str(ver)] if p]
        filename   = ('_'.join(_parts) if _parts else _orig_name.upper().replace(' ', '_')) + _ext.upper()
        extension  = _ext.lower()
        local_paths: dict[str, str] = {}
        root = self._cfg.root_path()

        for rule_name in rule_names:
            rule = self._db.get_rule(rule_name)

            if root and rule and rule.firmware_dir:
                # Place on WebDAV/network share (creates dirs if needed)
                ver_dir = os.path.join(root, rule.firmware_dir, str(ver))
            else:
                # Fallback: local cache (no root_path configured, or rule has no firmware_dir)
                local_dir = (rule.local_dir if rule and rule.local_dir
                             else re.sub(r'[^\w\-]', '_', rule_name))
                ver_dir = os.path.join(LOCAL_FW, local_dir, str(ver))

            os.makedirs(ver_dir, exist_ok=True)

            try:
                if os.path.isfile(src_path):
                    dst = os.path.join(ver_dir, filename)
                    shutil.copy2(src_path, dst)
                    local_paths[rule_name] = dst
                elif os.path.isdir(src_path):
                    dst = os.path.join(ver_dir, filename)
                    if os.path.exists(dst):
                        shutil.rmtree(dst)
                    shutil.copytree(src_path, dst, copy_function=shutil.copy2)
                    local_paths[rule_name] = dst
                else:
                    raise FileOperationError(f'Путь не найден: {src_path}')
            except (OSError, shutil.Error) as e:
                raise FileOperationError(str(e))

            # Extract archives if any
            extract_all_in_dir(ver_dir, keep=self._cfg.keep_archives())

            # Write CHANGELOG.md
            self._write_changelog(ver_dir, ver, description, changelog)

        # 4. Record in DB
        first_path = local_paths.get(rule_names[0], src_path) if rule_names else src_path
        fv = FirmwareVersion(
            id=None,
            rule_ids=[],
            rule_names=rule_names,
            version=ver,
            filename=filename,
            local_path=first_path,
            disk_path=first_path,   # path on server (or local fallback)
            controller=controller,
            device_type=device_type,
            work_type=work_type,
            extension=extension,
            description=description,
            changelog=changelog,
            upload_date=datetime.now(),
            archived=False,
            io_map_path=io_map_path,
            param_pch_dir=param_pch_dir,
            param_upp_dir=param_upp_dir,
        )
        fv.id = self._db.add_version(fv)
        return fv

    # ── Internal ──────────────────────────────────────────────────────────────

    def _suggest_next_version(self, device_type: str,
                               controller: str) -> Optional[Version]:
        """Find latest version across all versions and suggest +1 major."""
        all_versions = self._db.get_all_versions()
        candidates: list[Version] = []
        for fv in all_versions:
            if fv.archived:
                continue
            if device_type and fv.device_type != device_type:
                continue
            candidates.append(fv.version)
        if not candidates:
            return None
        latest = max(candidates)
        return latest.bump()

    @staticmethod
    def _write_changelog(ver_dir: str, ver: Version,
                          description: str, changelog: str):
        """Create/overwrite CHANGELOG.md in the version folder."""
        lines = [
            f'# Changelog — версия {ver}',
            f'',
            f'**Дата загрузки:** {datetime.now().strftime("%Y-%m-%d %H:%M")}',
        ]
        if description:
            lines += ['', f'## Описание', description]
        if changelog:
            lines += ['', f'## Изменения', changelog]
        path = os.path.join(ver_dir, 'CHANGELOG.md')
        with open(path, 'w', encoding='utf-8') as f:
            f.write('\n'.join(lines) + '\n')


import re  # needed for re.sub in upload()
