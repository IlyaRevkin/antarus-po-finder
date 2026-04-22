"""
FirmwareFinder — Sync Service
================================
Background sync: checks WebDAV disk, processes offline queue,
updates local cache from disk changes.
"""

import os
import threading
from datetime import datetime
from typing import Callable

from app.infrastructure.database import Database
from app.infrastructure.filesystem import disk_snapshot, scan_tree
from app.services.config_service import ConfigService, LOCAL_FW, LOCAL_TEMPLATES


class SyncService:
    """Manages sync between WebDAV disk and local cache."""

    def __init__(self, db: Database, cfg: ConfigService):
        self._db   = db
        self._cfg  = cfg
        self._lock = threading.Lock()

    # ── Disk status ───────────────────────────────────────────────────────────

    def is_disk_available(self) -> bool:
        root = self._cfg.root_path()
        return bool(root) and os.path.isdir(root)

    def disk_status(self) -> dict:
        """Return dict with available, path, file_count."""
        root = self._cfg.root_path()
        if not root or not os.path.isdir(root):
            return {'available': False, 'path': root, 'file_count': 0}
        snap = disk_snapshot(root)
        return {
            'available': True,
            'path': root,
            'file_count': snap['file_count'],
        }

    # ── Background sync ───────────────────────────────────────────────────────

    def run_background(
        self,
        on_done: Callable[[list[dict]], None],
        on_error: Callable[[str], None] | None = None,
    ):
        """Start background sync, call on_done(updates_list) when finished."""
        def _worker():
            try:
                updates = self._check_updates()
                on_done(updates)
            except Exception as e:
                if on_error:
                    on_error(str(e))
                else:
                    on_done([])

        threading.Thread(target=_worker, daemon=True).start()

    # ── Offline queue ─────────────────────────────────────────────────────────

    def flush_queue(self) -> tuple[int, int]:
        """Try to sync pending queue items. Returns (synced, failed) counts."""
        if not self.is_disk_available():
            return 0, 0
        items = self._db.get_pending()
        synced = failed = 0
        for item in items:
            try:
                self._process_queue_item(item)
                self._db.mark_synced(item.id)
                synced += 1
            except Exception as e:
                self._db.mark_failed(item.id, str(e))
                failed += 1
        return synced, failed

    # ── Rule snapshot check ───────────────────────────────────────────────────

    def _check_updates(self) -> list[dict]:
        """Compare disk snapshots for all rules. If changed, copy to LOCAL_FW."""
        import re
        import shutil
        from dataclasses import replace as dc_replace
        updates = []
        root = self._cfg.root_path()
        if not root or not os.path.isdir(root):
            return updates

        rules = self._db.get_all_rules()
        for rule in rules:
            if not rule.firmware_dir or not rule.local_synced:
                continue
            full_path = os.path.join(root, rule.firmware_dir)
            if not os.path.isdir(full_path):
                continue

            snap_new = disk_snapshot(full_path)
            snap_old = rule.disk_snapshot or {}

            changed = (snap_new['mtime'] != snap_old.get('mtime', 0.0) or
                       snap_new['file_count'] != snap_old.get('file_count', 0))

            if changed:
                # Copy updated files to LOCAL_FW
                local_dir = rule.local_dir or re.sub(r'[^\w\-]', '_', rule.name)
                dst = os.path.join(LOCAL_FW, local_dir)
                try:
                    shutil.copytree(full_path, dst, dirs_exist_ok=True)
                except Exception:
                    pass
                # Update snapshot in DB
                self._db.upsert_rule(dc_replace(rule, disk_snapshot=snap_new))
                updates.append({
                    'rule_name':    rule.name,
                    'firmware_dir': rule.firmware_dir,
                    'snap_new':     snap_new,
                    'snap_old':     snap_old,
                })

        # Also sync template files to local cache
        self._sync_templates()

        return updates

    def _sync_templates(self):
        """Copy template files/folders to LOCAL_TEMPLATES so they work offline."""
        import re
        import shutil
        templates = self._db.get_all_templates()
        for t in templates:
            if not t.path:
                continue
            # Skip if already stored inside LOCAL_TEMPLATES
            try:
                if os.path.commonpath([t.path, LOCAL_TEMPLATES]) == LOCAL_TEMPLATES:
                    continue
            except ValueError:
                pass
            if not os.path.exists(t.path):
                continue
            # Build local destination path
            safe = re.sub(r'[^\w\-]', '_', t.name)
            if os.path.isfile(t.path):
                ext = os.path.splitext(t.path)[1]
                dst = os.path.join(LOCAL_TEMPLATES, safe + ext)
                try:
                    shutil.copy2(t.path, dst)
                except Exception:
                    pass
            elif os.path.isdir(t.path):
                dst = os.path.join(LOCAL_TEMPLATES, safe)
                try:
                    shutil.copytree(t.path, dst, dirs_exist_ok=True)
                except Exception:
                    pass

    def _process_queue_item(self, item):
        """Execute a single queued action (currently: upload copy to disk)."""
        # For now, queue items are informational — actual disk write
        # would be done here when WebDAV write is implemented.
        pass
