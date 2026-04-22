"""
FirmwareFinder — Firmware Card Widget
========================================
Card showing rule name, version, controller, quick-action buttons.
"""

from PySide6.QtWidgets import (
    QFrame, QVBoxLayout, QHBoxLayout, QLabel, QPushButton, QSizePolicy
)
from PySide6.QtCore import Qt, Signal, QSize
from app.ui.icons import make_icon, ICON_SECONDARY

from app.domain.models import SearchResult


class FirmwareCard(QFrame):
    """Clickable card representing one search result."""

    open_requested     = Signal(object)   # SearchResult
    open_plc_requested = Signal(object)
    open_hmi_requested = Signal(object)
    download_requested = Signal(object)
    map_requested      = Signal(object)
    params_requested   = Signal(object)

    copy_name_requested    = Signal(object)
    passport_requested     = Signal(object)
    instructions_requested = Signal(object)
    history_requested      = Signal(object)

    def __init__(self, result: SearchResult, has_local: bool = False,
                 has_any_local: bool = False, has_params: bool = False, parent=None):
        super().__init__(parent)
        self.result        = result
        self.has_local     = has_local      # latest version exists locally
        self.has_any_local = has_any_local  # any version exists locally (possibly outdated)
        self.has_params    = has_params
        self.setObjectName('card')
        self.setCursor(Qt.PointingHandCursor)
        self._build(result)

    def _build(self, result: SearchResult):
        layout = QVBoxLayout(self)
        layout.setContentsMargins(14, 12, 14, 12)
        layout.setSpacing(6)

        rule = result.rule
        ver  = result.latest_version

        # ── Title row ─────────────────────────────────────────────────────────
        title_row = QHBoxLayout()
        name_lbl = QLabel(rule.name)
        name_lbl.setObjectName('title')
        name_lbl.setWordWrap(False)
        title_row.addWidget(name_lbl, 1)

        if ver:
            ver_lbl = QLabel(str(ver.version))
            ver_lbl.setStyleSheet('font-weight: 600; color: #89b4fa;')
            title_row.addWidget(ver_lbl)

        layout.addLayout(title_row)

        # ── Meta row ──────────────────────────────────────────────────────────
        meta_parts = []
        if rule.controller:
            meta_parts.append(f'Контроллер: {rule.controller}')
        if rule.equipment_type:
            meta_parts.append(rule.equipment_type)
        if rule.work_type:
            meta_parts.append(rule.work_type)
        if ver and ver.upload_date:
            meta_parts.append(ver.upload_date.strftime('%d.%m.%Y'))

        if meta_parts:
            meta_lbl = QLabel('  ·  '.join(meta_parts))
            meta_lbl.setObjectName('muted')
            layout.addWidget(meta_lbl)

        # ── Description ───────────────────────────────────────────────────────
        if ver and ver.description:
            desc = ver.description[:120] + ('…' if len(ver.description) > 120 else '')
            desc_lbl = QLabel(desc)
            desc_lbl.setObjectName('subtitle')
            desc_lbl.setWordWrap(True)
            layout.addWidget(desc_lbl)

        # ── Software name row ─────────────────────────────────────────────────
        sw_name = rule.software_name or rule.name
        if ver:
            sw_full = f'{sw_name} {ver.version}'
        else:
            sw_full = sw_name
        sw_row = QHBoxLayout()
        sw_row.setSpacing(6)
        sw_lbl = QLabel(sw_full)
        sw_lbl.setObjectName('muted')
        sw_row.addWidget(sw_lbl)
        copy_btn = QPushButton('Копировать')
        copy_btn.setObjectName('secondary')
        copy_btn.setIcon(make_icon('copy', ICON_SECONDARY, 13))
        copy_btn.setIconSize(QSize(13, 13))
        copy_btn.clicked.connect(lambda: self.copy_name_requested.emit(self.result))
        sw_row.addWidget(copy_btn)
        sw_row.addStretch()
        layout.addLayout(sw_row)

        # ── Action buttons ────────────────────────────────────────────────────
        btn_row = QHBoxLayout()
        btn_row.setSpacing(6)

        def _btn(label: str, slot, icon_name: str = '') -> QPushButton:
            b = QPushButton(label)
            b.setObjectName('secondary')
            if icon_name:
                b.setIcon(make_icon(icon_name, ICON_SECONDARY, 14))
                b.setIconSize(QSize(14, 14))
            b.clicked.connect(slot)
            return b

        if rule.firmware_type == 'plc_hmi':
            btn_row.addWidget(_btn('Открыть ПЛК', lambda: self.open_plc_requested.emit(self.result), 'open'))
            btn_row.addWidget(_btn('Открыть HMI', lambda: self.open_hmi_requested.emit(self.result), 'open'))
        else:
            btn_row.addWidget(_btn('Открыть', lambda: self.open_requested.emit(self.result), 'open'))
        if not self.has_local:
            if self.has_any_local:
                btn_row.addWidget(_btn('Обновить', lambda: self.download_requested.emit(self.result), 'download'))
            else:
                btn_row.addWidget(_btn('Синхронизировать', lambda: self.download_requested.emit(self.result), 'download'))
        if rule.io_map_path:
            btn_row.addWidget(_btn('Карта in/out', lambda: self.map_requested.emit(self.result), 'map'))
        if self.has_params:
            btn_row.addWidget(_btn('Параметры', lambda: self.params_requested.emit(self.result), 'params'))

        if rule.instructions_path:
            btn_row.addWidget(_btn('Инструкции', lambda: self.instructions_requested.emit(self.result), 'book'))
        if rule.passport_dir:
            btn_row.addWidget(_btn('Паспорт', lambda: self.passport_requested.emit(self.result), 'passport'))
        btn_row.addWidget(_btn('История', lambda: self.history_requested.emit(self.result), 'history'))

        btn_row.addStretch()

        layout.addLayout(btn_row)
