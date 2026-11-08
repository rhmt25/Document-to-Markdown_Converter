"""Main workspace window for the desktop converter."""

from pathlib import Path

from PySide6.QtCore import Qt
from PySide6.QtGui import QAction, QFont
from PySide6.QtWidgets import (
    QCheckBox,
    QFileDialog,
    QFrame,
    QHBoxLayout,
    QLabel,
    QMainWindow,
    QPlainTextEdit,
    QPushButton,
    QSplitter,
    QStatusBar,
    QTabWidget,
    QTextBrowser,
    QTreeWidget,
    QTreeWidgetItem,
    QVBoxLayout,
    QWidget,
)


SUPPORTED_EXTENSIONS = {".docx", ".pdf", ".txt", ".rtf"}


class MainWindow(QMainWindow):
    """Three-panel workspace shell; conversion actions are connected in later phases."""

    def __init__(self) -> None:
        super().__init__()
        self.input_directory: Path | None = None
        self.output_directory: Path | None = None
        self.current_markdown_path: Path | None = None
        self._build_ui()
        self._apply_theme()

    def _build_ui(self) -> None:
        self.setWindowTitle("Document to Markdown Converter")
        self.resize(1420, 860)
        self.setMinimumSize(980, 620)

        root = QWidget()
        root_layout = QVBoxLayout(root)
        root_layout.setContentsMargins(12, 10, 12, 8)
        root_layout.setSpacing(8)

        header = QHBoxLayout()
        title = QLabel("Document to Markdown")
        title.setObjectName("appTitle")
        subtitle = QLabel("Convert, review, and refine your documents")
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
        self.convert_button = QPushButton("Convert")
        self.convert_button.setToolTip("Convert the selected source file (conversion engine is not connected yet).")
        self.convert_all_button = QPushButton("Convert All")
        self.convert_all_button.setObjectName("primaryButton")
        self.cancel_button = QPushButton("Cancel")
        self.cancel_button.setEnabled(False)
        header.addWidget(self.convert_button)
        header.addWidget(self.convert_all_button)
        header.addWidget(self.cancel_button)
        root_layout.addLayout(header)

        workspace = QSplitter(Qt.Orientation.Horizontal)
        workspace.setChildrenCollapsible(False)
        workspace.addWidget(self._build_input_panel())
        workspace.addWidget(self._build_editor_panel())
        workspace.addWidget(self._build_output_panel())
        workspace.setSizes([300, 800, 300])
        root_layout.addWidget(workspace, 1)

        self.activity = QPlainTextEdit()
        self.activity.setReadOnly(True)
        self.activity.setMaximumBlockCount(500)
        self.activity.setPlaceholderText("Activity and conversion messages will appear here.")
        self.activity.setFixedHeight(92)
        root_layout.addWidget(self.activity)

        self.setCentralWidget(root)
        self._build_status_bar()
        self._build_menu()
        self._log("Workspace ready. Choose input and output folders to begin.")

    def _build_input_panel(self) -> QFrame:
        panel, layout = self._panel("INPUT WORKSPACE", "Choose source documents")
        self.input_path_label = QLabel("No input folder selected")
        self.input_path_label.setObjectName("pathLabel")
        self.input_path_label.setWordWrap(True)
        layout.addWidget(self.input_path_label)

        choose = QPushButton("Choose Input Folder…")
        choose.clicked.connect(self._choose_input_folder)
        layout.addWidget(choose)

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
        layout.addWidget(self.input_tree, 1)
        return panel

    def _build_editor_panel(self) -> QFrame:
        panel, layout = self._panel("MARKDOWN EDITOR", "Edit content and preview the result")
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
        self.preview = QTextBrowser()
        self.preview.setOpenExternalLinks(True)
        self.editor.textChanged.connect(self._refresh_preview)
        self.editor_tabs.addTab(self.editor, "Markdown")
        self.editor_tabs.addTab(self.preview, "Preview")
        layout.addWidget(self.editor_tabs, 1)

        editor_actions = QHBoxLayout()
        editor_actions.addStretch(1)
        save_button = QPushButton("Save Markdown…")
        save_button.clicked.connect(self._save_markdown)
        editor_actions.addWidget(save_button)
        layout.addLayout(editor_actions)
        return panel

    def _build_output_panel(self) -> QFrame:
        panel, layout = self._panel("OUTPUT WORKSPACE", "Choose where Markdown files are saved")
        self.output_path_label = QLabel("No output folder selected")
        self.output_path_label.setObjectName("pathLabel")
        self.output_path_label.setWordWrap(True)
        layout.addWidget(self.output_path_label)

        choose = QPushButton("Choose Output Folder…")
        choose.clicked.connect(self._choose_output_folder)
        layout.addWidget(choose)

        self.output_tree = QTreeWidget()
        self.output_tree.setHeaderHidden(True)
        self.output_tree.setRootIsDecorated(False)
        self.output_tree.setAlternatingRowColors(True)
        self.output_tree.itemDoubleClicked.connect(self._open_output_item)
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

    def _build_status_bar(self) -> None:
        status = QStatusBar()
        self.setStatusBar(status)
        self.selection_status = QLabel("0 files selected")
        status.addWidget(self.selection_status)
        status.addPermanentWidget(QLabel("Ready"))

    def _choose_input_folder(self) -> None:
        folder = QFileDialog.getExistingDirectory(self, "Choose Input Folder")
        if not folder:
            return
        self.input_directory = Path(folder)
        self.input_path_label.setText(str(self.input_directory))
        self._log(f"Input folder selected: {self.input_directory}")
        self._log("Folder scanning will be added in Phase 2.")

    def _scan_input_folder(self) -> None:
        """Initial lightweight scan; asynchronous scanning is planned for Phase 2."""
        self.input_tree.blockSignals(True)
        self.input_tree.clear()
        count = 0
        if self.input_directory:
            try:
                for path in sorted(self.input_directory.rglob("*"), key=lambda item: str(item).casefold()):
                    if path.is_file() and path.suffix.casefold() in SUPPORTED_EXTENSIONS:
                        item = QTreeWidgetItem([path.name])
                        item.setToolTip(0, str(path))
                        item.setData(0, Qt.ItemDataRole.UserRole, str(path))
                        item.setFlags(item.flags() | Qt.ItemFlag.ItemIsUserCheckable)
                        item.setCheckState(0, Qt.CheckState.Unchecked)
                        self.input_tree.addTopLevelItem(item)
                        count += 1
            except OSError as error:
                self._log(f"Could not scan input folder: {error}")
        self.input_tree.blockSignals(False)
        self.select_all.setEnabled(count > 0)
        self.select_all.setChecked(False)
        self._update_selection_count()
        self._log(f"Found {count} supported document(s).")

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
        if total and selected == total:
            self.select_all.blockSignals(True)
            self.select_all.setChecked(True)
            self.select_all.blockSignals(False)
        elif selected == 0:
            self.select_all.blockSignals(True)
            self.select_all.setChecked(False)
            self.select_all.blockSignals(False)

    def _choose_output_folder(self) -> None:
        folder = QFileDialog.getExistingDirectory(self, "Choose Output Folder")
        if not folder:
            return
        self.output_directory = Path(folder)
        self.output_path_label.setText(str(self.output_directory))
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
            self.editor_tabs.setCurrentWidget(self.editor)
            self.statusBar().showMessage(f"Opened {path.name}", 4000)
        except (OSError, UnicodeError) as error:
            self._log(f"Could not open {path.name}: {error}")

    def _refresh_preview(self) -> None:
        self.preview.setMarkdown(self.editor.toPlainText())

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
            self._refresh_output_files()
            self._log(f"Saved Markdown: {path}")
        except OSError as error:
            self._log(f"Could not save Markdown: {error}")

    def _log(self, message: str) -> None:
        self.activity.appendPlainText(message)

    def _apply_theme(self) -> None:
        self.setStyleSheet(
            """
            QMainWindow, QWidget { background: #1e1f22; color: #e6e6e6; }
            QMenuBar, QMenu, QStatusBar { background: #25262a; color: #e6e6e6; }
            QMenuBar::item { padding: 6px 9px; }
            QFrame#workspacePanel { background: #25262a; border: 1px solid #383a40; border-radius: 7px; }
            QLabel#appTitle { font-size: 18px; font-weight: 650; }
            QLabel#panelHeading { color: #aeb5c0; font-size: 10px; font-weight: 700; letter-spacing: 1px; }
            QLabel#muted { color: #9298a3; }
            QLabel#pathLabel { color: #c6cad2; }
            QPushButton { background: #34363d; border: 1px solid #454850; border-radius: 5px; padding: 7px 10px; }
            QPushButton:hover { background: #41444c; }
            QPushButton:disabled { color: #777b83; background: #2b2c30; }
            QPushButton#primaryButton { background: #315b91; border-color: #3e70ac; font-weight: 600; }
            QPushButton#primaryButton:hover { background: #3c6ba5; }
            QPlainTextEdit, QTextBrowser, QTreeWidget, QTabWidget::pane {
                background: #1b1c1f; border: 1px solid #383a40; border-radius: 4px;
                selection-background-color: #315b91;
            }
            QTreeWidget::item { padding: 4px 2px; }
            QTreeWidget::item:alternate { background: #222327; }
            QTabBar::tab { background: #292a2f; padding: 7px 14px; border: 1px solid #383a40; }
            QTabBar::tab:selected { background: #1b1c1f; }
            QCheckBox { spacing: 7px; }
            """
        )

