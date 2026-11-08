"""Application entry point for Document to Markdown Converter."""

import sys

from PySide6.QtWidgets import QApplication

from src.docmark.main_window import MainWindow


def main() -> int:
    app = QApplication(sys.argv)
    app.setApplicationName("Document to Markdown Converter")
    app.setOrganizationName("Document to Markdown Converter")
    app.setStyle("Fusion")

    window = MainWindow()
    window.show()
    return app.exec()


if __name__ == "__main__":
    raise SystemExit(main())
