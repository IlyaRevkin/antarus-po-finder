"""
Antarus PO Finder — Hierarchy Domain Models
=============================================
Structured equipment hierarchy: Group → SubType → Controller → Version
"""

from __future__ import annotations
from dataclasses import dataclass, field
from datetime import datetime
from typing import Optional
import re


# ── EquipmentGroup ────────────────────────────────────────────────────────────

@dataclass
class EquipmentGroup:
    """Top-level equipment cabinet type: ПЖ, НГР, ТГР, КНС, ..."""
    id:         Optional[int]
    name:       str          # "ПЖ", "НГР", "ТГР"
    prefix:     int          # version prefix digit: ПЖ=1, НГР=2, ТГР=5
    sort_order: int = 0


# ── EquipmentSubType ──────────────────────────────────────────────────────────

@dataclass
class EquipmentSubType:
    """Sub-type within a group: ПЖ-КПЧ, ПЖ-ХП, НГР-КПЧ, НГР-ВЗУ, ..."""
    id:           Optional[int]
    group_id:     int          # parent EquipmentGroup.id
    name:         str          # "КПЧ", "ХП", "FD", "ВЗУ", "КНС"
    prefix:       int          # sub-type prefix digit (0 = no sub-type)
    folder_name:  str          # full folder name: "ПЖ-КПЧ", "НГР-ВЗУ"
    sort_order:   int = 0


# ── ControllerModel ───────────────────────────────────────────────────────────

@dataclass
class ControllerModel:
    """Controller type: SMH4, SMH5, KINCO, PIXEL2"""
    id:         Optional[int]
    name:       str          # "SMH4", "SMH5", "KINCO", "PIXEL2"
    sort_order: int = 0


# ── FirmwareVersion (new format) ──────────────────────────────────────────────

@dataclass(order=True, frozen=True)
class FWVersion:
    """New firmware version: eq_prefix.sub_prefix.hw_ver.sw_ver.YYYYMMDD_HHMM

    Example: 2.1.42.1.20260422_1348
      eq_prefix  = 2   (НГР)
      sub_prefix = 1   (КПЧ, 0 if none)
      hw_version = 42  (hardware/apparatus version)
      sw_version = 1   (software/visual version)
      datetime   = "20260422_1348"
    """
    raw:        str   = field(compare=False)
    eq_prefix:  int   = field(compare=True)
    sub_prefix: int   = field(compare=True)
    hw_version: int   = field(compare=True)
    sw_version: int   = field(compare=True)
    dt_str:     str   = field(compare=True)  # "20260422_1348"

    @classmethod
    def build(cls, eq_prefix: int, sub_prefix: int,
              hw_version: int, sw_version: int,
              dt: datetime | None = None) -> 'FWVersion':
        if dt is None:
            dt = datetime.now()
        dt_str = dt.strftime('%Y%m%d_%H%M')
        raw = f'{eq_prefix}.{sub_prefix}.{hw_version}.{sw_version}.{dt_str}'
        return cls(raw=raw, eq_prefix=eq_prefix, sub_prefix=sub_prefix,
                   hw_version=hw_version, sw_version=sw_version, dt_str=dt_str)

    @classmethod
    def parse(cls, s: str) -> Optional['FWVersion']:
        """Parse version string. Accepts: '2.1.42.1.20260422_1348'"""
        s = s.strip()
        # Full format: N.N.N.N.YYYYMMDD_HHMM
        m = re.match(r'^(\d+)\.(\d+)\.(\d+)\.(\d+)\.(\d{8}_\d{4})$', s)
        if m:
            return cls(
                raw=s,
                eq_prefix=int(m.group(1)),
                sub_prefix=int(m.group(2)),
                hw_version=int(m.group(3)),
                sw_version=int(m.group(4)),
                dt_str=m.group(5),
            )
        return None

    def __str__(self) -> str:
        return self.raw

    @property
    def folder_name(self) -> str:
        return self.raw

    @property
    def display(self) -> str:
        """Human-readable: 'hw42.sw1 (22.04.2026 13:48)'"""
        try:
            d = datetime.strptime(self.dt_str, '%Y%m%d_%H%M')
            date_str = d.strftime('%d.%m.%Y %H:%M')
        except Exception:
            date_str = self.dt_str
        return f'hw{self.hw_version}.sw{self.sw_version}  ({date_str})'


# ── Firmware filename builder ─────────────────────────────────────────────────

def build_firmware_filename(folder_name: str, controller: str,
                            version: FWVersion, ext: str,
                            request_num: str = '') -> str:
    """Build standardized firmware filename.

    Normal:  НГР-КПЧ_SMH5_2.1.42.1.20260422_1348.psl
    OPC:     ПЖ_SMH4_1.1.36.1.20260422_1455_(1312).psl
    """
    parts = [folder_name, controller, str(version)]
    name = '_'.join(p for p in parts if p)
    if request_num:
        name += f'_({request_num})'
    if ext and not ext.startswith('.'):
        ext = '.' + ext
    return name.upper() + ext.upper()


# ── Default hierarchy data ────────────────────────────────────────────────────

DEFAULT_EQUIPMENT_GROUPS: list[dict] = [
    {'name': 'НГР', 'prefix': 1, 'sort_order': 1},
    {'name': 'ПЖ',  'prefix': 2, 'sort_order': 2},
    {'name': 'ТГР', 'prefix': 3, 'sort_order': 3},
]

DEFAULT_SUB_TYPES: list[dict] = [
    # НГР — всегда имеет подтипы, "—" не нужен
    {'group_name': 'НГР', 'name': 'КПЧ', 'prefix': 1, 'folder_name': 'НГР-КПЧ', 'sort_order': 1},
    {'group_name': 'НГР', 'name': 'ВЗУ', 'prefix': 2, 'folder_name': 'НГР-ВЗУ', 'sort_order': 2},
    {'group_name': 'НГР', 'name': 'КНС', 'prefix': 3, 'folder_name': 'НГР-КНС', 'sort_order': 3},
    {'group_name': 'НГР', 'name': 'ПП',  'prefix': 4, 'folder_name': 'НГР-ПП',  'sort_order': 4},
    # ПЖ
    {'group_name': 'ПЖ', 'name': 'КПЧ', 'prefix': 1, 'folder_name': 'ПЖ-КПЧ', 'sort_order': 1},
    {'group_name': 'ПЖ', 'name': 'ХП',  'prefix': 2, 'folder_name': 'ПЖ-ХП',  'sort_order': 2},
    {'group_name': 'ПЖ', 'name': 'FD',  'prefix': 3, 'folder_name': 'ПЖ-FD',  'sort_order': 3},
    # ТГР — нет подтипов
    {'group_name': 'ТГР', 'name': '—',   'prefix': 0, 'folder_name': 'ТГР',     'sort_order': 1},
]

DEFAULT_CONTROLLERS: list[dict] = [
    {'name': 'SMH4',   'sort_order': 1},
    {'name': 'SMH5',   'sort_order': 2},
    {'name': 'SMH2010','sort_order': 3},
    {'name': 'KINCO',  'sort_order': 4},
    {'name': 'PIXEL2', 'sort_order': 5},
    {'name': 'FORTUS', 'sort_order': 6},
]

# Special folder names (always created alongside controller folders)
INSTRUCTIONS_FOLDER = 'Инструкция'
IO_MAP_FOLDER       = 'Карта ВВ'
OPC_FOLDER          = 'ОПЦ'
UNKNOWN_FW_FOLDER   = 'Неизвестное'
UNKNOWN_PARAMS_FOLDER = 'Неизвестные параметры'
