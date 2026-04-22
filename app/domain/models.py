"""
FirmwareFinder — Domain Models
================================
Pure data classes. No I/O, no UI, no external dependencies.
"""

from __future__ import annotations
from dataclasses import dataclass, field
from datetime import datetime
from typing import Optional
import re


# ── Version ───────────────────────────────────────────────────────────────────

@dataclass(order=True, frozen=True)
class Version:
    """Firmware version: prefix.body.YYMMDD (e.g. 3.42.260414 or 4.35.6.260421).

    body is a tuple of ints — supports simple (42,) and sub-versioned (35, 6) formats.
    Comparison is numeric on (prefix, body, date) tuples.
    """
    raw:    str = field(compare=False)
    prefix: int = field(compare=True)
    body:   tuple[int, ...] = field(compare=True)  # e.g. (42,) or (35, 6)
    date:   int = field(compare=True)              # YYMMDD as int, 0 if absent

    @classmethod
    def parse(cls, s: str) -> Optional['Version']:
        """Parse version string → Version, or None if invalid.

        Accepted formats:
          "42"             → prefix=0, body=(42,), date=0
          "42.260421"      → prefix=0, body=(42,), date=260421
          "3.42"           → prefix=3, body=(42,), date=0
          "3.42.260421"    → prefix=3, body=(42,), date=260421
          "4.35.6.260421"  → prefix=4, body=(35,6), date=260421
        """
        s = s.strip()
        if not s:
            return None
        parts = s.split('.')
        try:
            first = int(parts[0])
        except ValueError:
            return None

        # Single number — body-only, no prefix, no date
        if len(parts) == 1:
            return cls(raw=s, prefix=0, body=(first,), date=0)

        # Last segment is date if exactly 6 digits
        if len(parts[-1]) == 6 and parts[-1].isdigit():
            date_val = int(parts[-1])
            body_parts = parts[1:-1]
        else:
            date_val = 0
            body_parts = parts[1:]
        try:
            body = tuple(int(p) for p in body_parts)
        except ValueError:
            return None
        if not body:
            # "N.YYMMDD" — no separate prefix, number is the version body
            body = (first,)
            return cls(raw=s, prefix=0, body=body, date=date_val)
        return cls(raw=s, prefix=first, body=body, date=date_val)

    @classmethod
    def make(cls, prefix: int, body: tuple[int, ...], date_str: str = '') -> 'Version':
        """Build a Version from components."""
        date_int = int(date_str) if date_str and len(date_str) == 6 else 0
        body_str = '.'.join(str(b) for b in body)
        raw = f'{prefix}.{body_str}.{date_str}' if date_int else f'{prefix}.{body_str}'
        return cls(raw=raw, prefix=prefix, body=body, date=date_int)

    def with_today(self) -> 'Version':
        """Return same version with today's date appended."""
        today = datetime.now().strftime('%y%m%d')
        body_str = '.'.join(str(b) for b in self.body)
        return Version(
            raw=f'{self.prefix}.{body_str}.{today}',
            prefix=self.prefix, body=self.body, date=int(today)
        )

    def bump(self) -> 'Version':
        """Increment last body segment by 1, keeping prefix, dropping date."""
        new_body = self.body[:-1] + (self.body[-1] + 1,) if self.body else (1,)
        return Version.make(self.prefix, new_body)

    def __str__(self) -> str:
        return self.raw


# ── Rule ──────────────────────────────────────────────────────────────────────

@dataclass
class Rule:
    """Maps a cabinet search pattern → firmware folder on disk."""
    id:                Optional[int]
    name:              str
    equipment_type:    str          # НГР, ПЖ, ТГР, КНС, ШУЗ, …
    work_type:         str          # ПП, УПП, ПЧ, …
    controller:        str          # SMH4, SMH5, KINCO, …
    firmware_dir:      str          # relative path from WebDAV root
    firmware_type:     str          # plc | plc_hmi
    software_name:     str
    keywords:          list[str]
    exclude_keywords:  list[str]
    kw_mode:           str          # all | any
    local_dir:         str          # name of local cache subdir
    local_synced:      bool
    disk_snapshot:     dict
    param_pch_dir:     str = ''
    param_upp_dir:     str = ''
    passport_dir:      str = ''
    io_map_path:       str = ''
    instructions_path: str = ''
    notes_file:        str = ''
    created_at:        datetime = field(default_factory=datetime.now)
    updated_at:        datetime = field(default_factory=datetime.now)


# ── FirmwareVersion ───────────────────────────────────────────────────────────

@dataclass
class FirmwareVersion:
    """A single uploaded firmware version tied to one or more rules."""
    id:           Optional[int]
    rule_ids:     list[int]
    rule_names:   list[str]
    version:      Version
    filename:     str
    local_path:   str
    disk_path:    str
    controller:   str
    device_type:  str
    work_type:    str
    extension:    str
    description:  str
    changelog:    str
    upload_date:  datetime
    archived:     bool
    io_map_path:   str = ''
    param_pch_dir: str = ''
    param_upp_dir: str = ''

    @property
    def is_active(self) -> bool:
        return not self.archived


# ── Template ──────────────────────────────────────────────────────────────────

@dataclass
class Template:
    """Shared parameter template (UPP, PCH, IO map, instructions)."""
    id:            Optional[int]
    name:          str
    template_type: str            # upp | pch | io_map | instructions
    path:          str
    description:   str
    rule_names:    list[str] = field(default_factory=list)


# ── SyncQueueItem ─────────────────────────────────────────────────────────────

@dataclass
class SyncQueueItem:
    """Offline action waiting to be synced to WebDAV."""
    id:         Optional[int]
    action:     str              # upload | update | delete
    payload:    dict
    created_at: datetime
    synced_at:  Optional[datetime]
    status:     str              # pending | synced | failed
    error:      str = ''


# ── SearchResult ──────────────────────────────────────────────────────────────

@dataclass
class SearchResult:
    """Single search hit returned by SearchService."""
    rule:           Rule
    score:          int
    latest_version: Optional[FirmwareVersion]
    all_versions:   list[FirmwareVersion] = field(default_factory=list)
