"""
FirmwareFinder — Main Window
===============================
Sidebar navigation + stacked page area.
Wires together all services and pages.
"""

import os
from PySide6.QtWidgets import (
    QMainWindow, QWidget, QHBoxLayout, QVBoxLayout,
    QPushButton, QLabel, QStackedWidget, QStatusBar,
    QFrame, QSizePolicy,
    QDialog, QFormLayout, QDialogButtonBox, QComboBox, QLineEdit, QMessageBox,
)
from PySide6.QtCore import Qt, QTimer, Signal, QSize
from PySide6.QtGui import QIcon, QPixmap, QPainter
from PySide6.QtSvg import QSvgRenderer
from app.ui.icons import icon_for_theme

from app.infrastructure.database import Database
from app.services.config_service import ConfigService, DB_PATH
from app.services.search_service import SearchService
from app.services.upload_service import UploadService
from app.services.sync_service import SyncService
from app.services.hierarchy_service import HierarchyService
from app.services.second_disk_service import SecondDiskService
from app.ui.theme import apply_theme, get_palette

from app.ui.pages.search_page import SearchPage
from app.ui.pages.upload_page import UploadPage
from app.ui.pages.settings_page import SettingsPage
from app.ui.pages.params_page import ParamsPage


NAV_ITEMS = [
    ('search',   'Поиск',     'naladchik'),
    ('upload',   'Загрузка',  'programmer'),
    ('params',   'Параметры', 'programmer'),
    ('settings', 'Настройки', 'administrator'),
]

ROLE_ACCESS = {
    'naladchik':       {'search'},
    'naladchik_admin': {'search', 'settings'},
    'programmer':      {'upload', 'params'},
    'administrator':   {'search', 'upload', 'params', 'settings'},
}


class MainWindow(QMainWindow):
    theme_changed = Signal(str)

    def __init__(self):
        super().__init__()
        self.setWindowTitle('Antarus ПО Finder')
        self.setMinimumSize(1100, 720)
        self.resize(1280, 800)

        # ── Services ──────────────────────────────────────────────────────────
        self.db   = Database(DB_PATH)
        self.cfg  = ConfigService(self.db)
        self.search_svc    = SearchService(self.db)
        self.upload_svc    = UploadService(self.db, self.cfg)
        self.sync_svc      = SyncService(self.db, self.cfg)
        self.hierarchy_svc  = HierarchyService(self.db)
        self.second_disk_svc = SecondDiskService()

        self._role = self.cfg.current_role()
        self._theme_name = self.cfg.theme()

        # ── Central widget ────────────────────────────────────────────────────
        central = QWidget()
        self.setCentralWidget(central)
        root_layout = QHBoxLayout(central)
        root_layout.setContentsMargins(0, 0, 0, 0)
        root_layout.setSpacing(0)

        # ── Sidebar ───────────────────────────────────────────────────────────
        self._sidebar = self._build_sidebar()
        root_layout.addWidget(self._sidebar)

        # ── Page area ─────────────────────────────────────────────────────────
        self._stack = QStackedWidget()
        root_layout.addWidget(self._stack, 1)

        # ── Pages ─────────────────────────────────────────────────────────────
        self._pages: dict[str, QWidget] = {}
        self._add_page('search',    SearchPage(self))
        self._add_page('upload',    UploadPage(self))
        self._add_page('params',    ParamsPage(self))
        self._add_page('settings',  SettingsPage(self))

        # ── Status bar ────────────────────────────────────────────────────────
        self._status = QStatusBar()
        self.setStatusBar(self._status)
        self._disk_lbl = QLabel('Диск: …')
        self._status.addPermanentWidget(self._disk_lbl)

        # ── Apply theme + role ────────────────────────────────────────────────
        self._apply_theme(self._theme_name)
        self._apply_role(self._role)
        self._navigate('search')
        self.theme_changed.connect(self._update_sidebar_icons)
        self._update_sidebar_icons(self._theme_name)

        # ── Background sync ───────────────────────────────────────────────────
        QTimer.singleShot(1500, self._start_sync)
        self._sync_timer = QTimer(self)
        self._sync_timer.timeout.connect(self._start_sync)
        interval_ms = self.cfg.sync_interval_min() * 60 * 1000
        self._sync_timer.start(interval_ms)

        # ── Ensure hierarchy on startup ───────────────────────────────────────
        QTimer.singleShot(2000, self._ensure_hierarchy)
        QTimer.singleShot(0, self.reload_sidebar_apps)

    # ── Sidebar ───────────────────────────────────────────────────────────────

    def _build_sidebar(self) -> QWidget:
        sidebar = QWidget()
        sidebar.setObjectName('sidebar')
        sidebar.setFixedWidth(215)
        layout = QVBoxLayout(sidebar)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(0)

        # ── Логотип Antarus ───────────────────────────────────────────────────
        logo_row = QWidget()
        logo_row_lay = QHBoxLayout(logo_row)
        logo_row_lay.setContentsMargins(0, 16, 0, 0)
        logo_row_lay.setSpacing(8)
        logo_row_lay.setAlignment(Qt.AlignCenter)

        # SVG-логотип рендерим в QPixmap и показываем в QLabel
        logo_lbl = QLabel()
        logo_lbl.setFixedSize(36, 36)
        _logo_path = os.path.join(os.path.dirname(os.path.dirname(os.path.dirname(
            os.path.abspath(__file__)))), 'assets', 'logo.svg')
        if os.path.exists(_logo_path):
            renderer = QSvgRenderer(_logo_path)
            pix = QPixmap(36, 36)
            pix.fill(Qt.transparent)
            painter = QPainter(pix)
            renderer.render(painter)
            painter.end()
            logo_lbl.setPixmap(pix)
        logo_row_lay.addWidget(logo_lbl)

        title_lbl = QLabel('Antarus ПО Finder')
        title_lbl.setObjectName('title')
        title_lbl.setAlignment(Qt.AlignVCenter | Qt.AlignLeft)
        logo_row_lay.addWidget(title_lbl)

        layout.addWidget(logo_row)
        layout.addSpacing(4)

        # Role label
        self._role_lbl = QLabel()
        self._role_lbl.setObjectName('subtitle')
        self._role_lbl.setAlignment(Qt.AlignCenter)
        layout.addWidget(self._role_lbl)

        # Role switch button — always visible
        self._role_btn = QPushButton('Сменить роль')
        self._role_btn.setObjectName('secondary')
        self._role_btn.setContentsMargins(0, 0, 0, 0)
        self._role_btn.clicked.connect(self._show_role_switch)
        layout.addWidget(self._role_btn)

        sep = QFrame()
        sep.setFrameShape(QFrame.HLine)
        sep.setContentsMargins(16, 8, 16, 8)
        layout.addWidget(sep)

        # Nav buttons
        self._nav_btns: dict[str, QPushButton] = {}
        for page_id, label, _ in NAV_ITEMS:
            btn = QPushButton(label)
            btn.setObjectName('nav-btn')
            btn.setCheckable(False)
            btn.clicked.connect(lambda _, pid=page_id: self._navigate(pid))
            layout.addWidget(btn)
            self._nav_btns[page_id] = btn

        # Quick apps section
        qa_sep = QFrame()
        qa_sep.setFrameShape(QFrame.HLine)
        qa_sep.setContentsMargins(16, 4, 16, 4)
        layout.addWidget(qa_sep)

        self._qa_sidebar_widget = QWidget()
        self._qa_sidebar_layout = QVBoxLayout(self._qa_sidebar_widget)
        self._qa_sidebar_layout.setContentsMargins(8, 0, 8, 0)
        self._qa_sidebar_layout.setSpacing(4)
        layout.addWidget(self._qa_sidebar_widget)

        layout.addStretch()

        # Theme toggle
        self._theme_btn = QPushButton('Тёмная тема')
        self._theme_btn.setObjectName('secondary')
        self._theme_btn.clicked.connect(self._toggle_theme)
        layout.addWidget(self._theme_btn)
        layout.addSpacing(12)

        return sidebar

    # ── Navigation ────────────────────────────────────────────────────────────

    def _add_page(self, page_id: str, page: QWidget):
        self._pages[page_id] = page
        self._stack.addWidget(page)

    def _navigate(self, page_id: str):
        if page_id not in self._pages:
            return
        # Update active button style
        for pid, btn in self._nav_btns.items():
            btn.setProperty('active', pid == page_id)
            btn.style().unpolish(btn)
            btn.style().polish(btn)
        self._stack.setCurrentWidget(self._pages[page_id])
        self._current_page = page_id

    # ── Role management ───────────────────────────────────────────────────────

    def _apply_role(self, role: str):
        self._role = role
        role_names = {
            'naladchik':       'Наладчик',
            'naladchik_admin': 'Нал-Администратор',
            'programmer':      'Программист',
            'administrator':   'Администратор',
        }
        self._role_lbl.setText(role_names.get(role, role))
        allowed = ROLE_ACCESS.get(role, set())
        for page_id, btn in self._nav_btns.items():
            btn.setVisible(page_id in allowed)
        # Navigate away if current page is hidden
        if hasattr(self, '_current_page') and self._current_page not in allowed:
            self._navigate('search')

    def _show_role_switch(self):
        dlg = QDialog(self)
        dlg.setWindowTitle('Сменить роль')
        dlg.setMinimumWidth(320)

        form = QFormLayout()
        role_combo = QComboBox()
        role_combo.addItem('Наладчик',         'naladchik')
        role_combo.addItem('Нал-Администратор', 'naladchik_admin')
        role_combo.addItem('Программист',       'programmer')
        role_combo.addItem('Администратор',     'administrator')
        # Pre-select current role
        idx = role_combo.findData(self._role)
        if idx >= 0:
            role_combo.setCurrentIndex(idx)
        form.addRow('Роль:', role_combo)

        pwd_edit = QLineEdit()
        pwd_edit.setEchoMode(QLineEdit.Password)
        pwd_edit.setPlaceholderText('Пароль (если требуется)')
        form.addRow('Пароль:', pwd_edit)

        btn_box = QDialogButtonBox(QDialogButtonBox.Ok | QDialogButtonBox.Cancel)
        btn_box.rejected.connect(dlg.reject)

        main_lay = QVBoxLayout(dlg)
        main_lay.addLayout(form)
        main_lay.addWidget(btn_box)

        def _on_ok():
            role = role_combo.currentData()
            pwd  = pwd_edit.text()
            if role == 'administrator':
                expected = self.cfg.admin_password()
                if pwd != expected:
                    QMessageBox.warning(dlg, 'Ошибка', 'Неверный пароль администратора.')
                    return
            elif role == 'programmer':
                expected = self.cfg.programmer_password()
                if expected and pwd != expected:
                    QMessageBox.warning(dlg, 'Ошибка', 'Неверный пароль программиста.')
                    return
            elif role == 'naladchik_admin':
                expected = self.cfg.naladchik_admin_password()
                if expected and pwd != expected:
                    QMessageBox.warning(dlg, 'Ошибка', 'Неверный пароль нал-администратора.')
                    return
            # naladchik — no password required
            dlg.accept()
            self.switch_role(role)

        btn_box.accepted.connect(_on_ok)
        dlg.exec()

    def switch_role(self, role: str):
        self._role = role
        self.cfg.set_role(role)
        self._apply_role(role)

    def current_role(self) -> str:
        return self._role

    # ── Theme ─────────────────────────────────────────────────────────────────

    def _apply_theme(self, name: str):
        self._theme_name = name
        apply_theme(self.parent() or self, name)     # QApplication
        # Update theme button label
        if hasattr(self, '_theme_btn'):
            self._theme_btn.setText(
                'Светлая тема' if name == 'dark' else 'Тёмная тема'
            )
        self.theme_changed.emit(name)

    def _toggle_theme(self):
        new = 'dark' if self._theme_name == 'light' else 'light'
        self._apply_theme(new)
        self.cfg.set_theme(new)

    def _update_sidebar_icons(self, theme: str):
        """Refresh sidebar button icons to match the current theme."""
        _nav_icons = {
            'search':    'search',
            'upload':    'upload',
            'params':    'folder',
            'settings':  'settings',
        }
        for pid, btn in self._nav_btns.items():
            icon_name = _nav_icons.get(pid, '')
            if icon_name:
                btn.setIcon(icon_for_theme(icon_name, theme, 16))
                btn.setIconSize(QSize(16, 16))
        if hasattr(self, '_role_btn'):
            self._role_btn.setIcon(icon_for_theme('refresh', theme, 14))
            self._role_btn.setIconSize(QSize(14, 14))
        if hasattr(self, '_theme_btn'):
            icon_name = 'sun' if theme == 'dark' else 'moon'
            self._theme_btn.setIcon(icon_for_theme(icon_name, theme, 14))
            self._theme_btn.setIconSize(QSize(14, 14))

    def palette_colors(self) -> dict:
        return get_palette(self._theme_name)

    # ── Sync ──────────────────────────────────────────────────────────────────

    def _start_sync(self):
        status = self.sync_svc.disk_status()
        if status['available']:
            self._disk_lbl.setText(f"Диск: ✓  ({status['file_count']} файлов)")
        else:
            self._disk_lbl.setText('Диск: ✗ недоступен')

        self.sync_svc.run_background(
            on_done=self._on_sync_done,
            on_error=lambda e: self._status.showMessage(f'Синхронизация: ошибка — {e}', 5000),
        )

    def _ensure_hierarchy(self):
        root = self.cfg.root_path()
        if not root:
            return
        result = self.hierarchy_svc.ensure_structure(root)
        if result.get('created_count', 0) > 0:
            self.show_status(
                f'Структура диска создана: {result["created_count"]} папок', 6000)

    def _on_sync_done(self, updates: list[dict]):
        if updates:
            self._status.showMessage(
                f'⚠ Обновлений на диске: {len(updates)}', 10000
            )

    # ── Public helpers for pages ──────────────────────────────────────────────

    def reload_sidebar_apps(self):
        """Rebuild quick-app buttons in sidebar from config."""
        lay = self._qa_sidebar_layout
        while lay.count():
            item = lay.takeAt(0)
            if item.widget():
                item.widget().deleteLater()
        apps = self.cfg.quick_apps()
        for app in apps:
            name = app.get('name', '') or os.path.basename(app.get('path', ''))
            path = app.get('path', '')
            if not path:
                continue
            btn = QPushButton(name)
            btn.setObjectName('secondary')
            btn.clicked.connect(lambda _, p=path: self._launch_app(p))
            lay.addWidget(btn)
        self._qa_sidebar_widget.setVisible(bool(apps))

    def _launch_app(self, path: str):
        try:
            os.startfile(path)
        except Exception as e:
            from PySide6.QtWidgets import QMessageBox
            QMessageBox.warning(self, 'Запуск', f'Не удалось запустить:\n{e}')

    def show_status(self, msg: str, ms: int = 4000):
        self._status.showMessage(msg, ms)

    def navigate(self, page_id: str):
        self._navigate(page_id)

    def closeEvent(self, event):
        self.db.close()
        super().closeEvent(event)
