"""Main workspace window for the desktop converter."""

from pathlib import Path
from html import escape
import os
import re
import subprocess
import sys

from threading import Event

from PySide6.QtCore import QObject, Qt, QThread, QTimer, QUrl, Signal, Slot, QSettings, QEvent
from PySide6.QtGui import QAction, QCloseEvent, QDesktopServices, QFont, QIcon, QKeySequence, QShortcut, QTextDocument
from PySide6.QtWidgets import QApplication, QLineEdit
from PySide6.QtWebEngineWidgets import QWebEngineView
from markdown import Markdown
from latex2mathml.converter import convert as latex_to_mathml
from PySide6.QtWebEngineCore import QWebEngineSettings
from PySide6.QtWidgets import (
    QCheckBox,
    QAbstractButton,
    QFileDialog,
    QFrame,
    QHBoxLayout,
    QLabel,
    QMainWindow,
    QMenu,
    QMessageBox,
    QInputDialog,
    QPlainTextEdit,
    QPushButton,
    QSplitter,
    QStatusBar,
    QTabWidget,
    QTreeWidget,
    QTreeWidgetItem,
    QVBoxLayout,
    QWidget,
)

from .conversion import ConversionOptions
from .conversion.worker import ConflictChoice, ConflictRequest, ConversionWorker, FileOutcome


SUPPORTED_EXTENSIONS = {".docx"}


def markdown_preview_html(markdown_text: str) -> str:
    """Render Markdown to complete HTML, retaining DOCX HTML tags and equations."""
    math_fragments: dict[str, str] = {}

    def preserve_math(match: re.Match[str]) -> str:
        latex = match.group(1).strip()
        token = f"DOCMARKMATHPLACEHOLDER{len(math_fragments)}TOKEN"
        label_match = re.search(r"\\tag\{([^}]*)\}", latex)
        latex = re.sub(r"\\tag\{[^}]*\}", "", latex, count=1)
        try:
            rendered = latex_to_mathml(latex)
            if label_match:
                rendered = rendered.replace('display="inline"', 'display="block"')
                rendered = rendered.replace("</math>", f'<mtext class="equation-label">({escape(label_match.group(1))})</mtext></math>')
        except (ValueError, TypeError):
            rendered = f'<code class="math-fallback">{escape(latex)}</code>'
        math_fragments[token] = rendered
        return token

    # Protect formula syntax from Markdown punctuation handling.
    markdown_text = re.sub(r"\$\$(.*?)\$\$", preserve_math, markdown_text, flags=re.DOTALL)
    markdown_text = re.sub(r"\\\[(.*?)\\\]", preserve_math, markdown_text, flags=re.DOTALL)
    markdown_text = re.sub(r"(?<!\\)\$(?!\$)(.+?)(?<!\\)\$", preserve_math, markdown_text)
    markdown_text = re.sub(r"\\\((.*?)\\\)", preserve_math, markdown_text, flags=re.DOTALL)
    body = Markdown(extensions=["tables", "fenced_code", "sane_lists", "nl2br"]).convert(markdown_text)
    for token, mathml in math_fragments.items():
        body = body.replace(token, mathml)

    return f"""<!doctype html>
<html><head><meta charset="utf-8"><style>
body {{ font: 15px/1.65 'Segoe UI', sans-serif; color: #242b35; margin: 24px; overflow-wrap: anywhere; }}
h1,h2,h3,h4 {{ line-height: 1.3; margin: 1.25em 0 .55em; }}
p {{ margin: .7em 0 1em; }}
img {{ display: block; max-width: min(100%, 760px); max-height: 65vh; width: auto; height: auto; object-fit: contain; margin: 1em auto; }}
table {{ border-collapse: collapse; width: 100%; margin: 1em 0; display: block; overflow-x: auto; }}
th,td {{ border: 1px solid #cbd3dc; padding: 7px 10px; vertical-align: top; }}
th {{ background: #eef2f6; }}
blockquote {{ border-left: 3px solid #94a3b8; margin-left: 0; padding-left: 1em; color: #526173; }}
pre {{ white-space: pre-wrap; background: #f3f5f7; padding: 12px; border-radius: 6px; }}
math[display="block"] {{ display: block; text-align: center; margin: 1em auto; overflow-x: auto; }}
math[display="inline"] {{ white-space: nowrap; }}
.equation-label {{ float: right; }}
.math-fallback {{ white-space: pre-wrap; }}
</style></head><body>{body}</body></html>"""


class FolderScanner(QObject):
    """Walk a folder off the UI thread and return supported documents."""

    finished = Signal(object, list, list)

    def __init__(self, root: Path) -> None:
        super().__init__()
        self.root = root

    @Slot()
    def run(self) -> None:
        files: list[Path] = []
        errors: list[str] = []
        pending = [self.root]
        while pending:
            directory = pending.pop()
            try:
                with os.scandir(directory) as entries:
                    for entry in entries:
                        try:
                            if entry.is_dir(follow_symlinks=False):
                                pending.append(Path(entry.path))
                            elif entry.is_file(follow_symlinks=False):
                                path = Path(entry.path)
                                if path.suffix.casefold() in SUPPORTED_EXTENSIONS and not path.name.startswith("~$"):
                                    files.append(path)
                        except OSError as error:
                            errors.append(f"{entry.path}: {error}")
            except OSError as error:
                errors.append(f"{directory}: {error}")
        files.sort(key=lambda path: str(path).casefold())
        self.finished.emit(self.root, files, errors)


class MainWindow(QMainWindow):
    """Three-panel workspace shell; conversion actions are connected in later phases."""

    def __init__(self) -> None:
        super().__init__()
        self.input_directory: Path | None = None
        self.output_directory: Path | None = None
        self.current_markdown_path: Path | None = None
        self._scan_thread: QThread | None = None
        self._scan_worker: FolderScanner | None = None
        self._scan_pending = False
        self._conversion_thread: QThread | None = None
        self._conversion_worker: ConversionWorker | None = None
        self._cancel_event: Event | None = None
        self._conversion_total = 0
        self._close_when_background_work_finishes = False
        self.settings = QSettings(
            QSettings.Format.IniFormat,
            QSettings.Scope.UserScope,
            "MarkDocx",
            "MarkDocx",
        )
        if not self.settings.allKeys():
            previous_settings = QSettings(
                QSettings.Format.IniFormat,
                QSettings.Scope.UserScope,
                "DocMark",
                "DocumentToMarkdownConverter",
            )
            for key in previous_settings.allKeys():
                self.settings.setValue(key, previous_settings.value(key))
        self._restored_checks: set[str] = set()
        self._find_open = False
        self._build_ui()
        self._apply_theme()
        self._restore_workspace()

    def _build_ui(self) -> None:
        self.setWindowTitle("MarkDocx")
        application_root = Path(getattr(sys, "_MEIPASS", Path(__file__).resolve().parents[2]))
        icon_path = application_root / "assets" / "markdocx.png"
        if icon_path.is_file():
            self.setWindowIcon(QIcon(str(icon_path)))
        self.resize(1420, 860)
        self.setMinimumSize(1040, 660)

        root = QWidget()
        root_layout = QVBoxLayout(root)
        root_layout.setContentsMargins(12, 10, 12, 8)
        root_layout.setSpacing(8)

        header = QHBoxLayout()
        title = QLabel("MarkDocx")
        title.setObjectName("appTitle")
        subtitle = QLabel("Convert Word documents, review, and refine Markdown")
        subtitle.setObjectName("muted")
        title_stack = QVBoxLayout()
        title_stack.setSpacing(1)
        title_stack.addWidget(title)
        title_stack.addWidget(subtitle)
        header.addLayout(title_stack)
        header.addStretch(1)

        self.export_images = QCheckBox("Export images")
        self.export_images.setChecked(True)
        self.export_images.setToolTip(
            "When enabled, supported embedded images are extracted into a folder named after the source file."
        )
        header.addWidget(self.export_images)
        self.convert_button = QPushButton("Convert checked")
        self.convert_button.setEnabled(False)
        self.convert_button.setToolTip("Convert checked DOCX files (Enter)")
        self.convert_all_button = QPushButton("Convert all DOCX (checked or not)")
        self.convert_all_button.setObjectName("primaryButton")
        self.convert_all_button.setEnabled(False)
        self.convert_all_button.setToolTip("Convert every DOCX in the input folder, whether checked or not (Ctrl+Enter)")
        self.cancel_button = QPushButton("Cancel")
        self.cancel_button.setEnabled(False)
        self.convert_button.clicked.connect(lambda: self._start_conversion())
        self.convert_all_button.clicked.connect(lambda: self._start_conversion(all_files=True))
        self.cancel_button.clicked.connect(self._cancel_conversion)
        header.addWidget(self.convert_button)
        header.addWidget(self.convert_all_button)
        header.addWidget(self.cancel_button)
        root_layout.addLayout(header)

        folders = QFrame()
        folders.setObjectName("folderBar")
        folders_layout = QHBoxLayout(folders)
        folders_layout.setContentsMargins(10, 6, 10, 6)
        folders_layout.setSpacing(8)
        folders_layout.addWidget(QLabel("Input"))
        self.input_path_label = QLabel("No input folder selected")
        self.input_path_label.setObjectName("pathLabel")
        self.input_path_label.setToolTip("Recursive DOCX source folder")
        folders_layout.addWidget(self.input_path_label, 1)
        self.choose_input_button = QPushButton("Change…")
        self.choose_input_button.setAccessibleName("Change input folder")
        self.choose_input_button.clicked.connect(self._choose_input_folder)
        folders_layout.addWidget(self.choose_input_button)
        folders_layout.addSpacing(12)
        folders_layout.addWidget(QLabel("Output"))
        self.output_path_label = QLabel("No output folder selected")
        self.output_path_label.setObjectName("pathLabel")
        self.output_path_label.setToolTip("Folder for generated Markdown files")
        folders_layout.addWidget(self.output_path_label, 1)
        self.choose_output_button = QPushButton("Change…")
        self.choose_output_button.setAccessibleName("Change output folder")
        self.choose_output_button.clicked.connect(self._choose_output_folder)
        folders_layout.addWidget(self.choose_output_button)
        root_layout.addWidget(folders)

        workspace = QSplitter(Qt.Orientation.Horizontal)
        self.workspace_splitter = workspace
        workspace.setChildrenCollapsible(False)
        workspace.addWidget(self._build_input_panel())
        workspace.addWidget(self._build_editor_panel())
        workspace.addWidget(self._build_output_panel())
        workspace.setStretchFactor(0, 1)
        workspace.setStretchFactor(1, 3)
        workspace.setStretchFactor(2, 1)
        root_layout.addWidget(workspace, 1)

        self.activity = QPlainTextEdit()
        self.activity.setReadOnly(True)
        self.activity.setMaximumBlockCount(500)
        self.activity.setPlaceholderText("Activity and conversion messages will appear here.")
        self.activity.setMaximumHeight(110)
        self.activity.hide()
        root_layout.addWidget(self.activity)

        self.setCentralWidget(root)
        self._build_status_bar()
        self._build_menu()
        self._build_shortcuts()
        self._log("Workspace ready. Choose input and output folders to begin.")

    def showEvent(self, event) -> None:
        super().showEvent(event)
        saved = self.settings.value("splitter_sizes")
        sizes = [int(value) for value in saved] if saved else [300, 800, 300]
        QTimer.singleShot(0, lambda: self.workspace_splitter.setSizes(sizes))

    def _build_input_panel(self) -> QFrame:
        panel, layout = self._panel("SOURCE DOCX", "Choose a folder; subfolders are included")
        selection_row = QHBoxLayout()
        self.select_all = QCheckBox("Select all")
        self.select_all.setEnabled(False)
        self.select_all.toggled.connect(self._set_all_checked)
        selection_row.addWidget(self.select_all)
        selection_row.addStretch(1)
        layout.addLayout(selection_row)

        self.input_tree = QTreeWidget()
        self.input_tree.setHeaderHidden(True)
        self.input_tree.setRootIsDecorated(False)
        self.input_tree.setAlternatingRowColors(True)
        self.input_tree.setSelectionMode(QTreeWidget.SelectionMode.ExtendedSelection)
        self.input_tree.itemChanged.connect(self._update_selection_count)
        self.input_tree.itemSelectionChanged.connect(self._update_selection_count)
        self.input_tree.setContextMenuPolicy(Qt.ContextMenuPolicy.CustomContextMenu)
        self.input_tree.customContextMenuRequested.connect(self._input_context_menu)
        self.input_tree.itemDoubleClicked.connect(self._open_source_item)
        layout.addWidget(self.input_tree, 1)
        return panel

    def _build_editor_panel(self) -> QFrame:
        panel, layout = self._panel("MARKDOWN", "Edit and preview the converted document")
        self.document_label = QLabel("Unsaved Markdown")
        self.document_label.setObjectName("muted")
        layout.addWidget(self.document_label)

        self.editor_tabs = QTabWidget()
        self.editor = QPlainTextEdit()
        self.editor.setPlaceholderText(
            "Converted Markdown will appear here. You can edit it and save the result as a .md file."
        )
        editor_font = QFont("Cascadia Code")
        editor_font.setStyleHint(QFont.StyleHint.Monospace)
        editor_font.setPointSize(10)
        self.editor.setFont(editor_font)
        self.preview = QWebEngineView()
        self.preview.settings().setAttribute(QWebEngineSettings.WebAttribute.JavascriptEnabled, False)
        self.preview.settings().setAttribute(QWebEngineSettings.WebAttribute.LocalContentCanAccessRemoteUrls, False)
        self.editor.textChanged.connect(self._refresh_preview)
        self.editor_tabs.addTab(self.editor, "Markdown")
        self.editor_tabs.addTab(self.preview, "Preview")
        layout.addWidget(self.editor_tabs, 1)

        self.find_bar = QWidget()
        find_layout = QHBoxLayout(self.find_bar)
        find_layout.setContentsMargins(0, 0, 0, 0)
        self.find_input = QLineEdit()
        self.find_input.setPlaceholderText("Find in Markdown…")
        self.find_input.setClearButtonEnabled(True)
        self.find_input.textChanged.connect(self._update_find_status)
        self.find_input.returnPressed.connect(lambda: self._find_next())
        find_layout.addWidget(self.find_input, 1)
        self.find_previous_button = QPushButton("Previous")
        self.find_previous_button.clicked.connect(lambda: self._find_next(backward=True))
        find_layout.addWidget(self.find_previous_button)
        self.find_next_button = QPushButton("Next")
        self.find_next_button.clicked.connect(self._find_next)
        find_layout.addWidget(self.find_next_button)
        self.find_status = QLabel("0 matches")
        find_layout.addWidget(self.find_status)
        close_find = QPushButton("×")
        close_find.setAccessibleName("Close Find")
        close_find.clicked.connect(lambda: self._close_find(return_to_editor=False))
        find_layout.addWidget(close_find)
        self.find_bar.hide()
        layout.addWidget(self.find_bar)

        editor_actions = QHBoxLayout()
        find_button = QPushButton("Find  Ctrl+F")
        find_button.clicked.connect(self._show_find)
        editor_actions.addWidget(find_button)
        editor_actions.addStretch(1)
        save_button = QPushButton("Save Markdown…")
        save_button.clicked.connect(self._save_markdown)
        editor_actions.addWidget(save_button)
        layout.addLayout(editor_actions)
        return panel

    def _build_output_panel(self) -> QFrame:
        panel, layout = self._panel("OUTPUT MARKDOWN", "Open results here to edit or preview them")
        self.output_tree = QTreeWidget()
        self.output_tree.setHeaderHidden(True)
        self.output_tree.setRootIsDecorated(False)
        self.output_tree.setAlternatingRowColors(True)
        self.output_tree.itemDoubleClicked.connect(self._open_output_item)
        self.output_tree.setContextMenuPolicy(Qt.ContextMenuPolicy.CustomContextMenu)
        self.output_tree.customContextMenuRequested.connect(self._output_context_menu)
        layout.addWidget(self.output_tree, 1)
        return panel

    @staticmethod
    def _panel(heading: str, description: str) -> tuple[QFrame, QVBoxLayout]:
        panel = QFrame()
        panel.setObjectName("workspacePanel")
        layout = QVBoxLayout(panel)
        layout.setContentsMargins(12, 10, 12, 12)
        layout.setSpacing(8)
        title = QLabel(heading)
        title.setObjectName("panelHeading")
        layout.addWidget(title)
        hint = QLabel(description)
        hint.setObjectName("muted")
        hint.setWordWrap(True)
        layout.addWidget(hint)
        return panel, layout

    def _build_menu(self) -> None:
        file_menu = self.menuBar().addMenu("&File")
        choose_input = QAction("Choose Input Folder…", self)
        choose_input.triggered.connect(self._choose_input_folder)
        file_menu.addAction(choose_input)
        choose_output = QAction("Choose Output Folder…", self)
        choose_output.triggered.connect(self._choose_output_folder)
        file_menu.addAction(choose_output)
        file_menu.addSeparator()
        save = QAction("Save Markdown…", self)
        save.setShortcut("Ctrl+S")
        save.triggered.connect(self._save_markdown)
        file_menu.addAction(save)

    def _build_shortcuts(self) -> None:
        self.find_shortcut = QShortcut(QKeySequence.Find, self.editor)
        self.find_shortcut.activated.connect(self._show_find)
        app = QApplication.instance()
        if app:
            app.installEventFilter(self)

    def _shortcut_convert(self) -> None:
        focus = QApplication.focusWidget()
        if self._find_open or self._conversion_thread is not None or self._active_modal():
            return
        if focus is not None and (focus is self.editor or self.editor.isAncestorOf(focus)):
            return
        if isinstance(focus, (QLineEdit, QPlainTextEdit, QAbstractButton)):
            return
        if self._checked_source_files():
            self._start_conversion()

    def _shortcut_convert_all(self) -> None:
        if self._find_open or self._conversion_thread is not None or self._active_modal():
            return
        self._start_conversion(all_files=True)

    def _active_modal(self) -> bool:
        app = QApplication.instance()
        return bool(app and app.activeModalWidget())

    def _show_find(self) -> None:
        self._find_open = True
        self.find_bar.show()
        self.find_input.setFocus()
        self.find_input.selectAll()
        self._update_find_status()

    def _close_find(self, *, return_to_editor: bool) -> None:
        self._find_open = False
        self.find_bar.hide()
        if return_to_editor:
            self.editor.setFocus()

    def _find_next(self, backward: bool = False) -> None:
        needle = self.find_input.text()
        if not needle:
            self._update_find_status()
            return
        flags = QTextDocument.FindFlag.FindBackward if backward else QTextDocument.FindFlag(0)
        if not self.editor.find(needle, flags):
            cursor = self.editor.textCursor()
            cursor.movePosition(cursor.MoveOperation.End if backward else cursor.MoveOperation.Start)
            self.editor.setTextCursor(cursor)
            self.editor.find(needle, flags)
        self._update_find_status()

    def _update_find_status(self, *_args) -> None:
        needle = self.find_input.text()
        if not needle:
            self.find_status.setText("0 matches")
            return
        count = self.editor.toPlainText().casefold().count(needle.casefold())
        self.find_status.setText(f"{count} match" + ("es" if count != 1 else ""))

    def eventFilter(self, watched, event) -> bool:
        if (event.type() == QEvent.Type.KeyPress
                and isinstance(watched, QWidget)
                and (watched is self or self.isAncestorOf(watched))):
            modifiers = event.modifiers()
            is_enter = event.key() in (Qt.Key.Key_Return, Qt.Key.Key_Enter)
            if is_enter and modifiers == Qt.KeyboardModifier.ControlModifier:
                if not self._find_open and not self._conversion_thread and not self._active_modal():
                    self._shortcut_convert_all()
                return True
            if is_enter and modifiers == Qt.KeyboardModifier.NoModifier:
                focus = QApplication.focusWidget()
                if (focus is not None
                        and not (focus is self.editor or self.editor.isAncestorOf(focus))
                        and not isinstance(focus, (QLineEdit, QPlainTextEdit, QAbstractButton))
                        and not self._find_open and not self._conversion_thread
                        and not self._active_modal()):
                    self._shortcut_convert()
                    return True
        if (self._find_open and watched is self.find_input
                and event.type() == QEvent.Type.KeyPress
                and event.key() == Qt.Key.Key_Escape):
            self._close_find(return_to_editor=True)
            return True
        if self._find_open and event.type() == QEvent.Type.MouseButtonPress:
            target = watched if isinstance(watched, QWidget) else QApplication.widgetAt(event.globalPosition().toPoint())
            if target is not None and not (target is self.find_bar or self.find_bar.isAncestorOf(target)):
                self._close_find(return_to_editor=False)
        return super().eventFilter(watched, event)

    def _restore_workspace(self) -> None:
        input_path = self.settings.value("input_directory", "", str)
        output_path = self.settings.value("output_directory", "", str)
        self._restored_checks = set(self.settings.value("checked_sources", [], list))
        if input_path and Path(input_path).is_dir():
            self.input_directory = Path(input_path)
            self.input_path_label.setText(input_path)
            self._start_input_scan()
        elif input_path:
            self._log(f"Saved input folder is unavailable: {input_path}")
        if output_path and Path(output_path).is_dir():
            self.output_directory = Path(output_path)
            self.output_path_label.setText(output_path)
            self._refresh_output_files()
        elif output_path:
            self._log(f"Saved output folder is unavailable: {output_path}")
        geometry = self.settings.value("window_geometry")
        if geometry:
            self.restoreGeometry(geometry)

    def _save_workspace(self) -> None:
        self.settings.setValue("input_directory", str(self.input_directory or ""))
        self.settings.setValue("output_directory", str(self.output_directory or ""))
        self.settings.setValue("checked_sources", [str(p) for p in self._checked_source_files()])
        self.settings.setValue("window_geometry", self.saveGeometry())
        self.settings.setValue("splitter_sizes", self.workspace_splitter.sizes())

    def _build_status_bar(self) -> None:
        status = QStatusBar()
        self.setStatusBar(status)
        self.selection_status = QLabel("0 files selected")
        status.addWidget(self.selection_status)
        self.activity_toggle = QPushButton("Show activity")
        self.activity_toggle.setFlat(True)
        self.activity_toggle.clicked.connect(self._toggle_activity)
        status.addPermanentWidget(self.activity_toggle)
        status.addPermanentWidget(QLabel("Ready"))

    def _toggle_activity(self) -> None:
        visible = not self.activity.isVisible()
        self.activity.setVisible(visible)
        self.activity_toggle.setText("Hide activity" if visible else "Show activity")

    def _choose_input_folder(self) -> None:
        folder = QFileDialog.getExistingDirectory(self, "Choose Input Folder")
        if not folder:
            return
        self.input_directory = Path(folder)
        self.input_path_label.setText(str(self.input_directory))
        self._restored_checks.clear()
        self._save_workspace()
        self._log(f"Input folder selected: {self.input_directory}")
        self._start_input_scan()

    def _start_input_scan(self) -> None:
        if self._scan_thread is not None:
            self._scan_pending = True
            return
        if not self.input_directory:
            return
        self.choose_input_button.setEnabled(False)
        self.input_tree.setEnabled(False)
        self.select_all.setEnabled(False)
        self.selection_status.setText("Scanning input folder…")
        self.statusBar().showMessage("Scanning input folder…")
        thread = QThread(self)
        worker = FolderScanner(self.input_directory)
        worker.moveToThread(thread)
        thread.started.connect(worker.run)
        worker.finished.connect(self._finish_input_scan)
        worker.finished.connect(thread.quit)
        worker.finished.connect(worker.deleteLater)
        thread.finished.connect(thread.deleteLater)
        thread.finished.connect(self._clear_scan_thread)
        self._scan_thread = thread
        self._scan_worker = worker
        thread.start()

    @Slot(object, list, list)
    def _finish_input_scan(self, scan_root: Path, files: list[Path], errors: list[str]) -> None:
        if scan_root != self.input_directory:
            self._scan_pending = True
            return
        self.input_tree.blockSignals(True)
        self.input_tree.clear()
        for path in files:
            relative_path = path.relative_to(scan_root)
            item = QTreeWidgetItem([str(relative_path)])
            item.setToolTip(0, str(path))
            item.setData(0, Qt.ItemDataRole.UserRole, str(path))
            item.setFlags(item.flags() | Qt.ItemFlag.ItemIsUserCheckable)
            item.setCheckState(0, Qt.CheckState.Checked if str(path) in self._restored_checks else Qt.CheckState.Unchecked)
            self.input_tree.addTopLevelItem(item)
        self.input_tree.blockSignals(False)
        self.choose_input_button.setEnabled(True)
        self.input_tree.setEnabled(True)
        self.select_all.setEnabled(bool(files))
        self.select_all.setChecked(False)
        self._update_selection_count()
        self.statusBar().showMessage(f"Found {len(files)} DOCX file(s).", 5000)
        self._log(f"Found {len(files)} DOCX file(s).")
        self._restored_checks.clear()
        self._save_workspace()
        for error in errors[:10]:
            self._log(f"Skipped inaccessible path: {error}")
        if len(errors) > 10:
            self._log(f"{len(errors) - 10} additional scan warning(s) were omitted.")

    @Slot()
    def _clear_scan_thread(self) -> None:
        self._scan_worker = None
        self._scan_thread = None
        if self._scan_pending:
            self._scan_pending = False
            self._start_input_scan()
        else:
            self._maybe_close_after_background_work()

    def _set_all_checked(self, checked: bool) -> None:
        for index in range(self.input_tree.topLevelItemCount()):
            self.input_tree.topLevelItem(index).setCheckState(
                0, Qt.CheckState.Checked if checked else Qt.CheckState.Unchecked
            )
        self._update_selection_count()

    def _update_selection_count(self, *_args: object) -> None:
        total = self.input_tree.topLevelItemCount()
        selected = sum(
            self.input_tree.topLevelItem(index).checkState(0) == Qt.CheckState.Checked
            for index in range(total)
        )
        self.selection_status.setText(f"{selected} of {total} files selected")
        is_converting = self._conversion_thread is not None
        self.convert_button.setEnabled(selected > 0 and not is_converting)
        self.convert_all_button.setEnabled(total > 0 and not is_converting)
        self._save_workspace()
        if total and selected == total:
            self.select_all.blockSignals(True)
            self.select_all.setChecked(True)
            self.select_all.blockSignals(False)
        elif selected == 0:
            self.select_all.blockSignals(True)
            self.select_all.setChecked(False)
            self.select_all.blockSignals(False)

    def _checked_source_files(self) -> list[Path]:
        files: list[Path] = []
        for index in range(self.input_tree.topLevelItemCount()):
            item = self.input_tree.topLevelItem(index)
            if item.checkState(0) == Qt.CheckState.Checked:
                files.append(Path(item.data(0, Qt.ItemDataRole.UserRole)))
        return files

    def _start_conversion(self, *, all_files: bool = False) -> None:
        if self._conversion_thread is not None:
            return
        if not self.output_directory:
            QMessageBox.information(self, "Choose output folder", "Choose an output folder before converting.")
            return

        sources = self._all_source_files() if all_files else self._checked_source_files()
        if not sources:
            QMessageBox.information(self, "Select DOCX files", "Choose a source folder containing DOCX files first.")
            return

        self._cancel_event = Event()
        self._conversion_total = len(sources)
        options = ConversionOptions(export_images=self.export_images.isChecked())
        thread = QThread(self)
        worker = ConversionWorker(sources, self.output_directory, options, self._cancel_event)
        worker.moveToThread(thread)
        thread.started.connect(worker.run)
        worker.progress.connect(self._on_conversion_progress)
        worker.conflict_requested.connect(self._resolve_output_conflict)
        worker.file_finished.connect(self._on_file_conversion_finished)
        worker.finished.connect(self._on_conversion_finished)
        worker.finished.connect(worker.deleteLater)
        thread.finished.connect(thread.deleteLater)
        thread.finished.connect(self._clear_conversion_thread)

        self._conversion_thread = thread
        self._conversion_worker = worker
        self.convert_button.setEnabled(False)
        self.convert_all_button.setEnabled(False)
        self.cancel_button.setEnabled(True)
        self.choose_input_button.setEnabled(False)
        self.choose_output_button.setEnabled(False)
        self.select_all.setEnabled(False)
        self.input_tree.setEnabled(False)
        self.output_tree.setEnabled(False)
        action = "all DOCX in the source folder" if all_files else "checked DOCX files"
        self._log(f"Started conversion of {action} ({len(sources)} file(s)).")
        thread.start()

    def _all_source_files(self) -> list[Path]:
        return [Path(self.input_tree.topLevelItem(i).data(0, Qt.ItemDataRole.UserRole))
                for i in range(self.input_tree.topLevelItemCount())]

    @Slot(int, int, str)
    def _on_conversion_progress(self, current: int, total: int, filename: str) -> None:
        message = f"Converting {current}/{total}: {filename}"
        self.statusBar().showMessage(message)
        self._log(message)

    @Slot(object)
    def _resolve_output_conflict(self, request: ConflictRequest) -> None:
        dialog = QMessageBox(self)
        dialog.setWindowTitle("Output file already exists")
        dialog.setIcon(QMessageBox.Icon.Warning)
        dialog.setText(f"An output file with this name already exists:\n{request.destination}")
        dialog.setInformativeText(f"Source: {request.source.name}\nChoose what to do with this file.")
        overwrite = dialog.addButton("Overwrite", QMessageBox.ButtonRole.AcceptRole)
        dialog.setDefaultButton(overwrite)
        overwrite.setDefault(True)
        overwrite.setText("Overwrite  ·  Enter")
        numbered_copy = dialog.addButton("Keep both (numbered copy)", QMessageBox.ButtonRole.ActionRole)
        skip = dialog.addButton("Skip this file", QMessageBox.ButtonRole.DestructiveRole)
        cancel = dialog.addButton("Cancel queue", QMessageBox.ButtonRole.RejectRole)
        if request.allow_apply_to_all:
            apply_all = QCheckBox("Apply this choice to all remaining conflicts")
            dialog.setCheckBox(apply_all)
        else:
            apply_all = None
        dialog.exec()

        clicked = dialog.clickedButton()
        if clicked is overwrite:
            request.choice = ConflictChoice.OVERWRITE
        elif clicked is numbered_copy:
            request.choice = ConflictChoice.NUMBERED_COPY
        elif clicked is skip:
            request.choice = ConflictChoice.SKIP
        elif clicked is cancel or clicked is None:
            request.choice = ConflictChoice.CANCEL
            if self._cancel_event is not None:
                self._cancel_event.set()
        request.apply_to_all = bool(apply_all and apply_all.isChecked())
        request.response_ready.set()

    @Slot(object)
    def _on_file_conversion_finished(self, outcome: FileOutcome) -> None:
        if outcome.status == "success":
            self._log(f"Converted: {outcome.source.name} → {outcome.destination.name if outcome.destination else ''}")
            if " — " in outcome.message:
                self._log(f"Note: {outcome.message.split(' — ', 1)[1]}")
        elif outcome.status == "skipped":
            self._log(f"Skipped: {outcome.source.name} (name conflict)")
        else:
            self._log(f"Failed: {outcome.source.name} — {outcome.message}")

    @Slot(object)
    def _on_conversion_finished(self, outcomes: list[FileOutcome]) -> None:
        successful = [item for item in outcomes if item.status == "success" and item.destination]
        skipped = sum(item.status == "skipped" for item in outcomes)
        failed = sum(item.status == "failed" for item in outcomes)
        total = self._conversion_total
        completed = len(outcomes)
        cancelled = self._cancel_event is not None and self._cancel_event.is_set()
        remaining = max(0, total - completed)
        summary = f"Finished: {len(successful)} converted, {skipped} skipped, {failed} failed"
        if cancelled or remaining:
            summary += f", {remaining} not processed"
        self._log(summary + ".")
        self.statusBar().showMessage(summary, 8000)
        self._refresh_output_files()

        if successful:
            first = successful[0].destination
            for index in range(self.output_tree.topLevelItemCount()):
                item = self.output_tree.topLevelItem(index)
                if Path(item.data(0, Qt.ItemDataRole.UserRole)) == first:
                    self._open_output_item(item, 0)
                    break
        if self._conversion_thread is not None:
            self._conversion_thread.quit()

    def _cancel_conversion(self) -> None:
        if self._cancel_event is None or self._cancel_event.is_set():
            return
        self._cancel_event.set()
        self.cancel_button.setEnabled(False)
        self.statusBar().showMessage("Cancel requested; the current file will finish first.")
        self._log("Cancel requested; the current file will finish before the remaining queue stops.")

    @Slot()
    def _clear_conversion_thread(self) -> None:
        self._conversion_worker = None
        self._conversion_thread = None
        self._cancel_event = None
        self._conversion_total = 0
        self.cancel_button.setEnabled(False)
        self.choose_input_button.setEnabled(True)
        self.choose_output_button.setEnabled(True)
        self.input_tree.setEnabled(True)
        self.output_tree.setEnabled(True)
        self.select_all.setEnabled(self.input_tree.topLevelItemCount() > 0)
        self._update_selection_count()
        self._maybe_close_after_background_work()

    def closeEvent(self, event: QCloseEvent) -> None:
        if self._scan_thread is not None or self._conversion_thread is not None:
            self._close_when_background_work_finishes = True
            if self._conversion_thread is not None:
                self._cancel_conversion()
            self.statusBar().showMessage("Closing after background work finishes…")
            event.ignore()
            return
        self._save_workspace()
        event.accept()

    def _maybe_close_after_background_work(self) -> None:
        if (
            self._close_when_background_work_finishes
            and self._scan_thread is None
            and self._conversion_thread is None
        ):
            QTimer.singleShot(0, self.close)

    def _choose_output_folder(self) -> None:
        folder = QFileDialog.getExistingDirectory(self, "Choose Output Folder")
        if not folder:
            return
        self.output_directory = Path(folder)
        self.output_path_label.setText(str(self.output_directory))
        self._save_workspace()
        self._refresh_output_files()
        self._log(f"Output folder selected: {self.output_directory}")

    def _refresh_output_files(self) -> None:
        self.output_tree.clear()
        if not self.output_directory or not self.output_directory.exists():
            return
        try:
            for path in sorted(self.output_directory.glob("*.md"), key=lambda item: item.name.casefold()):
                item = QTreeWidgetItem([path.name])
                item.setToolTip(0, str(path))
                item.setData(0, Qt.ItemDataRole.UserRole, str(path))
                self.output_tree.addTopLevelItem(item)
        except OSError as error:
            self._log(f"Could not list output files: {error}")

    def _open_output_item(self, item: QTreeWidgetItem, _column: int) -> None:
        path = Path(item.data(0, Qt.ItemDataRole.UserRole))
        try:
            self.editor.setPlainText(path.read_text(encoding="utf-8"))
            self.current_markdown_path = path
            self.document_label.setText(path.name)
            self.editor.document().setModified(False)
            self.editor_tabs.setCurrentWidget(self.editor)
            self.statusBar().showMessage(f"Opened {path.name}", 4000)
        except (OSError, UnicodeError) as error:
            self._log(f"Could not open {path.name}: {error}")

    def _open_source_item(self, item: QTreeWidgetItem, _column: int) -> None:
        path = Path(item.data(0, Qt.ItemDataRole.UserRole))
        if not QDesktopServices.openUrl(QUrl.fromLocalFile(str(path))):
            self._log(f"Windows could not open {path.name} with an associated application.")

    def _input_context_menu(self, position) -> None:
        item = self.input_tree.itemAt(position)
        if item is None:
            return
        menu = QMenu(self)
        open_action = menu.addAction("Open source in Windows app")
        rename_action = menu.addAction("Rename source file…")
        delete_action = menu.addAction("Delete source file…")
        menu.addSeparator()
        reveal_action = menu.addAction("Reveal in File Explorer")
        selected = menu.exec(self.input_tree.viewport().mapToGlobal(position))
        path = Path(item.data(0, Qt.ItemDataRole.UserRole))
        if selected == open_action:
            self._open_source_item(item, 0)
        elif selected == rename_action:
            self._rename_file(path, source=True)
        elif selected == delete_action:
            self._delete_file(path, source=True)
        elif selected == reveal_action:
            self._reveal_in_explorer(path)

    def _output_context_menu(self, position) -> None:
        item = self.output_tree.itemAt(position)
        if item is None:
            return
        menu = QMenu(self)
        edit_action = menu.addAction("Edit in Markdown editor")
        open_action = menu.addAction("Open with Windows app")
        rename_action = menu.addAction("Rename output file…")
        delete_action = menu.addAction("Delete output file…")
        menu.addSeparator()
        reveal_action = menu.addAction("Reveal in File Explorer")
        selected = menu.exec(self.output_tree.viewport().mapToGlobal(position))
        path = Path(item.data(0, Qt.ItemDataRole.UserRole))
        if selected == edit_action:
            self._open_output_item(item, 0)
        elif selected == open_action:
            QDesktopServices.openUrl(QUrl.fromLocalFile(str(path)))
        elif selected == rename_action:
            self._rename_file(path, source=False)
        elif selected == delete_action:
            self._delete_file(path, source=False)
        elif selected == reveal_action:
            self._reveal_in_explorer(path)

    def _rename_file(self, path: Path, *, source: bool) -> None:
        label = "source file" if source else "output file"
        new_name, accepted = QInputDialog.getText(
            self, "Rename file", f"New name for {label}:", text=path.name
        )
        if not accepted:
            return
        new_name = new_name.strip()
        invalid_windows_name = any(character in new_name for character in '<>:"/\\|?*')
        invalid_windows_name = invalid_windows_name or any(ord(character) < 32 for character in new_name)
        if (
            not new_name
            or Path(new_name).name != new_name
            or new_name in {".", ".."}
            or new_name.endswith((" ", "."))
            or invalid_windows_name
        ):
            QMessageBox.warning(self, "Invalid name", "Enter a file name without a folder path.")
            return
        if source and Path(new_name).suffix.casefold() != path.suffix.casefold():
            QMessageBox.warning(self, "Keep the file type", "A source file must keep its current extension.")
            return
        if not source and Path(new_name).suffix.casefold() != ".md":
            QMessageBox.warning(self, "Keep the Markdown extension", "An output file must keep the .md extension.")
            return
        destination = path.with_name(new_name)
        if destination.exists() and destination != path:
            QMessageBox.warning(self, "Name already exists", f"A file named {new_name} already exists.")
            return
        try:
            path.rename(destination)
            self._log(f"Renamed {label}: {path.name} → {destination.name}")
            if source:
                self._start_input_scan_after_rename()
            else:
                if self.current_markdown_path == path:
                    self.current_markdown_path = destination
                    self.document_label.setText(destination.name)
                self._refresh_output_files()
        except OSError as error:
            QMessageBox.critical(self, "Rename failed", str(error))

    def _start_input_scan_after_rename(self) -> None:
        self._start_input_scan()

    def _delete_file(self, path: Path, *, source: bool) -> None:
        label = "source" if source else "output"
        answer = QMessageBox.question(
            self,
            f"Delete {label} file?",
            f"Permanently delete this {label} file?\n\n{path}",
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.Cancel,
            QMessageBox.StandardButton.Cancel,
        )
        if answer != QMessageBox.StandardButton.Yes:
            return
        try:
            path.unlink()
            self._log(f"Deleted {label} file: {path}")
            if source:
                self._start_input_scan()
            else:
                if self.current_markdown_path == path:
                    self.current_markdown_path = None
                    self.document_label.setText("Unsaved Markdown")
                self._refresh_output_files()
        except OSError as error:
            QMessageBox.critical(self, "Delete failed", str(error))

    @staticmethod
    def _reveal_in_explorer(path: Path) -> None:
        if sys.platform == "win32":
            subprocess.Popen(["explorer.exe", f"/select,{path}"])
        else:
            QDesktopServices.openUrl(QUrl.fromLocalFile(str(path.parent)))

    def _refresh_preview(self) -> None:
        base_url = QUrl()
        if self.current_markdown_path:
            base_url = QUrl.fromLocalFile(str(self.current_markdown_path.parent) + os.sep)
        self.preview.setHtml(markdown_preview_html(self.editor.toPlainText()), base_url)
        if self.current_markdown_path and self.editor.document().isModified():
            self.document_label.setText(f"{self.current_markdown_path.name} • Unsaved changes")

    def _save_markdown(self) -> None:
        suggested = str(self.current_markdown_path) if self.current_markdown_path else "document.md"
        filename, _ = QFileDialog.getSaveFileName(
            self, "Save Markdown", suggested, "Markdown files (*.md);;All files (*.*)"
        )
        if not filename:
            return
        path = Path(filename)
        if path.suffix.casefold() != ".md":
            path = path.with_suffix(".md")
        try:
            path.write_text(self.editor.toPlainText(), encoding="utf-8", newline="\n")
            self.current_markdown_path = path
            self.document_label.setText(path.name)
            self.editor.document().setModified(False)
            self._refresh_output_files()
            self._log(f"Saved Markdown: {path}")
        except OSError as error:
            self._log(f"Could not save Markdown: {error}")

    def _log(self, message: str) -> None:
        self.activity.appendPlainText(message)

    def _apply_theme(self) -> None:
        self.setStyleSheet(
            """
            QMainWindow, QWidget { background: #20242b; color: #e8edf4; }
            QMenuBar, QMenu, QStatusBar { background: #282e38; color: #e8edf4; }
            QMenuBar::item { padding: 6px 9px; }
            QFrame#workspacePanel { background: #282e38; border: 1px solid #3a4350; border-radius: 8px; }
            QFrame#folderBar { background: #282e38; border: 1px solid #3a4350; border-radius: 7px; }
            QLabel#appTitle { font-size: 18px; font-weight: 650; }
            QLabel#panelHeading { color: #aeb5c0; font-size: 10px; font-weight: 700; letter-spacing: 1px; }
            QLabel#muted { color: #a6b0be; }
            QLabel#pathLabel { color: #d1d9e3; }
            QPushButton { background: #343d4a; border: 1px solid #4b5869; border-radius: 6px; padding: 8px 11px; }
            QPushButton:hover { background: #414e60; }
            QPushButton:focus { border: 2px solid #83b9ff; }
            QPushButton:disabled { color: #858d98; background: #2b3038; }
            QPushButton#primaryButton { background: #2769a9; border-color: #4386c4; font-weight: 600; }
            QPushButton#primaryButton:hover { background: #347ab9; }
            QPlainTextEdit, QWebEngineView, QTreeWidget, QTabWidget::pane {
                background: #1d2229; border: 1px solid #3a4350; border-radius: 5px;
                selection-background-color: #2769a9;
            }
            QTreeWidget::item { padding: 4px 2px; }
            QTreeWidget::item:alternate { background: #222327; }
            QTabBar::tab { background: #303742; padding: 8px 14px; border: 1px solid #3a4350; }
            QTabBar::tab:selected { background: #1d2229; }
            QCheckBox { spacing: 7px; }
            QLineEdit { background: #1d2229; border: 1px solid #4b5869; border-radius: 5px; padding: 7px; }
            QLineEdit:focus { border: 2px solid #83b9ff; }
            """
        )

