$ErrorActionPreference = "Stop"

Set-Location $PSScriptRoot

if (-not (Test-Path ".venv\Scripts\python.exe")) {
    Write-Host "Creating virtual environment..."
    if (Get-Command python -ErrorAction SilentlyContinue) {
        python -m venv .venv
    } elseif (Get-Command py -ErrorAction SilentlyContinue) {
        py -3.12 -m venv .venv
    } else {
        throw "Python 3.12 is not installed or not on PATH. Install Python 3.12, then run this script again."
    }
}

Write-Host "Installing dependencies..."
.\.venv\Scripts\python.exe -m pip install -r requirements.txt

Write-Host "Starting AI Material Assistant..."
.\.venv\Scripts\python.exe -m app.main
