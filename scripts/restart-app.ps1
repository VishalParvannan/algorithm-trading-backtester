[CmdletBinding()]
param(
    [ValidateRange(1024, 65535)][int]$Port = 8000,
    [switch]$CheckOnly,
    [switch]$OpenBrowser
)

$ErrorActionPreference = 'Stop'
$projectRoot = [IO.Path]::GetFullPath((Join-Path $PSScriptRoot '..'))
$projectPython = Join-Path $projectRoot '.venv\Scripts\python.exe'
if (-not (Test-Path -LiteralPath $projectPython)) {
    throw "Project environment is missing. Create .venv and install requirements.txt first."
}

# A port number alone never authorizes stopping a process. Require this
# checkout's Python environment AND a recognized server command.
$processes = @(Get-CimInstance Win32_Process)
$servers = @($processes | Where-Object {
    $_.ExecutablePath -and
    [string]::Equals($_.ExecutablePath, $projectPython, [StringComparison]::OrdinalIgnoreCase) -and
    ($_.CommandLine -match '(?i)\s-m\s+uvicorn\s+(?:backend\.)?server:application(?:\s|$)' -or
     $_.CommandLine -match '(?i)\s-m\s+backend\.backtest_service(?:\s|$)' -or
     $_.CommandLine -match '(?i)\s(?:"[^"\r\n]*[\\/]app\.py"|"app\.py"|(?:[^\s"]*[\\/])?app\.py)(?:\s|$)')
})

# Include Python's reload workers and Windows venv launcher children.
$owned = @{}
foreach ($server in $servers) { $owned[[int]$server.ProcessId] = $server }
do {
    $added = $false
    foreach ($process in $processes) {
        if ($owned.ContainsKey([int]$process.ParentProcessId) -and -not $owned.ContainsKey([int]$process.ProcessId) -and
            $process.CreationDate -ge $owned[[int]$process.ParentProcessId].CreationDate) {
            $owned[[int]$process.ProcessId] = $process
            $added = $true
        }
    }
} while ($added)

function Get-PortListeners {
    # Enumerate all listeners: no-match on a particular port is not an error.
    @(Get-NetTCPConnection -State Listen -ErrorAction Stop | Where-Object { $_.LocalPort -eq $Port })
}

$listeners = @(Get-PortListeners)
$unrelated = @($listeners | Where-Object { -not $owned.ContainsKey([int]$_.OwningProcess) })
if ($unrelated.Count) {
    $identifiers = ($unrelated.OwningProcess | Sort-Object -Unique) -join ', '
    throw "Port $Port belongs to an unverified process (PID $identifiers). Nothing was stopped. Use .\restart.cmd -Port 8002 or stop that app yourself."
}

if ($CheckOnly) {
    Write-Host "Project: $projectRoot"
    Write-Host "Verified server processes: $($owned.Count)"
    foreach ($process in $owned.Values) { Write-Host "PID $($process.ProcessId): $($process.CommandLine)" }
    Write-Host "Port ${Port}: ready for restart. Check only; nothing stopped or started."
    exit 0
}

# Stop server supervisors before their workers so they cannot spawn replacements.
$ordered = @($servers) + @($owned.Values | Where-Object { $_.ProcessId -notin $servers.ProcessId })
foreach ($process in $ordered) {
    $current = Get-CimInstance Win32_Process -Filter "ProcessId = $($process.ProcessId)"
    # Refuse a recycled PID: process identity must still match the snapshot.
    if ($current -and $current.CreationDate -eq $process.CreationDate) {
        Write-Host "Stopping project server PID $($process.ProcessId)..."
        Stop-Process -Id $process.ProcessId -ErrorAction Stop
    }
}

$deadline = [DateTime]::UtcNow.AddSeconds(5)
while ((Get-PortListeners).Count -gt 0) {
    if ([DateTime]::UtcNow -ge $deadline) { throw "Port $Port is still occupied. No new server was started." }
    Start-Sleep -Milliseconds 200
}

Set-Location -LiteralPath $projectRoot
Write-Host "Starting Backtest Lab at http://127.0.0.1:$Port"
Write-Host 'Save code to reload automatically. Press Ctrl+C in this terminal to stop.'
if ($OpenBrowser) {
    $browserHelper = Join-Path $PSScriptRoot 'open-browser.py'
    Start-Process -FilePath $projectPython -ArgumentList @(('"' + $browserHelper + '"'), '--port', $Port) -WindowStyle Hidden
}
& $projectPython -m uvicorn backend.server:application --host 127.0.0.1 --port $Port --reload --app-dir $projectRoot --reload-dir $projectRoot
exit $LASTEXITCODE
