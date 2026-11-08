# PyInstaller one-file, windowed build for Windows.
from pathlib import Path

from PyInstaller.utils.hooks import collect_data_files, collect_submodules, copy_metadata


project_root = Path(SPECPATH)
icon_path = project_root / "assets" / "markdocx.png"
datas = []
if icon_path.is_file():
    datas.append((str(icon_path), "assets"))
datas += collect_data_files("docx")
datas += collect_data_files("latex2mathml")
datas += copy_metadata("python-docx")

hiddenimports = []
hiddenimports += collect_submodules("docx")
hiddenimports += collect_submodules("markdown")
hiddenimports += collect_submodules("latex2mathml")

a = Analysis(
    [str(project_root / "main.py")],
    pathex=[str(project_root)],
    binaries=[],
    datas=datas,
    hiddenimports=hiddenimports,
    hookspath=[],
    hooksconfig={},
    runtime_hooks=[],
    excludes=[],
    noarchive=False,
    optimize=0,
)

pyz = PYZ(a.pure)

exe = EXE(
    pyz,
    a.scripts,
    a.binaries,
    a.datas,
    [],
    name="MarkDocx",
    debug=False,
    bootloader_ignore_signals=False,
    strip=False,
    upx=True,
    upx_exclude=[],
    runtime_tmpdir=None,
    console=False,
    icon=str(icon_path) if icon_path.is_file() else None,
    disable_windowed_traceback=False,
    argv_emulation=False,
    target_arch=None,
    codesign_identity=None,
    entitlements_file=None,
)
