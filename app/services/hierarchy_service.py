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
from pathlib import Path
from typing import Optional

from app.domain.hierarchy import (
    EquipmentGroup, EquipmentSubType, ControllerModel,
    INSTRUCTIONS_FOLDER, IO_MAP_FOLDER, OPC_FOLDER,
    UNKNOWN_FW_FOLDER, UNKNOWN_PARAMS_FOLDER,
)
from app.infrastructure.database import Database

log = logging.getLogger(__name__)

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
        """Create missing folders in the hierarchy. Returns summary."""
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

        # ── ПО structure ──────────────────────────────────────────────────────
        po_root = os.path.join(root_path, FOLDER_PO)
        _mkdir(po_root)

        groups     = self._db.get_all_equipment_groups()
        subtypes   = self._db.get_all_equipment_subtypes()
        controllers = self._db.get_all_controller_models()

        for sub in subtypes:
            folder = os.path.join(po_root, sub.folder_name)
            _mkdir(folder)

            for ctrl in controllers:
                ctrl_folder = os.path.join(folder, ctrl.name)
                _mkdir(ctrl_folder)
                _mkdir(os.path.join(ctrl_folder, INSTRUCTIONS_FOLDER))
                _mkdir(os.path.join(ctrl_folder, IO_MAP_FOLDER))

            # ОПЦ folder at same level as controllers
            _mkdir(os.path.join(folder, OPC_FOLDER))

        # ── Параметры structure ───────────────────────────────────────────────
        params_root = os.path.join(root_path, FOLDER_PARAMS)
        _mkdir(params_root)
        _mkdir(os.path.join(params_root, UNKNOWN_PARAMS_FOLDER))

        for param_type_folder in [FOLDER_UPP, FOLDER_PCH]:
            pt_root = os.path.join(params_root, param_type_folder)
            _mkdir(pt_root)
            # Sub-type folders inside params
            for sub in subtypes:
                sub_folder = os.path.join(pt_root, sub.folder_name)
                _mkdir(sub_folder)

        # ── Конфиг ───────────────────────────────────────────────────────────
        _mkdir(os.path.join(root_path, FOLDER_CONFIG))

        # ── Unknown firmware folder ───────────────────────────────────────────
        _mkdir(os.path.join(po_root, UNKNOWN_FW_FOLDER))

        return {
            'ok': True,
            'created': created,
            'errors': errors,
            'created_count': len(created),
        }

    def scan_unknown_files(self, root_path: str) -> list[dict]:
        """Find files that don't fit the hierarchy structure."""
        if not root_path or not os.path.isdir(root_path):
            return []

        po_root = os.path.join(root_path, FOLDER_PO)
        if not os.path.isdir(po_root):
            return []

        subtypes    = {s.folder_name for s in self._db.get_all_equipment_subtypes()}
        controllers = {c.name for c in self._db.get_all_controller_models()}
        known_eq    = subtypes | {OPC_FOLDER, UNKNOWN_FW_FOLDER}

        unknown = []
        try:
            for entry in os.scandir(po_root):
                if not entry.is_dir():
                    unknown.append({'path': entry.path, 'name': entry.name, 'type': 'file'})
                    continue
                if entry.name in known_eq:
                    # Scan inside for orphan files not in controller subfolders
                    for sub_entry in os.scandir(entry.path):
                        if sub_entry.is_dir() and sub_entry.name not in controllers | {OPC_FOLDER, INSTRUCTIONS_FOLDER, IO_MAP_FOLDER}:
                            unknown.append({'path': sub_entry.path, 'name': sub_entry.name, 'type': 'unknown_folder'})
                        elif sub_entry.is_file():
                            unknown.append({'path': sub_entry.path, 'name': sub_entry.name, 'type': 'orphan_file'})
                else:
                    unknown.append({'path': entry.path, 'name': entry.name, 'type': 'unknown_folder'})
        except (OSError, PermissionError) as e:
            log.warning(f'scan_unknown_files error: {e}')

        return unknown

    def fw_path(self, root_path: str, sub_folder_name: str,
                controller: str, version_str: str, is_opc: bool = False) -> str:
        """Build expected path for a firmware version folder."""
        ctrl_or_opc = OPC_FOLDER if is_opc else controller
        return os.path.join(root_path, FOLDER_PO, sub_folder_name,
                            ctrl_or_opc, version_str)

    def instr_path(self, root_path: str, sub_folder_name: str,
                   controller: str) -> str:
        return os.path.join(root_path, FOLDER_PO, sub_folder_name,
                            controller, INSTRUCTIONS_FOLDER)

    def io_map_path(self, root_path: str, sub_folder_name: str,
                    controller: str) -> str:
        return os.path.join(root_path, FOLDER_PO, sub_folder_name,
                            controller, IO_MAP_FOLDER)

    def params_path(self, root_path: str, param_type: str,
                    sub_folder_name: str, manufacturer: str,
                    connection_type: str) -> str:
        """Build path for parameter file folder.
        param_type: 'УПП' | 'ПЧ-КПЧ'
        connection_type: 'Аналог' | 'Дискрет'
        """
        return os.path.join(root_path, FOLDER_PARAMS, param_type,
                            sub_folder_name, manufacturer, connection_type)
