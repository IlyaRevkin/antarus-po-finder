"""
FirmwareFinder — Search Service
==================================
Parses search query, finds matching rules, ranks results.
Also searches the new fw_versions hierarchy table.
No I/O — uses rules from DB and version data.
"""

import json
import re
from datetime import datetime
from typing import Optional

from app.domain.models import Rule, FirmwareVersion, SearchResult
from app.infrastructure.database import Database


# ── Hierarchy search adapters ─────────────────────────────────────────────────

class _HVStr:
    """Duck-types Version — str() returns version_raw."""
    def __init__(self, raw: str):
        self.raw = raw
    def __str__(self) -> str:
        return self.raw
    def __repr__(self) -> str:
        return self.raw
    def __lt__(self, other) -> bool:
        return self.raw < str(other)
    def __le__(self, other) -> bool:
        return self.raw <= str(other)


class _HierarchyVersion:
    """Duck-types FirmwareVersion for FirmwareCard."""
    def __init__(self, row: dict):
        self.version     = _HVStr(row.get('version_raw', ''))
        self.description = row.get('description', '')
        try:
            self.upload_date = datetime.fromisoformat(row.get('upload_date', ''))
        except Exception:
            self.upload_date = datetime.now()
        self.is_active = True


class _HierarchyRule:
    """Duck-types Rule for FirmwareCard (hierarchy-based search result)."""
    def __init__(self, row: dict):
        sub  = row.get('subtype_folder', '') or row.get('subtype_name', '')
        ctrl = row.get('ctrl_name', '')
        launch_types = json.loads(row.get('launch_types', '[]') or '[]')

        self.name              = f'{sub} {ctrl}'.strip()
        self.controller        = ctrl
        self.equipment_type    = row.get('group_name', '')
        self.work_type         = ', '.join(launch_types)
        self.software_name     = self.name
        self.firmware_type     = 'plc'
        self.io_map_path       = row.get('io_map_path', '')
        self.instructions_path = row.get('instructions_path', '')
        self.passport_dir      = ''
        self.local_dir         = ''
        self.firmware_dir      = row.get('disk_path', '')  # absolute — used as open fallback
        self.local_synced      = False
        self.disk_snapshot     = {}
        self.param_pch_dir     = ''
        self.param_upp_dir     = ''
        self.notes_file        = ''
        # For history lookup
        self._fw_subtype_id    = row.get('subtype_id')
        self._fw_controller_id = row.get('controller_id')
        self._fw_ctrl_name     = ctrl


_SEPARATORS = re.compile(r'[,;\-/\\]+')
_BOUNDARY   = re.compile(r'(?<![А-ЯЁA-Z0-9])%s(?![А-ЯЁA-Z0-9])')


def _normalize(q: str) -> str:
    q = _SEPARATORS.sub(' ', q)
    return re.sub(r'\s+', ' ', q).strip().upper()


class SearchService:
    """Handles cabinet name → Rule matching and result ranking."""

    def __init__(self, db: Database):
        self._db = db

    def search(self, query: str) -> list[SearchResult]:
        """Return ranked SearchResult list for the given query string."""
        q = _normalize(query)
        if not q:
            return []

        rules = self._db.get_all_rules()
        results: list[SearchResult] = []

        for rule in rules:
            score = self._score_rule(rule, q)
            if score <= 0:
                continue

            versions = self._db.get_versions_for_rule(rule.name)
            latest   = self._latest(versions)
            results.append(SearchResult(
                rule=rule, score=score,
                latest_version=latest, all_versions=versions,
            ))

        results.sort(key=lambda r: -r.score)
        return results

    def search_hierarchy(self, query: str) -> list[SearchResult]:
        """Search fw_versions table by matching query tokens against hierarchy names."""
        q = _normalize(query)
        if not q:
            return []
        tokens = q.split()
        if not tokens:
            return []

        rows = self._db.search_fw_versions_by_tokens(tokens)
        results = []
        for row in rows:
            rule = _HierarchyRule(row)
            ver  = _HierarchyVersion(row)
            results.append(SearchResult(
                rule=rule,
                score=len(tokens) * 10,
                latest_version=ver,
                all_versions=[ver],
            ))
        return results

    # ── Internal ──────────────────────────────────────────────────────────────

    def _score_rule(self, rule: Rule, q_upper: str) -> int:
        """Return relevance score (0 = no match)."""
        keywords = rule.keywords
        if not keywords:
            return 0

        mode = rule.kw_mode  # 'all' | 'any'
        score = 0

        if mode == 'any':
            for kw in keywords:
                ku = _normalize(kw)
                if re.search(_BOUNDARY.pattern % re.escape(ku), q_upper):
                    score += len(kw) * 2
        else:  # all
            for kw in keywords:
                ku = _normalize(kw)
                if re.search(_BOUNDARY.pattern % re.escape(ku), q_upper):
                    score += len(kw) * 2
                else:
                    return 0  # all-mode: any miss = no match

        if score == 0:
            return 0

        # Exclusion check
        for kw in rule.exclude_keywords:
            ku = _normalize(kw)
            if ku in q_upper:
                return 0

        return score

    @staticmethod
    def _latest(versions: list[FirmwareVersion]) -> Optional[FirmwareVersion]:
        active = [v for v in versions if v.is_active]
        if not active:
            return None
        return max(active, key=lambda v: v.version)
