# Document-to-Markdown Converter — Project Plan

## Project goal

Build a Windows desktop application (`.exe`) that converts supported documents into clean, structured Markdown for use with AI tools. The app will use Python and PySide6, with a modular conversion engine and a modern workspace-style interface inspired by VS Code.

This document is the project source of truth for scope and decisions. Update `TODO.md` as work progresses so another AI agent can resume from the latest checkpoint.

## Confirmed product decisions

- **Platform:** Windows desktop application.
- **Technology direction:** Python, PySide6, and PyInstaller. Select and document suitable parsers for each format during implementation.
- **Supported input formats:** `.docx`, `.pdf`, `.txt`, and `.rtf`.
- **Workspace layout:** input file browser on the left, editable Markdown preview/editor in the center, output browser on the right, and activity/status area along the bottom.
- **Folder scanning:** recursive scan of the selected input folder; users can check individual files, select all, or make a bulk selection.
- **Conversion:** convert one selected file or process selected files as a batch in the background, keeping the UI responsive.
- **Image export:** provide an On/Off control. When enabled and the source format/parser supports extraction, write images into a folder named after the source file (without its extension), following the general behavior of `pandoc --extract-media`. When disabled, do not export images. Apply the setting to both single and batch conversion.
- **Markdown editing:** users can edit the generated Markdown in the app and save it as `.md`.
- **File actions:** context menus may act on source files and generated output files. Opening a source file launches its Windows-associated application; editing a source file is done in that associated application. Generated Markdown can be opened/edited in the app. Rename, delete, and reveal-in-Explorer actions should clearly identify the target and confirm destructive deletion.
- **Name conflicts:** show conflict choices only when an output name already exists. Support overwrite and create-numbered-copy. For batches, allow a per-conflict choice and an apply-to-all choice, in a flow familiar to copying multiple files in Windows Explorer.
- **Queue control:** include a Cancel button for active/pending batch work, with clear distinction between completed and cancelled items.
- **Token estimate:** excluded from scope.
- **LLM cleanup:** optional cleanup for repeated page numbers and headers/footers may be offered, with conservative behavior and clear controls. Avoid silently deleting meaningful content.
- **Packaging:** prepare a PyInstaller build for a distributable Windows `.exe` and check it in the available Windows environment. A clean-machine portability claim requires a clean Windows test environment.

## Conversion quality rules

- Preserve document heading hierarchy, paragraphs, emphasis, lists, and tables where the source structure can be read reliably.
- Use Markdown tables for tables that can be represented without losing their basic row/column structure. Document fallback behavior for complex or malformed tables.
- Preserve source reading order as reliably as the chosen parser allows. PDF column ordering can be ambiguous; document limitations and provide a sensible extraction strategy.
- Text extraction from scanned/image-only PDFs is not guaranteed without OCR. OCR is not in the initial scope unless explicitly added later; detect or report when a PDF yields no meaningful text.
- Preserve non-UTF-8 text by decoding with appropriate fallbacks and emit Markdown as UTF-8. Normalize line endings and remove only clearly extraneous whitespace.
- Keep conversion errors visible per file and continue processing other files in a batch where possible.
- Ensure extracted media references in Markdown point to the generated source-named media folder and remain valid when the output is saved in the selected output workspace.

## Current parser choices and known limits

- **DOCX:** `python-docx`; top-level paragraphs and tables are emitted in document order. Paragraph styles, bold/italic/underline/strike, common list numbering, tables, and embedded images are supported. Images inside table cells are extracted. Complex merged-cell layouts can repeat content because Word cells may be shared.
- **PDF:** PyMuPDF; text blocks use its reading-order sort and table detection where geometry permits. Detected table regions are represented as Markdown tables and skipped in the regular text block pass. Multi-column order and borderless/complex tables remain best-effort. Extracted PDF images are linked after the page text because their exact semantic position is not always recoverable.
- **Scanned PDF:** OCR is not included. Image-only PDFs are detected and reported with that limitation.
- **RTF:** `striprtf` converts RTF to readable plain text; rich RTF styling is not retained in this first implementation.
- **Images disabled:** embedded DOCX/PDF image positions are represented by `[Image not exported]`; no media files are written.
- **Optional PDF cleanup:** when enabled, short lines repeated near the top or bottom of multiple pages are removed. This can remove repeated content that is meaningful, so it is off by default.
- **Unsupported fidelity:** footnotes/endnotes, tracked changes, comments, floating object positioning, and intricate table layout are not fully represented. Review important documents after conversion.

## Implementation phases

### Phase 1 — Project foundation and UI shell

1. Inspect the repository and establish a clear source layout (for example `src/`, `tests/`, and `assets/`) appropriate to the existing project.
2. Create the PySide6 main window with resizable input, editor/preview, and output areas.
3. Add the bottom activity/status area. Do not show token estimates.
4. Add a Markdown editor and a readable preview, with an explicit way to save edits.
5. Add visible image-export On/Off control and conversion/cancel controls in the UI shell.

**Phase exit:** application launches, main areas resize correctly, and controls have clear labels; backend actions may still be placeholders.

### Phase 2 — Workspace and file management

1. Add input/output folder pickers.
2. Recursively scan supported formats without freezing the UI.
3. Show files in the input workspace with individual checkboxes, select-all, and bulk selection.
4. Show generated output files in the output workspace and refresh after writes.
5. Add context actions for source and output items, including open, rename, delete, and reveal in Explorer where applicable.
6. Open source documents with the Windows-associated application. Keep source edit behavior external to this app.

**Phase exit:** users can choose workspaces, find and select supported files, and perform clearly scoped file actions.

### Phase 3 — Conversion engine

1. Define a modular converter interface and a common result/error model.
2. Implement DOCX parsing for headings, paragraphs, emphasis, lists, and tables; support image extraction when enabled.
3. Implement PDF text and table extraction with documented reading-order limitations; support image extraction when practical and enabled.
4. Implement TXT decoding/normalization and RTF-to-text/Markdown conversion.
5. Add optional conservative header/footer and repeated-page-number cleanup.
6. Write UTF-8 Markdown and ensure image links resolve to the source-named media folder.
7. Detect image-only/scanned PDFs and report the OCR limitation clearly.

**Phase exit:** representative fixtures for every supported format produce readable Markdown and useful per-file errors.

### Phase 4 — Conversion workflow, queue, and conflicts

1. Run conversion work off the UI thread and report progress/results.
2. Support single-file conversion and sequential batch conversion.
3. Implement cancellation for active and pending queue work.
4. Detect output conflicts and offer overwrite or numbered copy only when needed.
5. For batch conflicts, allow a choice per item or an apply-to-all choice; define how cancellation affects the remaining queue.
6. Refresh output listings and allow users to open generated Markdown in the editor.

**Phase exit:** single and batch workflows remain responsive, handle errors per file, and respect conflict choices and cancellation.

### Phase 5 — Packaging and Windows verification

1. Add and maintain a PyInstaller spec/build configuration, including required Qt plugins, parser modules, and assets.
2. Build the Windows executable (prefer a single-file build if reliability and startup behavior are acceptable).
3. Run a smoke check of the built executable in the available Windows environment.
4. Check representative conversions and image-export On/Off behavior from the packaged app.
5. Record build steps, output location, environment, and any portability limitation. Only claim clean-machine support after testing on a clean Windows machine/VM.

**Phase exit:** reproducible build instructions and a verified packaged build are documented.

## Definition of done

- A user can choose input/output folders, select supported files, convert one or many, edit/save Markdown, and see clear progress/errors.
- Image export can be switched on/off; when on, supported extracted media is stored in the source-named folder and linked correctly.
- Conflict handling supports overwrite and numbered duplicates, including per-file and apply-to-all decisions for batches.
- Queue cancellation behaves predictably and does not leave the UI stuck.
- Source-file open/edit actions use Windows file associations; output files can be managed from the app.
- The Windows packaging workflow and the scope of verification are documented.
- `TODO.md` accurately reflects completed work, current checkpoint, next action, and known issues.

## Handoff/checkpoint protocol

At the end of each work session or phase, update `TODO.md` with:

1. Completed items (mark `[x]` only when implemented and checked).
2. The current phase and the exact next actionable task.
3. Files/modules changed and important design choices.
4. Checks actually performed and their results (do not claim checks that were not run).
5. Known issues, limitations, and any decision still needed.

The next agent should read this plan and `TODO.md`, inspect the current repository state, and continue from the recorded checkpoint rather than redoing completed work.
