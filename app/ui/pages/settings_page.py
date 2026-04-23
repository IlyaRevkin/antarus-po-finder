"""
FirmwareFinder — Settings Page
==================================
Administrator-only settings: root path, roles, rules CRUD, prefixes, quick apps.
"""

import os
import json
from PySide6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QFormLayout, QStackedWidget,
    QLabel, QLineEdit, QPushButton, QComboBox, QListWidget,
    QListWidgetItem, QMessageBox, QGroupBox, QFileDialog,
    QDialog, QTextEdit, QDialogButtonBox, QAbstractItemView,
    QTableWidget, QTableWidgetItem, QHeaderView, QCheckBox,
    QScrollArea, QFrame, QInputDialog,
)
from PySide6.QtCore import Qt, QSize
from app.ui.icons import make_icon, ICON_SECONDARY, ICON_ON_ACCENT

from app.domain.models import Rule
from app.ui.widgets.drop_zone import PathDropEdit, MiniDropZone
from datetime import datetime


class SettingsPage(QWidget):
    def __init__(self, main_win):
        super().__init__()
        self._mw = main_win
        self._build()

    def _build(self):
        layout = QVBoxLayout(self)
        layout.setContentsMargins(24, 24, 24, 16)
        layout.setSpacing(16)

        title = QLabel('Настройки')
        title.setObjectName('title')
        layout.addWidget(title)

        # ── Custom tab bar (QPushButton row + QStackedWidget) ──────────────────
        # QTabWidget::tab QSS is ignored by the Windows native style, so we
        # build our own tab bar to get full CSS control.
        tab_defs = [
            ('Общие',          self._build_general_tab),
            ('Правила',        self._build_rules_tab),
            ('Иерархия',       self._build_hierarchy_tab),
            ('Быстрый доступ', self._build_quickapps_tab),
        ]

        tab_bar = QHBoxLayout()
        tab_bar.setSpacing(4)
        tab_bar.setContentsMargins(0, 0, 0, 0)
        self._tab_btns: list[QPushButton] = []
        self._tab_stack = QStackedWidget()

        for i, (label, builder) in enumerate(tab_defs):
            btn = QPushButton(label)
            btn.setObjectName('tab-btn')
            btn.setCheckable(True)
            btn.setFixedHeight(34)
            btn.clicked.connect(lambda checked, idx=i: self._switch_tab(idx))
            tab_bar.addWidget(btn)
            self._tab_btns.append(btn)
            self._tab_stack.addWidget(builder())

        tab_bar.addStretch()
        layout.addLayout(tab_bar)
        layout.addWidget(self._tab_stack, 1)

        self._switch_tab(0)

    def _switch_tab(self, idx: int):
        self._tab_stack.setCurrentIndex(idx)
        for i, btn in enumerate(self._tab_btns):
            btn.setChecked(i == idx)

    # ═══════════════════════════ GENERAL TAB ══════════════════════════════════

    def _build_general_tab(self) -> QWidget:
        outer = QWidget()
        outer_lay = QVBoxLayout(outer)
        outer_lay.setContentsMargins(0, 0, 0, 0)

        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setFrameShape(QFrame.NoFrame)
        scroll.setHorizontalScrollBarPolicy(Qt.ScrollBarAlwaysOff)

        w = QWidget()
        layout = QVBoxLayout(w)
        layout.setContentsMargins(20, 16, 20, 16)
        layout.setSpacing(0)

        def _section(title: str):
            lbl = QLabel(title)
            lbl.setObjectName('muted')
            lbl.setStyleSheet('font-size: 11px; font-weight: 700; text-transform: uppercase;'
                              'letter-spacing: 0.5px; margin-top: 16px; margin-bottom: 4px;')
            layout.addWidget(lbl)

        def _sep():
            line = QFrame()
            line.setFrameShape(QFrame.HLine)
            line.setObjectName('separator')
            line.setFixedHeight(1)
            line.setStyleSheet('margin-top: 12px;')
            layout.addWidget(line)

        # ── Disk path ─────────────────────────────────────────────────────────
        _section('Путь к диску (WebDAV / сетевая папка)')
        disk_row = QHBoxLayout()
        disk_row.setSpacing(6)
        self._root_path_input = QLineEdit()
        self._root_path_input.setFixedHeight(36)
        disk_row.addWidget(self._root_path_input, 1)
        browse_btn = QPushButton('…')
        browse_btn.setFixedWidth(36)
        browse_btn.setFixedHeight(36)
        browse_btn.setObjectName('secondary')
        browse_btn.clicked.connect(self._browse_root)
        disk_row.addWidget(browse_btn)
        save_disk_btn = QPushButton('Сохранить')
        save_disk_btn.setFixedHeight(36)
        save_disk_btn.setObjectName('secondary')
        save_disk_btn.clicked.connect(self._save_root_path)
        disk_row.addWidget(save_disk_btn)
        layout.addLayout(disk_row)
        _sep()

        # ── Second disk path ───────────────────────────────────────────────────
        _section('Второй диск (шкафы и электросхемы)')
        disk2_row = QHBoxLayout()
        disk2_row.setSpacing(6)
        self._second_disk_input = QLineEdit()
        self._second_disk_input.setFixedHeight(36)
        self._second_disk_input.setPlaceholderText('Путь к папке с кабинетами (шкафами)')
        disk2_row.addWidget(self._second_disk_input, 1)
        browse_disk2_btn = QPushButton('…')
        browse_disk2_btn.setFixedWidth(36)
        browse_disk2_btn.setFixedHeight(36)
        browse_disk2_btn.setObjectName('secondary')
        browse_disk2_btn.clicked.connect(self._browse_second_disk)
        disk2_row.addWidget(browse_disk2_btn)
        save_disk2_btn = QPushButton('Сохранить')
        save_disk2_btn.setFixedHeight(36)
        save_disk2_btn.setObjectName('secondary')
        save_disk2_btn.clicked.connect(self._save_second_disk_path)
        disk2_row.addWidget(save_disk2_btn)
        layout.addLayout(disk2_row)
        _sep()

        # ── Config sync ────────────────────────────────────────────────────────
        _section('Синхронизация конфига')
        conf_row = QHBoxLayout()
        conf_row.setSpacing(6)
        export_btn = QPushButton('Экспорт на диск')
        export_btn.setFixedHeight(36)
        export_btn.setObjectName('secondary')
        export_btn.clicked.connect(self._export_config)
        conf_row.addWidget(export_btn)
        import_btn = QPushButton('Импорт с диска')
        import_btn.setFixedHeight(36)
        import_btn.setObjectName('secondary')
        import_btn.clicked.connect(self._import_config)
        conf_row.addWidget(import_btn)
        conf_row.addStretch()
        layout.addLayout(conf_row)
        _sep()

        # ── Role switch ───────────────────────────────────────────────────────
        _section('Сменить роль')
        role_row = QHBoxLayout()
        role_row.setSpacing(6)
        self._role_combo = QComboBox()
        self._role_combo.setFixedHeight(36)
        self._role_combo.addItem('Наладчик',          'naladchik')
        self._role_combo.addItem('Нал-Администратор', 'naladchik_admin')
        self._role_combo.addItem('Программист',       'programmer')
        self._role_combo.addItem('Администратор',     'administrator')
        role_row.addWidget(self._role_combo)
        self._pwd_input = QLineEdit()
        self._pwd_input.setPlaceholderText('Пароль (если требуется)')
        self._pwd_input.setEchoMode(QLineEdit.Password)
        self._pwd_input.setFixedHeight(36)
        role_row.addWidget(self._pwd_input, 1)
        switch_btn = QPushButton('Сменить')
        switch_btn.setFixedHeight(36)
        switch_btn.clicked.connect(self._switch_role)
        role_row.addWidget(switch_btn)
        layout.addLayout(role_row)
        _sep()

        # ── Passwords ─────────────────────────────────────────────────────────
        _section('Пароли доступа')
        admin_row = QHBoxLayout()
        admin_row.setSpacing(6)
        admin_lbl = QLabel('Администратор:')
        admin_lbl.setFixedWidth(160)
        admin_row.addWidget(admin_lbl)
        self._admin_pwd = QLineEdit(self._mw.cfg.admin_password())
        self._admin_pwd.setEchoMode(QLineEdit.Password)
        self._admin_pwd.setFixedHeight(36)
        self._admin_pwd.setPlaceholderText('Пароль администратора')
        admin_row.addWidget(self._admin_pwd, 1)
        layout.addLayout(admin_row)
        prog_row = QHBoxLayout()
        prog_row.setSpacing(6)
        prog_lbl = QLabel('Программист:')
        prog_lbl.setFixedWidth(160)
        prog_row.addWidget(prog_lbl)
        self._prog_pwd = QLineEdit(self._mw.cfg.programmer_password())
        self._prog_pwd.setEchoMode(QLineEdit.Password)
        self._prog_pwd.setFixedHeight(36)
        self._prog_pwd.setPlaceholderText('Пароль программиста')
        prog_row.addWidget(self._prog_pwd, 1)
        layout.addLayout(prog_row)
        save_pwd_row = QHBoxLayout()
        save_pwd_btn = QPushButton('Сохранить пароли')
        save_pwd_btn.setFixedHeight(36)
        save_pwd_btn.setObjectName('secondary')
        save_pwd_btn.clicked.connect(self._save_passwords)
        save_pwd_row.addStretch()
        save_pwd_row.addWidget(save_pwd_btn)
        layout.addLayout(save_pwd_row)
        _sep()

        # ── Sync interval ──────────────────────────────────────────────────────
        _section('Интервал синхронизации с диском')
        sync_row = QHBoxLayout()
        sync_row.setSpacing(8)
        sync_row.addWidget(QLabel('Каждые'))
        self._sync_interval_input = QLineEdit()
        self._sync_interval_input.setFixedWidth(64)
        self._sync_interval_input.setFixedHeight(36)
        sync_row.addWidget(self._sync_interval_input)
        sync_row.addWidget(QLabel('минут'))
        save_sync_btn = QPushButton('Сохранить')
        save_sync_btn.setFixedHeight(36)
        save_sync_btn.setObjectName('secondary')
        save_sync_btn.clicked.connect(self._save_sync_interval)
        sync_row.addWidget(save_sync_btn)
        sync_row.addStretch()
        layout.addLayout(sync_row)
        _sep()

        # ── Misc ──────────────────────────────────────────────────────────────
        _section('Прочее')
        misc_row = QHBoxLayout()
        misc_row.setSpacing(8)
        self._keep_arch_cb = QCheckBox('Хранить архивы после извлечения')
        misc_row.addWidget(self._keep_arch_cb)
        save_misc_btn = QPushButton('Сохранить')
        save_misc_btn.setFixedHeight(36)
        save_misc_btn.setObjectName('secondary')
        save_misc_btn.clicked.connect(self._save_misc)
        misc_row.addWidget(save_misc_btn)
        misc_row.addStretch()
        layout.addLayout(misc_row)

        layout.addStretch()
        scroll.setWidget(w)
        outer_lay.addWidget(scroll)
        return outer

    # ═══════════════════════════ RULES TAB ════════════════════════════════════

    def _build_rules_tab(self) -> QWidget:
        w = QWidget()
        layout = QVBoxLayout(w)
        layout.setContentsMargins(16, 16, 16, 16)
        layout.setSpacing(12)

        # Row 1: filter
        filter_row = QHBoxLayout()
        filter_row.setSpacing(8)
        self._rule_search = QLineEdit()
        self._rule_search.setPlaceholderText('Фильтр по имени…')
        self._rule_search.textChanged.connect(self._filter_rules)
        filter_row.addWidget(self._rule_search)
        layout.addLayout(filter_row)

        # Row 2: action buttons (right-aligned)
        btn_row = QHBoxLayout()
        btn_row.setSpacing(8)

        add_btn = QPushButton('Добавить')
        add_btn.setIcon(make_icon('plus', ICON_ON_ACCENT, 14))
        add_btn.setIconSize(QSize(14, 14))
        add_btn.clicked.connect(self._add_rule)
        btn_row.addWidget(add_btn)

        edit_btn = QPushButton('Изменить')
        edit_btn.setObjectName('secondary')
        edit_btn.setIcon(make_icon('edit', ICON_SECONDARY, 14))
        edit_btn.setIconSize(QSize(14, 14))
        edit_btn.clicked.connect(self._edit_rule)
        btn_row.addWidget(edit_btn)

        copy_btn = QPushButton('Копировать')
        copy_btn.setObjectName('secondary')
        copy_btn.setIcon(make_icon('copy', ICON_SECONDARY, 14))
        copy_btn.setIconSize(QSize(14, 14))
        copy_btn.clicked.connect(self._copy_rule)
        btn_row.addWidget(copy_btn)

        del_btn = QPushButton('Удалить')
        del_btn.setObjectName('danger')
        del_btn.setIcon(make_icon('trash', ICON_ON_ACCENT, 14))
        del_btn.setIconSize(QSize(14, 14))
        del_btn.clicked.connect(self._delete_rule)
        btn_row.addWidget(del_btn)

        btn_row.addStretch()
        layout.addLayout(btn_row)

        # Table
        self._rules_table = QTableWidget()
        self._rules_table.setColumnCount(4)
        self._rules_table.setHorizontalHeaderLabels(
            ['Название', 'Тип', 'Контроллер', 'Папка на диске']
        )
        hh = self._rules_table.horizontalHeader()
        hh.setSectionResizeMode(0, QHeaderView.ResizeToContents)
        hh.setSectionResizeMode(1, QHeaderView.ResizeToContents)
        hh.setSectionResizeMode(2, QHeaderView.ResizeToContents)
        hh.setSectionResizeMode(3, QHeaderView.Stretch)
        self._rules_table.setSelectionBehavior(QAbstractItemView.SelectRows)
        self._rules_table.setSelectionMode(QAbstractItemView.SingleSelection)
        self._rules_table.setEditTriggers(QAbstractItemView.NoEditTriggers)
        self._rules_table.verticalHeader().hide()
        self._rules_table.doubleClicked.connect(self._edit_rule)
        layout.addWidget(self._rules_table)

        self._rules_status = QLabel('')
        self._rules_status.setObjectName('muted')
        layout.addWidget(self._rules_status)

        return w

    # ═══════════════════════════ PREFIXES TAB ═════════════════════════════════

    def _build_prefixes_tab(self) -> QWidget:
        w = QWidget()
        layout = QVBoxLayout(w)
        layout.setContentsMargins(16, 16, 16, 16)
        layout.setSpacing(12)

        lbl = QLabel('Соответствие типа оборудования → номер версии (префикс)')
        lbl.setObjectName('subtitle')
        layout.addWidget(lbl)

        # Table for prefix editing
        self._prefix_table = QTableWidget()
        self._prefix_table.setColumnCount(2)
        self._prefix_table.setHorizontalHeaderLabels(['Тип оборудования', 'Префикс'])
        self._prefix_table.horizontalHeader().setSectionResizeMode(0, QHeaderView.Stretch)
        self._prefix_table.horizontalHeader().setSectionResizeMode(1, QHeaderView.ResizeToContents)
        self._prefix_table.setFixedHeight(220)
        layout.addWidget(self._prefix_table)

        btn_row = QHBoxLayout()
        add_row_btn = QPushButton('Добавить строку')
        add_row_btn.setObjectName('secondary')
        add_row_btn.setIcon(make_icon('plus', ICON_SECONDARY, 14))
        add_row_btn.setIconSize(QSize(14, 14))
        add_row_btn.clicked.connect(self._add_prefix_row)
        btn_row.addWidget(add_row_btn)

        del_row_btn = QPushButton('Удалить строку')
        del_row_btn.setObjectName('secondary')
        del_row_btn.setIcon(make_icon('trash', ICON_SECONDARY, 14))
        del_row_btn.setIconSize(QSize(14, 14))
        del_row_btn.clicked.connect(self._del_prefix_row)
        btn_row.addWidget(del_row_btn)

        btn_row.addStretch()

        save_btn = QPushButton('Сохранить префиксы')
        save_btn.setIcon(make_icon('save', ICON_ON_ACCENT, 14))
        save_btn.setIconSize(QSize(14, 14))
        save_btn.clicked.connect(self._save_prefixes)
        btn_row.addWidget(save_btn)
        layout.addWidget(QLabel(''))
        layout.addLayout(btn_row)

        hint = QLabel(
            'Пример: КПЧ → 3 даст версию 3.42.260414\n'
            'Формат версии: prefix.тело.YYMMDD (тело может быть 42 или 35.6)'
        )
        hint.setObjectName('muted')
        layout.addWidget(hint)

        layout.addStretch()
        return w

    # ═══════════════════════════ QUICK APPS TAB ═══════════════════════════════

    def _build_quickapps_tab(self) -> QWidget:
        w = QWidget()
        layout = QVBoxLayout(w)
        layout.setContentsMargins(16, 16, 16, 16)
        layout.setSpacing(12)

        lbl = QLabel('Ярлыки для быстрого запуска (доступны наладчику в поиске)')
        lbl.setObjectName('subtitle')
        layout.addWidget(lbl)

        self._apps_table = QTableWidget()
        self._apps_table.setColumnCount(3)
        self._apps_table.setHorizontalHeaderLabels(['Название', 'Путь', 'Иконка'])
        self._apps_table.horizontalHeader().setSectionResizeMode(0, QHeaderView.ResizeToContents)
        self._apps_table.horizontalHeader().setSectionResizeMode(1, QHeaderView.Stretch)
        self._apps_table.horizontalHeader().setSectionResizeMode(2, QHeaderView.ResizeToContents)
        self._apps_table.setSelectionBehavior(QAbstractItemView.SelectRows)
        self._apps_table.verticalHeader().hide()
        layout.addWidget(self._apps_table)

        btn_row = QHBoxLayout()
        add_app_btn = QPushButton('Добавить')
        add_app_btn.setObjectName('secondary')
        add_app_btn.setIcon(make_icon('plus', ICON_SECONDARY, 14))
        add_app_btn.setIconSize(QSize(14, 14))
        add_app_btn.clicked.connect(self._add_app_row)
        btn_row.addWidget(add_app_btn)

        del_app_btn = QPushButton('Удалить')
        del_app_btn.setObjectName('secondary')
        del_app_btn.setIcon(make_icon('trash', ICON_SECONDARY, 14))
        del_app_btn.setIconSize(QSize(14, 14))
        del_app_btn.clicked.connect(self._del_app_row)
        btn_row.addWidget(del_app_btn)

        btn_row.addStretch()

        save_apps_btn = QPushButton('Сохранить')
        save_apps_btn.setIcon(make_icon('save', ICON_ON_ACCENT, 14))
        save_apps_btn.setIconSize(QSize(14, 14))
        save_apps_btn.clicked.connect(self._save_apps)
        btn_row.addWidget(save_apps_btn)
        layout.addLayout(btn_row)

        layout.addStretch()
        return w

    # ═══════════════════════════ HIERARCHY TAB ════════════════════════════════

    def _build_hierarchy_tab(self) -> QWidget:
        w = QWidget()
        outer = QVBoxLayout(w)
        outer.setContentsMargins(0, 0, 0, 0)

        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setFrameShape(QFrame.NoFrame)
        inner = QWidget()
        layout = QVBoxLayout(inner)
        layout.setContentsMargins(16, 16, 16, 16)
        layout.setSpacing(16)

        # ── Groups ────────────────────────────────────────────────────────────
        grp_box = QGroupBox('Типы шкафов (группы)')
        grp_lay = QVBoxLayout(grp_box)
        self._grp_table = QTableWidget()
        self._grp_table.setColumnCount(2)
        self._grp_table.setHorizontalHeaderLabels(['Название', 'Префикс версии'])
        self._grp_table.horizontalHeader().setSectionResizeMode(0, QHeaderView.Stretch)
        self._grp_table.horizontalHeader().setSectionResizeMode(1, QHeaderView.ResizeToContents)
        self._grp_table.setSelectionBehavior(QAbstractItemView.SelectRows)
        self._grp_table.verticalHeader().hide()
        self._grp_table.setFixedHeight(180)
        grp_lay.addWidget(self._grp_table)
        grp_btns = QHBoxLayout()
        for label, slot in [('Добавить', self._add_group),
                             ('Удалить',  self._del_group)]:
            btn = QPushButton(label)
            btn.setObjectName('secondary')
            btn.clicked.connect(slot)
            grp_btns.addWidget(btn)
        grp_btns.addStretch()
        grp_lay.addLayout(grp_btns)
        layout.addWidget(grp_box)

        # ── Subtypes ──────────────────────────────────────────────────────────
        sub_box = QGroupBox('Подтипы шкафов')
        sub_lay = QVBoxLayout(sub_box)
        self._sub_table = QTableWidget()
        self._sub_table.setColumnCount(4)
        self._sub_table.setHorizontalHeaderLabels(
            ['Группа', 'Название', 'Префикс', 'Папка'])
        hh = self._sub_table.horizontalHeader()
        hh.setSectionResizeMode(0, QHeaderView.ResizeToContents)
        hh.setSectionResizeMode(1, QHeaderView.ResizeToContents)
        hh.setSectionResizeMode(2, QHeaderView.ResizeToContents)
        hh.setSectionResizeMode(3, QHeaderView.Stretch)
        self._sub_table.setSelectionBehavior(QAbstractItemView.SelectRows)
        self._sub_table.verticalHeader().hide()
        self._sub_table.setFixedHeight(200)
        sub_lay.addWidget(self._sub_table)
        sub_btns = QHBoxLayout()
        for label, slot in [('Добавить', self._add_subtype),
                             ('Удалить',  self._del_subtype)]:
            btn = QPushButton(label)
            btn.setObjectName('secondary')
            btn.clicked.connect(slot)
            sub_btns.addWidget(btn)
        sub_btns.addStretch()
        sub_lay.addLayout(sub_btns)
        layout.addWidget(sub_box)

        # ── Controllers ───────────────────────────────────────────────────────
        ctrl_box = QGroupBox('Типы контроллеров')
        ctrl_lay = QVBoxLayout(ctrl_box)
        self._ctrl_hier_list = QListWidget()
        self._ctrl_hier_list.setFixedHeight(130)
        ctrl_lay.addWidget(self._ctrl_hier_list)
        ctrl_btns = QHBoxLayout()
        for label, slot in [('Добавить', self._add_controller),
                             ('Удалить',  self._del_controller)]:
            btn = QPushButton(label)
            btn.setObjectName('secondary')
            btn.clicked.connect(slot)
            ctrl_btns.addWidget(btn)
        ctrl_btns.addStretch()
        ctrl_lay.addLayout(ctrl_btns)
        layout.addWidget(ctrl_box)

        # ── Rebuild button ────────────────────────────────────────────────────
        rebuild_btn = QPushButton('Пересоздать структуру диска')
        rebuild_btn.setIcon(make_icon('folder', ICON_ON_ACCENT, 14))
        rebuild_btn.setIconSize(QSize(14, 14))
        rebuild_btn.clicked.connect(self._rebuild_hierarchy)
        layout.addWidget(rebuild_btn)

        scan_unknown_btn = QPushButton('Сканировать неизвестные файлы')
        scan_unknown_btn.setObjectName('secondary')
        scan_unknown_btn.clicked.connect(self._scan_unknown_files)
        layout.addWidget(scan_unknown_btn)

        layout.addStretch()
        scroll.setWidget(inner)
        outer.addWidget(scroll)
        return w

    def _load_hierarchy(self):
        # Groups
        groups = self._mw.db.get_all_equipment_groups()
        self._grp_table.setRowCount(len(groups))
        for row, g in enumerate(groups):
            self._grp_table.setItem(row, 0, QTableWidgetItem(g.name))
            self._grp_table.setItem(row, 1, QTableWidgetItem(str(g.prefix)))
            self._grp_table.item(row, 0).setData(Qt.UserRole, g)

        # Subtypes
        subtypes = self._mw.db.get_all_equipment_subtypes()
        groups_map = {g.id: g.name for g in groups}
        self._sub_table.setRowCount(len(subtypes))
        for row, s in enumerate(subtypes):
            self._sub_table.setItem(row, 0, QTableWidgetItem(groups_map.get(s.group_id, '?')))
            self._sub_table.setItem(row, 1, QTableWidgetItem(s.name))
            self._sub_table.setItem(row, 2, QTableWidgetItem(str(s.prefix)))
            self._sub_table.setItem(row, 3, QTableWidgetItem(s.folder_name))
            self._sub_table.item(row, 0).setData(Qt.UserRole, s)

        # Controllers
        self._ctrl_hier_list.clear()
        for c in self._mw.db.get_all_controller_models():
            item = QListWidgetItem(c.name)
            item.setData(Qt.UserRole, c)
            self._ctrl_hier_list.addItem(item)

    def _add_group(self):
        from app.domain.hierarchy import EquipmentGroup
        name, ok = QInputDialog.getText(self, 'Добавить группу', 'Название (напр. НГР):')
        if not ok or not name.strip():
            return
        prefix_str, ok2 = QInputDialog.getText(
            self, 'Префикс', 'Цифровой префикс версии (напр. 2):')
        if not ok2:
            return
        try:
            prefix = int(prefix_str.strip())
        except ValueError:
            QMessageBox.warning(self, 'Ошибка', 'Префикс должен быть числом.')
            return
        g = EquipmentGroup(id=None, name=name.strip(), prefix=prefix,
                           sort_order=self._grp_table.rowCount() + 1)
        self._mw.db.upsert_equipment_group(g)
        self._load_hierarchy()
        self._mw.show_status(f'Группа добавлена: {name.strip()}')

    def _del_group(self):
        row = self._grp_table.currentRow()
        if row < 0:
            QMessageBox.information(self, 'Удалить', 'Выберите группу.')
            return
        g = self._grp_table.item(row, 0).data(Qt.UserRole)
        reply = QMessageBox.question(
            self, 'Удалить группу',
            f'Удалить группу «{g.name}»? Все подтипы будут удалены.',
            QMessageBox.Yes | QMessageBox.No, QMessageBox.No)
        if reply == QMessageBox.Yes:
            self._mw.db.delete_equipment_group(g.id)
            self._load_hierarchy()

    def _add_subtype(self):
        from app.domain.hierarchy import EquipmentSubType
        groups = self._mw.db.get_all_equipment_groups()
        if not groups:
            QMessageBox.warning(self, 'Ошибка', 'Сначала добавьте хотя бы одну группу.')
            return
        group_names = [g.name for g in groups]
        grp_name, ok = QInputDialog.getItem(
            self, 'Группа', 'Выберите группу:', group_names, 0, False)
        if not ok:
            return
        group = next(g for g in groups if g.name == grp_name)

        sub_name, ok2 = QInputDialog.getText(
            self, 'Подтип', 'Название подтипа (напр. КПЧ или — если нет):')
        if not ok2 or not sub_name.strip():
            return
        prefix_str, ok3 = QInputDialog.getText(
            self, 'Префикс подтипа', 'Префикс (0 — если нет подтипа):')
        if not ok3:
            return
        try:
            prefix = int(prefix_str.strip())
        except ValueError:
            QMessageBox.warning(self, 'Ошибка', 'Префикс должен быть числом.')
            return
        folder_name = (f'{grp_name}-{sub_name.strip()}'
                       if sub_name.strip() != '—' else grp_name)
        s = EquipmentSubType(id=None, group_id=group.id,
                             name=sub_name.strip(), prefix=prefix,
                             folder_name=folder_name,
                             sort_order=len(self._mw.db.get_subtypes_for_group(group.id)) + 1)
        self._mw.db.upsert_equipment_subtype(s)
        self._load_hierarchy()
        self._mw.show_status(f'Подтип добавлен: {folder_name}')

    def _del_subtype(self):
        row = self._sub_table.currentRow()
        if row < 0:
            QMessageBox.information(self, 'Удалить', 'Выберите подтип.')
            return
        s = self._sub_table.item(row, 0).data(Qt.UserRole)
        reply = QMessageBox.question(
            self, 'Удалить подтип', f'Удалить подтип «{s.folder_name}»?',
            QMessageBox.Yes | QMessageBox.No, QMessageBox.No)
        if reply == QMessageBox.Yes:
            self._mw.db.delete_equipment_subtype(s.id)
            self._load_hierarchy()

    def _add_controller(self):
        from app.domain.hierarchy import ControllerModel
        name, ok = QInputDialog.getText(
            self, 'Добавить контроллер', 'Название (напр. SMH6):')
        if not ok or not name.strip():
            return
        c = ControllerModel(id=None, name=name.strip().upper(),
                            sort_order=self._ctrl_hier_list.count() + 1)
        self._mw.db.upsert_controller_model(c)
        self._load_hierarchy()
        self._mw.show_status(f'Контроллер добавлен: {name.strip().upper()}')

    def _del_controller(self):
        item = self._ctrl_hier_list.currentItem()
        if not item:
            QMessageBox.information(self, 'Удалить', 'Выберите контроллер.')
            return
        c = item.data(Qt.UserRole)
        reply = QMessageBox.question(
            self, 'Удалить контроллер', f'Удалить контроллер «{c.name}»?',
            QMessageBox.Yes | QMessageBox.No, QMessageBox.No)
        if reply == QMessageBox.Yes:
            self._mw.db.delete_controller_model(c.id)
            self._load_hierarchy()

    def _rebuild_hierarchy(self):
        root = self._mw.cfg.root_path()
        if not root or not os.path.isdir(root):
            QMessageBox.warning(self, 'Диск', 'Сетевой диск недоступен.')
            return
        result = self._mw.hierarchy_svc.ensure_structure(root)
        if result.get('errors'):
            QMessageBox.warning(self, 'Ошибка',
                '\n'.join(result['errors'][:10]))
        else:
            QMessageBox.information(self, 'Готово',
                f'Создано папок: {result["created_count"]}')
        self._mw.show_status(f'Структура обновлена: {result["created_count"]} папок')

    def _scan_unknown_files(self):
        import shutil as _shutil
        from app.domain.hierarchy import UNKNOWN_FW_FOLDER
        from app.services.hierarchy_service import FOLDER_PO
        from PySide6.QtWidgets import (QDialog, QVBoxLayout, QListWidget,
                                        QListWidgetItem, QHBoxLayout, QAbstractItemView)

        root = self._mw.cfg.root_path()
        if not root or not os.path.isdir(root):
            QMessageBox.warning(self, 'Сканирование', 'Сетевой диск недоступен.')
            return

        unknown = self._mw.hierarchy_svc.scan_unknown_files(root)
        if not unknown:
            QMessageBox.information(self, 'Сканирование', 'Неизвестных файлов не найдено.')
            return

        dlg = QDialog(self)
        dlg.setWindowTitle(f'Неизвестные файлы ({len(unknown)})')
        dlg.setMinimumSize(600, 400)
        lay = QVBoxLayout(dlg)

        lst = QListWidget()
        lst.setSelectionMode(QAbstractItemView.MultiSelection)
        for item_data in unknown:
            text = f"[{item_data['type']}]  {item_data['name']}  —  {item_data['path']}"
            item = QListWidgetItem(text)
            item.setData(Qt.UserRole, item_data)
            lst.addItem(item)
        lay.addWidget(lst)

        btn_row = QHBoxLayout()

        def _move_selected():
            unknown_folder = os.path.join(root, FOLDER_PO, UNKNOWN_FW_FOLDER)
            os.makedirs(unknown_folder, exist_ok=True)
            moved = 0
            for i in range(lst.count()):
                item = lst.item(i)
                if item.isSelected():
                    d = item.data(Qt.UserRole)
                    try:
                        _shutil.move(d['path'], os.path.join(unknown_folder, d['name']))
                        moved += 1
                    except Exception as e:
                        QMessageBox.warning(dlg, 'Ошибка', f'Не удалось переместить {d["name"]}: {e}')
            dlg.accept()
            self._mw.show_status(f'Перемещено: {moved}')

        move_btn = QPushButton(f'Переместить в {UNKNOWN_FW_FOLDER}/')
        move_btn.clicked.connect(_move_selected)
        btn_row.addWidget(move_btn)
        btn_row.addStretch()
        close_btn = QPushButton('Закрыть')
        close_btn.clicked.connect(dlg.accept)
        btn_row.addWidget(close_btn)
        lay.addLayout(btn_row)

        dlg.exec()

    # ═══════════════════════════ TYPES TAB (legacy) ════════════════════════════

    def _build_types_tab(self) -> QWidget:
        w = QWidget()
        outer = QVBoxLayout(w)
        outer.setContentsMargins(0, 0, 0, 0)
        outer.setSpacing(0)

        # Scrollable area so content is accessible on any window height
        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setFrameShape(QFrame.NoFrame)
        inner = QWidget()
        layout = QVBoxLayout(inner)
        layout.setContentsMargins(16, 16, 16, 16)
        layout.setSpacing(16)

        for title, attr, cfg_key in [
            ('Типы оборудования', '_equip_list', 'equipment_types'),
            ('Типы работ',        '_work_list',  'work_types'),
            ('Типы контроллеров', '_ctrl_list',  'controller_types'),
        ]:
            box = QGroupBox(title)
            bl = QVBoxLayout(box)
            bl.setSpacing(6)
            lst = QListWidget()
            lst.setMinimumHeight(130)
            setattr(self, attr, lst)
            bl.addWidget(lst)
            btn_row = QHBoxLayout()
            btn_row.setSpacing(6)
            add_btn = QPushButton('Добавить')
            add_btn.setObjectName('secondary')
            add_btn.setIcon(make_icon('plus', ICON_SECONDARY, 14))
            add_btn.setIconSize(QSize(14, 14))
            del_btn = QPushButton('Удалить')
            del_btn.setObjectName('secondary')
            del_btn.setIcon(make_icon('trash', ICON_SECONDARY, 14))
            del_btn.setIconSize(QSize(14, 14))
            # Use lambda to swallow the clicked(bool) signal arg so l stays bound
            add_btn.clicked.connect(lambda *_, l=lst: (
                lambda text, ok: l.addItem(text.strip()) if ok and text.strip() else None
            )(*QInputDialog.getText(self, 'Добавить', 'Новое значение:')))
            del_btn.clicked.connect(lambda *_, l=lst: (
                l.takeItem(l.currentRow()) if l.currentRow() >= 0 else None
            ))
            btn_row.addWidget(add_btn)
            btn_row.addWidget(del_btn)
            btn_row.addStretch()
            bl.addLayout(btn_row)
            layout.addWidget(box)

        save_btn = QPushButton('Сохранить все типы')
        save_btn.setIcon(make_icon('save', ICON_ON_ACCENT, 14))
        save_btn.setIconSize(QSize(14, 14))
        save_btn.clicked.connect(self._save_types)
        layout.addWidget(save_btn)
        layout.addStretch()

        scroll.setWidget(inner)
        outer.addWidget(scroll)
        return w

    def _load_types(self):
        for lst, cfg_key in [
            (self._equip_list, 'equipment_types'),
            (self._work_list,  'work_types'),
            (self._ctrl_list,  'controller_types'),
        ]:
            lst.clear()
            try:
                items = json.loads(self._mw.cfg.get(cfg_key))
            except Exception:
                items = []
            for item in items:
                lst.addItem(item)

    def _save_types(self):
        for lst, cfg_key in [
            (self._equip_list, 'equipment_types'),
            (self._work_list,  'work_types'),
            (self._ctrl_list,  'controller_types'),
        ]:
            items = [lst.item(i).text() for i in range(lst.count())]
            self._mw.cfg.set(cfg_key, json.dumps(items, ensure_ascii=False))
        self._mw.show_status('Типы сохранены')

    # ── Lifecycle ─────────────────────────────────────────────────────────────

    def showEvent(self, event):
        super().showEvent(event)
        self._load_general()
        self._load_rules()
        self._load_apps()
        self._load_hierarchy()

    # ── General load/save ─────────────────────────────────────────────────────

    def _load_general(self):
        self._root_path_input.setText(self._mw.cfg.root_path())
        self._keep_arch_cb.setChecked(self._mw.cfg.keep_archives())

        self._sync_interval_input.setText(str(self._mw.cfg.sync_interval_min()))
        self._second_disk_input.setText(self._mw.cfg.second_disk_path())

        role = self._mw.current_role()
        for i in range(self._role_combo.count()):
            if self._role_combo.itemData(i) == role:
                self._role_combo.setCurrentIndex(i)
                break

    def _browse_root(self):
        path = QFileDialog.getExistingDirectory(self, 'Папка прошивок', '')
        if path:
            self._root_path_input.setText(path)

    def _save_root_path(self):
        self._mw.cfg.set_root_path(self._root_path_input.text().strip())
        self._mw.show_status('Путь сохранён')

    def _save_passwords(self):
        self._mw.cfg.set('admin_password',      self._admin_pwd.text())
        self._mw.cfg.set('programmer_password',  self._prog_pwd.text())
        self._mw.show_status('Пароли сохранены')

    def _save_misc(self):
        self._mw.cfg.set('keep_archives', 'true' if self._keep_arch_cb.isChecked() else 'false')
        self._mw.show_status('Настройки сохранены')

    def _browse_second_disk(self):
        path = QFileDialog.getExistingDirectory(self, 'Второй диск (шкафы)', '')
        if path:
            self._second_disk_input.setText(path)

    def _save_second_disk_path(self):
        path = self._second_disk_input.text().strip()
        self._mw.cfg.set_second_disk_path(path)
        self._mw.second_disk_svc.invalidate_cache()
        self._mw.show_status('Путь второго диска сохранён')


    def _save_sync_interval(self):
        try:
            v = max(1, int(self._sync_interval_input.text().strip()))
        except ValueError:
            QMessageBox.warning(self, 'Ошибка', 'Введите целое число минут.')
            return
        self._mw.cfg.set('sync_interval_min', str(v))
        # Restart sync timer with new interval
        self._mw._sync_timer.setInterval(v * 60 * 1000)
        self._mw.show_status(f'Интервал синхронизации: {v} мин')

    def _export_config(self):
        import json as _json
        from datetime import datetime as _dt
        root = self._mw.cfg.root_path()
        if not root or not os.path.isdir(root):
            QMessageBox.warning(self, 'Экспорт', 'Сетевой диск недоступен.')
            return
        conf_dir = os.path.join(root, 'Конфиг')
        os.makedirs(conf_dir, exist_ok=True)
        rows = self._mw.db._conn.execute('SELECT key, value FROM settings').fetchall()
        settings = {r['key']: r['value'] for r in rows}
        data = {
            'exported_at': _dt.now().isoformat(timespec='seconds'),
            'settings': settings,
        }
        out_path = os.path.join(conf_dir, 'po_finder_config.json')
        with open(out_path, 'w', encoding='utf-8') as f:
            _json.dump(data, f, ensure_ascii=False, indent=2)
        QMessageBox.information(self, 'Экспорт', f'Конфиг сохранён:\n{out_path}')
        self._mw.show_status('Конфиг экспортирован')

    def _import_config(self):
        import json as _json
        root = self._mw.cfg.root_path()
        if not root or not os.path.isdir(root):
            QMessageBox.warning(self, 'Импорт', 'Сетевой диск недоступен.')
            return
        src = os.path.join(root, 'Конфиг', 'po_finder_config.json')
        if not os.path.isfile(src):
            QMessageBox.warning(self, 'Импорт', f'Файл конфига не найден:\n{src}')
            return
        with open(src, encoding='utf-8') as f:
            data = _json.load(f)
        settings = data.get('settings', {})
        skip_keys = {'admin_password', 'programmer_password'}
        count = 0
        for key, value in settings.items():
            if key not in skip_keys:
                self._mw.cfg.set(key, value)
                count += 1
        self._load_general()
        QMessageBox.information(self, 'Импорт',
            f'Применено настроек: {count}\n'
            f'Экспортировано: {data.get("exported_at", "?")}')
        self._mw.show_status(f'Конфиг импортирован: {count} настроек')

    def _switch_role(self):
        role = self._role_combo.currentData()
        pwd  = self._pwd_input.text()

        if role == 'administrator':
            expected = self._mw.cfg.admin_password()
            if pwd != expected:
                QMessageBox.warning(self, 'Доступ', 'Неверный пароль администратора.')
                return
        elif role == 'programmer':
            expected = self._mw.cfg.programmer_password()
            if expected and pwd != expected:
                QMessageBox.warning(self, 'Доступ', 'Неверный пароль программиста.')
                return

        self._mw.switch_role(role)
        self._pwd_input.clear()
        self._mw.show_status(f'Роль изменена: {self._role_combo.currentText()}')

    # ── Rules load/save ───────────────────────────────────────────────────────

    def _load_rules(self):
        rules = self._mw.db.get_all_rules()
        self._all_rules = rules
        self._populate_rules(rules)

    def _populate_rules(self, rules: list[Rule]):
        self._rules_table.setRowCount(len(rules))
        for row, r in enumerate(rules):
            self._rules_table.setItem(row, 0, QTableWidgetItem(r.name))
            self._rules_table.setItem(row, 1, QTableWidgetItem(r.equipment_type))
            self._rules_table.setItem(row, 2, QTableWidgetItem(r.controller))
            self._rules_table.setItem(row, 3, QTableWidgetItem(r.firmware_dir))
            self._rules_table.item(row, 0).setData(Qt.UserRole, r)
        self._rules_status.setText(f'Правил: {len(rules)}')

    def _filter_rules(self, text: str):
        text = text.lower()
        filtered = [r for r in self._all_rules if text in r.name.lower()] if text else self._all_rules
        self._populate_rules(filtered)

    def _selected_rule(self) -> Rule | None:
        row = self._rules_table.currentRow()
        if row < 0:
            return None
        item = self._rules_table.item(row, 0)
        return item.data(Qt.UserRole) if item else None

    def _add_rule(self):
        dlg = _RuleDialog(self, self._mw.cfg, db=self._mw.db)
        if dlg.exec() == QDialog.Accepted:
            rule = dlg.get_rule()
            self._mw.db.upsert_rule(rule)
            dlg.save_template_links(rule.name, self._mw.db)
            self._load_rules()

    def _edit_rule(self):
        rule = self._selected_rule()
        if not rule:
            QMessageBox.information(self, 'Изменить', 'Выберите правило.')
            return
        dlg = _RuleDialog(self, self._mw.cfg, rule=rule, db=self._mw.db)
        if dlg.exec() == QDialog.Accepted:
            updated = dlg.get_rule()
            self._mw.db.upsert_rule(updated)
            dlg.save_template_links(updated.name, self._mw.db)
            self._load_rules()

    def _copy_rule(self):
        rule = self._selected_rule()
        if not rule:
            QMessageBox.information(self, 'Копировать', 'Выберите правило.')
            return
        from dataclasses import replace as _dc
        # Generate unique name
        existing = {r.name for r in self._mw.db.get_all_rules()}
        base = f'{rule.name} (копия)'
        name, n = base, 2
        while name in existing:
            name = f'{base} {n}'
            n += 1
        new_rule = _dc(rule, id=None, name=name,
                       local_synced=False, disk_snapshot={})
        self._mw.db.upsert_rule(new_rule)
        self._load_rules()
        self._mw.show_status(f'Правило скопировано: {name}')

    def _delete_rule(self):
        rule = self._selected_rule()
        if not rule:
            QMessageBox.information(self, 'Удалить', 'Выберите правило.')
            return
        reply = QMessageBox.question(self, 'Удалить правило',
            f'Удалить правило «{rule.name}»?\n'
            'Загруженные версии останутся в базе.',
            QMessageBox.Yes | QMessageBox.No, QMessageBox.No)
        if reply == QMessageBox.Yes:
            self._mw.db.delete_rule(rule.id)
            self._load_rules()

    # ── Prefix load/save ──────────────────────────────────────────────────────

    def _load_prefixes(self):
        prefixes = self._mw.cfg.version_prefixes()
        self._prefix_table.setRowCount(len(prefixes))
        for row, (k, v) in enumerate(prefixes.items()):
            self._prefix_table.setItem(row, 0, QTableWidgetItem(k))
            self._prefix_table.setItem(row, 1, QTableWidgetItem(str(v)))

    def _add_prefix_row(self):
        row = self._prefix_table.rowCount()
        self._prefix_table.insertRow(row)

    def _del_prefix_row(self):
        row = self._prefix_table.currentRow()
        if row >= 0:
            self._prefix_table.removeRow(row)

    def _save_prefixes(self):
        data = {}
        for row in range(self._prefix_table.rowCount()):
            k_item = self._prefix_table.item(row, 0)
            v_item = self._prefix_table.item(row, 1)
            if k_item and v_item and k_item.text().strip():
                data[k_item.text().strip()] = v_item.text().strip()
        self._mw.cfg.set('version_prefixes', json.dumps(data, ensure_ascii=False))
        self._mw.show_status('Префиксы сохранены')

    # ── Quick apps load/save ──────────────────────────────────────────────────

    def _load_apps(self):
        apps = self._mw.cfg.quick_apps()
        self._apps_table.setRowCount(len(apps))
        for row, app in enumerate(apps):
            self._apps_table.setItem(row, 0, QTableWidgetItem(app.get('name', '')))
            self._apps_table.setItem(row, 1, QTableWidgetItem(app.get('path', '')))
            self._apps_table.setItem(row, 2, QTableWidgetItem(app.get('icon', '')))

    def _add_app_row(self):
        path, _ = QFileDialog.getOpenFileName(
            self, 'Выбрать приложение', '',
            'Исполняемые файлы (*.exe *.bat *.lnk);;Все файлы (*.*)'
        )
        if not path:
            return
        row = self._apps_table.rowCount()
        self._apps_table.insertRow(row)
        name = os.path.splitext(os.path.basename(path))[0]
        self._apps_table.setItem(row, 0, QTableWidgetItem(name))
        self._apps_table.setItem(row, 1, QTableWidgetItem(path))
        self._apps_table.setItem(row, 2, QTableWidgetItem(''))

    def _del_app_row(self):
        row = self._apps_table.currentRow()
        if row >= 0:
            self._apps_table.removeRow(row)

    def _save_apps(self):
        apps = []
        for row in range(self._apps_table.rowCount()):
            name = (self._apps_table.item(row, 0) or QTableWidgetItem('')).text()
            path = (self._apps_table.item(row, 1) or QTableWidgetItem('')).text()
            icon = (self._apps_table.item(row, 2) or QTableWidgetItem('')).text()
            if name or path:
                apps.append({'name': name, 'path': path, 'icon': icon})
        self._mw.cfg.set_quick_apps(apps)
        self._mw.reload_sidebar_apps()
        self._mw.show_status('Быстрые приложения сохранены')


# ──────────────────────────────────────────────────────────────────────────────
# Rule dialog
# ──────────────────────────────────────────────────────────────────────────────

class _RuleDialog(QDialog):
    """Create / edit a Rule."""

    def __init__(self, parent, cfg, rule: Rule | None = None, db=None):
        super().__init__(parent)
        self._cfg  = cfg
        self._rule = rule
        self._db   = db
        self.setWindowTitle('Правило' if rule is None else f'Правило: {rule.name}')
        self.setMinimumWidth(560)
        self.setMinimumHeight(620)
        self._build()

    def _build(self):
        layout = QVBoxLayout(self)

        # Scrollable form — viewport must also accept drops for PathDropEdit children
        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setFrameShape(QFrame.NoFrame)
        scroll.setAcceptDrops(True)
        scroll.viewport().setAcceptDrops(True)
        form_widget = QWidget()
        form = QFormLayout(form_widget)
        form.setSpacing(10)
        form.setLabelAlignment(Qt.AlignRight)

        r = self._rule  # shortcut

        self._name = QLineEdit(r.name if r else '')
        self._name.setPlaceholderText('Уникальное имя правила')
        form.addRow('Название *', self._name)

        self._eq_combo = QComboBox()
        self._eq_combo.setEditable(True)
        self._eq_combo.addItems(self._cfg.equipment_types())
        if r and r.equipment_type:
            self._eq_combo.setCurrentText(r.equipment_type)
        form.addRow('Тип оборудования', self._eq_combo)

        selected_wt = [w.strip() for w in r.work_type.split(',')] if r else []
        self._work_checks: dict[str, QCheckBox] = {}
        work_w = QWidget()
        work_hlay = QHBoxLayout(work_w)
        work_hlay.setContentsMargins(0, 0, 0, 0)
        work_hlay.setSpacing(16)
        for wt in self._cfg.work_types():
            cb = QCheckBox(wt)
            cb.setChecked(wt in selected_wt)
            work_hlay.addWidget(cb)
            self._work_checks[wt] = cb
        work_hlay.addStretch()
        form.addRow('Тип работы', work_w)

        self._ctrl_combo = QComboBox()
        self._ctrl_combo.setEditable(True)
        self._ctrl_combo.addItems(self._cfg.controller_types())
        if r and r.controller:
            self._ctrl_combo.setCurrentText(r.controller)
        form.addRow('Контроллер', self._ctrl_combo)

        self._fw_dir = QLineEdit(r.firmware_dir if r else '')
        self._fw_dir.setPlaceholderText('Папка на диске (от корня), напр. НГР/КПЧ/SMH5')
        fw_dir_row = QWidget()
        fw_dir_layout = QHBoxLayout(fw_dir_row)
        fw_dir_layout.setContentsMargins(0, 0, 0, 0)
        fw_dir_layout.setSpacing(4)
        fw_dir_layout.addWidget(self._fw_dir)
        _browse_fw = QPushButton('Обзор')
        _browse_fw.setObjectName('secondary')
        _browse_fw.setFixedHeight(30)
        _browse_fw.clicked.connect(self._browse_fw_dir)
        fw_dir_layout.addWidget(_browse_fw)
        form.addRow('Папка прошивки *', fw_dir_row)

        self._fw_type_combo = QComboBox()
        self._fw_type_combo.addItems(['plc', 'plc_hmi'])
        if r and r.firmware_type:
            self._fw_type_combo.setCurrentText(r.firmware_type)
        form.addRow('Тип прошивки', self._fw_type_combo)

        self._keywords = QLineEdit(', '.join(r.keywords) if r and r.keywords else '')
        self._keywords.setPlaceholderText('Ключевые слова через запятую')
        form.addRow('Ключевые слова', self._keywords)

        self._excl_kw = QLineEdit(', '.join(r.exclude_keywords) if r and r.exclude_keywords else '')
        self._excl_kw.setPlaceholderText('Исключить (через запятую)')
        form.addRow('Исключить слова', self._excl_kw)

        self._local_dir = QLineEdit(r.local_dir if r else '')
        self._local_dir.setPlaceholderText('Имя локальной папки (необязательно)')
        form.addRow('Локальная папка', self._local_dir)

        self._pch_list = QListWidget()
        self._pch_list.setSelectionMode(QAbstractItemView.MultiSelection)
        self._pch_list.setFixedHeight(80)
        self._upp_list = QListWidget()
        self._upp_list.setSelectionMode(QAbstractItemView.MultiSelection)
        self._upp_list.setFixedHeight(80)
        if self._db:
            rule_name = r.name if r else ''
            for t in self._db.get_all_templates():
                if t.template_type == 'pch':
                    item = QListWidgetItem(t.name)
                    item.setData(Qt.UserRole, t.id)
                    self._pch_list.addItem(item)
                    if rule_name and rule_name in t.rule_names:
                        item.setSelected(True)
                elif t.template_type == 'upp':
                    item = QListWidgetItem(t.name)
                    item.setData(Qt.UserRole, t.id)
                    self._upp_list.addItem(item)
                    if rule_name and rule_name in t.rule_names:
                        item.setSelected(True)
        form.addRow('Параметры ПЧ/КПЧ', self._pch_list)
        form.addRow('Параметры УПП', self._upp_list)

        self._io_map = MiniDropZone(r.io_map_path if r else '')
        form.addRow('Карта in/out', self._make_browse_row(
            self._io_map, file=True, folder=True))

        self._passport_dir = MiniDropZone(r.passport_dir if r else '')
        form.addRow('Паспорт (файл)', self._make_browse_row(
            self._passport_dir, file=True))

        self._instructions = MiniDropZone(r.instructions_path if r else '')
        form.addRow('Инструкции', self._make_browse_row(
            self._instructions, file=True, folder=True))

        self._notes_file = MiniDropZone(r.notes_file if r else '')
        form.addRow('Примечания (файл)', self._make_browse_row(
            self._notes_file, file=True))

        self._software_name = QLineEdit(r.software_name if r else '')
        self._software_name.setPlaceholderText('Название ПО для протокола')
        form.addRow('Название ПО', self._software_name)

        scroll.setWidget(form_widget)
        layout.addWidget(scroll)

        buttons = QDialogButtonBox(QDialogButtonBox.Ok | QDialogButtonBox.Cancel)
        buttons.accepted.connect(self._validate_and_accept)
        buttons.rejected.connect(self.reject)
        layout.addWidget(buttons)

    def _make_browse_row(self, line_edit: 'MiniDropZone',
                          file: bool = False, folder: bool = False) -> QWidget:
        """MiniDropZone слева (растягивается) + кнопки «×», «Файл»/«Папка» справа."""
        wrapper = QWidget()
        hlay = QHBoxLayout(wrapper)
        hlay.setContentsMargins(0, 0, 0, 0)
        hlay.setSpacing(6)
        hlay.addWidget(line_edit, 1)

        clr = QPushButton('× Удалить')
        clr.setObjectName('secondary')
        clr.setToolTip('Очистить путь — нажмите OK чтобы сохранить')
        clr.clicked.connect(lambda *_, le=line_edit: le.set_path(''))
        hlay.addWidget(clr)

        if file:
            btn = QPushButton('Файл')
            btn.setObjectName('secondary')
            btn.clicked.connect(lambda *_, le=line_edit: self._browse_file_into(le))
            hlay.addWidget(btn)
        if folder:
            btn = QPushButton('Папка')
            btn.setObjectName('secondary')
            btn.clicked.connect(lambda *_, le=line_edit: self._browse_folder_into(le))
            hlay.addWidget(btn)

        return wrapper

    def _browse_file_into(self, le: QLineEdit):
        path, _ = QFileDialog.getOpenFileName(self, 'Выберите файл', '', 'Все файлы (*.*)')
        if path:
            le.setText(path)

    def _browse_folder_into(self, le: QLineEdit):
        path = QFileDialog.getExistingDirectory(self, 'Выберите папку', '')
        if path:
            le.setText(path)

    def _rel_or_abs(self, path: str, root: str) -> str:
        """Used only for firmware_dir (relative to WebDAV root)."""
        if root:
            try:
                return os.path.relpath(path, root)
            except ValueError:
                pass
        return path

    def _browse_fw_dir(self):
        """Browse for firmware_dir — stored relative to root_path."""
        root = self._cfg.root_path()
        path = QFileDialog.getExistingDirectory(self, 'Выберите папку прошивки', root or '')
        if path:
            self._fw_dir.setText(self._rel_or_abs(path, root))

    def save_template_links(self, rule_name: str, db):
        """Update pch/upp template rule_names based on current list selection."""
        from dataclasses import replace as dc_replace
        selected_pch_ids = {
            self._pch_list.item(i).data(Qt.UserRole)
            for i in range(self._pch_list.count())
            if self._pch_list.item(i).isSelected()
        }
        selected_upp_ids = {
            self._upp_list.item(i).data(Qt.UserRole)
            for i in range(self._upp_list.count())
            if self._upp_list.item(i).isSelected()
        }
        for t in db.get_all_templates():
            if t.template_type not in ('pch', 'upp'):
                continue
            sel_ids = selected_pch_ids if t.template_type == 'pch' else selected_upp_ids
            names = list(t.rule_names)
            changed = False
            if t.id in sel_ids and rule_name not in names:
                names.append(rule_name)
                changed = True
            elif t.id not in sel_ids and rule_name in names:
                names.remove(rule_name)
                changed = True
            if changed:
                db.upsert_template(dc_replace(t, rule_names=names))

    def _validate_and_accept(self):
        if not self._name.text().strip():
            QMessageBox.warning(self, 'Ошибка', 'Укажите название правила.')
            return
        if not self._fw_dir.text().strip():
            QMessageBox.warning(self, 'Ошибка', 'Укажите папку прошивки.')
            return
        self.accept()

    def _split_kw(self, text: str) -> list[str]:
        return [w.strip() for w in text.split(',') if w.strip()]

    def get_rule(self) -> Rule:
        r = self._rule
        return Rule(
            id               = r.id if r else None,
            name             = self._name.text().strip(),
            equipment_type   = self._eq_combo.currentText().strip(),
            work_type        = ', '.join(
                wt for wt, cb in self._work_checks.items() if cb.isChecked()
            ),
            controller       = self._ctrl_combo.currentText().strip(),
            firmware_dir     = self._fw_dir.text().strip(),
            firmware_type    = self._fw_type_combo.currentText(),
            software_name    = self._software_name.text().strip(),
            keywords         = self._split_kw(self._keywords.text()),
            exclude_keywords = self._split_kw(self._excl_kw.text()),
            kw_mode          = 'any',
            local_dir        = self._local_dir.text().strip(),
            local_synced     = r.local_synced if r else False,
            disk_snapshot    = r.disk_snapshot if r else {},
            param_pch_dir    = '',
            param_upp_dir    = '',
            io_map_path      = self._io_map.text().strip(),
            passport_dir     = self._passport_dir.text().strip(),
            instructions_path = self._instructions.text().strip(),
            notes_file       = self._notes_file.text().strip(),
            created_at       = r.created_at if r else datetime.now(),
            updated_at       = datetime.now(),
        )
