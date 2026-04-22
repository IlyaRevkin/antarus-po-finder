"""
Antarus PO Finder — Second Disk Service
=========================================
Scans a second network disk for cabinet names (шкафы) and their
electrical schematics. Used for search autocomplete and schematic printing.

Expected structure on second disk (flexible — any of these work):
  {second_disk}/
  ├── ПЖ-101/          ← folder named after cabinet
  │   └── схема.pdf    ← any PDF/image inside
  ├── НГР-205.pdf      ← file named after cabinet
  └── ТГР-301.pdf
"""

import os
import re
import logging
from functools import lru_cache

log = logging.getLogger(__name__)

SCHEMATIC_EXTENSIONS = {'.pdf', '.jpg', '.jpeg', '.png', '.tif', '.tiff', '.bmp', '.dwg', '.dxf'}
PRINT_EXTENSIONS = {'.pdf', '.jpg', '.jpeg', '.png', '.tif', '.tiff', '.bmp'}


class SecondDiskService:
    """Scans second disk for cabinet names and schematics."""

    def __init__(self):
        self._cache: dict[str, list[str]] = {}   # disk_path → cabinet names
        self._schematic_map: dict[str, str] = {}  # cabinet_name → schematic path

    def cabinet_names(self, disk_path: str) -> list[str]:
        """Return sorted list of cabinet names found on disk. Cached per disk path."""
        if not disk_path or not os.path.isdir(disk_path):
            return []
        if disk_path in self._cache:
            return self._cache[disk_path]
        names = self._scan(disk_path)
        self._cache[disk_path] = names
        return names

    def invalidate_cache(self):
        self._cache.clear()
        self._schematic_map.clear()

    def find_schematic(self, disk_path: str, cabinet_name: str) -> str:
        """Return path to schematic file for cabinet, or '' if not found."""
        if not disk_path or not cabinet_name:
            return ''
        key = f'{disk_path}::{cabinet_name.upper()}'
        if key in self._schematic_map:
            return self._schematic_map[key]
        # Make sure cache is built
        self.cabinet_names(disk_path)
        return self._schematic_map.get(key, '')

    def _scan(self, disk_path: str) -> list[str]:
        names: list[str] = []
        self._schematic_map.clear()
        try:
            for entry in os.scandir(disk_path):
                name = entry.name
                if entry.is_dir():
                    # Folder named after cabinet — look for schematic inside
                    cabinet = name.strip()
                    names.append(cabinet)
                    schematic = self._find_in_folder(entry.path)
                    if schematic:
                        self._schematic_map[f'{disk_path}::{cabinet.upper()}'] = schematic
                elif entry.is_file():
                    stem, ext = os.path.splitext(name)
                    if ext.lower() in SCHEMATIC_EXTENSIONS:
                        cabinet = stem.strip()
                        names.append(cabinet)
                        self._schematic_map[f'{disk_path}::{cabinet.upper()}'] = entry.path
        except (OSError, PermissionError) as e:
            log.warning('SecondDiskService scan error: %s', e)
        return sorted(set(names))

    @staticmethod
    def _find_in_folder(folder: str) -> str:
        """Return first schematic file found in folder."""
        try:
            for entry in os.scandir(folder):
                if entry.is_file():
                    ext = os.path.splitext(entry.name)[1].lower()
                    if ext in SCHEMATIC_EXTENSIONS:
                        return entry.path
        except OSError:
            pass
        return ''

    def matches(self, disk_path: str, query: str) -> list[str]:
        """Return cabinet names that partially match the query (case-insensitive)."""
        if not query or not disk_path:
            return []
        q = query.upper()
        return [n for n in self.cabinet_names(disk_path) if q in n.upper()]

    @staticmethod
    def open_schematic(path: str):
        """Open schematic file with default application."""
        if path and os.path.isfile(path):
            os.startfile(path)

    @staticmethod
    def print_schematic(path: str):
        """Print schematic via OS default printer."""
        if not path or not os.path.isfile(path):
            return
        ext = os.path.splitext(path)[1].lower()
        if ext in PRINT_EXTENSIONS:
            try:
                os.startfile(path, 'print')
            except OSError:
                os.startfile(path)
        else:
            os.startfile(path)
