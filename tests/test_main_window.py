"""Offscreen checks for shortcut and workspace interaction rules."""
from __future__ import annotations

import os
os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
os.environ.setdefault("QTWEBENGINE_DISABLE_SANDBOX", "1")
os.environ.setdefault("QTWEBENGINE_CHROMIUM_FLAGS", "--disable-gpu --no-sandbox")

import tempfile
import time
import unittest
from pathlib import Path

from PySide6.QtCore import QSettings, Qt, QTimer
from PySide6.QtTest import QTest
from PySide6.QtWidgets import QApplication, QTreeWidgetItem

import src.docmark.main_window as main_window


class MainWindowTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.app = QApplication.instance() or QApplication([])

    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.settings_path = str(Path(self.temp.name) / "settings.ini")
        self.original_settings = main_window.QSettings
        def temporary_settings(*_args):
            return QSettings(self.settings_path, QSettings.Format.IniFormat)
        temporary_settings.Format = QSettings.Format
        temporary_settings.Scope = QSettings.Scope
        main_window.QSettings = temporary_settings
        self.window = main_window.MainWindow()
        self.window.show()
        self.app.processEvents()

    def tearDown(self):
        self.window.close()
        self.app.processEvents()
        main_window.QSettings = self.original_settings
        self.temp.cleanup()

    def test_find_counts_and_escape_returns_focus_to_editor(self):
        self.window.editor.setPlainText("alpha beta alpha")
        self.window._show_find()
        self.window.find_input.setText("alpha")
        self.assertEqual(self.window.find_status.text(), "2 matches")
        QTest.keyClick(self.window.find_input, Qt.Key.Key_Escape)
        self.assertFalse(self.window._find_open)
        self.assertIs(QApplication.focusWidget(), self.window.editor)

    def test_convert_all_uses_all_scanned_files(self):
        for name in ("one.docx", "two.docx"):
            item = QTreeWidgetItem([name])
            item.setData(0, Qt.ItemDataRole.UserRole, str(Path(self.temp.name) / name))
            self.window.input_tree.addTopLevelItem(item)
        self.window.input_tree.topLevelItem(0).setCheckState(0, Qt.CheckState.Checked)
        self.assertEqual(len(self.window._checked_source_files()), 1)
        self.assertEqual(len(self.window._all_source_files()), 2)
        self.assertTrue(callable(self.window._shortcut_convert_all))

    def test_editor_panel_gets_the_largest_default_share(self):
        sizes = self.window.workspace_splitter.sizes()
        self.assertGreater(sizes[1], sizes[0])
        self.assertGreater(sizes[1], sizes[2])

    def test_outside_click_closes_find(self):
        self.window._show_find()
        self.app.processEvents()
        QTest.mouseClick(self.window.output_tree.viewport(), Qt.MouseButton.LeftButton)
        self.app.processEvents()
        self.assertFalse(self.window._find_open)
        self.assertIs(QApplication.focusWidget(), self.window.output_tree)

    def test_main_enter_does_not_take_focus_from_editor(self):
        self.window.input_tree.addTopLevelItem(QTreeWidgetItem(["checked.docx"]))
        item = self.window.input_tree.topLevelItem(0)
        item.setData(0, Qt.ItemDataRole.UserRole, str(Path(self.temp.name) / "checked.docx"))
        item.setFlags(item.flags() | Qt.ItemFlag.ItemIsUserCheckable)
        item.setCheckState(0, Qt.CheckState.Checked)
        self.window.editor.setFocus()
        invoked = []
        self.window._start_conversion = lambda **kwargs: invoked.append(kwargs)
        self.window._shortcut_convert()
        self.assertEqual(invoked, [])

    def test_enter_shortcut_converts_checked_files_from_workspace_controls(self):
        item = QTreeWidgetItem(["checked.docx"])
        item.setData(0, Qt.ItemDataRole.UserRole, str(Path(self.temp.name) / "checked.docx"))
        item.setFlags(item.flags() | Qt.ItemFlag.ItemIsUserCheckable)
        item.setCheckState(0, Qt.CheckState.Checked)
        self.window.input_tree.addTopLevelItem(item)
        invoked = []
        self.window._start_conversion = lambda **kwargs: invoked.append(kwargs)
        self.window.input_tree.setFocus()
        QTest.keyClick(self.window.input_tree, Qt.Key.Key_Return)
        self.assertEqual(invoked, [{}])

    def test_ctrl_enter_shortcut_converts_all_docx(self):
        item = QTreeWidgetItem(["unchecked.docx"])
        item.setData(0, Qt.ItemDataRole.UserRole, str(Path(self.temp.name) / "unchecked.docx"))
        self.window.input_tree.addTopLevelItem(item)
        invoked = []
        self.window._start_conversion = lambda **kwargs: invoked.append(kwargs)
        self.window.input_tree.setFocus()
        QTest.keyClick(self.window.input_tree, Qt.Key.Key_Return, Qt.KeyboardModifier.ControlModifier)
        self.assertEqual(invoked, [{"all_files": True}])

    def test_preview_uses_github_markdown_for_tables_and_relative_images(self):
        html = main_window.markdown_preview_html(
            "| A | B |\n| --- | --- |\n| one | two |\n\n"
            "![leaf](media/leaf.jpg)\n\nBefore <sup>2</sup> after\n\n"
            "$$\nx^2 + \\frac{1}{2}\\tag{3}\n$$\n\nLast paragraph."
        )
        self.assertIn("<table", html)
        self.assertIn("media/leaf.jpg", html)
        self.assertIn("max-height: 65vh", html)
        self.assertIn("<sup>2</sup>", html)
        self.assertIn("<math", html)
        self.assertIn("equation-label", html)
        self.assertIn("Last paragraph.", html)

    def test_workspace_paths_and_checked_files_restore(self):
        source = Path(self.temp.name) / "source"
        output = Path(self.temp.name) / "output"
        source.mkdir()
        output.mkdir()
        docx = source / "remembered.docx"
        docx.write_bytes(b"scan-only fixture")
        self.window.input_directory = source
        self.window.output_directory = output
        self.window.input_tree.clear()
        item = QTreeWidgetItem(["remembered.docx"])
        item.setData(0, Qt.ItemDataRole.UserRole, str(docx))
        item.setFlags(item.flags() | Qt.ItemFlag.ItemIsUserCheckable)
        item.setCheckState(0, Qt.CheckState.Checked)
        self.window.input_tree.addTopLevelItem(item)
        self.window._save_workspace()
        self.window.close()
        self.window = main_window.MainWindow()
        deadline = time.monotonic() + 3
        while self.window._scan_thread is not None and time.monotonic() < deadline:
            self.app.processEvents()
            QTest.qWait(10)
        self.assertEqual(self.window.input_directory, source)
        self.assertEqual(self.window.output_directory, output)
        self.assertEqual(self.window._checked_source_files(), [docx])

    def test_conflict_enter_selects_overwrite(self):
        from threading import Event
        from src.docmark.conversion.worker import ConflictRequest, ConflictChoice

        request = ConflictRequest(
            source=Path(self.temp.name) / "source.docx",
            destination=Path(self.temp.name) / "source.md",
            allow_apply_to_all=False,
            response_ready=Event(),
        )

        def press_enter():
            dialog = self.app.activeModalWidget()
            if dialog is not None:
                QTest.keyClick(dialog, Qt.Key.Key_Return)

        QTimer.singleShot(100, press_enter)
        self.window._resolve_output_conflict(request)
        self.assertEqual(request.choice, ConflictChoice.OVERWRITE)


if __name__ == "__main__":
    unittest.main()
