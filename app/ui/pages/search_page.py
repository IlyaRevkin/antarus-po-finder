"""
FirmwareFinder — Search Page
================================
Search bar + quick apps bar + scrollable firmware cards.
"""

import os
import socket
import threading
from PySide6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QLineEdit,
    QPushButton, QLabel, QScrollArea, QFrame, QSizePolicy,
    QMessageBox, QApplication, QFileDialog, QCompleter,
)
from PySide6.QtCore import Qt, QTimer, QSize, QStringListModel
from app.ui.icons import make_icon, ICON_SECONDARY, ICON_ON_ACCENT

from app.domain.models import SearchResult
from app.ui.widgets.firmware_card import FirmwareCard


class SearchPage(QWidget):
    def __init__(self, main_win):
        super().__init__()
        self._mw = main_win
        self._cards: list[FirmwareCard] = []
        self._build()

    def _build(self):
        layout = QVBoxLayout(self)
        layout.setContentsMargins(24, 24, 24, 16)
        layout.setSpacing(16)

        # ── Title ─────────────────────────────────────────────────────────────
        title = QLabel('Поиск прошивок')
        title.setObjectName('title')
        layout.addWidget(title)

        # ── Protocol / inspection toolbar ─────────────────────────────────────
        proto_row = QHBoxLayout()
        proto_row.setSpacing(6)

        proto_lbl = QLabel('Папка осмотра:')
        proto_lbl.setSizePolicy(QSizePolicy.Fixed, QSizePolicy.Fixed)
        proto_row.addWidget(proto_lbl)

        open_proto_btn = QPushButton('Открыть')
        open_proto_btn.setObjectName('secondary')
        open_proto_btn.setIcon(make_icon('open', ICON_SECONDARY, 14))
        open_proto_btn.setIconSize(QSize(14, 14))
        open_proto_btn.clicked.connect(self._open_protocol_folder)
        proto_row.addWidget(open_proto_btn)

        self._pick_proto_btn = QPushButton('Выбрать...')
        self._pick_proto_btn.setObjectName('secondary')
        self._pick_proto_btn.clicked.connect(self._pick_protocol_folder)
        proto_row.addWidget(self._pick_proto_btn)

        clear_proto_btn = QPushButton('Очистить папку')
        clear_proto_btn.setObjectName('secondary')
        clear_proto_btn.clicked.connect(self._clear_protocol_folder)
        proto_row.addWidget(clear_proto_btn)

        scan_btn = QPushButton('Сканировать')
        scan_btn.setObjectName('secondary')
        scan_btn.setIcon(make_icon('scan', ICON_SECONDARY, 14))
        scan_btn.setIconSize(QSize(14, 14))
        scan_btn.clicked.connect(self._scan_document)
        proto_row.addWidget(scan_btn)

        photo_btn = QPushButton('Фото')
        photo_btn.setObjectName('secondary')
        photo_btn.setIcon(make_icon('camera', ICON_SECONDARY, 14))
        photo_btn.setIconSize(QSize(14, 14))
        photo_btn.clicked.connect(self._open_photo_upload_global)
        proto_row.addWidget(photo_btn)

        params_hier_btn = QPushButton('Параметры')
        params_hier_btn.setObjectName('secondary')
        params_hier_btn.clicked.connect(self._show_params_hierarchy_dialog)
        proto_row.addWidget(params_hier_btn)

        proto_row.addStretch()
        layout.addLayout(proto_row)

        # ── Search bar ────────────────────────────────────────────────────────
        search_row = QHBoxLayout()
        self._search_input = QLineEdit()
        self._search_input.setPlaceholderText(
            'Введите название шкафа — напр. «НГР КПЧ SMH5» или «ПЖ KINCO»'
        )
        self._search_input.setFixedHeight(38)
        self._search_input.returnPressed.connect(self._do_search)
        self._search_input.textChanged.connect(self._on_query_changed)
        search_row.addWidget(self._search_input, 1)

        search_btn = QPushButton('Найти')
        search_btn.setMinimumWidth(100)
        search_btn.setIcon(make_icon('search', ICON_ON_ACCENT, 15))
        search_btn.setIconSize(QSize(15, 15))
        search_btn.clicked.connect(self._do_search)
        search_row.addWidget(search_btn)

        self._schema_btn = QPushButton('Схема')
        self._schema_btn.setObjectName('secondary')
        self._schema_btn.setFixedHeight(38)
        self._schema_btn.setVisible(False)
        self._schema_btn.clicked.connect(self._open_or_print_schematic)
        search_row.addWidget(self._schema_btn)

        layout.addLayout(search_row)

        # ── Cabinet autocomplete (second disk) ────────────────────────────────
        self._completer_model = QStringListModel()
        self._completer = QCompleter(self._completer_model, self)
        self._completer.setCaseSensitivity(Qt.CaseInsensitive)
        self._completer.setFilterMode(Qt.MatchContains)
        self._search_input.setCompleter(self._completer)

        # ── Status label ──────────────────────────────────────────────────────
        self._status_lbl = QLabel('')
        self._status_lbl.setObjectName('subtitle')
        layout.addWidget(self._status_lbl)

        # ── Results scroll area ───────────────────────────────────────────────
        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setFrameShape(QFrame.NoFrame)
        scroll.setHorizontalScrollBarPolicy(Qt.ScrollBarAlwaysOff)

        self._results_container = QWidget()
        self._results_layout    = QVBoxLayout(self._results_container)
        self._results_layout.setContentsMargins(0, 0, 8, 0)
        self._results_layout.setSpacing(10)
        self._results_layout.addStretch()

        scroll.setWidget(self._results_container)
        layout.addWidget(scroll, 1)

        # ── Empty state ───────────────────────────────────────────────────────
        self._empty_lbl = QLabel(
            'Начните вводить название шкафа для поиска прошивки'
        )
        self._empty_lbl.setObjectName('muted')
        self._empty_lbl.setAlignment(Qt.AlignCenter)
        self._results_layout.insertWidget(0, self._empty_lbl)

    # ── Quick apps ────────────────────────────────────────────────────────────

    # ── showEvent ─────────────────────────────────────────────────────────────

    def showEvent(self, event):
        super().showEvent(event)
        self._refresh_completer()
        self._pick_proto_btn.setVisible(not bool(self._mw.cfg.protocol_folder()))

    def _refresh_completer(self):
        disk = self._mw.cfg.second_disk_path()
        names = self._mw.second_disk_svc.cabinet_names(disk) if disk else []
        self._completer_model.setStringList(names)

    def _on_query_changed(self, text: str):
        disk = self._mw.cfg.second_disk_path()
        if not disk or not text.strip():
            self._schema_btn.setVisible(False)
            return
        path = self._mw.second_disk_svc.find_schematic(disk, text.strip())
        self._schema_btn.setVisible(bool(path))

    def _open_or_print_schematic(self):
        from PySide6.QtWidgets import QMenu
        disk = self._mw.cfg.second_disk_path()
        query = self._search_input.text().strip()
        if not disk or not query:
            return
        path = self._mw.second_disk_svc.find_schematic(disk, query)
        if not path:
            QMessageBox.information(self, 'Схема', 'Схема не найдена для этого шкафа.')
            return
        menu = QMenu(self)
        open_act  = menu.addAction('Открыть схему')
        print_act = menu.addAction('Печать схемы')
        chosen = menu.exec(self._schema_btn.mapToGlobal(self._schema_btn.rect().bottomLeft()))
        if chosen == open_act:
            self._mw.second_disk_svc.open_schematic(path)
        elif chosen == print_act:
            self._mw.second_disk_svc.print_schematic(path)

    # ── Protocol folder helpers ───────────────────────────────────────────────

    def _open_protocol_folder(self):
        path = self._mw.cfg.protocol_folder()
        if path and os.path.isdir(path):
            os.startfile(path)
        else:
            new_path = QFileDialog.getExistingDirectory(self, 'Выберите папку протокола')
            if new_path:
                self._mw.cfg.set_inspection_folder( new_path)
                os.startfile(new_path)

    def _pick_protocol_folder(self):
        path = QFileDialog.getExistingDirectory(self, 'Выберите папку протокола')
        if path:
            self._mw.cfg.set_inspection_folder(path)
            self._pick_proto_btn.setVisible(False)
            self._mw.show_status(f'Папка протокола: {path}')

    def _scan_document(self):
        """Acquire scan: try WIA COM first, fall back to Windows Scan app."""
        import datetime, shutil

        proto = self._mw.cfg.protocol_folder()
        if not proto:
            proto = QFileDialog.getExistingDirectory(self, 'Выберите папку для сканов')
            if not proto:
                return
            self._mw.cfg.set_inspection_folder( proto)
        os.makedirs(proto, exist_ok=True)

        # ── Try classic WIA COM (works when WIA driver is installed) ──────────
        try:
            import win32com.client
            mgr = win32com.client.Dispatch('WIA.DeviceManager')
            if mgr.DeviceInfos.Count > 0:
                wia = win32com.client.Dispatch('WIA.CommonDialog')
                image = wia.ShowAcquireImage(
                    1, 1, 0,
                    '{19E4A5AA-5662-4FC5-A0C0-1758028E1057}',
                    False, True, False,
                )
                if image is None:
                    return
                ts = datetime.datetime.now().strftime('%Y%m%d_%H%M%S')
                save_path = os.path.join(proto, f'scan_{ts}.jpg')
                image.SaveFile(save_path)
                self._mw.show_status(f'Скан сохранён: {os.path.basename(save_path)}')
                os.startfile(save_path)
                return
        except Exception:
            pass  # WIA not available or no devices — use fallback

        # ── Fallback: Windows Scan app ────────────────────────────────────────
        self._scan_via_windows_scan(proto)

    def _scan_via_windows_scan(self, proto: str):
        """Launch Windows Scan app, wait for user, import new file to proto folder."""
        import subprocess, shutil, datetime
        from PySide6.QtWidgets import (
            QDialog, QVBoxLayout, QLabel, QPushButton, QDialogButtonBox,
        )
        from PySide6.QtCore import Qt

        # Typical default output dirs for Windows Scan on RU/EN Windows
        home = os.path.expanduser('~')
        scan_candidates = [
            os.path.join(home, 'Documents', 'Scanned Documents'),
            os.path.join(home, 'Документы', 'Отсканированные документы'),
            os.path.join(home, 'OneDrive', 'Documents', 'Scanned Documents'),
            os.path.join(home, 'OneDrive', 'Документы', 'Отсканированные документы'),
            os.path.join(home, 'Pictures'),
            os.path.join(home, 'Изображения'),
        ]

        # Snapshot existing files before user scans
        def _snapshot():
            snaps = {}
            for d in scan_candidates:
                if os.path.isdir(d):
                    for f in os.listdir(d):
                        fp = os.path.join(d, f)
                        if os.path.isfile(fp):
                            snaps[fp] = os.path.getmtime(fp)
            return snaps

        before = _snapshot()

        # Launch Windows Scan
        launched = False
        aumid = r'shell:AppsFolder\Microsoft.WindowsScan_8wekyb3d8bbwe!App'
        try:
            subprocess.Popen(['explorer.exe', aumid])
            launched = True
        except Exception:
            pass

        if not launched:
            QMessageBox.warning(self, 'Сканирование',
                'Не удалось запустить приложение Windows Scan.\n'
                'Откройте сканер вручную, выполните скан и выберите файл.')

        # Show instruction dialog
        dlg = QDialog(self)
        dlg.setWindowTitle('Сканирование')
        dlg.setMinimumWidth(420)
        lay = QVBoxLayout(dlg)

        hint_lbl = QLabel(
            ('Windows Scan запущен.\n\n' if launched else '') +
            '1. Выполните сканирование\n'
            '2. Сохраните скан (приложение само выберет папку)\n'
            '3. Нажмите «Готово» — файл будет скопирован\n'
            f'\n→ Папка назначения:\n   {proto}'
        )
        hint_lbl.setWordWrap(True)
        lay.addWidget(hint_lbl)

        open_proto_btn = QPushButton('Открыть папку назначения')
        open_proto_btn.setObjectName('secondary')
        open_proto_btn.clicked.connect(lambda: os.startfile(proto))
        lay.addWidget(open_proto_btn)

        btns = QDialogButtonBox(QDialogButtonBox.Ok | QDialogButtonBox.Cancel)
        btns.button(QDialogButtonBox.Ok).setText('Готово — импортировать')
        btns.accepted.connect(dlg.accept)
        btns.rejected.connect(dlg.reject)
        lay.addWidget(btns)

        if dlg.exec() != QDialog.Accepted:
            return

        # Find new files
        after = _snapshot()
        new_files = [
            fp for fp, mtime in after.items()
            if fp not in before and os.path.isfile(fp)
        ]

        # If nothing detected, let user browse
        if not new_files:
            start_dir = next((d for d in scan_candidates if os.path.isdir(d)), home)
            path, _ = QFileDialog.getOpenFileName(
                self, 'Выбрать отсканированный файл', start_dir,
                'Изображения (*.jpg *.jpeg *.png *.tif *.tiff *.bmp *.pdf)',
            )
            if path:
                new_files = [path]

        if not new_files:
            return

        # Copy to proto folder
        copied = []
        for src in new_files:
            ext  = os.path.splitext(src)[1]
            ts   = datetime.datetime.now().strftime('%Y%m%d_%H%M%S')
            name = f'scan_{ts}{ext}'
            dst  = os.path.join(proto, name)
            try:
                shutil.copy2(src, dst)
                copied.append(dst)
            except Exception:
                pass

        if copied:
            self._mw.show_status(f'Скан сохранён: {os.path.basename(copied[0])}')
            os.startfile(copied[0])

    # ── Search ────────────────────────────────────────────────────────────────

    def _do_search(self):
        query = self._search_input.text().strip()
        if not query:
            return
        self._status_lbl.setText('Поиск…')
        self._clear_cards()

        results = self._mw.search_svc.search(query)

        # Also search new hierarchy (fw_versions); skip duplicates by rule name
        hierarchy = self._mw.search_svc.search_hierarchy(query)
        existing  = {r.rule.name for r in results}
        for hr in hierarchy:
            if hr.rule.name not in existing:
                results.append(hr)

        if not results:
            self._status_lbl.setText(f'По запросу «{query}» ничего не найдено')
            self._empty_lbl.setText('Правило не найдено — добавьте его во вкладке Настройки')
            self._empty_lbl.show()
            return

        self._empty_lbl.hide()
        self._status_lbl.setText(f'Найдено: {len(results)}')

        for res in results:
            sub_id = getattr(res.rule, '_subtype_id', None)
            if sub_id is not None:
                has_params = bool(self._mw.db.get_param_files(subtype_id=sub_id))
            else:
                all_tpl = self._mw.db.get_all_templates()
                has_params = any(res.rule.name in t.rule_names for t in all_tpl)
            card = FirmwareCard(
                res,
                has_local=self._has_local(res.rule),
                has_any_local=self._has_any_local(res.rule),
                has_params=has_params,
            )
            card.open_requested.connect(self._open_fw)
            card.open_plc_requested.connect(self._open_plc)
            card.open_hmi_requested.connect(self._open_hmi)
            card.download_requested.connect(self._download_fw)
            card.map_requested.connect(self._open_map)
            card.params_requested.connect(self._open_params)
            card.copy_name_requested.connect(self._copy_name)
            card.passport_requested.connect(self._open_passport)
            card.instructions_requested.connect(self._open_instructions)
            card.history_requested.connect(self._show_history)
            # Insert before the stretch
            idx = self._results_layout.count() - 1
            self._results_layout.insertWidget(idx, card)
            self._cards.append(card)

    def _clear_cards(self):
        for card in self._cards:
            self._results_layout.removeWidget(card)
            card.deleteLater()
        self._cards.clear()
        self._empty_lbl.setText('Начните вводить название шкафа для поиска прошивки')
        self._empty_lbl.show()

    # ── Card actions ──────────────────────────────────────────────────────────

    def _open_fw(self, result: SearchResult):
        """Open firmware file from LOCAL_FW cache only (never from WebDAV)."""
        import re
        from app.services.config_service import LOCAL_FW
        rule = result.rule
        ver  = result.latest_version
        local_dir = rule.local_dir or re.sub(r'[^\w\-]', '_', rule.name)

        # 1. Latest version folder in LOCAL_FW
        if ver:
            ver_dir = os.path.join(LOCAL_FW, local_dir, str(ver.version))
            if os.path.isdir(ver_dir):
                fw = self._find_fw_file(ver_dir)
                os.startfile(fw or ver_dir)
                return

        # 2. Any version in LOCAL_FW — pick newest subfolder
        local_root = os.path.join(LOCAL_FW, local_dir)
        if os.path.isdir(local_root):
            subdirs = sorted(
                (d for d in os.listdir(local_root)
                 if os.path.isdir(os.path.join(local_root, d))),
                reverse=True,
            )
            for sd in subdirs:
                fw = self._find_fw_file(os.path.join(local_root, sd))
                if fw:
                    os.startfile(fw)
                    return

        # 3. Hierarchy result: firmware_dir is the absolute disk_path folder
        fw_dir = self._resolve_rule_path(rule.firmware_dir)
        if fw_dir and os.path.isdir(fw_dir):
            fw = self._find_fw_file(fw_dir)
            os.startfile(fw or fw_dir)
            return

        QMessageBox.information(self, 'Открыть',
            'Прошивка не найдена локально.\nНажмите «Скачать» для копирования с сервера.')

    @staticmethod
    def _find_fw_file(folder: str) -> str | None:
        """Return path to the main firmware file in a folder (skip .md/.txt)."""
        try:
            files = [
                os.path.join(folder, f) for f in os.listdir(folder)
                if os.path.isfile(os.path.join(folder, f))
                and not f.lower().endswith(('.md', '.txt', '.log'))
            ]
            return files[0] if files else None
        except Exception:
            return None

    def _download_fw(self, result: SearchResult):
        from app.infrastructure.filesystem import copy_tree
        from app.services.config_service import LOCAL_FW, LOCAL_TEMPLATES
        from app.domain.models import Rule as _RuleClass
        from dataclasses import replace as _dc
        import re
        import shutil as _shutil
        rule = result.rule
        ver  = result.latest_version
        root = self._mw.cfg.root_path()
        if not root or not rule.firmware_dir:
            QMessageBox.warning(self, 'Ошибка', 'Путь к диску или папка прошивки не заданы.')
            return
        src = os.path.join(root, rule.firmware_dir)
        # firmware_dir for hierarchy rules is already absolute — use as-is if exists
        if not os.path.isdir(src) and os.path.isabs(rule.firmware_dir):
            src = rule.firmware_dir
        if not os.path.isdir(src):
            QMessageBox.warning(self, 'Ошибка', f'Папка не найдена на диске:\n{src}')
            return
        local_dir = rule.local_dir or re.sub(r'[^\w\-]', '_', rule.name)
        dst = os.path.join(LOCAL_FW, local_dir)
        try:
            copy_tree(src, dst)
            # Mark rule as locally synced (only for legacy Rule dataclass)
            if not rule.local_synced and isinstance(rule, _RuleClass):
                self._mw.db.upsert_rule(_dc(rule, local_synced=True))
            # Copy io_map and instructions to LOCAL_TEMPLATES for offline use
            os.makedirs(LOCAL_TEMPLATES, exist_ok=True)
            for asset_path in [
                getattr(rule, 'io_map_path', ''),
                getattr(rule, 'instructions_path', ''),
            ]:
                if not asset_path:
                    continue
                ap = asset_path
                if not os.path.exists(ap):
                    ap = os.path.join(root, asset_path)
                if not os.path.exists(ap):
                    continue
                if os.path.isfile(ap):
                    _shutil.copy2(ap, os.path.join(LOCAL_TEMPLATES, os.path.basename(ap)))
                elif os.path.isdir(ap):
                    for entry in os.scandir(ap):
                        if entry.is_file():
                            _shutil.copy2(entry.path,
                                          os.path.join(LOCAL_TEMPLATES, entry.name))
            self._mw.show_status(f'Скопировано: {rule.name}')
            # Open the latest version immediately
            if ver:
                ver_dir = os.path.join(dst, str(ver.version))
                fw = self._find_fw_file(ver_dir) if os.path.isdir(ver_dir) else None
                if fw:
                    os.startfile(fw)
                    return
            os.startfile(dst)
        except Exception as e:
            QMessageBox.critical(self, 'Ошибка', str(e))

    def _resolve_rule_path(self, path: str) -> str:
        """Resolve a rule asset path: try absolute, then root-relative, then local cache."""
        if not path:
            return ''
        # Absolute and exists — normalize to remove any '..' segments before calling os.startfile
        if os.path.isabs(path):
            norm = os.path.normpath(path)
            if os.path.exists(norm):
                return norm
        # Relative — try against root_path (WebDAV share); normalize the join result
        root = self._mw.cfg.root_path()
        if root:
            candidate = os.path.normpath(os.path.join(root, path))
            if os.path.exists(candidate):
                return candidate
        # Maybe stored as absolute but network is down — check local templates cache
        from app.services.config_service import LOCAL_TEMPLATES
        # Try to find a cached copy matching the basename
        basename = os.path.basename(path)
        if basename:
            for fname in os.listdir(LOCAL_TEMPLATES) if os.path.isdir(LOCAL_TEMPLATES) else []:
                if fname == basename or os.path.splitext(fname)[0] == os.path.splitext(basename)[0]:
                    cached = os.path.join(LOCAL_TEMPLATES, fname)
                    if os.path.exists(cached):
                        return cached
        # Last resort: as-is normalized (might work if CWD is root)
        norm = os.path.normpath(path)
        if os.path.exists(norm):
            return norm
        return ''

    def _open_map(self, result: SearchResult):
        path = self._resolve_rule_path(result.rule.io_map_path)
        if not path:
            QMessageBox.information(self, 'Карта in/out',
                f'Файл карты не найден.\nПуть: {result.rule.io_map_path}')
            return
        try:
            os.startfile(path)
        except OSError:
            folder = path if os.path.isdir(path) else os.path.dirname(path)
            msg = QMessageBox(self)
            msg.setWindowTitle('Карта in/out')
            msg.setText(
                f'Не удалось открыть файл:\n{path}\n\n'
                f'Возможно, не установлена программа для этого типа файлов.'
            )
            msg.setInformativeText('Открыть папку с файлом?')
            msg.setStandardButtons(QMessageBox.Yes | QMessageBox.No)
            msg.setDefaultButton(QMessageBox.Yes)
            if msg.exec() == QMessageBox.Yes:
                try:
                    os.startfile(folder)
                except OSError:
                    pass

    @staticmethod
    def _template_best_path(t) -> str:
        """Return local cached path if it exists, otherwise original path."""
        import re
        from app.services.config_service import LOCAL_TEMPLATES
        safe = re.sub(r'[^\w\-]', '_', t.name)
        if os.path.isfile(t.path):
            ext = os.path.splitext(t.path)[1]
            local = os.path.join(LOCAL_TEMPLATES, safe + ext)
        else:
            local = os.path.join(LOCAL_TEMPLATES, safe)
        if os.path.exists(local):
            return local
        return t.path

    def _open_params(self, result: SearchResult):
        from PySide6.QtWidgets import (
            QDialog, QVBoxLayout, QHBoxLayout, QListWidget, QListWidgetItem,
            QPushButton, QDialogButtonBox, QTabWidget, QWidget,
        )
        from PySide6.QtCore import Qt
        import shutil
        rule = result.rule
        sub_id = getattr(rule, '_subtype_id', None)

        if sub_id is not None:
            # ── Hierarchy result: use param_files ─────────────────────────────
            param_files = self._mw.db.get_param_files(subtype_id=sub_id)
            if not param_files:
                QMessageBox.information(self, 'Параметры',
                    'Параметры для этого типа шкафа не найдены.\n'
                    'Загрузите параметры в разделе «Параметры».')
                return

            dlg = QDialog(self)
            dlg.setWindowTitle(f'Параметры — {rule.name}')
            dlg.setMinimumSize(500, 380)
            lay = QVBoxLayout(dlg)

            lst = QListWidget()
            for pf in param_files:
                label = f'{pf["filename"]}  [{pf["manufacturer"]}]'
                item = QListWidgetItem(label)
                item.setData(Qt.UserRole, pf['disk_path'])
                if pf.get('description'):
                    item.setToolTip(pf['description'])
                lst.addItem(item)
            lay.addWidget(lst)

            btn_row = QHBoxLayout()

            def _open():
                item = lst.currentItem()
                if not item:
                    return
                path = item.data(Qt.UserRole)
                if path and os.path.exists(path):
                    os.startfile(path)
                else:
                    QMessageBox.warning(dlg, 'Открыть', f'Файл не найден:\n{path}')

            def _open_folder():
                item = lst.currentItem()
                if not item:
                    return
                path = item.data(Qt.UserRole)
                folder = path if os.path.isdir(path) else os.path.dirname(path)
                if folder and os.path.isdir(folder):
                    os.startfile(folder)

            def _copy_to_proto():
                proto = self._mw.cfg.protocol_folder()
                if not proto:
                    proto = QFileDialog.getExistingDirectory(self, 'Папка протокола')
                    if proto:
                        self._mw.cfg.set_inspection_folder(proto)
                if proto and os.path.isdir(proto):
                    item = lst.currentItem()
                    if item:
                        src = item.data(Qt.UserRole)
                        if os.path.isfile(src):
                            shutil.copy2(src, proto)
                            self._mw.show_status(f'Скопировано: {os.path.basename(src)}')

            for label, cmd, iname in [
                ('Открыть',    _open,          'open'),
                ('Папка',      _open_folder,   'folder'),
                ('В протокол', _copy_to_proto, 'copy'),
            ]:
                b = QPushButton(label)
                b.setObjectName('secondary')
                b.setIcon(make_icon(iname, ICON_SECONDARY, 14))
                b.setIconSize(QSize(14, 14))
                b.clicked.connect(cmd)
                btn_row.addWidget(b)
            btn_row.addStretch()
            lay.addLayout(btn_row)

            close_btn = QDialogButtonBox(QDialogButtonBox.Close)
            close_btn.rejected.connect(dlg.accept)
            lay.addWidget(close_btn)
            dlg.exec()
            return

        # ── Legacy rule: use old templates system ─────────────────────────────
        all_templates = self._mw.db.get_all_templates()
        pch_templates = [t for t in all_templates
                         if t.template_type == 'pch' and rule.name in t.rule_names]
        upp_templates = [t for t in all_templates
                         if t.template_type == 'upp' and rule.name in t.rule_names]

        if not pch_templates and not upp_templates:
            QMessageBox.information(self, 'Параметры',
                'Шаблоны параметров для этого правила не найдены.\n'
                'Добавьте шаблоны в разделе «Шаблоны» и привяжите к правилу.')
            return

        dlg = QDialog(self)
        dlg.setWindowTitle(f'Параметры — {rule.name}')
        dlg.setMinimumSize(500, 400)
        lay = QVBoxLayout(dlg)
        tabs = QTabWidget()

        def _build_param_tab(templates):
            w = QWidget()
            wl = QVBoxLayout(w)
            lst = QListWidget()
            for t in templates:
                item = QListWidgetItem(t.name)
                best = self._template_best_path(t)
                item.setData(Qt.UserRole, best)
                item.setData(Qt.UserRole + 1, t.path)
                tip = t.description or ''
                if best != t.path:
                    tip = (tip + '\n' if tip else '') + '[локальная копия]'
                if tip:
                    item.setToolTip(tip.strip())
                lst.addItem(item)
            wl.addWidget(lst)
            btn_row = QHBoxLayout()

            def _open():
                item = lst.currentItem()
                if item:
                    path = item.data(Qt.UserRole)
                    if path and os.path.exists(path):
                        os.startfile(path)
                    else:
                        orig = item.data(Qt.UserRole + 1)
                        QMessageBox.warning(dlg, 'Открыть',
                            f'Файл не найден локально и на сетевом диске.\n{orig}')

            def _copy_to_proto():
                proto = self._mw.cfg.protocol_folder()
                if not proto:
                    proto = QFileDialog.getExistingDirectory(self, 'Папка протокола')
                    if proto:
                        self._mw.cfg.set_inspection_folder(proto)
                if proto and os.path.isdir(proto):
                    item = lst.currentItem()
                    if item:
                        src = item.data(Qt.UserRole)
                        if os.path.isfile(src):
                            shutil.copy2(src, proto)
                            self._mw.show_status(f'Скопировано в протокол: {os.path.basename(src)}')
                        elif os.path.isdir(src):
                            dst = os.path.join(proto, os.path.basename(src))
                            shutil.copytree(src, dst, dirs_exist_ok=True)
                            self._mw.show_status(f'Скопировано в протокол: {os.path.basename(src)}')

            def _print_file():
                item = lst.currentItem()
                if item:
                    path = item.data(Qt.UserRole)
                    if path and os.path.isfile(path):
                        import subprocess
                        subprocess.run(['notepad', '/p', path], check=False)

            for label, cmd, iname in [
                ('Открыть',    _open,          'open'),
                ('В протокол', _copy_to_proto, 'copy'),
                ('Печать',     _print_file,    'print'),
            ]:
                b = QPushButton(label)
                b.setObjectName('secondary')
                b.setIcon(make_icon(iname, ICON_SECONDARY, 14))
                b.setIconSize(QSize(14, 14))
                b.clicked.connect(cmd)
                btn_row.addWidget(b)
            btn_row.addStretch()
            wl.addLayout(btn_row)
            return w

        if pch_templates:
            tabs.addTab(_build_param_tab(pch_templates), 'Параметры ПЧ')
        if upp_templates:
            tabs.addTab(_build_param_tab(upp_templates), 'Параметры УПП')

        lay.addWidget(tabs)
        close_btn = QDialogButtonBox(QDialogButtonBox.Close)
        close_btn.rejected.connect(dlg.accept)
        lay.addWidget(close_btn)
        dlg.exec()

    def _has_local(self, rule) -> bool:
        """True if the LATEST version of this rule exists in local cache."""
        import re
        from app.services.config_service import LOCAL_FW
        local_dir = rule.local_dir or re.sub(r'[^\w\-]', '_', rule.name)
        ver = self._mw.db.get_latest_version(rule.name)
        if ver:
            ver_dir = os.path.join(LOCAL_FW, local_dir, str(ver.version))
            return os.path.isdir(ver_dir) and bool(os.listdir(ver_dir))
        # No versions in DB yet — check if folder exists at all
        path = os.path.join(LOCAL_FW, local_dir)
        return os.path.isdir(path) and bool(os.listdir(path))

    def _has_any_local(self, rule) -> bool:
        """True if ANY version folder exists in local cache (may be outdated)."""
        import re
        from app.services.config_service import LOCAL_FW
        local_dir = rule.local_dir or re.sub(r'[^\w\-]', '_', rule.name)
        path = os.path.join(LOCAL_FW, local_dir)
        return os.path.isdir(path) and bool(os.listdir(path))

    _KINCO_PLC_EXTS = frozenset({'.kpr', '.kpj', '.kpro', '.cpj', '.prj'})
    _KINCO_HMI_EXTS = frozenset({'.dpj', '.emt', '.emtp', '.emsln'})

    def _open_plc(self, result: SearchResult):
        self._open_fw_filtered(result, self._KINCO_PLC_EXTS, 'ПЛК')

    def _open_hmi(self, result: SearchResult):
        self._open_fw_filtered(result, self._KINCO_HMI_EXTS, 'HMI')

    def _open_fw_filtered(self, result: SearchResult, exts: frozenset, label: str):
        import re
        from app.services.config_service import LOCAL_FW
        rule = result.rule
        ver  = result.latest_version
        local_dir = rule.local_dir or re.sub(r'[^\w\-]', '_', rule.name)
        if ver:
            ver_dir = os.path.join(LOCAL_FW, local_dir, str(ver.version))
            if os.path.isdir(ver_dir):
                fw = self._find_fw_file_by_exts(ver_dir, exts)
                os.startfile(fw if fw else ver_dir)
                return
        QMessageBox.information(self, f'Открыть {label}',
            'Прошивка не найдена локально.\nНажмите «Скачать» для копирования с сервера.')

    @staticmethod
    def _find_fw_file_by_exts(folder: str, exts: frozenset) -> str | None:
        try:
            for root, _dirs, files in os.walk(folder):
                for f in files:
                    if os.path.splitext(f.lower())[1] in exts:
                        return os.path.join(root, f)
        except Exception:
            pass
        return None

    def _clear_protocol_folder(self):
        import shutil
        proto = self._mw.cfg.protocol_folder()
        if not proto or not os.path.isdir(proto):
            QMessageBox.information(self, 'Очистить', 'Папка осмотра не задана.')
            return
        reply = QMessageBox.question(self, 'Очистить папку',
            f'Удалить все файлы из:\n{proto}\n\nОтменить нельзя.',
            QMessageBox.Yes | QMessageBox.No, QMessageBox.No)
        if reply == QMessageBox.Yes:
            for entry in os.scandir(proto):
                try:
                    if entry.is_file() or entry.is_symlink():
                        os.remove(entry.path)
                    elif entry.is_dir():
                        shutil.rmtree(entry.path)
                except Exception:
                    pass
            self._mw.show_status('Папка осмотра очищена')

    def _copy_name(self, result: SearchResult):
        rule = result.rule
        ver  = result.latest_version
        parts = []
        if rule.software_name:
            parts.append(rule.software_name)
        else:
            parts.append(rule.name)
        if ver:
            parts.append(str(ver.version))
        text = '_'.join(p.upper().replace(' ', '_') for p in parts)
        QApplication.clipboard().setText(text)
        self._mw.show_status(f'Скопировано: {text}')

    def _open_passport(self, result: SearchResult):
        path = self._resolve_rule_path(result.rule.passport_dir)
        if not path:
            QMessageBox.information(self, 'Паспорт',
                f'Файл паспорта не найден.\nПуть: {result.rule.passport_dir}')
            return
        try:
            os.startfile(path)
        except OSError:
            folder = path if os.path.isdir(path) else os.path.dirname(path)
            msg = QMessageBox(self)
            msg.setWindowTitle('Паспорт')
            msg.setText(
                f'Не удалось открыть файл:\n{path}\n\n'
                f'Возможно, не установлена программа для этого типа файлов.'
            )
            msg.setInformativeText('Открыть папку с файлом?')
            msg.setStandardButtons(QMessageBox.Yes | QMessageBox.No)
            msg.setDefaultButton(QMessageBox.Yes)
            if msg.exec() == QMessageBox.Yes:
                try:
                    os.startfile(folder)
                except OSError:
                    pass

    def _open_instructions(self, result: SearchResult):
        path = self._resolve_rule_path(result.rule.instructions_path)
        if not path:
            QMessageBox.information(self, 'Инструкции',
                f'Файл инструкций не найден.\nПуть: {result.rule.instructions_path}')
            return
        try:
            os.startfile(path)
        except OSError as e:
            # Нет программы для открытия этого типа файлов
            folder = path if os.path.isdir(path) else os.path.dirname(path)
            msg = QMessageBox(self)
            msg.setWindowTitle('Инструкции')
            msg.setText(
                f'Не удалось открыть файл:\n{path}\n\n'
                f'Возможно, не установлена программа для этого типа файлов.'
            )
            msg.setInformativeText('Открыть папку с файлом?')
            msg.setStandardButtons(QMessageBox.Yes | QMessageBox.No)
            msg.setDefaultButton(QMessageBox.Yes)
            if msg.exec() == QMessageBox.Yes:
                try:
                    os.startfile(folder)
                except OSError:
                    pass

    def _open_photo_upload_global(self):
        """Photo upload to the protocol/inspection folder."""
        proto = self._mw.cfg.protocol_folder()
        if not proto:
            proto = QFileDialog.getExistingDirectory(self, 'Выберите папку осмотра')
            if not proto:
                return
            self._mw.cfg.set_inspection_folder( proto)
        os.makedirs(proto, exist_ok=True)
        self._start_photo_server(proto)

    def _open_photo_upload(self, result: SearchResult):
        """Photo upload tied to a firmware rule — saves to protocol folder."""
        self._open_photo_upload_global()

    def _start_photo_server(self, upload_dir: str):
        """Start HTTP upload server and show QR dialog. Saves to upload_dir."""
        from http.server import HTTPServer, BaseHTTPRequestHandler
        port = self._mw.cfg.image_server_port()

        class H(BaseHTTPRequestHandler):
            def do_GET(self):
                self.send_response(200)
                self.send_header('Content-type', 'text/html; charset=utf-8')
                self.end_headers()
                page = (
                    '<!DOCTYPE html><html><head><meta charset="utf-8">'
                    '<meta name="viewport" content="width=device-width,initial-scale=1">'
                    '<style>body{font:18px sans-serif;max-width:420px;margin:0 auto;padding:16px}'
                    'label{display:block;border:2px dashed #aaa;padding:24px;text-align:center;'
                    'border-radius:8px;margin:12px 0;cursor:pointer;color:#555}'
                    'input[type=file]{display:none}'
                    'button{width:100%;padding:14px;background:#1976D2;color:#fff;'
                    'border:none;font-size:18px;border-radius:6px;cursor:pointer}</style>'
                    '</head><body><h2>Загрузка фото</h2>'
                    '<form method="POST" enctype="multipart/form-data">'
                    '<label><input type="file" name="files" multiple accept="image/*">Выбрать фото</label>'
                    '<button type="submit">Отправить</button></form></body></html>'
                )
                self.wfile.write(page.encode('utf-8'))

            def do_POST(self):
                import re as _re, datetime as _dt, os as _os
                ct = self.headers.get('Content-Type', '')
                length = int(self.headers.get('Content-Length', 0))
                body = self.rfile.read(length)
                saved = []
                bm = _re.search(r'boundary=([^\s;]+)', ct)
                if bm:
                    boundary = ('--' + bm.group(1)).encode()
                    for part in body.split(boundary)[1:]:
                        if part.startswith(b'--'):
                            break
                        idx = part.find(b'\r\n\r\n')
                        if idx < 0:
                            continue
                        hdr = part[:idx].decode('utf-8', errors='replace')
                        data = part[idx + 4:]
                        if data.endswith(b'\r\n'):
                            data = data[:-2]
                        fm = _re.search(r'filename="([^"]+)"', hdr)
                        if fm and data:
                            fname = fm.group(1)
                            dest = _os.path.join(upload_dir, fname)
                            if _os.path.exists(dest):
                                base, ext = _os.path.splitext(fname)
                                ts = _dt.datetime.now().strftime('%H%M%S')
                                dest = _os.path.join(upload_dir, f'{base}_{ts}{ext}')
                            with open(dest, 'wb') as fh:
                                fh.write(data)
                            saved.append(fname)
                self.send_response(200)
                self.send_header('Content-type', 'text/html; charset=utf-8')
                self.end_headers()
                self.wfile.write(
                    f'<html><body><p>Загружено: {len(saved)}</p><a href="/">Ещё</a></body></html>'.encode('utf-8')
                )

            def log_message(self, *a):
                pass

        try:
            srv = HTTPServer(('0.0.0.0', port), H)
        except OSError:
            QMessageBox.warning(self, 'Фото', f'Порт {port} занят. Измените в настройках.')
            return

        threading.Thread(target=srv.serve_forever, daemon=True).start()

        try:
            s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
            s.connect(('8.8.8.8', 80))
            ip = s.getsockname()[0]
            s.close()
        except Exception:
            ip = '127.0.0.1'
        url = f'http://{ip}:{port}'

        from PySide6.QtWidgets import QDialog, QVBoxLayout, QDialogButtonBox
        from PySide6.QtCore import Qt
        dlg = QDialog(self)
        dlg.setWindowTitle('Загрузка фото с телефона')
        dlg.setMinimumWidth(340)
        lay = QVBoxLayout(dlg)
        lbl = QLabel(
            f'Отсканируйте QR с телефона\nили перейдите по ссылке:\n\n{url}\n\nПапка сохранения:\n{upload_dir}'
        )
        lbl.setAlignment(Qt.AlignCenter)
        lay.addWidget(lbl)
        try:
            import qrcode
            from PySide6.QtGui import QPixmap, QImage
            from io import BytesIO
            qr = qrcode.make(url)
            buf = BytesIO()
            qr.save(buf, format='PNG')
            buf.seek(0)
            img = QImage.fromData(buf.read())
            pix = QPixmap.fromImage(img).scaled(220, 220, Qt.KeepAspectRatio, Qt.SmoothTransformation)
            qr_lbl = QLabel()
            qr_lbl.setPixmap(pix)
            qr_lbl.setAlignment(Qt.AlignCenter)
            lay.addWidget(qr_lbl)
        except Exception:
            pass
        btns = QDialogButtonBox(QDialogButtonBox.Close)
        btns.rejected.connect(dlg.accept)
        lay.addWidget(btns)
        dlg.exec()
        srv.shutdown()

    def _show_params_hierarchy_dialog(self):
        from PySide6.QtWidgets import (QDialog, QVBoxLayout, QFormLayout, QComboBox,
                                        QLabel, QPushButton, QHBoxLayout)
        root_path = self._mw.cfg.root_path()

        dlg = QDialog(self)
        dlg.setWindowTitle('Поиск параметров')
        dlg.setMinimumWidth(500)
        lay = QVBoxLayout(dlg)

        hint = QLabel('Не заполняйте поля — покажет все параметры.\nЧем больше выбрано, тем точнее выборка.')
        hint.setObjectName('muted')
        lay.addWidget(hint)

        form = QFormLayout()
        form.setSpacing(8)
        ALL = '— (все) —'

        # Group combo
        groups = self._mw.db.get_all_equipment_groups()
        grp_combo = QComboBox()
        grp_combo.addItem(ALL, None)
        for g in groups:
            grp_combo.addItem(g.name, g)
        form.addRow('Группа (тип шкафа):', grp_combo)

        # Subtype combo — rebuilt when group changes
        sub_combo = QComboBox()
        sub_combo.addItem(ALL, None)
        form.addRow('Подтип:', sub_combo)

        def _rebuild_subtypes():
            grp = grp_combo.currentData()
            sub_combo.blockSignals(True)
            sub_combo.clear()
            sub_combo.addItem(ALL, None)
            if grp:
                for s in self._mw.db.get_subtypes_for_group(grp.id):
                    if s.name != '—':
                        sub_combo.addItem(s.name, s)
            sub_combo.blockSignals(False)
            _update()

        grp_combo.currentIndexChanged.connect(_rebuild_subtypes)

        mfr_combo = QComboBox()
        mfr_combo.addItem(ALL, '')
        for m in self._mw.db.get_param_manufacturers():
            mfr_combo.addItem(m, m)
        form.addRow('Производитель:', mfr_combo)

        lay.addLayout(form)

        preview_lbl = QLabel('—')
        preview_lbl.setWordWrap(True)
        preview_lbl.setObjectName('muted')
        lay.addWidget(preview_lbl)

        def _best_path():
            if not root_path:
                return ''
            parts = [root_path, 'Параметры']
            grp = grp_combo.currentData()
            if grp:
                parts.append(grp.name)
            sub = sub_combo.currentData()
            if sub:
                parts.append(sub.name)
            m = mfr_combo.currentData()
            if m:
                parts.append(m)
            return os.path.join(*parts)

        def _update():
            path = _best_path()
            if not path:
                preview_lbl.setText('Путь к диску не настроен')
                return
            exists = '✓' if os.path.isdir(path) else '✗'
            preview_lbl.setText(f'{exists} {path}')

        sub_combo.currentIndexChanged.connect(_update)
        mfr_combo.currentIndexChanged.connect(_update)
        _update()

        btn_row = QHBoxLayout()
        open_btn = QPushButton('Открыть папку')

        def _open():
            path = _best_path()
            if not path:
                return
            os.makedirs(path, exist_ok=True)
            os.startfile(path)

        open_btn.clicked.connect(_open)
        btn_row.addWidget(open_btn)
        btn_row.addStretch()
        close_btn = QPushButton('Закрыть')
        close_btn.clicked.connect(dlg.accept)
        btn_row.addWidget(close_btn)
        lay.addLayout(btn_row)

        dlg.exec()

    def _show_history(self, result: SearchResult):
        from PySide6.QtWidgets import (
            QDialog, QVBoxLayout, QHBoxLayout, QTableWidget, QTableWidgetItem,
            QHeaderView, QDialogButtonBox, QTextEdit, QLabel, QSplitter,
        )
        from PySide6.QtCore import Qt
        from datetime import datetime as _dt

        rule = result.rule
        sub_id  = getattr(rule, '_subtype_id', None)
        ctrl_id = getattr(rule, '_controller_id', None)

        if sub_id is not None and ctrl_id is not None:
            # Hierarchy result — read from fw_versions table
            raw = self._mw.db.get_fw_versions_history(sub_id, ctrl_id)

            class _Proxy:
                def __init__(self, d: dict):
                    class _V:
                        def __str__(self_): return d.get('version_raw', '')
                    self.version     = _V()
                    upload_str = d.get('upload_date', '')
                    try:
                        self.upload_date = _dt.fromisoformat(upload_str) if upload_str else None
                    except Exception:
                        self.upload_date = None
                    self.controller  = d.get('ctrl_name', '')
                    self.description = d.get('description', '') or ''
                    self.changelog   = d.get('changelog', '') or ''
                    self.local_path  = d.get('local_path', '') or ''
                    self.disk_path   = d.get('disk_path', '') or ''

            versions = [_Proxy(d) for d in raw]
        else:
            versions = self._mw.db.get_versions_for_rule(rule.name)
        dlg = QDialog(self)
        dlg.setWindowTitle(f'История версий — {result.rule.name}')
        dlg.setMinimumSize(700, 500)
        lay = QVBoxLayout(dlg)

        splitter = QSplitter(Qt.Vertical)

        # ── Versions table ────────────────────────────────────────────────────
        tbl = QTableWidget(len(versions), 4)
        tbl.setHorizontalHeaderLabels(['Версия', 'Дата', 'Контроллер', 'Описание'])
        tbl.horizontalHeader().setSectionResizeMode(3, QHeaderView.Stretch)
        tbl.horizontalHeader().setSectionResizeMode(0, QHeaderView.ResizeToContents)
        tbl.horizontalHeader().setSectionResizeMode(1, QHeaderView.ResizeToContents)
        tbl.horizontalHeader().setSectionResizeMode(2, QHeaderView.ResizeToContents)
        tbl.setEditTriggers(QTableWidget.NoEditTriggers)
        tbl.setSelectionBehavior(QTableWidget.SelectRows)
        tbl.verticalHeader().setVisible(False)
        for row, v in enumerate(versions):
            tbl.setItem(row, 0, QTableWidgetItem(str(v.version)))
            tbl.setItem(row, 1, QTableWidgetItem(
                v.upload_date.strftime('%d.%m.%Y %H:%M') if v.upload_date else ''
            ))
            tbl.setItem(row, 2, QTableWidgetItem(v.controller))
            desc_preview = (v.description or '')[:80]
            if len(v.description or '') > 80:
                desc_preview += '…'
            tbl.setItem(row, 3, QTableWidgetItem(desc_preview))
        splitter.addWidget(tbl)

        # ── Detail panel ──────────────────────────────────────────────────────
        detail_widget = QDialog()  # dummy parent for layout
        detail_widget = QWidget()
        detail_lay = QVBoxLayout(detail_widget)
        detail_lay.setContentsMargins(0, 4, 0, 0)
        detail_lay.setSpacing(4)

        detail_lbl = QLabel('Описание / Изменения:')
        detail_lbl.setObjectName('muted')
        detail_lay.addWidget(detail_lbl)

        detail_text = QTextEdit()
        detail_text.setReadOnly(True)
        detail_text.setMinimumHeight(100)
        detail_lay.addWidget(detail_text)

        splitter.addWidget(detail_widget)
        splitter.setSizes([280, 140])

        def _on_row_changed(row, *_):
            if 0 <= row < len(versions):
                v = versions[row]
                parts = []
                if v.description:
                    parts.append(f'Описание:\n{v.description}')
                if v.changelog:
                    parts.append(f'Изменения:\n{v.changelog}')
                if v.local_path:
                    parts.append(f'Путь:\n{v.local_path}')
                detail_text.setPlainText('\n\n'.join(parts) if parts else '(нет данных)')
            else:
                detail_text.clear()

        tbl.currentCellChanged.connect(_on_row_changed)
        if versions:
            tbl.selectRow(0)
            _on_row_changed(0)

        def _on_double_click(row, _col):
            if 0 <= row < len(versions):
                v = versions[row]
                disk_path = getattr(v, 'disk_path', '') or ''
                local_path = getattr(v, 'local_path', '') or ''
                path = disk_path if disk_path else local_path
                if path and os.path.isdir(path):
                    os.startfile(path)
                elif path:
                    from PySide6.QtWidgets import QMessageBox
                    QMessageBox.information(dlg, 'Папка',
                        f'Папка не существует:\n{path}')

        tbl.cellDoubleClicked.connect(_on_double_click)

        lay.addWidget(splitter)

        bottom_row = QHBoxLayout()
        maximize_btn = QPushButton('Развернуть')
        maximize_btn.setObjectName('secondary')
        maximize_btn.clicked.connect(dlg.showMaximized)
        bottom_row.addWidget(maximize_btn)
        bottom_row.addStretch()
        btns = QDialogButtonBox(QDialogButtonBox.Close)
        btns.rejected.connect(dlg.accept)
        bottom_row.addWidget(btns.button(QDialogButtonBox.Close))
        lay.addLayout(bottom_row)
        dlg.exec()
