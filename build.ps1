$ErrorActionPreference = "Stop"

$ProjectRoot = Split-Path -Parent $MyInvocation.MyCommand.Path
Set-Location -LiteralPath $ProjectRoot

$VenvPython = Join-Path $ProjectRoot ".venv\Scripts\python.exe"
if (Test-Path -LiteralPath $VenvPython) {
    $BuildPython = $VenvPython
} else {
    $BuildPython = (Get-Command python -ErrorAction Stop).Source
}

& $BuildPython -m pip install -r requirements-build.txt
if ($LASTEXITCODE -ne 0) {
    throw "Installing build requirements failed with exit code $LASTEXITCODE."
}

& $BuildPython -m PyInstaller --noconfirm --clean MarkDocx.spec
if ($LASTEXITCODE -ne 0) {
    throw "PyInstaller failed with exit code $LASTEXITCODE."
}

$Artifact = Join-Path $ProjectRoot "dist\MarkDocx.exe"
if (-not (Test-Path -LiteralPath $Artifact)) {
    throw "Build finished without the expected executable: $Artifact"
}

Write-Host "Build complete: $Artifact"
