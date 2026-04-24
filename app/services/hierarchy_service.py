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

        groups      = {g.name for g in self._db.get_all_equipment_groups()}
        subtypes    = self._db.get_all_equipment_subtypes()
        sub_names   = {s.name for s in subtypes if s.name != '—'}
        controllers = {c.name for c in self._db.get_all_controller_models()}
        known_eq    = groups | {UNKNOWN_FW_FOLDER}

        unknown = []
        try:
            for entry in os.scandir(po_root):
                if not entry.is_dir():
                    unknown.append({'path': entry.path, 'name': entry.name, 'type': 'file'})
                    continue
                if entry.name not in known_eq:
                    unknown.append({'path': entry.path, 'name': entry.name, 'type': 'unknown_folder'})
                    continue
                # Inside group folder: sub or ctrl
                for sub_entry in os.scandir(entry.path):
                    if sub_entry.is_file():
                        unknown.append({'path': sub_entry.path, 'name': sub_entry.name, 'type': 'orphan_file'})
                    elif sub_entry.name in sub_names:
                        pass  # valid subtype folder
                    elif sub_entry.name in controllers | {OPC_FOLDER, INSTRUCTIONS_FOLDER, IO_MAP_FOLDER}:
                        pass  # valid controller/special folder
                    else:
                        unknown.append({'path': sub_entry.path, 'name': sub_entry.name, 'type': 'unknown_folder'})
        except (OSError, PermissionError) as e:
            log.warning(f'scan_unknown_files error: {e}')

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
