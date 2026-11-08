# Document to Markdown Converter

Windows desktop application for converting documents into editable Markdown.

## Current status

The PySide6 workspace shell and Phase 2 workspace/file management are in place. The app can scan supported source files asynchronously, select files individually or in bulk, list Markdown outputs, and edit/save Markdown. Conversion and batch actions are planned for later phases.

## Run from source

1. Install Python 3.11 or newer.
2. Install dependencies: `python -m pip install -r requirements.txt`.
3. Start the application: `python main.py`.

See [PROJECT_PLAN.md](PROJECT_PLAN.md) for scope and [TODO.md](TODO.md) for the current implementation checkpoint.

Generated Python bytecode, local environments, build output, and common editor/OS artifacts are excluded by `.gitignore`.
