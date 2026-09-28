from __future__ import annotations

import ctypes
import sys

from PySide6.QtGui import QIcon, QPixmap
from PySide6.QtWidgets import QApplication

from .icon_data import icon_png_bytes
from .ui import MainWindow


def _set_windows_app_id() -> None:
    if sys.platform != "win32":
        return

    try:
        ctypes.windll.shell32.SetCurrentProcessExplicitAppUserModelID(
            "Ratanak.MediaConverter"
        )
    except (AttributeError, OSError):
        pass


def _application_icon() -> QIcon:
    pixmap = QPixmap()
    if pixmap.loadFromData(icon_png_bytes(), "PNG"):
        return QIcon(pixmap)
    return QIcon()


def main() -> int:
    _set_windows_app_id()

    app = QApplication(sys.argv)
    app.setApplicationName("Ratanak Media Converter")
    app.setOrganizationName("Ratanak")

    icon = _application_icon()
    if not icon.isNull():
        app.setWindowIcon(icon)

    window = MainWindow()
    if not icon.isNull():
        window.setWindowIcon(icon)

    window.show()
    return app.exec()
