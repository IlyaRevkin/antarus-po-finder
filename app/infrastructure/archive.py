"""
FirmwareFinder — Archive Extraction
======================================
Handles .zip, .7z archives. .rar requires WinRAR.
"""

import os
import zipfile
from pathlib import Path

try:
    import py7zr as _py7zr
    _7Z_OK = True
except ImportError:
    _7Z_OK = False

ARCHIVE_EXTS = {'.zip', '.7z', '.rar'}


def extract(src: str, dest_dir: str) -> tuple[bool, str]:
    """Extract archive to dest_dir. Returns (success, message)."""
    ext = Path(src).suffix.lower()
    os.makedirs(dest_dir, exist_ok=True)
    try:
        if ext == '.zip':
            with zipfile.ZipFile(src) as z:
                if any(i.flag_bits & 0x1 for i in z.infolist()):
                    return False, 'Архив защищён паролем — скопируйте вручную'
                z.extractall(dest_dir)
            return True, dest_dir
        if ext == '.7z':
            if not _7Z_OK:
                return False, 'py7zr не установлен — скопируйте вручную'
            with _py7zr.SevenZipFile(src, 'r') as z:
                z.extractall(path=dest_dir)
            return True, dest_dir
        if ext == '.rar':
            return False, '.rar требует WinRAR — скопируйте вручную'
        return False, f'Неизвестный формат: {ext}'
    except Exception as e:
        msg = str(e)
        if 'password' in msg.lower() or 'encrypted' in msg.lower():
            return False, 'Архив защищён паролем'
        return False, msg


def extract_all_in_dir(dirpath: str, keep: bool = False) -> list[str]:
    """Find and extract all archives in dirpath recursively."""
    extracted = []
    archives = []
    for root, dirs, files in os.walk(dirpath):
        dirs[:] = [d for d in dirs if d not in {'Архив', '__pycache__'}]
        for fn in files:
            if Path(fn).suffix.lower() in ARCHIVE_EXTS:
                archives.append(os.path.join(root, fn))
    for arc_path in archives:
        stem = Path(arc_path).stem
        dest = os.path.join(os.path.dirname(arc_path), stem)
        ok, _ = extract(arc_path, dest)
        if ok:
            extracted.append(dest)
            if not keep:
                try:
                    os.remove(arc_path)
                except Exception:
                    pass
    return extracted
