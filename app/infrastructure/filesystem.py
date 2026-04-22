"""
FirmwareFinder — Filesystem Operations
=========================================
File scanning, copying, version folder management.
All paths are absolute; no UI dependencies.
"""

import os
import re
import shutil
import stat
from datetime import datetime
from pathlib import Path
from typing import Optional

ARCHIVE_EXTS = {'.zip', '.7z', '.rar'}
SKIP_DIRS    = {'Архив', 'Старая структура', '__pycache__', 'build', 'dist', '_archive'}

# Regexes for auto-detecting firmware metadata from filenames / paths.
# Note: avoid \b around names that may be adjacent to underscores (underscore is \w).
_RE_CTRL = [
    (r'SMH\s*2010',     'SMH2010'),
    (r'SMH\s*5',        'SMH5'),
    (r'SMH\s*4',        'SMH4'),
    (r'(?<![A-Za-z])SMH(?![A-Za-z0-9])', 'SMH'),
    (r'(?i)KINCO',      'KINCO'),
    (r'MK\s?070',       'MK070'),
    (r'(?<![A-Za-z])PIXEL(?![A-Za-z])',  'PIXEL'),
    (r'(?<![A-Za-z])FORTUS(?![A-Za-z])', 'FORTUS'),
]

# KINCO-specific file extensions — used to detect controller from folder contents
_KINCO_EXTS = frozenset({'.kpj', '.kpro', '.cpj', '.emt', '.emtp', '.emsln'})
_RE_DEV_TYPES = ['ПЖ', 'КНС', 'ТГР', 'ХП', 'БНС', 'ФНС', 'НГР', 'ОПЦ']
_RE_WORK_TYPES = ['УПП', 'КПЧ', 'ПП', 'ПЧ']


def parse_firmware_info(filename: str, path: str = '') -> dict:
    """Extract controller, version, device_type, work_type from filename/path."""
    combined = filename + ' ' + path
    info = {
        'controller':  '',
        'version':     '',
        'date':        '',
        'extension':   Path(filename).suffix.lower() if filename else '',
        'device_type': '',
        'work_type':   '',
    }
    # Controller — check name first
    for pattern, ctype in _RE_CTRL:
        if re.search(pattern, combined, re.I):
            info['controller'] = ctype
            break
    # If path is a directory and controller not yet detected, scan contents for KINCO files
    if not info['controller'] and path and os.path.isdir(path):
        try:
            for root_dir, _dirs, files in os.walk(path):
                for fname in files:
                    if Path(fname).suffix.lower() in _KINCO_EXTS:
                        info['controller'] = 'KINCO'
                        break
                if info['controller']:
                    break
        except (OSError, PermissionError):
            pass
    # Version (e.g. 3.42.260414 or v3.42)
    vm = re.search(r'\b(\d+\.\d+(?:\.\d{6})?)\b', combined)
    if vm:
        info['version'] = vm.group(1)
    # Date in path or filename
    dm = re.search(r'\b(\d{6})\b', combined)
    if dm:
        info['date'] = dm.group(1)
    # Device type
    for dtype in _RE_DEV_TYPES:
        if re.search(r'\b' + re.escape(dtype) + r'\b', combined, re.I):
            info['device_type'] = dtype
            break
    # Work type
    for wtype in _RE_WORK_TYPES:
        if re.search(r'\b' + re.escape(wtype) + r'\b', combined, re.I):
            info['work_type'] = wtype
            break
    return info


def scan_tree(root_path: str, skip_dirs=None, max_depth: int = 6) -> list:
    """Recursively scan directory, returning nested list of dicts."""
    if skip_dirs is None:
        skip_dirs = SKIP_DIRS

    def _walk(path: str, depth: int) -> list:
        if depth > max_depth:
            return []
        items = []
        try:
            entries = sorted(Path(path).iterdir(),
                             key=lambda e: (not e.is_dir(), e.name.lower()))
        except (PermissionError, OSError):
            return []
        for e in entries:
            if e.name.startswith('.') or e.name == 'Thumbs.db':
                continue
            if e.is_dir():
                if e.name in skip_dirs:
                    continue
                items.append({
                    'name': e.name, 'path': str(e),
                    'is_dir': True, 'size': 0, 'is_archive': False,
                    'children': _walk(str(e), depth + 1),
                })
            else:
                ext = e.suffix.lower()
                try:
                    sz = e.stat().st_size
                except Exception:
                    sz = 0
                items.append({
                    'name': e.name, 'path': str(e),
                    'is_dir': False, 'size': sz,
                    'is_archive': ext in ARCHIVE_EXTS,
                    'children': [],
                })
        return items

    return _walk(root_path, 0)


def flat_files(items: list, extensions: set, prefix: str = '') -> list:
    """Flatten tree, keeping only files with given extensions."""
    result = []
    for it in items:
        display = f"{prefix}{it['name']}" if prefix else it['name']
        if it['is_dir']:
            result.extend(flat_files(it.get('children', []), extensions, f'{display}/'))
        else:
            if Path(it['name']).suffix.lower() in extensions:
                result.append({**it, 'name': display})
    return result


def find_latest_version_folder(firmware_dir: str) -> Optional[str]:
    """Find the highest-versioned subfolder (e.g. 3.42.260414) in firmware_dir."""
    if not os.path.isdir(firmware_dir):
        return None
    candidates = []
    for entry in Path(firmware_dir).iterdir():
        if entry.is_dir():
            m = re.match(r'^(\d+)\.(\d+)(?:\.(\d{6}))?$', entry.name)
            if m:
                key = (int(m.group(1)), int(m.group(2)), int(m.group(3) or 0))
                candidates.append((key, str(entry)))
    if not candidates:
        return None
    return max(candidates, key=lambda x: x[0])[1]


def rmtree_safe(path: str):
    """Remove directory tree, force-deleting read-only files."""
    def _on_err(func, fpath, _):
        try:
            os.chmod(fpath, stat.S_IWRITE)
            func(fpath)
        except Exception:
            pass
    shutil.rmtree(path, onerror=_on_err)


def copy_tree(src: str, dst: str, overwrite: bool = True):
    """Copy directory tree src → dst. Optionally remove dst first."""
    if overwrite and os.path.exists(dst):
        rmtree_safe(dst)
    shutil.copytree(src, dst, copy_function=shutil.copy2, dirs_exist_ok=not overwrite)


def copy_file(src: str, dst_dir: str) -> str:
    """Copy single file to dst_dir, return destination path."""
    os.makedirs(dst_dir, exist_ok=True)
    dst = os.path.join(dst_dir, os.path.basename(src))
    shutil.copy2(src, dst)
    return dst


def disk_snapshot(path: str) -> dict:
    """Compute mtime + file_count snapshot for a directory."""
    if not os.path.isdir(path):
        return {'mtime': 0.0, 'file_count': 0}
    try:
        mtime = os.path.getmtime(path)
    except Exception:
        mtime = 0.0
    count = sum(len(files) for _, _, files in os.walk(path))
    return {'mtime': mtime, 'file_count': count}


def archive_old_files(dest_dir: str, extension: str):
    """Move existing files with given extension to _archive/ subfolder."""
    if not extension:
        return
    archive_dir = os.path.join(dest_dir, '_archive')
    os.makedirs(archive_dir, exist_ok=True)
    today = datetime.now().strftime('%Y%m%d')
    for fp in Path(dest_dir).glob(f'*{extension}'):
        if fp.is_file():
            new_name = fp.stem + f'_bak{today}' + fp.suffix
            try:
                shutil.move(str(fp), os.path.join(archive_dir, new_name))
            except Exception:
                pass
