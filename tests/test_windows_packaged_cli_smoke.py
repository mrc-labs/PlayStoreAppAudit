"""Exercise the package smoke with a real Windows GUI-subsystem process."""

from __future__ import annotations

import shutil
import subprocess
import sys
from pathlib import Path

import pytest


@pytest.mark.skipif(sys.platform != "win32", reason="Windows GUI process semantics")
@pytest.mark.parametrize(
    ("output", "exit_code", "accepted"),
    [("app-list", 0, True), ("app-list", 7, False), ("unexpected", 0, False)],
)
def test_packaged_cli_waits_and_checks_output(
    tmp_path: Path, output: str, exit_code: int, accepted: bool,
) -> None:
    shell = shutil.which("pwsh")
    pythonw = Path(sys.executable).with_name("pythonw.exe")
    if shell is None or not pythonw.is_file():
        pytest.skip("PowerShell and native pythonw are required")
    # A delayed GUI process reproduces the launch/wait boundary without Nuitka.
    (tmp_path / "cli").write_text(
        "import sys, time\ntime.sleep(0.5)\n"
        f"print({output!r}, flush=True)\nsys.exit({exit_code})\n",
        encoding="utf-8",
    )
    root = Path(__file__).resolve().parents[1]
    builder = (root / ".github/scripts/build_windows_standalone.ps1").read_text(encoding="utf-8")
    smoke = builder.split('Write-Host "=== PACKAGED CLI SMOKE TEST ==="', 1)[1]
    smoke = smoke.split('Write-Host "=== CREATE VERSIONED PACKAGE ==="', 1)[0]
    script = tmp_path / "smoke.ps1"
    script.write_text(
        "param([string]$Binary, [string]$BuildRoot)\n"
        "$ErrorActionPreference = 'Stop'\n"
        "function Fail([string]$Message) { throw $Message }\n"
        "$Exe = Get-Item -LiteralPath $Binary\n"
        "$LASTEXITCODE = 0\n" + smoke,
        encoding="utf-8",
    )
    result = subprocess.run(
        [shell, "-NoProfile", "-File", str(script), str(pythonw), str(tmp_path)],
        cwd=tmp_path, capture_output=True, text=True, timeout=30, check=False,
    )
    assert (result.returncode == 0) is accepted, result.stdout + result.stderr
    if accepted:
        assert "Packaged CLI smoke test: PASS" in result.stdout
