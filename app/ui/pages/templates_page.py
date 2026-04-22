"""
FirmwareFinder — Templates Page
===================================
Browse and manage shared parameter templates (UPP, PCH, IO maps, instructions).
"""

import os
from PySide6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QLabel, QPushButton,
    QTableWidget, QTableWidgetItem, QHeaderView, QComboBox,
    QMessageBox, QDialog, QFormLayout, QLineEdit, QTextEdit,
    QDialogButtonBox, QAbstractItemView, QFileDialog, QListWidget,
    QListWidgetItem,
)
from PySide6.QtCore import Qt, QSize
from app.ui.icons import make_icon, ICON_SECONDARY, ICON_ON_ACCENT

from app.domain.models import Template


_TYPE_LABELS = {
    'upp':          'УПП',
    'pch':          'ПЧ/КПЧ',
    'io_map':       'Карта in/out',
    'instructions': 'Инструкция',
}


class TemplatesPage(QWidget):
    def __init__(self, main_win):
        super().__init__()
        self._mw = main_win
        self._build()

    def _build(self):
        layout = QVBoxLayout(self)
        layout.setContentsMargins(24, 24, 24, 16)
        layout.setSpacing(16)

        # ── Title ─────────────────────────────────────────────────────────────
        title = QLabel('Шаблоны параметров')
        title.setObjectName('title')
        layout.addWidget(title)

        # ── Toolbar ───────────────────────────────────────────────────────────
        toolbar = QHBoxLayout()
        toolbar.setSpacing(8)

        self._type_filter = QComboBox()
        self._type_filter.addItem('Все типы', '')
        for key, label in _TYPE_LABELS.items():
            self._type_filter.addItem(label, key)
        self._type_filter.currentIndexChanged.connect(self._reload)
        toolbar.addWidget(self._type_filter)

        toolbar.addStretch()

        add_btn = QPushButton('Добавить')
        add_btn.setIcon(make_icon('plus', ICON_ON_ACCENT, 14))
        add_btn.setIconSize(QSize(14, 14))
        add_btn.clicked.connect(self._add_template)
        toolbar.addWidget(add_btn)

        edit_btn = QPushButton('Изменить')
        edit_btn.setObjectName('secondary')
        edit_btn.setIcon(make_icon('edit', ICON_SECONDARY, 14))
        edit_btn.setIconSize(QSize(14, 14))
        edit_btn.clicked.connect(self._edit_template)
        toolbar.addWidget(edit_btn)

        del_btn = QPushButton('Удалить')
        del_btn.setObjectName('danger')
        del_btn.setIcon(make_icon('trash', ICON_ON_ACCENT, 14))
        del_btn.setIconSize(QSize(14, 14))
        del_btn.clicked.connect(self._delete_template)
        toolbar.addWidget(del_btn)

        layout.addLayout(toolbar)

        # ── Table ─────────────────────────────────────────────────────────────
        self._table = QTableWidget()
        self._table.setColumnCount(4)
        self._table.setHorizontalHeaderLabels(['Название', 'Тип', 'Описание', 'Путь'])
        self._table.horizontalHeader().setSectionResizeMode(0, QHeaderView.ResizeToContents)
        self._table.horizontalHeader().setSectionResizeMode(1, QHeaderView.ResizeToContents)
        self._table.horizontalHeader().setSectionResizeMode(2, QHeaderView.Stretch)
        self._table.horizontalHeader().setSectionResizeMode(3, QHeaderView.ResizeToContents)
        self._table.setSelectionBehavior(QAbstractItemView.SelectRows)
        self._table.setSelectionMode(QAbstractItemView.SingleSelection)
        self._table.setEditTriggers(QAbstractItemView.NoEditTriggers)
        self._table.verticalHeader().hide()
        self._table.doubleClicked.connect(self._open_selected)
        layout.addWidget(self._table)

        # ── Bottom bar ────────────────────────────────────────────────────────
        bottom = QHBoxLayout()
        self._status_lbl = QLabel('')
        self._status_lbl.setObjectName('muted')
        bottom.addWidget(self._status_lbl)
        bottom.addStretch()

        open_btn = QPushButton('Открыть')
        open_btn.setObjectName('secondary')
        open_btn.setIcon(make_icon('open', ICON_SECONDARY, 14))
        open_btn.setIconSize(QSize(14, 14))
        open_btn.clicked.connect(self._open_selected)
        bottom.addWidget(open_btn)

        edit_content_btn = QPushButton('Редактировать текст')
        edit_content_btn.setObjectName('secondary')
        edit_content_btn.setIcon(make_icon('edit', ICON_SECONDARY, 14))
        edit_content_btn.setIconSize(QSize(14, 14))
        edit_content_btn.clicked.connect(self._edit_content)
        bottom.addWidget(edit_content_btn)

        layout.addLayout(bottom)

    # ── Lifecycle ─────────────────────────────────────────────────────────────

    def showEvent(self, event):
        super().showEvent(event)
        self._reload()

    # ── Data ──────────────────────────────────────────────────────────────────

    def _reload(self):
        type_filter = self._type_filter.currentData()
        templates = self._mw.db.get_all_templates()
        if type_filter:
            templates = [t for t in templates if t.template_type == type_filter]

        self._table.setRowCount(len(templates))
        for row, t in enumerate(templates):
            self._table.setItem(row, 0, QTableWidgetItem(t.name))
            self._table.setItem(row, 1, QTableWidgetItem(
                _TYPE_LABELS.get(t.template_type, t.template_type)
            ))
            self._table.setItem(row, 2, QTableWidgetItem(t.description))
            self._table.setItem(row, 3, QTableWidgetItem(t.path))
            # Store template in first cell's UserRole
            self._table.item(row, 0).setData(Qt.UserRole, t)

        self._status_lbl.setText(f'Шаблонов: {len(templates)}')

    def _selected_template(self) -> Template | None:
        row = self._table.currentRow()
        if row < 0:
            return None
        item = self._table.item(row, 0)
        return item.data(Qt.UserRole) if item else None

    # ── Actions ───────────────────────────────────────────────────────────────

    def _open_selected(self, *_):
        t = self._selected_template()
        if not t:
            return
        if t.path and os.path.exists(t.path):
            os.startfile(t.path)
        else:
            QMessageBox.information(self, 'Открыть', f'Путь не найден:\n{t.path}')

    def _add_template(self):
        rule_names = [r.name for r in self._mw.db.get_all_rules()]
        dlg = _TemplateDialog(self, rule_names=rule_names)
        if dlg.exec() == QDialog.Accepted:
            data = dlg.get_data()
            t = Template(
                id=None,
                name=data['name'],
                template_type=data['template_type'],
                path=data['path'],
                description=data['description'],
                rule_names=data['rule_names'],
            )
            self._mw.db.upsert_template(t)
            self._reload()

    def _edit_template(self):
        t = self._selected_template()
        if not t:
            QMessageBox.information(self, 'Изменить', 'Выберите шаблон.')
            return
        rule_names = [r.name for r in self._mw.db.get_all_rules()]
        dlg = _TemplateDialog(self, template=t, rule_names=rule_names)
        if dlg.exec() == QDialog.Accepted:
            data = dlg.get_data()
            updated = Template(
                id=t.id,
                name=data['name'],
                template_type=data['template_type'],
                path=data['path'],
                description=data['description'],
                rule_names=data['rule_names'],
            )
            self._mw.db.upsert_template(updated)
            self._reload()

    def _edit_content(self):
        """Open .txt / .md file in inline text editor."""
        t = self._selected_template()
        if not t:
            QMessageBox.information(self, 'Редактировать', 'Выберите шаблон.')
            return
        path = t.path
        if not path or not os.path.isfile(path):
            QMessageBox.information(self, 'Редактировать',
                'Файл не найден. Укажите корректный путь в шаблоне.')
            return
        ext = os.path.splitext(path)[1].lower()
        if ext not in ('.txt', '.md', '.ini', '.csv'):
            QMessageBox.information(self, 'Редактировать',
                'Встроенный редактор поддерживает только .txt / .md файлы.')
            return
        try:
            with open(path, 'r', encoding='utf-8') as f:
                content = f.read()
        except Exception as e:
            QMessageBox.critical(self, 'Ошибка', str(e))
            return

        dlg = QDialog(self)
        dlg.setWindowTitle(f'Редактор — {os.path.basename(path)}')
        dlg.setMinimumSize(680, 500)
        lay = QVBoxLayout(dlg)
        editor = QTextEdit()
        editor.setPlainText(content)
        editor.setFont(__import__('PySide6.QtGui', fromlist=['QFont']).QFont('Courier New', 10))
        lay.addWidget(editor)
        btns = QDialogButtonBox(QDialogButtonBox.Save | QDialogButtonBox.Cancel)
        btns.accepted.connect(dlg.accept)
        btns.rejected.connect(dlg.reject)
        lay.addWidget(btns)
        if dlg.exec() == QDialog.Accepted:
            try:
                with open(path, 'w', encoding='utf-8') as f:
                    f.write(editor.toPlainText())
                self._mw.show_status(f'Сохранено: {os.path.basename(path)}')
            except Exception as e:
                QMessageBox.critical(self, 'Ошибка сохранения', str(e))

    def _delete_template(self):
        t = self._selected_template()
        if not t:
            QMessageBox.information(self, 'Удалить', 'Выберите шаблон.')
            return
        reply = QMessageBox.question(self, 'Удалить шаблон',
            f'Удалить «{t.name}»?',
            QMessageBox.Yes | QMessageBox.No, QMessageBox.No)
        if reply == QMessageBox.Yes:
            self._mw.db.delete_template(t.id)
            self._reload()


class _TemplateDialog(QDialog):
    """Add / edit template dialog."""

    def __init__(self, parent, template: Template | None = None,
                 rule_names: list[str] | None = None):
        super().__init__(parent)
        self.setWindowTitle('Шаблон' if template is None else 'Изменить шаблон')
        self.setMinimumWidth(480)
        self._build(template, rule_names or [])

    def _build(self, t: Template | None, rule_names: list[str]):
        layout = QVBoxLayout(self)
        form = QFormLayout()
        form.setSpacing(10)

        self._name = QLineEdit(t.name if t else '')
        self._name.setPlaceholderText('Название шаблона')
        form.addRow('Название *', self._name)

        self._type_combo = QComboBox()
        for key, label in _TYPE_LABELS.items():
            self._type_combo.addItem(label, key)
        if t:
            idx = self._type_combo.findData(t.template_type)
            if idx >= 0:
                self._type_combo.setCurrentIndex(idx)
        form.addRow('Тип', self._type_combo)

        path_row = QHBoxLayout()
        self._path = QLineEdit(t.path if t else '')
        self._path.setPlaceholderText('Путь к файлу или папке')
        path_row.addWidget(self._path)
        browse_btn = QPushButton('…')
        browse_btn.setFixedWidth(36)
        browse_btn.setObjectName('secondary')
        browse_btn.clicked.connect(self._browse)
        path_row.addWidget(browse_btn)
        new_txt_btn = QPushButton('.txt')
        new_txt_btn.setObjectName('secondary')
        new_txt_btn.setFixedWidth(44)
        new_txt_btn.setToolTip('Создать новый .txt файл')
        new_txt_btn.clicked.connect(lambda: self._create_file('.txt'))
        path_row.addWidget(new_txt_btn)
        new_md_btn = QPushButton('.md')
        new_md_btn.setObjectName('secondary')
        new_md_btn.setFixedWidth(40)
        new_md_btn.setToolTip('Создать новый .md файл')
        new_md_btn.clicked.connect(lambda: self._create_file('.md'))
        path_row.addWidget(new_md_btn)
        form.addRow('Путь *', path_row)

        self._desc = QTextEdit(t.description if t else '')
        self._desc.setFixedHeight(60)
        self._desc.setPlaceholderText('Краткое описание')
        form.addRow('Описание', self._desc)

        # Rule binding list
        self._rules_list = QListWidget()
        self._rules_list.setSelectionMode(QAbstractItemView.MultiSelection)
        self._rules_list.setFixedHeight(120)
        selected_names = set(t.rule_names) if t else set()
        for rn in rule_names:
            item = QListWidgetItem(rn)
            self._rules_list.addItem(item)
            if rn in selected_names:
                item.setSelected(True)
        form.addRow('Правила (шкафы)', self._rules_list)

        layout.addLayout(form)

        buttons = QDialogButtonBox(
            QDialogButtonBox.Ok | QDialogButtonBox.Cancel
        )
        buttons.accepted.connect(self._validate_and_accept)
        buttons.rejected.connect(self.reject)
        layout.addWidget(buttons)

    def _browse(self):
        path, _ = QFileDialog.getOpenFileName(self, 'Выбрать файл', '')
        if not path:
            path = QFileDialog.getExistingDirectory(self, 'Выбрать папку', '')
        if path:
            self._path.setText(path)

    def _create_file(self, ext: str):
        """Create a new text file with inline editor, then fill path field."""
        save_path, _ = QFileDialog.getSaveFileName(
            self, f'Создать {ext} файл', '', f'Текстовый файл (*{ext})')
        if not save_path:
            return
        if not save_path.endswith(ext):
            save_path += ext

        dlg = QDialog(self)
        dlg.setWindowTitle(f'Новый файл — {os.path.basename(save_path)}')
        dlg.setMinimumSize(680, 500)
        lay = QVBoxLayout(dlg)
        hint = QLabel('Введите содержимое файла:')
        hint.setObjectName('muted')
        lay.addWidget(hint)
        editor = QTextEdit()
        if ext == '.md':
            editor.setPlaceholderText(
                '# Параметры УПП\n\n## Общие\n- Параметр 1: значение\n- Параметр 2: значение\n')
        editor.setFont(__import__('PySide6.QtGui', fromlist=['QFont']).QFont('Courier New', 10))
        lay.addWidget(editor)
        btns = QDialogButtonBox(QDialogButtonBox.Save | QDialogButtonBox.Cancel)
        btns.accepted.connect(dlg.accept)
        btns.rejected.connect(dlg.reject)
        lay.addWidget(btns)

        if dlg.exec() == QDialog.Accepted:
            try:
                with open(save_path, 'w', encoding='utf-8') as f:
                    f.write(editor.toPlainText())
                self._path.setText(save_path)
            except Exception as e:
                QMessageBox.critical(self, 'Ошибка', str(e))

    def _validate_and_accept(self):
        if not self._name.text().strip():
            QMessageBox.warning(self, 'Ошибка', 'Укажите название.')
            return
        if not self._path.text().strip():
            QMessageBox.warning(self, 'Ошибка', 'Укажите путь.')
            return
        self.accept()

    def get_data(self) -> dict:
        return {
            'name':          self._name.text().strip(),
            'template_type': self._type_combo.currentData(),
            'path':          self._path.text().strip(),
            'description':   self._desc.toPlainText().strip(),
            'rule_names':    [
                self._rules_list.item(i).text()
                for i in range(self._rules_list.count())
                if self._rules_list.item(i).isSelected()
            ],
        }
