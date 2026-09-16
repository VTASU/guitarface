"""Application entry point."""

from __future__ import annotations

import sys

from PySide6.QtCore import QCoreApplication
from PySide6.QtWidgets import QApplication

from .config import SettingsStore
from .resources import model_path
from .ui import MainWindow


def main() -> int:
    app = QApplication(sys.argv)
    QCoreApplication.setOrganizationName("Guitar Face")
    QCoreApplication.setApplicationName("Guitar Face")
    app.setApplicationDisplayName("Guitar Face")
    app.setStyle("Fusion")

    try:
        model = model_path()
    except FileNotFoundError:
        model = None
    window = MainWindow(SettingsStore(), model)
    window.show()
    return app.exec()
