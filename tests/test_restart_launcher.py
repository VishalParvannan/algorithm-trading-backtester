"""Run the real PowerShell check with synthetic process/port snapshots."""
import os
from pathlib import Path
import subprocess

import pytest

pytestmark = pytest.mark.skipif(os.name != 'nt', reason='Windows launcher')
ROOT = Path(__file__).resolve().parents[1]


@pytest.mark.parametrize('conflict', [False, True])
@pytest.mark.parametrize('module', ['server:application','backend.server:application'])
def test_restart_checks_process_ownership_without_stopping(tmp_path, conflict,module):
    script = tmp_path / 'check.ps1'
    root = str(ROOT).replace("'", "''")
    script.write_text(f"""
$root = '{root}'
function Get-CimInstance {{
    @(
        [pscustomobject]@{{ProcessId=101;ParentProcessId=1;CreationDate=[datetime]'2025-01-01';ExecutablePath="$root\\.venv\\Scripts\\python.exe";CommandLine='python.exe -m uvicorn {module} --reload'}},
        [pscustomobject]@{{ProcessId=102;ParentProcessId=101;CreationDate=[datetime]'2025-01-02';ExecutablePath='C:\\Python\\python.exe';CommandLine='reload worker'}},
        [pscustomobject]@{{ProcessId=103;ParentProcessId=1;CreationDate=[datetime]'2025-01-01';ExecutablePath='C:\\Other\\python.exe';CommandLine='python.exe -m uvicorn backend.server:application'}},
        [pscustomobject]@{{ProcessId=104;ParentProcessId=1;CreationDate=[datetime]'2025-01-01';ExecutablePath="$root\\.venv\\Scripts\\python.exe";CommandLine='python.exe examples/moving_average.py'}}
    )
}}
function Get-NetTCPConnection {{ [pscustomobject]@{{LocalPort=8000;OwningProcess={103 if conflict else 102}}} }}
function Stop-Process {{ throw 'Must never stop processes during check' }}
& "$root\\scripts\\restart-app.ps1" -CheckOnly
""", encoding='utf-8')
    result = subprocess.run(['powershell.exe','-NoProfile','-ExecutionPolicy','Bypass','-File',str(script)],capture_output=True,text=True,timeout=20)
    output = result.stdout + result.stderr
    assert 'Must never stop' not in output
    if conflict:
        assert result.returncode != 0
        assert 'unverified process' in output
        assert 'Nothing was stopped' in output
    else:
        assert result.returncode == 0, output
        assert 'Verified server processes: 2' in output
        assert 'PID 101:' in output and 'PID 102:' in output
        assert 'PID 103:' not in output and 'PID 104:' not in output
