"""
FirmwareFinder — Theme
========================
Dark / Light color palettes and QSS stylesheets.
"""

import os
import tempfile

from PySide6.QtGui import QColor, QPalette
from PySide6.QtWidgets import QApplication


def _ensure_arrow_svg(color: str) -> str:
    """Write a small filled down-triangle SVG to temp and return its path (forward slashes)."""
    safe = color.replace('#', '')
    path = os.path.join(tempfile.gettempdir(), f'ff_arrow_{safe}.svg')
    if not os.path.exists(path):
        svg = (
            f'<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 10 6">'
            f'<path fill="{color}" d="M0 0 L10 0 L5 6 Z"/></svg>'
        )
        with open(path, 'w', encoding='utf-8') as f:
            f.write(svg)
    return path.replace('\\', '/')


# ── Color palettes ────────────────────────────────────────────────────────────

DARK = {
    'bg':          '#1e1e2e',
    'bg_sidebar':  '#181825',
    'bg_card':     '#2a2a3a',
    'bg_input':    '#313244',
    'border':      '#45475a',
    'accent':      '#89b4fa',
    'accent_hover':'#b4d0fb',
    'text':        '#cdd6f4',
    'text_muted':  '#6c7086',
    'text_on_acc': '#1e1e2e',
    'success':     '#a6e3a1',
    'warning':     '#f9e2af',
    'error':       '#f38ba8',
    'tag_bg':      '#313244',
}

LIGHT = {
    'bg':          '#f5f5f7',
    'bg_sidebar':  '#e8e8ed',
    'bg_card':     '#ffffff',
    'bg_input':    '#ffffff',
    'border':      '#d1d1d6',
    'accent':      '#1d6fe8',
    'accent_hover':'#1558c0',
    'text':        '#1c1c1e',
    'text_muted':  '#8e8e93',
    'text_on_acc': '#ffffff',
    'success':     '#34c759',
    'warning':     '#ff9500',
    'error':       '#ff3b30',
    'tag_bg':      '#e8e8ed',
}


def get_palette(name: str) -> dict:
    return DARK if name == 'dark' else LIGHT


def build_qss(c: dict) -> str:
    """Build complete application QSS from color dict."""
    arrow_path = _ensure_arrow_svg(c['text_muted'])
    return f"""
/* ── Global ── */
QWidget {{
    background-color: {c['bg']};
    color: {c['text']};
    font-family: 'Segoe UI', sans-serif;
    font-size: 13px;
}}

/* ── Sidebar ── */
#sidebar {{
    background-color: {c['bg_sidebar']};
    border-right: 1px solid {c['border']};
}}

/* ── Nav buttons ── */
#nav-btn {{
    background: transparent;
    border: none;
    color: {c['text_muted']};
    padding: 9px 16px;
    text-align: left;
    font-size: 13px;
    border-radius: 6px;
    margin: 2px 8px;
    min-height: 36px;
}}
#nav-btn:hover {{
    background-color: {c['bg_card']};
    color: {c['text']};
}}
#nav-btn[active=true] {{
    background-color: {c['accent']};
    color: {c['text_on_acc']};
    font-weight: bold;
}}

/* ── Cards ── */
#card {{
    background-color: {c['bg_card']};
    border: 1px solid {c['border']};
    border-radius: 10px;
    padding: 12px;
}}
#card:hover {{
    border-color: {c['accent']};
}}

/* ── Inputs ── */
QLineEdit, QPlainTextEdit {{
    background-color: {c['bg_input']};
    border: 1px solid {c['border']};
    border-radius: 6px;
    padding: 6px 10px;
    color: {c['text']};
    min-height: 32px;
    selection-background-color: {c['accent']};
}}
QTextEdit {{
    background-color: {c['bg_input']};
    border: 1px solid {c['border']};
    border-radius: 6px;
    padding: 6px 10px;
    color: {c['text']};
    selection-background-color: {c['accent']};
}}
QLineEdit:focus, QTextEdit:focus, QPlainTextEdit:focus {{
    border-color: {c['accent']};
    border-width: 1px;
}}
QLineEdit:read-only {{
    color: {c['text_muted']};
    background-color: {c['bg_sidebar']};
}}

/* PathDropEdit — пунктирная рамка показывает что поле принимает перетаскивание */
QLineEdit[droppable="true"] {{
    border: 1px dashed {c['accent']};
    background-color: {c['bg_input']};
}}

/* PathDropEdit active drag state */
QLineEdit[drag-active="true"] {{
    border: 2px dashed {c['accent']};
    background-color: {c['bg_input']};
}}

/* ── ComboBox ── */
QComboBox {{
    background-color: {c['bg_input']};
    border: 1px solid {c['border']};
    border-radius: 6px;
    padding: 6px 32px 6px 10px;
    color: {c['text']};
    min-height: 32px;
}}
QComboBox:focus {{ border-color: {c['accent']}; }}
QComboBox:editable {{
    background-color: {c['bg_input']};
}}
QComboBox::drop-down {{
    subcontrol-origin: padding;
    subcontrol-position: top right;
    width: 24px;
    border-left: 1px solid {c['border']};
    border-radius: 0 6px 6px 0;
}}
QComboBox::down-arrow {{
    image: url({arrow_path});
    width: 10px;
    height: 6px;
}}
QComboBox QAbstractItemView {{
    background-color: {c['bg_card']};
    border: 1px solid {c['border']};
    border-radius: 6px;
    selection-background-color: {c['accent']};
    selection-color: {c['text_on_acc']};
    padding: 4px;
    outline: none;
}}
QComboBox QAbstractItemView::item {{
    padding: 6px 10px;
    min-height: 28px;
    border-radius: 4px;
}}

/* ── Buttons ── */
QPushButton {{
    background-color: {c['accent']};
    color: {c['text_on_acc']};
    border: none;
    border-radius: 6px;
    padding: 6px 16px;
    font-weight: 600;
    min-height: 32px;
    min-width: 60px;
}}
QPushButton:hover  {{ background-color: {c['accent_hover']}; }}
QPushButton:pressed {{ background-color: {c['accent']}; opacity: 0.85; }}
QPushButton:disabled {{
    background-color: {c['border']};
    color: {c['text_muted']};
}}

QPushButton#secondary {{
    background-color: {c['bg_card']};
    color: {c['text']};
    border: 1px solid {c['border']};
    font-weight: normal;
    min-width: 48px;
}}
QPushButton#secondary:hover {{
    border-color: {c['accent']};
    color: {c['accent']};
    background-color: {c['bg_input']};
}}
QPushButton#secondary:pressed {{
    background-color: {c['bg_sidebar']};
}}

QPushButton#danger {{
    background-color: {c['error']};
    color: #ffffff;
    border: none;
}}
QPushButton#danger:hover {{
    background-color: {c['error']};
    opacity: 0.85;
}}

/* ── Labels ── */
QLabel#title {{
    font-size: 18px;
    font-weight: 700;
    color: {c['text']};
    background: transparent;
}}
QLabel#subtitle {{
    font-size: 13px;
    color: {c['text_muted']};
    background: transparent;
}}
QLabel#muted {{
    color: {c['text_muted']};
    font-size: 12px;
    background: transparent;
}}

/* ── GroupBox ── */
QGroupBox {{
    border: 1px solid {c['border']};
    border-radius: 8px;
    margin-top: 20px;
    padding: 12px 12px 8px 12px;
    font-weight: 600;
    color: {c['text']};
}}
QGroupBox::title {{
    subcontrol-origin: margin;
    subcontrol-position: top left;
    padding: 2px 8px;
    left: 12px;
    background-color: {c['bg']};
    border-radius: 4px;
    color: {c['text_muted']};
    font-size: 12px;
    font-weight: 600;
}}

/* ── CheckBox ── */
QCheckBox {{
    spacing: 8px;
    color: {c['text']};
    background: transparent;
}}
QCheckBox::indicator {{
    width: 18px;
    height: 18px;
    border: 1px solid {c['border']};
    border-radius: 4px;
    background-color: {c['bg_input']};
}}
QCheckBox::indicator:checked {{
    background-color: {c['accent']};
    border-color: {c['accent']};
}}
QCheckBox::indicator:hover {{
    border-color: {c['accent']};
}}

/* ── Scrollbars ── */
QScrollBar:vertical {{
    background: transparent;
    width: 10px;
    margin: 2px 1px 2px 1px;
}}
QScrollBar::handle:vertical {{
    background: {c['border']};
    border-radius: 4px;
    min-height: 40px;
}}
QScrollBar::handle:vertical:hover {{
    background: {c['text_muted']};
}}
QScrollBar::add-line:vertical, QScrollBar::sub-line:vertical {{ height: 0; }}
QScrollBar::add-page:vertical, QScrollBar::sub-page:vertical {{ background: none; }}

QScrollBar:horizontal {{
    background: transparent;
    height: 10px;
    margin: 1px 2px 1px 2px;
}}
QScrollBar::handle:horizontal {{
    background: {c['border']};
    border-radius: 4px;
    min-width: 40px;
}}
QScrollBar::handle:horizontal:hover {{
    background: {c['text_muted']};
}}
QScrollBar::add-line:horizontal, QScrollBar::sub-line:horizontal {{ width: 0; }}
QScrollBar::add-page:horizontal, QScrollBar::sub-page:horizontal {{ background: none; }}

/* ── ScrollArea ── */
QScrollArea {{
    border: none;
    background: transparent;
}}
QScrollArea > QWidget > QWidget {{
    background: transparent;
}}

/* ── Table / List ── */
QListWidget, QTreeWidget, QTableWidget {{
    background-color: {c['bg_card']};
    border: 1px solid {c['border']};
    border-radius: 8px;
    gridline-color: {c['border']};
    outline: none;
}}
QListWidget::item, QTreeWidget::item {{
    padding: 6px 8px;
    border-radius: 4px;
    min-height: 28px;
}}
QListWidget::item:selected, QTreeWidget::item:selected {{
    background-color: {c['accent']};
    color: {c['text_on_acc']};
}}
QListWidget::item:hover:!selected, QTreeWidget::item:hover:!selected {{
    background-color: {c['bg_input']};
}}
QTableWidget::item {{
    padding: 4px 8px;
}}
QTableWidget::item:selected {{
    background-color: {c['accent']};
    color: {c['text_on_acc']};
}}
QHeaderView::section {{
    background-color: {c['bg_sidebar']};
    color: {c['text_muted']};
    border: none;
    border-right: 1px solid {c['border']};
    border-bottom: 1px solid {c['border']};
    padding: 6px 10px;
    font-weight: 600;
    font-size: 12px;
}}
QHeaderView::section:last {{
    border-right: none;
}}

/* ── Custom tab buttons ── */
QPushButton#tab-btn {{
    background-color: {c['bg_card']};
    color: {c['text']};
    border: 1px solid {c['border']};
    border-radius: 6px;
    padding: 7px 16px;
    font-weight: normal;
    min-width: 80px;
    min-height: 34px;
}}
QPushButton#tab-btn:hover {{
    border-color: {c['accent']};
    color: {c['accent']};
    background-color: {c['bg_input']};
}}
QPushButton#tab-btn:checked {{
    background-color: {c['accent']};
    color: {c['text_on_acc']};
    border-color: {c['accent']};
    font-weight: 600;
}}

/* ── TabWidget (for params dialog etc.) ── */
QTabWidget::pane {{
    border: 1px solid {c['border']};
    border-radius: 0 6px 6px 6px;
    background-color: {c['bg']};
    top: -1px;
}}
QTabBar {{
    background-color: transparent;
}}
QTabBar::tab {{
    background-color: {c['bg_card']};
    color: {c['text']};
    border: 1px solid {c['border']};
    border-bottom: none;
    border-radius: 6px 6px 0 0;
    padding: 7px 18px;
    margin-right: 2px;
    min-width: 80px;
    min-height: 32px;
}}
QTabBar::tab:selected {{
    background-color: {c['accent']};
    color: {c['text_on_acc']};
    font-weight: 600;
    border-color: {c['accent']};
}}
QTabBar::tab:hover:!selected {{
    background-color: {c['bg_input']};
    color: {c['text']};
    border-color: {c['accent']};
}}

/* ── Dialog ── */
QDialog {{
    background-color: {c['bg']};
}}
QDialogButtonBox QPushButton {{
    min-width: 80px;
}}

/* ── Separator ── */
QFrame[frameShape="4"], QFrame[frameShape="5"] {{
    color: {c['border']};
    background-color: {c['border']};
    border: none;
    max-height: 1px;
}}

/* ── ToolTip ── */
QToolTip {{
    background-color: {c['bg_card']};
    color: {c['text']};
    border: 1px solid {c['border']};
    border-radius: 4px;
    padding: 4px 8px;
}}

/* ── StatusBar ── */
QStatusBar {{
    background: {c['bg_sidebar']};
    color: {c['text_muted']};
    border-top: 1px solid {c['border']};
    font-size: 11px;
}}
QStatusBar::item {{
    border: none;
}}

/* ── DropZone ── */
#drop-zone {{
    border: 2px dashed {c['border']};
    border-radius: 10px;
    background: transparent;
    color: {c['text_muted']};
    font-size: 14px;
}}

/* ── MiniDropZone ── */
#mini-drop-zone {{
    border: 2px dashed {c['border']};
    border-radius: 8px;
    background: transparent;
    color: {c['text_muted']};
    font-size: 12px;
    padding: 6px;
}}
#mini-drop-zone[drag-active="true"] {{
    border-color: {c['accent']};
    color: {c['text']};
}}
"""


def apply_theme(app: QApplication, theme_name: str):
    c = get_palette(theme_name)
    app.setStyleSheet(build_qss(c))
