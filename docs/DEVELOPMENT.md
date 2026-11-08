# Development guide

## Project layout

```text
main.py                         Desktop app entry point
src/docmark/main_window.py      PySide6 workspace, settings, and shortcuts
src/docmark/conversion/engine.py DOCX parsing and Markdown/image output
src/docmark/conversion/worker.py Background batch queue and output conflicts
tests/                          Runtime-generated DOCX and UI regression checks
MarkDocx.spec                    PyInstaller one-file Windows build
build.ps1                       Reproducible local Windows build command
```

The app is a Windows desktop program built with PySide6. The conversion engine uses `python-docx`; Preview uses Python-Markdown, Qt WebEngine, and `latex2mathml`.

## Set up a development environment

```powershell
python -m venv .venv
.\.venv\Scripts\python.exe -m pip install -r requirements-build.txt
```

`requirements-build.txt` includes runtime requirements and PyInstaller. To run the app from source:

```powershell
.\.venv\Scripts\python.exe main.py
```

## Run the regression suite

```powershell
.\.venv\Scripts\python.exe -m unittest discover -s tests -v
```

The tests generate synthetic DOCX files in temporary directories; no private sample documents are required. Qt tests select the offscreen platform automatically.

## Build the Windows executable

```powershell
.\build.ps1
```

The script installs the declared build dependency ranges and invokes the checked-in PyInstaller spec. Output is written to `dist\MarkDocx.exe`. The one-file executable includes Qt WebEngine and is substantially larger than the Python source project. `build/`, `dist/`, and virtual environments are local artifacts and must not be committed.

To embed a custom Windows application icon, place a square PNG at `assets/markdocx.png`. A 512 × 512 pixel image with a transparent background is recommended. PyInstaller uses Pillow from the build requirements to convert PNG to Windows icon format.

To test a build without replacing an existing executable:

```powershell
.\.venv\Scripts\python.exe -m PyInstaller --noconfirm --distpath .packaged-preview MarkDocx.spec
```

## Conversion pipeline

`convert_document()` validates the input extension, walks body paragraphs and tables in order, renders supported run formatting and Office Math, extracts pictures as configured, then writes Markdown. `ConversionWorker` runs a sequential queue outside the UI thread and sends conflict requests back to the main window. The main window owns user settings, output browsing, editing, preview, and keyboard behavior.

When changing conversion behavior, add or update a synthetic DOCX fixture rather than relying only on one real-world document. See [conversion support](CONVERSION_SUPPORT.md) for current guarantees and limits.

## Build and release notes

- Build and smoke-check on Windows; the desktop app is currently Windows-focused.
- Do not claim portability on a clean Windows installation until it has been tested there.
- Never commit generated executables, private DOCX samples, conversion output, environment folders, or debug logs.
- Update the user guide when behavior or shortcuts change, and update the conversion support table when parser coverage changes.
