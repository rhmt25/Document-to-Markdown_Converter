"""Application entry point for MarkDocx."""

import sys

from PySide6.QtWidgets import QApplication

from src.docmark.main_window import MainWindow


def main() -> int:
    app = QApplication(sys.argv)
    app.setApplicationName("MarkDocx")
    app.setOrganizationName("MarkDocx")
    app.setStyle("Fusion")

    window = MainWindow()
    window.show()
    return app.exec()


if __name__ == "__main__":
    raise SystemExit(main())
