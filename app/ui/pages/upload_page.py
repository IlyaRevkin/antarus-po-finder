"""
Antarus PO Finder — Upload Page
================================
Firmware upload using new hierarchy format.
Equipment group → sub-type → controller → HW.SW version.
"""

import os
import shutil
from datetime import datetime

from PySide6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QFormLayout,
    QLabel, QLineEdit, QComboBox, QTextEdit, QPushButton,
    QCheckBox, QGroupBox, QSizePolicy, QFrame, QGridLayout,
    QScrollArea, QFileDialog, QMessageBox,
)
from PySide6.QtCore import Qt, QSize, QTimer

from app.ui.icons import make_icon, ICON_SECONDARY, ICON_ON_ACCENT
from app.ui.widgets.drop_zone import DropZone, MiniDropZone
from app.domain.hierarchy import FWVersion, build_firmware_filename
from app.services.config_service import LAUNCH_TYPES


class UploadPage(QWidget):
    def __init__(self, main_win):
        super().__init__()
        self._mw = main_win
        self._src_path = ''
        self._build()

    # ── Build UI ──────────────────────────────────────────────────────────────

    def _build(self):
        layout = QVBoxLayout(self)
        layout.setContentsMargins(24, 24, 24, 16)
        layout.setSpacing(16)

        title = QLabel('Загрузка прошивки')
        title.setObjectName('title')
        layout.addWidget(title)

        body_row = QHBoxLayout()
        body_row.setSpacing(20)

        # ── Left: drop zone + path preview ───────────────────────────────────
        left_col = QVBoxLayout()
        left_col.setSpacing(10)

        self._drop_zone = DropZone()
        self._drop_zone.path_dropped.connect(self._on_file_dropped)
        self._drop_zone.mousePressEvent = self._browse_file
        self._drop_zone.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Expanding)
        left_col.addWidget(self._drop_zone, 1)

        browse_row = QHBoxLayout()
        browse_row.setSpacing(6)
        btn_file = QPushButton('Файл...')
        btn_file.setObjectName('secondary')
        btn_file.setIcon(make_icon('file', ICON_SECONDARY, 14))
        btn_file.setIconSize(QSize(14, 14))
        btn_file.clicked.connect(self._browse_file)
        browse_row.addWidget(btn_file, 1)
        btn_dir = QPushButton('Папка...')
        btn_dir.setObjectName('secondary')
        btn_dir.setIcon(make_icon('folder', ICON_SECONDARY, 14))
        btn_dir.setIconSize(QSize(14, 14))
        btn_dir.clicked.connect(self._browse_folder)
        browse_row.addWidget(btn_dir, 1)
        left_col.addLayout(browse_row)

        preview_box = QGroupBox('Путь на диске')
        preview_lay = QVBoxLayout(preview_box)
        self._preview_lbl = QLabel('—')
        self._preview_lbl.setObjectName('muted')
        self._preview_lbl.setWordWrap(True)
        preview_lay.addWidget(self._preview_lbl)
        left_col.addWidget(preview_box)

        body_row.addLayout(left_col, 1)

        # ── Right: form ───────────────────────────────────────────────────────
        right_col = QVBoxLayout()
        right_col.setSpacing(12)

        form_box = QGroupBox('Метаданные')
        form_box_vlay = QVBoxLayout(form_box)
        form_box_vlay.setContentsMargins(4, 4, 4, 4)
        form_scroll = QScrollArea()
        form_scroll.setWidgetResizable(True)
        form_scroll.setFrameShape(QFrame.NoFrame)
        form_widget = QWidget()
        self._form = QFormLayout(form_widget)
        self._form.setSpacing(10)
        self._form.setLabelAlignment(Qt.AlignRight)
        self._form.setRowWrapPolicy(QFormLayout.DontWrapRows)
        form_scroll.setWidget(form_widget)
        form_box_vlay.addWidget(form_scroll)

        # Тип шкафа (equipment group)
        self._group_combo = QComboBox()
        self._group_combo.currentIndexChanged.connect(self._on_group_changed)
        self._form.addRow('Тип шкафа *', self._group_combo)

        # Подтип
        self._sub_combo = QComboBox()
        self._sub_combo.currentIndexChanged.connect(self._on_sub_changed)
        self._form.addRow('Подтип *', self._sub_combo)

        # Контроллер
        self._ctrl_combo = QComboBox()
        self._ctrl_combo.currentIndexChanged.connect(self._on_ctrl_changed)
        self._form.addRow('Контроллер *', self._ctrl_combo)

        # HW / SW + ОПЦ in one row
        hw_sw_w = QWidget()
        hw_sw_w.setFixedHeight(36)
        hw_sw_lay = QHBoxLayout(hw_sw_w)
        hw_sw_lay.setContentsMargins(0, 0, 0, 0)
        hw_sw_lay.setSpacing(8)
        self._hw_input = QLineEdit()
        self._hw_input.setPlaceholderText('42')
        self._hw_input.setFixedHeight(34)
        self._hw_input.textChanged.connect(self._update_preview)
        hw_sw_lay.addWidget(self._hw_input, 1)
        hw_sw_lay.addWidget(QLabel('SW:'))
        self._sw_input = QLineEdit()
        self._sw_input.setPlaceholderText('1')
        self._sw_input.setFixedHeight(34)
        self._sw_input.textChanged.connect(self._update_preview)
        hw_sw_lay.addWidget(self._sw_input, 1)
        self._opc_check = QCheckBox('ОПЦ')
        self._opc_check.toggled.connect(self._on_opc_toggled)
        hw_sw_lay.addWidget(self._opc_check)
        self._form.addRow('HW / SW *', hw_sw_w)

        self._req_num_input = QLineEdit()
        self._req_num_input.setPlaceholderText('напр. 1312')
        self._req_num_input.textChanged.connect(self._update_preview)
        self._form.addRow('Номер заявки', self._req_num_input)
        self._form.setRowVisible(self._req_num_input, False)

        # Тип пуска — horizontal row
        launch_w = QWidget()
        launch_w.setFixedHeight(28)
        launch_hlay = QHBoxLayout(launch_w)
        launch_hlay.setContentsMargins(0, 0, 0, 0)
        launch_hlay.setSpacing(20)
        self._launch_checks: dict[str, QCheckBox] = {}
        for lt in LAUNCH_TYPES:
            cb = QCheckBox(lt)
            launch_hlay.addWidget(cb)
            self._launch_checks[lt] = cb
        launch_hlay.addStretch()
        self._form.addRow('Тип пуска *', launch_w)

        # Описание
        self._desc_edit = QTextEdit()
        self._desc_edit.setPlaceholderText('Краткое описание версии')
        self._desc_edit.setFixedHeight(56)
        self._form.addRow('Описание', self._desc_edit)

        # Карта ВВ
        self._io_map_input = MiniDropZone()
        self._form.addRow('Карта ВВ', self._make_path_row(
            self._io_map_input,
            lambda: self._browse_path_into(self._io_map_input, file=True),
            lambda: self._browse_path_into(self._io_map_input, folder=True),
        ))

        # Инструкция
        self._instructions_input = MiniDropZone()
        self._form.addRow('Инструкция', self._make_path_row(
            self._instructions_input,
            lambda: self._browse_path_into(self._instructions_input, file=True),
            lambda: self._browse_path_into(self._instructions_input, folder=True),
        ))

        right_col.addWidget(form_box, 1)

        self._status_lbl = QLabel('')
        self._status_lbl.setObjectName('subtitle')
        self._status_lbl.setWordWrap(True)
        right_col.addWidget(self._status_lbl)

        self._upload_btn = QPushButton('Загрузить прошивку')
        self._upload_btn.setMinimumHeight(40)
        self._upload_btn.setIcon(make_icon('upload', ICON_ON_ACCENT, 16))
        self._upload_btn.setIconSize(QSize(16, 16))
        self._upload_btn.clicked.connect(self._do_upload)
        right_col.addWidget(self._upload_btn)

        body_row.addLayout(right_col, 1)
        layout.addLayout(body_row)

        QTimer.singleShot(0, self._reload_combos)

    # ── Static helpers ────────────────────────────────────────────────────────

    @staticmethod
    def _make_path_row(field: MiniDropZone, on_file, on_folder) -> QWidget:
        wrapper = QWidget()
        h = QHBoxLayout(wrapper)
        h.setContentsMargins(0, 0, 0, 0)
        h.setSpacing(6)
        h.addWidget(field, 1)
        clr = QPushButton('×')
        clr.setObjectName('secondary')
        clr.setFixedWidth(28)
        clr.setToolTip('Очистить')
        clr.clicked.connect(lambda *_, f=field: f.set_path(''))
        h.addWidget(clr)
        fb = QPushButton('Файл')
        fb.setObjectName('secondary')
        fb.setIcon(make_icon('file', ICON_SECONDARY, 14))
        fb.setIconSize(QSize(14, 14))
        fb.clicked.connect(on_file)
        h.addWidget(fb)
        db = QPushButton('Папка')
        db.setObjectName('secondary')
        db.setIcon(make_icon('folder', ICON_SECONDARY, 14))
        db.setIconSize(QSize(14, 14))
        db.clicked.connect(on_folder)
        h.addWidget(db)
        return wrapper

    def _browse_path_into(self, field: MiniDropZone, file=False, folder=False):
        if file:
            path, _ = QFileDialog.getOpenFileName(self, 'Выберите файл', '', 'Все файлы (*.*)')
        else:
            path = QFileDialog.getExistingDirectory(self, 'Выберите папку', '')
        if path:
            field.set_path(path)

    # ── Lifecycle ─────────────────────────────────────────────────────────────

    def showEvent(self, event):
        super().showEvent(event)
        self._reload_combos()

    # ── Combo population ──────────────────────────────────────────────────────

    def _reload_combos(self):
        # Groups
        groups = self._mw.db.get_all_equipment_groups()
        prev_gid = (self._group_combo.currentData().id
                    if self._group_combo.currentData() else None)
        self._group_combo.blockSignals(True)
        self._group_combo.clear()
        for g in groups:
            self._group_combo.addItem(g.name, g)
        if prev_gid is not None:
            for i in range(self._group_combo.count()):
                if self._group_combo.itemData(i).id == prev_gid:
                    self._group_combo.setCurrentIndex(i)
                    break
        self._group_combo.blockSignals(False)

        # Controllers
        controllers = self._mw.db.get_all_controller_models()
        prev_cid = (self._ctrl_combo.currentData().id
                    if self._ctrl_combo.currentData() else None)
        self._ctrl_combo.blockSignals(True)
        self._ctrl_combo.clear()
        for c in controllers:
            self._ctrl_combo.addItem(c.name, c)
        if prev_cid is not None:
            for i in range(self._ctrl_combo.count()):
                if self._ctrl_combo.itemData(i).id == prev_cid:
                    self._ctrl_combo.setCurrentIndex(i)
                    break
        self._ctrl_combo.blockSignals(False)

        self._populate_subtypes()
        self._update_preview()

    def _populate_subtypes(self):
        group = self._group_combo.currentData()
        prev_sid = (self._sub_combo.currentData().id
                    if self._sub_combo.currentData() else None)

        subtypes = self._mw.db.get_subtypes_for_group(group.id) if group else []

        self._sub_combo.blockSignals(True)
        self._sub_combo.clear()
        for s in subtypes:
            label = s.folder_name if s.name == '—' else f'{s.folder_name} ({s.name})'
            self._sub_combo.addItem(label, s)
        if prev_sid is not None:
            for i in range(self._sub_combo.count()):
                if self._sub_combo.itemData(i).id == prev_sid:
                    self._sub_combo.setCurrentIndex(i)
                    break
        self._sub_combo.blockSignals(False)
        self._update_preview()

    # ── Change handlers ───────────────────────────────────────────────────────

    def _on_group_changed(self, _):
        self._populate_subtypes()
        self._update_preview()

    def _on_sub_changed(self, _):
        self._update_preview()
        self._suggest_from_previous()

    def _on_ctrl_changed(self, _):
        self._update_preview()
        self._suggest_from_previous()

    def _on_opc_toggled(self, checked: bool):
        self._form.setRowVisible(self._req_num_input, checked)
        self._update_preview()

    # ── Path preview ──────────────────────────────────────────────────────────

    def _update_preview(self):
        sub  = self._sub_combo.currentData()
        ctrl = self._ctrl_combo.currentData()
        group = self._group_combo.currentData()
        hw_str = self._hw_input.text().strip()
        sw_str = self._sw_input.text().strip()

        if not sub or not ctrl or not hw_str or not sw_str:
            self._preview_lbl.setText('—')
            return
        try:
            hw_int = int(hw_str)
            sw_int = int(sw_str)
        except ValueError:
            self._preview_lbl.setText('HW и SW должны быть числами')
            return

        eq_prefix  = group.prefix if group else 0
        sub_prefix = sub.prefix
        fwv = FWVersion.build(eq_prefix, sub_prefix, hw_int, sw_int)

        folder_in_ctrl = 'ОПЦ' if self._opc_check.isChecked() else ctrl.name
        req_num = self._req_num_input.text().strip() if self._opc_check.isChecked() else ''
        ext = os.path.splitext(self._src_path)[1] if self._src_path else '.psl'
        fname = build_firmware_filename(sub.folder_name, ctrl.name, fwv, ext, req_num)

        self._preview_lbl.setText(
            f'ПО / {sub.folder_name} / {folder_in_ctrl} / {fwv.raw}\n{fname}'
        )

    # ── Previous version suggestion ───────────────────────────────────────────

    def _suggest_from_previous(self):
        sub  = self._sub_combo.currentData()
        ctrl = self._ctrl_combo.currentData()
        if not sub or not ctrl:
            return

        prev = self._mw.db.get_latest_fw_version(
            subtype_id=sub.id, controller_id=ctrl.id,
        )
        if not prev:
            return

        # Pre-fill HW/SW from previous version if fields are empty
        if not self._hw_input.text():
            self._hw_input.setText(str(prev.get('hw_version', '')))
        if not self._sw_input.text():
            self._sw_input.setText(str(prev.get('sw_version', '')))

        # Offer to carry over io_map / instructions
        prev_io    = prev.get('io_map_path', '')
        prev_instr = prev.get('instructions_path', '')
        if (prev_io or prev_instr) and \
                not self._io_map_input.text() and \
                not self._instructions_input.text():
            reply = QMessageBox.question(
                self, 'Перенести файлы',
                f'Предыдущая версия: {prev.get("version_raw", "")}\n'
                'Перенести Карту ВВ и Инструкцию из неё?',
                QMessageBox.Yes | QMessageBox.No, QMessageBox.Yes,
            )
            if reply == QMessageBox.Yes:
                if prev_io:
                    self._io_map_input.set_path(prev_io)
                if prev_instr:
                    self._instructions_input.set_path(prev_instr)

    # ── File selection ────────────────────────────────────────────────────────

    def _browse_file(self, event=None):
        path, _ = QFileDialog.getOpenFileName(
            self, 'Выберите файл прошивки', '', 'Все файлы (*.*)')
        if path:
            self._on_file_dropped(path)

    def _browse_folder(self):
        path = QFileDialog.getExistingDirectory(self, 'Выберите папку прошивки', '')
        if path:
            self._on_file_dropped(path)

    def _on_file_dropped(self, path: str):
        self._src_path = path
        # Always clear io_map / instructions on new firmware drop (bug fix)
        self._io_map_input.set_path('')
        self._instructions_input.set_path('')
        self._status_lbl.setText(f'Файл: {os.path.basename(path)}')
        self._update_preview()

    # ── Upload ────────────────────────────────────────────────────────────────

    def _do_upload(self):
        if not self._src_path:
            QMessageBox.warning(self, 'Загрузка', 'Выберите файл прошивки.')
            return

        group = self._group_combo.currentData()
        sub   = self._sub_combo.currentData()
        ctrl  = self._ctrl_combo.currentData()
        if not group or not sub or not ctrl:
            QMessageBox.warning(self, 'Загрузка', 'Укажите тип шкафа, подтип и контроллер.')
            return

        hw_str = self._hw_input.text().strip()
        sw_str = self._sw_input.text().strip()
        if not hw_str or not sw_str:
            QMessageBox.warning(self, 'Загрузка', 'Укажите версии HW и SW.')
            return
        try:
            hw_int = int(hw_str)
            sw_int = int(sw_str)
        except ValueError:
            QMessageBox.warning(self, 'Загрузка', 'HW и SW должны быть целыми числами.')
            return

        launch_types = [lt for lt, cb in self._launch_checks.items() if cb.isChecked()]
        if not launch_types:
            QMessageBox.warning(self, 'Загрузка', 'Выберите хотя бы один тип пуска.')
            return

        root_path = self._mw.cfg.root_path()
        if not root_path or not os.path.isdir(root_path):
            QMessageBox.warning(self, 'Загрузка',
                'Сетевой диск недоступен. Проверьте настройки.')
            return

        is_opc  = self._opc_check.isChecked()
        req_num = self._req_num_input.text().strip() if is_opc else ''

        fwv = FWVersion.build(group.prefix, sub.prefix, hw_int, sw_int)
        hs  = self._mw.hierarchy_svc

        dst_folder = hs.fw_path(root_path, sub.folder_name,
                                ctrl.name, fwv.raw, is_opc=is_opc)

        if os.path.exists(dst_folder):
            reply = QMessageBox.question(
                self, 'Версия существует',
                f'Папка {fwv.raw} уже существует.\nПерезаписать?',
                QMessageBox.Yes | QMessageBox.No, QMessageBox.No,
            )
            if reply != QMessageBox.Yes:
                return

        try:
            os.makedirs(dst_folder, exist_ok=True)

            ext = os.path.splitext(self._src_path)[1]
            dst_name = build_firmware_filename(
                sub.folder_name, ctrl.name, fwv, ext, req_num)
            shutil.copy2(self._src_path, os.path.join(dst_folder, dst_name))

            desc = self._desc_edit.toPlainText().strip()
            self._write_changelog(dst_folder, fwv, launch_types, desc)

            io_map_src = self._io_map_input.text().strip()
            if io_map_src:
                io_dst = hs.io_map_path(root_path, sub.folder_name, ctrl.name)
                self._copy_to_folder(io_map_src, io_dst)

            instr_src = self._instructions_input.text().strip()
            if instr_src:
                instr_dst = hs.instr_path(root_path, sub.folder_name, ctrl.name)
                self._copy_to_folder(instr_src, instr_dst)

        except OSError as e:
            QMessageBox.critical(self, 'Ошибка файла', str(e))
            return

        self._mw.db.add_fw_version({
            'subtype_id':       sub.id,
            'controller_id':    ctrl.id,
            'eq_prefix':        group.prefix,
            'sub_prefix':       sub.prefix,
            'hw_version':       hw_int,
            'sw_version':       sw_int,
            'dt_str':           fwv.dt_str,
            'version_raw':      fwv.raw,
            'filename':         dst_name,
            'disk_path':        dst_folder,
            'local_path':       '',
            'description':      desc,
            'changelog':        '',
            'launch_types':     launch_types,
            'io_map_path':      io_map_src if io_map_src else '',
            'instructions_path': instr_src if instr_src else '',
            'is_opc':           is_opc,
            'request_num':      req_num,
        })

        self._mw.show_status(f'Загружено: {fwv.raw}')
        QMessageBox.information(self, 'Готово',
            f'Прошивка {fwv.raw} загружена.\nПапка: {dst_folder}')
        self._reset_form()

    @staticmethod
    def _write_changelog(folder: str, fwv: FWVersion,
                         launch_types: list, desc: str):
        lines = [f'# {fwv.raw}', f'Дата: {fwv.dt_str}',
                 f'Тип пуска: {", ".join(launch_types)}']
        if desc:
            lines += ['', desc]
        with open(os.path.join(folder, 'CHANGELOG.md'), 'w', encoding='utf-8') as f:
            f.write('\n'.join(lines))

    @staticmethod
    def _copy_to_folder(src: str, dst_folder: str):
        os.makedirs(dst_folder, exist_ok=True)
        if os.path.isfile(src):
            shutil.copy2(src, os.path.join(dst_folder, os.path.basename(src)))
        elif os.path.isdir(src):
            for entry in os.scandir(src):
                if entry.is_file():
                    shutil.copy2(entry.path, os.path.join(dst_folder, entry.name))

    def _reset_form(self):
        self._src_path = ''
        self._drop_zone.reset()
        self._hw_input.clear()
        self._sw_input.clear()
        self._opc_check.setChecked(False)
        self._req_num_input.clear()
        for cb in self._launch_checks.values():
            cb.setChecked(False)
        self._desc_edit.clear()
        self._io_map_input.set_path('')
        self._instructions_input.set_path('')
        self._status_lbl.setText('')
        self._preview_lbl.setText('—')
