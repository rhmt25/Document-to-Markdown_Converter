# Document to Markdown Converter

Windows desktop application for converting documents into editable Markdown.

## Current status

The PySide6 workspace shell, Phase 2 workspace/file management, and Phase 3 conversion engine are in place. The app can scan supported source files asynchronously, select files individually or in bulk, list Markdown outputs, and edit/save Markdown. Format conversion is available through the conversion engine API; connecting it to the app's Convert/Convert All buttons is planned for Phase 4.

The engine is available from `src.docmark.conversion`:

```python
from src.docmark.conversion import ConversionOptions, convert_document

result = convert_document(
    "input.docx",
    "output/input.md",
    ConversionOptions(export_images=True),
)
```

Supported source formats are `.docx`, `.pdf`, `.txt`, and `.rtf`. Scanned PDFs need OCR, which is not included.

## Run from source on Windows

1. Install Python 3.11 or newer.
2. From PowerShell in the project folder, create a virtual environment:

   ```powershell
   python -m venv .venv
   ```

3. Install dependencies into that environment:

   ```powershell
   .\.venv\Scripts\python.exe -m pip install -r requirements.txt
   ```

4. Start the application with the same environment's interpreter:

   ```powershell
   .\.venv\Scripts\python.exe main.py
   ```

If running without a virtual environment, install dependencies through the same `python` command used to launch the app:

```powershell
python -m pip install -r requirements.txt
python main.py
```

This avoids installing PySide6 into one Python installation and launching the app with another.

See [PROJECT_PLAN.md](PROJECT_PLAN.md) for scope and [TODO.md](TODO.md) for the current implementation checkpoint.

Generated Python bytecode, local environments, build output, and common editor/OS artifacts are excluded by `.gitignore`.
