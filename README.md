# MarkDocx — DOCX to Markdown Converter

A Windows desktop app that turns Word `.docx` files into editable Markdown. It can convert one checked file or a whole folder, extract embedded pictures, and lets you review the result in an editor and HTML preview.

## Features

- Recursively scan a folder and convert `.docx` files in its subfolders.
- Convert checked documents or all discovered documents.
- Export embedded pictures beside each Markdown file, with relative links; image export can be disabled.
- Convert common Word formatting, lists, tables, and native Office Math.
- Review and edit Markdown, preview tables and equations, find text, and save changes.
- Run batch conversions in the background, cancel a queue, and resolve output name conflicts.
- Restore the last workspace folders, file selections, window size, and panel sizes.

## Quick start

1. Install Python 3.11 or newer on Windows.
2. In PowerShell, change to the project folder and install dependencies:

   ```powershell
   python -m venv .venv
   .\.venv\Scripts\python.exe -m pip install -r requirements.txt
   ```

3. Start the app:

   ```powershell
   .\.venv\Scripts\python.exe main.py
   ```

4. Choose an input folder and an output folder. Select individual DOCX files for **Convert checked**, or choose **Convert all DOCX** to process every discovered file.
5. Leave **Export images** enabled to save pictures in a sibling folder named after each Markdown file. Turn it off to insert an omission placeholder instead.
6. Select a result in the output list to edit it. Use the **Preview** tab to review the rendered document, then save your changes.

See the [complete user guide](docs/USER_GUIDE.md) for the full workflow and troubleshooting. See [conversion support and limitations](docs/CONVERSION_SUPPORT.md) for details about DOCX features.

## Keyboard shortcuts

| Shortcut | Action |
| --- | --- |
| `Enter` | Convert checked files when focus is outside text fields, the editor, Find, and dialogs |
| `Ctrl+Enter` | Convert all DOCX files in the recursive input scan |
| `Ctrl+F` | Find text in the Markdown editor |
| `Esc` | Close Find and return focus to the editor |
| `Enter` in an output conflict dialog | Choose the marked **Overwrite** action |
| `Ctrl+S` | Save Markdown |

## Development

Install the build and test dependencies, then run the regression suite:

```powershell
.\.venv\Scripts\python.exe -m pip install -r requirements-build.txt
.\.venv\Scripts\python.exe -m unittest discover -s tests -v
```

Create a Windows executable with:

```powershell
.\build.ps1
```

The executable is written to `dist\MarkDocx.exe`. To use a custom application icon, place a square PNG at `assets/markdocx.png`; 512 × 512 pixels with a transparent background is recommended. The build embeds it in the Windows executable. Build output and local environments are ignored by Git. For project structure and contributor workflow, see [Development guide](docs/DEVELOPMENT.md) and [Contributing](CONTRIBUTING.md).

## Python API

The conversion engine can also be used without the desktop UI:

```python
from src.docmark.conversion import ConversionOptions, convert_document

result = convert_document(
    "input.docx",
    "output/input.md",
    ConversionOptions(export_images=True),
)
print(result.destination)
print(result.image_files)
print(result.warnings)
```

Only `.docx` input is accepted. API errors are raised as `ConversionError`.

## Documentation

- [User guide](docs/USER_GUIDE.md)
- [Conversion support and limitations](docs/CONVERSION_SUPPORT.md)
- [Development guide](docs/DEVELOPMENT.md)
- [Contributing](CONTRIBUTING.md)

## License

This project is licensed under the MIT License. See [LICENSE](LICENSE) for details.
