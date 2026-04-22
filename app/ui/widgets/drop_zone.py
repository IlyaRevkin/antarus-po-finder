"""
FirmwareFinder — Drop Zone Widget
=====================================
Drag-and-drop file/folder target. Emits path_dropped(str) on drop.
Also contains PathDropEdit: QLineEdit that accepts file/folder drops.
Also contains MiniDropZone: small dashed area used next to File/Folder buttons.
"""

import os
from PySide6.QtWidgets import QLabel, QLineEdit
from PySide6.QtCore    import Qt, Signal
from PySide6.QtGui     import QDragEnterEvent, QDropEvent


class DropZone(QLabel):
    """Rectangular area that accepts file/folder drag-and-drop."""

    path_dropped = Signal(str)   # emitted with the dropped path

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setText('Перетащите файл или папку сюда\n\nили нажмите для выбора')
        self.setAlignment(Qt.AlignCenter)
        self.setAcceptDrops(True)
        self.setObjectName('drop-zone')
        self.setMinimumHeight(120)
        self.setCursor(Qt.PointingHandCursor)
        self._update_style(False)

    # ── Drag events ───────────────────────────────────────────────────────────

    def dragEnterEvent(self, event: QDragEnterEvent):
        if event.mimeData().hasUrls():
            event.acceptProposedAction()
            self._update_style(True)

    def dragLeaveEvent(self, event):
        self._update_style(False)

    def dropEvent(self, event: QDropEvent):
        self._update_style(False)
        urls = event.mimeData().urls()
        if urls:
            path = urls[0].toLocalFile()
            self.path_dropped.emit(path)
            self._set_filename(path)

    # ── Helpers ───────────────────────────────────────────────────────────────

    def _update_style(self, active: bool):
        border_color = '#89b4fa' if active else '#45475a'
        bg_color     = 'rgba(137,180,250,0.08)' if active else 'transparent'
        self.setStyleSheet(f"""
            QLabel {{
                border: 2px dashed {border_color};
                border-radius: 10px;
                background: {bg_color};
                color: #6c7086;
                font-size: 14px;
            }}
        """)

    def _set_filename(self, path: str):
        import os
        name = os.path.basename(path)
        self.setText(f'Файл: {name}')

    def reset(self):
        self.setText('Перетащите файл или папку сюда\n\nили нажмите для выбора')
        self._update_style(False)


class MiniDropZone(QLabel):
    """Small dashed drag-and-drop area, placed next to File/Folder browse buttons.
    Behaves like a path field: text()/setText() work for compatibility.
    """
    path_changed = Signal(str)

    def __init__(self, initial_path: str = '', parent=None):
        super().__init__(parent)
        self._path = ''
        self.setAlignment(Qt.AlignCenter)
        self.setAcceptDrops(True)
        self.setObjectName('mini-drop-zone')
        self.setMinimumHeight(64)
        self.setCursor(Qt.PointingHandCursor)
        self.setWordWrap(True)
        if initial_path:
            self.set_path(initial_path)
        else:
            self._refresh_label()

    # ── Public API ────────────────────────────────────────────────────────────

    def path(self) -> str:
        return self._path

    def text(self) -> str:
        """Compatibility: returns the stored path, not the display text."""
        return self._path

    def setText(self, path: str):
        """Compatibility: treat setText() as set_path()."""
        self.set_path(path)

    def set_path(self, path: str):
        self._path = path
        self._refresh_label()
        self.path_changed.emit(path)

    # ── Drag events ───────────────────────────────────────────────────────────

    def dragEnterEvent(self, event: QDragEnterEvent):
        if event.mimeData().hasUrls():
            event.acceptProposedAction()
            self._set_active(True)

    def dragMoveEvent(self, event):
        if event.mimeData().hasUrls():
            event.acceptProposedAction()

    def dragLeaveEvent(self, event):
        self._set_active(False)

    def dropEvent(self, event: QDropEvent):
        self._set_active(False)
        urls = event.mimeData().urls()
        if urls:
            self.set_path(urls[0].toLocalFile())
            event.acceptProposedAction()

    # ── Helpers ───────────────────────────────────────────────────────────────

    def _refresh_label(self):
        if self._path:
            QLabel.setText(self, os.path.basename(self._path) or self._path)
        else:
            QLabel.setText(self, 'Перетащите\nфайл или папку')

    def _set_active(self, active: bool):
        self.setProperty('drag-active', 'true' if active else 'false')
        self.style().unpolish(self)
        self.style().polish(self)
        self.update()


class PathDropEdit(QLineEdit):
    """QLineEdit that accepts drag-and-drop of files and folders.
    Always shows a subtle dashed border to indicate droppability.
    Shows a highlighted border while actively dragging over the field.
    """

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.setAcceptDrops(True)
        # 'droppable' property lets QSS apply a persistent dashed border
        self.setProperty('droppable', 'true')
        if not self.placeholderText():
            self.setPlaceholderText('Перетащите файл или папку…')

    def _set_drag_active(self, active: bool):
        self.setProperty('drag-active', 'true' if active else 'false')
        self.style().unpolish(self)
        self.style().polish(self)
        self.update()

    def dragEnterEvent(self, event: QDragEnterEvent):
        if event.mimeData().hasUrls():
            event.acceptProposedAction()
            self._set_drag_active(True)
        else:
            super().dragEnterEvent(event)

    def dragMoveEvent(self, event):
        if event.mimeData().hasUrls():
            event.acceptProposedAction()
        else:
            super().dragMoveEvent(event)

    def dragLeaveEvent(self, event):
        self._set_drag_active(False)
        super().dragLeaveEvent(event)

    def dropEvent(self, event: QDropEvent):
        self._set_drag_active(False)
        urls = event.mimeData().urls()
        if urls:
            self.setText(urls[0].toLocalFile())
            event.acceptProposedAction()
        else:
            super().dropEvent(event)
