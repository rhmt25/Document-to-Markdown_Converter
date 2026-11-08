# Project TODO and Handoff Checkpoint

Use this file to track implementation. Update it at every meaningful checkpoint so another AI agent can continue without relying on chat history. Do not mark an item complete until it is implemented and checked.

## Current checkpoint

- **Status:** Phases 1–4 are implemented. Single/batch conversion, image and cleanup settings, cancellation, conflict choices, and result preview passed smoke checks. Interactive source/output context-action review remains open from Phase 2.
- **Current phase:** Phase 4 — Queue, conversion workflow, and conflicts (implementation complete).
- **Next action:** Review context actions in an interactive desktop session, then start Phase 5 PyInstaller packaging and Windows verification.
- **Last checked:** 2026-11-08 (Python 3.12; PySide6 6.12.0, python-docx 1.2.0, PyMuPDF 1.28.2, striprtf 0.0.35; compile check and runtime smoke checks for conversion, conflicts, and cancellation).

## Phase 1 — Project foundation and UI shell

- [x] Inspect repository and existing files (initially contained only the plan and tracking documents).
- [x] Choose and document Python 3.11+ and `requirements.txt` dependency approach.
- [x] Establish the application source package layout (`src/docmark/`).
- [x] Create PySide6 main window with resizable input, editor/preview, and output areas.
- [x] Add bottom activity/status area; omit token estimate.
- [x] Add editable Markdown view, preview, and save action.
- [x] Add image-export On/Off control (default On; conversion connection is pending).
- [x] Add Convert, Convert All, and Cancel controls (actions are intentionally pending later phases).
- [x] Check that the Python source compiles and the main window constructs in an offscreen smoke check.
- [x] Confirm the main window responds to resizing and renders at 1200×720 in an offscreen UI check. (The offscreen Qt environment has no registered fonts, so text glyph rendering could not be visually assessed there.)

## Phase 2 — Workspace and file management

- [x] Add input and output folder pickers.
- [x] Scan input folders recursively for `.docx`, `.pdf`, `.txt`, and `.rtf` off the UI thread.
- [x] Add individual checkboxes, select-all, and bulk selection.
- [x] Display and refresh output files.
- [x] Add context actions for source and generated files with clear target labels.
- [x] Open source files using the Windows-associated application (`QDesktopServices`).
- [x] Add rename, delete (with confirmation), and reveal-in-Explorer actions as applicable.
- [ ] Manually review context actions and Windows file-association behavior in an interactive desktop session.

## Phase 3 — Conversion engine

- [x] Define shared converter interface, result type, and per-file error reporting.
- [x] Implement DOCX structure conversion (headings, paragraphs, emphasis, lists, tables).
- [x] Implement DOCX image extraction when enabled, including images in table cells.
- [x] Implement PDF text/table extraction and sorted text-block reading-order fallback.
- [x] Implement PDF image extraction when enabled and supported by PyMuPDF.
- [x] Detect image-only/scanned PDFs and explain that OCR is not included.
- [x] Implement TXT decoding, UTF-8 output, and line-ending normalization.
- [x] Implement RTF to readable plain text conversion.
- [x] Add optional conservative PDF repeated-edge-line cleanup (off by default).
- [x] Ensure media folder uses source filename (without extension) and Markdown links resolve.
- [x] Check representative files for each supported format and both image-export settings.

## Phase 4 — Queue, conversion workflow, and conflicts

- [x] Add background worker for single-file conversion with progress reporting.
- [x] Add sequential batch conversion for checked files.
- [x] Add Cancel behavior for current and pending work; report completed/cancelled/failed items.
- [x] Detect output filename conflicts and show choices only when a collision exists.
- [x] Support overwrite and numbered duplicate output names.
- [x] Support per-file conflict choice and apply-to-all choice for batch conflicts.
- [x] Connect generated Markdown to the editable view and save action.
- [x] Refresh output workspace and show success/failure notifications.
- [x] Check background single/batch flow, conflict dialog/apply-to-all, and queue cancellation with temporary documents.

## Phase 5 — Packaging and Windows verification

- [ ] Add PyInstaller spec/build configuration and include Qt plugins, parser modules, and assets.
- [ ] Build the Windows `.exe`.
- [ ] Smoke-check launch and representative conversion in the available Windows environment.
- [ ] Check packaged image export On/Off behavior and output media links.
- [ ] Record reproducible build instructions and executable location.
- [ ] Record environment and limits of portability testing; do not claim clean-machine support without a clean Windows test.

## Decisions and constraints

- Python + PySide6 desktop application; PyInstaller packaging for Windows.
- Input formats: `.docx`, `.pdf`, `.txt`, `.rtf`.
- Layout: input browser, editable Markdown editor/preview, output browser, bottom activity/status area.
- Image export has a user-controlled On/Off setting; when enabled, extracted images go to a folder named after the source file, without extension, and Markdown references must resolve.
- Numbered conflict copies receive a correspondingly numbered media folder, so each Markdown copy has independent media links.
- Source file open/edit uses Windows-associated applications. Generated Markdown can be edited in-app and saved.
- Conflict dialog appears only for actual collisions; batch workflow supports per-item decisions and apply-to-all.
- Include queue cancellation. Do not include token estimation.
- OCR for scanned PDFs is outside the initial scope; detect and report image-only PDFs.
- Conversion limits: PDF multi-column reading order and complex tables are best-effort; RTF rich styling, footnotes/endnotes, tracked changes, comments, and floating-object positioning are not fully preserved. See `PROJECT_PLAN.md`.
- `.gitignore` excludes Python bytecode/caches, virtual environments, build output, local environment files, and common OS/editor artifacts. Previously tracked bytecode was removed from the Git index while keeping local copies.

## Session log

- 2026-11-08: Created the PySide6 workspace shell, source entry point, dependency list, and run instructions. Folder pickers and Markdown edit/preview/save/open are wired. Scanning and conversion controls remain placeholders for planned phases. Initial lookup missed Python because PATH exposed only the Windows Store alias; found Python 3.12 under the user's Local Programs directory. Installed requirements (`PySide6 6.12.0`), compiled the Python sources, and successfully constructed the main window offscreen (1420×860). No automated test suite was run. Interactive visual/resizing review remains pending.
- 2026-11-08: Completed Phase 2 workspace management: asynchronous recursive source scan, per-file checkboxes/select-all, output Markdown listing, and context actions for open, rename, delete, and reveal for both source and output files. Added `.gitignore` and untracked previously committed `__pycache__` bytecode from Git's index while retaining local files. `compileall` and an offscreen smoke check of async scanning, bulk selection, and output listing passed. Interactive file-action review remains pending. The offscreen Qt environment registers no fonts, so its screenshot cannot assess actual text rendering.
- 2026-11-08: Added Windows virtual-environment run steps to `README.md` after the user encountered `ModuleNotFoundError: PySide6`; use the same interpreter for dependency installation and app launch.
- 2026-11-08: Completed Phase 3 engine in `src/docmark/conversion/`: shared options/result/error API; DOCX headings, inline emphasis, lists, tables, embedded images (including table cells); PyMuPDF text/table/image extraction; image-only PDF detection; TXT encoding fallbacks; RTF text extraction; and optional repeated PDF edge-line cleanup. Added parser dependencies to `requirements.txt`, an opt-in cleanup toggle to the UI shell, and developer/API documentation. Installed the dependencies in the available Python 3.12 interpreter. `compileall` and manual temporary-document smoke checks passed for all four formats, DOCX media links plus On/Off, images in DOCX tables and PDFs, PDF table extraction, and the OCR-limit notice. Conversion actions remain unconnected pending Phase 4.
- 2026-11-08: Completed Phase 4: wired Convert/Convert All to a sequential QThread worker, passed image-export and cleanup controls, added progress/result logging, cancel-after-current behavior, and conflict choices for overwrite, numbered copy, skip, or cancel. Batch conflict dialogs include apply-to-all. Successful output refreshes the output list and opens the first Markdown file in the editor. Numbered copies get matching numbered media folders. `compileall` and temporary-file smoke checks passed for the UI worker path, apply-to-all dialog, overwrite/skip/cancel decisions, and stopping pending queue items. Phase 5 packaging remains; interactive context-menu review is still pending.
