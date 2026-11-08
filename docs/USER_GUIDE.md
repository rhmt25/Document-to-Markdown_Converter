# User guide

This guide covers a complete conversion from a folder of Word documents to reviewed Markdown files.

## Install and start

The desktop app runs on Windows. Install Python 3.11 or newer, open PowerShell in the project folder, and run:

```powershell
python -m venv .venv
.\.venv\Scripts\python.exe -m pip install -r requirements.txt
.\.venv\Scripts\python.exe main.py
```

To use a ready-made executable, build it with `build.ps1` or obtain a release from the project's GitHub Releases page when one is published.

## Choose folders and documents

1. Click **Change…** beside **Input** and choose the folder containing your `.docx` documents.
2. The app scans that folder and its subfolders. Temporary Word lock files are ignored.
3. Click **Change…** beside **Output** and choose where Markdown files should be saved.
4. Select files in the **Source DOCX** list. **Select all** toggles the discovered files.

Use **Convert checked** to process checked rows only. **Convert all DOCX** processes every discovered DOCX, including unchecked rows. The status area reports progress, warnings, and per-file errors.

## Export pictures

With **Export images** enabled, the app writes each embedded picture once to a folder beside its Markdown file. For example:

```text
output/
├── Report.md
└── Report/
    ├── image_001.png
    └── image_002.jpg
```

Markdown links use paths relative to `Report.md`. Keep the media folder with the Markdown file when moving or sharing the result. When image export is disabled, no pictures are written and the Markdown contains an omission placeholder at the picture position.

Pictures that contain a table or equation remain pictures. The converter does not use OCR to reconstruct them.

## Review and edit the result

Select a file in **Output Markdown** to open it in the editor. Switch between **Markdown** and **Preview**. The Preview renders pipe tables and common DOCX inline tags, converts supported LaTeX formulas to MathML, and limits image dimensions. Unsupported formula syntax is shown as readable TeX. Edit in the Markdown tab and choose **Save Markdown…** to save changes.

Use **Find** or `Ctrl+F` to search the Markdown. The Find bar supports next and previous match navigation. Press `Esc` to close it and return to the editor; click another control to close it and keep focus there.

## Resolve output name conflicts

If the destination Markdown file already exists, choose one of these actions:

- **Overwrite** replaces the existing Markdown file.
- **Keep both** saves a numbered copy such as `Report (1).md`.
- **Skip** leaves the existing file unchanged and moves to the next document.
- **Cancel queue** stops processing the remaining files.

For a multi-file queue, the dialog can apply the chosen action to later conflicts.

## Keyboard shortcuts

- `Enter`: convert checked files when focus is outside text entry, the Markdown editor, Find, modal dialogs, and active conversion.
- `Ctrl+Enter`: convert every DOCX found in the selected input folder scan.
- `Ctrl+F`: open Find from the Markdown editor.
- `Esc`: close Find and return focus to the editor.
- `Enter` in a conflict dialog: choose the visibly marked Overwrite option.
- `Ctrl+S`: open the Save Markdown dialog.

The app remembers the last input and output folders, checked files, window geometry, and panel sizes. Missing folders or files are skipped safely.

## Troubleshooting

### No documents appear

Choose the folder that contains the `.docx` files. The scan includes subfolders. `.doc` and `.docm` files are not supported.

### Pictures are missing from a shared Markdown file

Confirm **Export images** was enabled and share the media folder next to the Markdown file. Picture export is based on embedded DOCX image objects; externally linked or unusually placed drawing content may need review.

### A formula looks like TeX in Preview

The Preview renders formulas that the LaTeX-to-MathML converter supports. Other syntax is shown as TeX so the source remains visible. A formula inserted into Word as a picture stays an image.

### A complex table looks simplified

Markdown cannot represent merged cells or nested tables exactly. Merged values are repeated across logical cells, while nested tables are flattened with a warning. Review the original DOCX for layout details that Markdown cannot express.

### Conversion reports a warning or failure

Check the activity/status area and the per-file message. A failed document does not prevent the remaining queue from being processed. Review complex drawings and uncommon Word extensions in the original document.
