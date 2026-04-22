"""
FirmwareFinder — Search Service
==================================
Parses search query, finds matching rules, ranks results.
No I/O — uses rules from DB and version data.
"""

import re
from typing import Optional

from app.domain.models import Rule, FirmwareVersion, SearchResult
from app.infrastructure.database import Database


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
