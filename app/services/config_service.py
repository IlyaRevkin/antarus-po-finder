"""
Antarus PO Finder — Config Service
=====================================
Central access to all application settings stored in SQLite.
Provides typed getters/setters with defaults.
"""

import os
import sys
import json

from app.infrastructure.database import Database

# ── App paths ──────────────────────────────────────────────────────────────────
if getattr(sys, 'frozen', False):
    _BASE = os.path.dirname(sys.executable)
else:
    _BASE = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

APP_DATA         = os.path.join(os.environ.get('LOCALAPPDATA', _BASE), 'AntarusPOFinder')
DB_PATH          = os.path.join(APP_DATA, 'po_finder.db')
LOCAL_FW         = os.path.join(APP_DATA, 'firmware')
LOCAL_TEMPLATES  = os.path.join(APP_DATA, 'templates')
SYNC_LOG         = os.path.join(APP_DATA, 'sync.log')

os.makedirs(APP_DATA, exist_ok=True)
os.makedirs(LOCAL_FW, exist_ok=True)
os.makedirs(LOCAL_TEMPLATES, exist_ok=True)

# ── Defaults ──────────────────────────────────────────────────────────────────
DEFAULTS = {
    'root_path':            '',
    'inspection_folder':    '',   # папка осмотра (фото/сканы) — очищается кнопкой
    'admin_password':       '12345',
    'programmer_password':  '',
    'current_role':         'naladchik',
    'theme':                'light',
    'keep_archives':        'false',
    'image_server_port':    '9876',
    'sync_interval_min':    '5',    # configurable scan interval (minutes)
    'quick_apps':           '[]',
    # Legacy (kept for backward compatibility with old rules)
    'version_prefixes':    '{}',
    'equipment_types':     '[]',
    'work_types':          '[]',
    'controller_types':    '[]',
}

# Launch types (тип пуска) — fixed set
LAUNCH_TYPES = ['УПП', 'ПП', 'ПЧ', 'КПЧ']


class ConfigService:
    """Typed settings access backed by SQLite settings table."""

    def __init__(self, db: Database):
        self._db = db

    # ── Generic ───────────────────────────────────────────────────────────────

    def get(self, key: str) -> str:
        return self._db.get_setting(key, DEFAULTS.get(key, ''))

    def set(self, key: str, value: str):
        self._db.set_setting(key, value)

    # ── Typed accessors ───────────────────────────────────────────────────────

    def root_path(self) -> str:
        return self.get('root_path')

    def set_root_path(self, path: str):
        self.set('root_path', path)

    def inspection_folder(self) -> str:
        """Папка осмотра (фото/сканы). Defaults to LOCAL_FW if not set."""
        v = self.get('inspection_folder')
        return v if v else LOCAL_FW

    def set_inspection_folder(self, path: str):
        self.set('inspection_folder', path)

    def admin_password(self) -> str:
        return self.get('admin_password')

    def programmer_password(self) -> str:
        return self.get('programmer_password')

    def current_role(self) -> str:
        return self.get('current_role')

    def set_role(self, role: str):
        self.set('current_role', role)

    def theme(self) -> str:
        return self.get('theme')

    def set_theme(self, theme: str):
        self.set('theme', theme)

    def keep_archives(self) -> bool:
        return self.get('keep_archives').lower() == 'true'

    def sync_interval_min(self) -> int:
        try:
            v = int(self.get('sync_interval_min'))
            return max(1, v)
        except Exception:
            return 5

    def quick_apps(self) -> list[dict]:
        try:
            return json.loads(self.get('quick_apps'))
        except Exception:
            return []

    def set_quick_apps(self, apps: list[dict]):
        self.set('quick_apps', json.dumps(apps, ensure_ascii=False))

    def image_server_port(self) -> int:
        try:
            return int(self.get('image_server_port'))
        except Exception:
            return 9876

    # ── Legacy (for old rules system) ─────────────────────────────────────────

    def version_prefixes(self) -> dict[str, str]:
        try:
            return json.loads(self.get('version_prefixes'))
        except Exception:
            return {}

    def equipment_types(self) -> list[str]:
        try:
            return json.loads(self.get('equipment_types'))
        except Exception:
            return []

    def work_types(self) -> list[str]:
        return LAUNCH_TYPES  # Now fixed; kept for old upload_service compat

    def controller_types(self) -> list[str]:
        try:
            return json.loads(self.get('controller_types'))
        except Exception:
            return []

    def protocol_folder(self) -> str:
        return self.inspection_folder()
