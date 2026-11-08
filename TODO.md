# Project TODO and Handoff Checkpoint

Use this file to track implementation. Update it at every meaningful checkpoint so another AI agent can continue without relying on chat history. Do not mark an item complete until it is implemented and checked.

## Current checkpoint

- **Status:** Phase 1 is complete. Phase 2 workspace management is implemented; asynchronous scanning, bulk selection, and output listing passed a smoke check. Context menu actions still need interactive review.
- **Current phase:** Phase 2 — Workspace and file management.
- **Next action:** Review source/output context actions and Windows file association behavior interactively, then proceed to Phase 3 conversion engine.
- **Last checked:** 2026-11-08 (Python 3.12 and PySide6 6.12.0; compile check, offscreen window resize/render, and Phase 2 async scan/selection/output-list smoke check succeeded).

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

- [ ] Define shared converter interface, result type, and per-file error reporting.
- [ ] Implement DOCX structure conversion (headings, paragraphs, emphasis, lists, tables).
- [ ] Implement DOCX image extraction when enabled.
- [ ] Implement PDF text/table extraction and reading-order fallback behavior.
- [ ] Implement PDF image extraction when enabled and supported by the chosen parser.
- [ ] Detect image-only/scanned PDFs and explain that OCR is not included.
- [ ] Implement TXT decoding, UTF-8 output, and line-ending normalization.
- [ ] Implement RTF conversion.
- [ ] Add optional conservative header/footer/page-number cleanup.
- [ ] Ensure media folder uses source filename (without extension) and Markdown links resolve.
- [ ] Check representative files for each supported format and both image-export settings.

## Phase 4 — Queue, conversion workflow, and conflicts

- [ ] Add background worker for single-file conversion with progress reporting.
- [ ] Add sequential batch conversion for checked files.
- [ ] Add Cancel behavior for current and pending work; report completed/cancelled/failed items.
- [ ] Detect output filename conflicts and show choices only when a collision exists.
- [ ] Support overwrite and numbered duplicate output names.
- [ ] Support per-file conflict choice and apply-to-all choice for batch conflicts.
- [ ] Connect generated Markdown to the editable view and save action.
- [ ] Refresh output workspace and show success/failure notifications.
- [ ] Check that the UI remains responsive during representative conversions.

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
- Source file open/edit uses Windows-associated applications. Generated Markdown can be edited in-app and saved.
- Conflict dialog appears only for actual collisions; batch workflow supports per-item decisions and apply-to-all.
- Include queue cancellation. Do not include token estimation.
- OCR for scanned PDFs is outside the initial scope; detect and report image-only PDFs.
- `.gitignore` excludes Python bytecode/caches, virtual environments, build output, local environment files, and common OS/editor artifacts. Previously tracked bytecode was removed from the Git index while keeping local copies.

## Session log

- 2026-11-08: Created the PySide6 workspace shell, source entry point, dependency list, and run instructions. Folder pickers and Markdown edit/preview/save/open are wired. Scanning and conversion controls remain placeholders for planned phases. Initial lookup missed Python because PATH exposed only the Windows Store alias; found Python 3.12 under the user's Local Programs directory. Installed requirements (`PySide6 6.12.0`), compiled the Python sources, and successfully constructed the main window offscreen (1420×860). No automated test suite was run. Interactive visual/resizing review remains pending.
- 2026-11-08: Completed Phase 2 workspace management: asynchronous recursive source scan, per-file checkboxes/select-all, output Markdown listing, and context actions for open, rename, delete, and reveal for both source and output files. Added `.gitignore` and untracked previously committed `__pycache__` bytecode from Git's index while retaining local files. `compileall` and an offscreen smoke check of async scanning, bulk selection, and output listing passed. Interactive file-action review remains pending. The offscreen Qt environment registers no fonts, so its screenshot cannot assess actual text rendering.
