"""
FirmwareFinder — Entry Point
==============================
Launch the PySide6 application.
"""

import sys
import os

# Ensure the project root is on sys.path when run from command line
_ROOT = os.path.dirname(os.path.abspath(__file__))
if _ROOT not in sys.path:
    sys.path.insert(0, _ROOT)

from PySide6.QtWidgets import QApplication, QStyleFactory
from PySide6.QtCore import Qt, QTranslator, QLocale, QLibraryInfo
from PySide6.QtGui import QIcon

from app.ui.app import MainWindow


def main():
    # High-DPI support
    QApplication.setHighDpiScaleFactorRoundingPolicy(
        Qt.HighDpiScaleFactorRoundingPolicy.PassThrough
    )

    app = QApplication(sys.argv)
    app.setStyle(QStyleFactory.create('Fusion'))   # fully respects QSS on all platforms
    app.setApplicationName('Antarus ПО Finder')
    app.setOrganizationName('Antarus')

    # Russian translations for QDialogButtonBox (OK → ОК, Cancel → Отмена, etc.)
    _translator = QTranslator(app)
    _tr_path = QLibraryInfo.path(QLibraryInfo.LibraryPath.TranslationsPath)
    if _translator.load(QLocale(QLocale.Language.Russian), 'qtbase', '_', _tr_path):
        app.installTranslator(_translator)

    # Set app icon if available
    icon_path = os.path.join(_ROOT, 'assets', 'icon.ico')
    if os.path.exists(icon_path):
        app.setWindowIcon(QIcon(icon_path))

    window = MainWindow()
    window.show()

    sys.exit(app.exec())


if __name__ == '__main__':
    main()
