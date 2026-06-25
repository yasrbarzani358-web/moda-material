$ErrorActionPreference = "SilentlyContinue"

$projectRoot = Split-Path -Parent $MyInvocation.MyCommand.Path
$processes = Get-CimInstance Win32_Process |
    Where-Object {
        $_.CommandLine -like "*app.main*" -and
        $_.CommandLine -like "*$projectRoot*"
    }

foreach ($process in $processes) {
    Stop-Process -Id $process.ProcessId -Force
    Write-Host "Stopped bot process $($process.ProcessId)"
}

if (-not $processes) {
    Write-Host "No AI Material Assistant bot process found."
}
