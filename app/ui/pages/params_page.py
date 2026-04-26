"""
Antarus PO Finder — Parameters Page
======================================
Upload and browse parameter files for ПЧ / УПП equipment.
Structure: Параметры / {Group} / {SubType} / {Manufacturer} / file
"""

import os
import shutil
from datetime import datetime

from PySide6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QFormLayout,
    QLabel, QLineEdit, QPushButton, QComboBox,
    QTableWidget, QTableWidgetItem, QHeaderView,
    QMessageBox, QFileDialog, QFrame, QSplitter,
    QAbstractItemView, QSizePolicy,
)
from PySide6.QtCore import Qt

from app.ui.widgets.drop_zone import MiniDropZone


class ParamsPage(QWidget):
    """Upload and manage ПЧ/УПП parameter files."""

    def __init__(self, main_win):
        super().__init__(main_win)
        self._mw = main_win
        self._src_path = ''
        self._build_ui()

    # ── UI ────────────────────────────────────────────────────────────────────

    def _build_ui(self):
        layout = QVBoxLayout(self)
        layout.setContentsMargins(24, 16, 24, 16)
        layout.setSpacing(12)

        title = QLabel('Параметры ПЧ / УПП')
        title.setObjectName('title')
        layout.addWidget(title)

        splitter = QSplitter(Qt.Vertical)
        splitter.setChildrenCollapsible(False)

        splitter.addWidget(self._build_upload_section())
        splitter.addWidget(self._build_list_section())
        splitter.setSizes([320, 400])

        layout.addWidget(splitter, 1)

    def _sep(self) -> QFrame:
        f = QFrame()
        f.setFrameShape(QFrame.HLine)
        f.setObjectName('separator')
        return f

    # ── Upload form ───────────────────────────────────────────────────────────

    def _build_upload_section(self) -> QWidget:
        w = QWidget()
        layout = QVBoxLayout(w)
        layout.setContentsMargins(0, 0, 0, 8)
        layout.setSpacing(8)

        sec_lbl = QLabel('ЗАГРУЗИТЬ ПАРАМЕТРЫ')
        sec_lbl.setObjectName('section-label')
        layout.addWidget(sec_lbl)

        form = QFormLayout()
        form.setSpacing(8)
        form.setLabelAlignment(Qt.AlignRight | Qt.AlignVCenter)

        # Group
        self._group_combo = QComboBox()
        self._group_combo.setFixedHeight(36)
        self._group_combo.currentIndexChanged.connect(self._on_group_changed)
        form.addRow('Тип шкафа:', self._group_combo)

        # Subtype
        self._sub_combo = QComboBox()
        self._sub_combo.setFixedHeight(36)
        form.addRow('Подтип:', self._sub_combo)

        # Manufacturer
        self._manuf_combo = QComboBox()
        self._manuf_combo.setFixedHeight(36)
        form.addRow('Производитель:', self._manuf_combo)

        # File picker + drop zone
        file_row = QHBoxLayout()
        file_row.setSpacing(6)
        self._file_lbl = QLabel('Файл не выбран')
        self._file_lbl.setObjectName('hint')
        self._file_lbl.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Preferred)
        browse_btn = QPushButton('Выбрать файл…')
        browse_btn.setFixedHeight(34)
        browse_btn.setObjectName('secondary')
        browse_btn.clicked.connect(self._browse_file)
        file_row.addWidget(self._file_lbl, 1)
        file_row.addWidget(browse_btn)
        form.addRow('Файл:', file_row)

        # Drop zone
        self._drop_zone = MiniDropZone(self)
        self._drop_zone.setFixedHeight(52)
        self._drop_zone.file_dropped.connect(self._on_file_dropped)
        form.addRow('', self._drop_zone)

        # Description
        self._desc_input = QLineEdit()
        self._desc_input.setFixedHeight(36)
        self._desc_input.setPlaceholderText('Краткое описание (необязательно)')
        form.addRow('Описание:', self._desc_input)

        layout.addLayout(form)

        upload_row = QHBoxLayout()
        upload_row.addStretch()
        upload_btn = QPushButton('Загрузить параметры')
        upload_btn.setFixedHeight(38)
        upload_btn.clicked.connect(self._upload)
        upload_row.addWidget(upload_btn)
        layout.addLayout(upload_row)

        return w

    # ── File list ─────────────────────────────────────────────────────────────

    def _build_list_section(self) -> QWidget:
        w = QWidget()
        layout = QVBoxLayout(w)
        layout.setContentsMargins(0, 8, 0, 0)
        layout.setSpacing(8)

        sec_lbl = QLabel('ЗАГРУЖЕННЫЕ ПАРАМЕТРЫ')
        sec_lbl.setObjectName('section-label')
        layout.addWidget(sec_lbl)

        # Filter bar
        filter_row = QHBoxLayout()
        filter_row.setSpacing(8)
        self._filter_group = QComboBox()
        self._filter_group.setFixedHeight(32)
        self._filter_group.setMinimumWidth(140)
        self._filter_group.currentIndexChanged.connect(self._reload_table)
        filter_row.addWidget(QLabel('Группа:'))
        filter_row.addWidget(self._filter_group)
        self._filter_manuf = QComboBox()
        self._filter_manuf.setFixedHeight(32)
        self._filter_manuf.setMinimumWidth(160)
        self._filter_manuf.currentIndexChanged.connect(self._reload_table)
        filter_row.addWidget(QLabel('Производитель:'))
        filter_row.addWidget(self._filter_manuf)
        filter_row.addStretch()
        refresh_btn = QPushButton('Обновить')
        refresh_btn.setFixedHeight(32)
        refresh_btn.setObjectName('secondary')
        refresh_btn.clicked.connect(self._reload_table)
        filter_row.addWidget(refresh_btn)
        layout.addLayout(filter_row)

        # Table
        self._table = QTableWidget()
        self._table.setColumnCount(5)
        self._table.setHorizontalHeaderLabels(
            ['Файл', 'Группа / Подтип', 'Производитель', 'Дата', 'Описание'])
        self._table.horizontalHeader().setSectionResizeMode(0, QHeaderView.Interactive)
        self._table.horizontalHeader().setSectionResizeMode(1, QHeaderView.ResizeToContents)
        self._table.horizontalHeader().setSectionResizeMode(2, QHeaderView.ResizeToContents)
        self._table.horizontalHeader().setSectionResizeMode(3, QHeaderView.ResizeToContents)
        self._table.horizontalHeader().setSectionResizeMode(4, QHeaderView.Stretch)
        self._table.setSelectionBehavior(QAbstractItemView.SelectRows)
        self._table.setEditTriggers(QAbstractItemView.NoEditTriggers)
        self._table.verticalHeader().setVisible(False)
        self._table.setAlternatingRowColors(True)
        layout.addWidget(self._table, 1)

        btn_row = QHBoxLayout()
        btn_row.setSpacing(8)
        open_btn = QPushButton('Открыть папку')
        open_btn.setFixedHeight(34)
        open_btn.setObjectName('secondary')
        open_btn.clicked.connect(self._open_selected)
        btn_row.addWidget(open_btn)
        del_btn = QPushButton('Удалить запись')
        del_btn.setFixedHeight(34)
        del_btn.setObjectName('secondary')
        del_btn.clicked.connect(self._delete_selected)
        btn_row.addWidget(del_btn)
        btn_row.addStretch()
        self._count_lbl = QLabel('Записей: 0')
        self._count_lbl.setObjectName('hint')
        btn_row.addWidget(self._count_lbl)
        layout.addLayout(btn_row)

        return w

    # ── showEvent — reload on every visit ─────────────────────────────────────

    def showEvent(self, event):
        super().showEvent(event)
        self._populate_combos()
        self._reload_table()

    # ── Populate combos ───────────────────────────────────────────────────────

    def _populate_combos(self):
        groups = self._mw.db.get_all_equipment_groups()
        manufacturers = self._mw.db.get_param_manufacturers()

        # Upload form combos
        self._group_combo.blockSignals(True)
        self._group_combo.clear()
        for g in groups:
            self._group_combo.addItem(g.name, g)
        self._group_combo.blockSignals(False)
        self._populate_subtypes()

        self._manuf_combo.clear()
        for m in manufacturers:
            self._manuf_combo.addItem(m)

        # Filter combos
        self._filter_group.blockSignals(True)
        self._filter_group.clear()
        self._filter_group.addItem('Все группы', None)
        for g in groups:
            self._filter_group.addItem(g.name, g)
        self._filter_group.blockSignals(False)

        self._filter_manuf.blockSignals(True)
        self._filter_manuf.clear()
        self._filter_manuf.addItem('Все производители', None)
        for m in manufacturers:
            self._filter_manuf.addItem(m, m)
        self._filter_manuf.blockSignals(False)

    def _populate_subtypes(self):
        group = self._group_combo.currentData()
        self._sub_combo.clear()
        if not group:
            return
        subtypes = self._mw.db.get_subtypes_for_group(group.id)
        for s in subtypes:
            label = group.name if s.name == '—' else f'{s.name}'
            self._sub_combo.addItem(label, s)

    def _on_group_changed(self, _):
        self._populate_subtypes()

    # ── Browse / drop file ────────────────────────────────────────────────────

    def _browse_file(self):
        path, _ = QFileDialog.getOpenFileName(self, 'Выбрать файл параметров', '')
        if path:
            self._set_file(path)

    def _on_file_dropped(self, path: str):
        self._set_file(path)

    def _set_file(self, path: str):
        self._src_path = path
        self._file_lbl.setText(os.path.basename(path))

    # ── Upload ────────────────────────────────────────────────────────────────

    def _upload(self):
        if not self._src_path or not os.path.isfile(self._src_path):
            QMessageBox.warning(self, 'Загрузка', 'Выберите файл параметров.')
            return

        sub = self._sub_combo.currentData()
        manuf = self._manuf_combo.currentText().strip()

        if not sub:
            QMessageBox.warning(self, 'Загрузка', 'Выберите подтип шкафа.')
            return
        if not manuf:
            QMessageBox.warning(self, 'Загрузка', 'Выберите производителя.')
            return

        root_path = self._mw.cfg.root_path()
        if not root_path or not os.path.isdir(root_path):
            QMessageBox.warning(self, 'Загрузка',
                                'Путь к диску не задан. Проверьте Настройки.')
            return

        group = self._group_combo.currentData()
        dst_folder = self._mw.hierarchy_svc.params_path(
            root_path, group.name, sub.name, manuf)

        try:
            os.makedirs(dst_folder, exist_ok=True)
            fname = os.path.basename(self._src_path)
            dst_path = os.path.join(dst_folder, fname)
            shutil.copy2(self._src_path, dst_path)
        except OSError as e:
            QMessageBox.critical(self, 'Ошибка', str(e))
            return

        self._mw.db.add_param_file({
            'subtype_id':   sub.id,
            'manufacturer': manuf,
            'filename':     fname,
            'disk_path':    dst_folder,
            'description':  self._desc_input.text().strip(),
            'upload_date':  datetime.now().strftime('%Y-%m-%d %H:%M:%S'),
        })

        self._mw.show_status(f'Параметры загружены: {fname}')
        self._desc_input.clear()
        self._src_path = ''
        self._file_lbl.setText('Файл не выбран')
        self._reload_table()

    # ── Table ─────────────────────────────────────────────────────────────────

    def _reload_table(self):
        grp_data = self._filter_group.currentData()
        manuf_data = self._filter_manuf.currentData()

        # Determine subtype_id filter from group filter
        subtype_ids = None
        if grp_data is not None:
            subs = self._mw.db.get_subtypes_for_group(grp_data.id)
            subtype_ids = [s.id for s in subs]

        rows = self._mw.db.get_param_files(
            manufacturer=manuf_data if manuf_data else None,
        )

        # Filter by group client-side if needed
        if subtype_ids is not None:
            rows = [r for r in rows if r.get('subtype_id') in subtype_ids]

        self._table.setRowCount(len(rows))
        for i, row in enumerate(rows):
            sub_name = row.get('subtype_name') or '—'
            grp_name = row.get('group_name') or ''
            hier = f'{grp_name} / {sub_name}' if sub_name != '—' else grp_name

            self._table.setItem(i, 0, QTableWidgetItem(row.get('filename', '')))
            self._table.setItem(i, 1, QTableWidgetItem(hier))
            self._table.setItem(i, 2, QTableWidgetItem(row.get('manufacturer', '')))
            date_str = (row.get('upload_date', '') or '')[:10]
            self._table.setItem(i, 3, QTableWidgetItem(date_str))
            self._table.setItem(i, 4, QTableWidgetItem(row.get('description', '')))
            self._table.item(i, 0).setData(Qt.UserRole, row)

        self._count_lbl.setText(f'Записей: {len(rows)}')

    def _selected_row(self) -> dict | None:
        row = self._table.currentRow()
        if row < 0:
            return None
        item = self._table.item(row, 0)
        return item.data(Qt.UserRole) if item else None

    def _open_selected(self):
        row = self._selected_row()
        if not row:
            QMessageBox.information(self, 'Открыть', 'Выберите строку.')
            return
        folder = row.get('disk_path', '')
        if folder and os.path.isdir(folder):
            os.startfile(folder)
        else:
            QMessageBox.warning(self, 'Открыть', f'Папка не найдена:\n{folder}')

    def _delete_selected(self):
        row = self._selected_row()
        if not row:
            QMessageBox.information(self, 'Удалить', 'Выберите строку.')
            return
        reply = QMessageBox.question(
            self, 'Удалить запись',
            f'Удалить запись о файле «{row["filename"]}»?\n'
            f'Файл на диске НЕ удаляется.',
            QMessageBox.Yes | QMessageBox.No, QMessageBox.No,
        )
        if reply == QMessageBox.Yes:
            self._mw.db.delete_param_file(row['id'])
            self._reload_table()
