from __future__ import annotations

import subprocess
import sys
from pathlib import Path
from unittest.mock import Mock

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / '.github/scripts'))
import probe_macos_x64_health as probe  # noqa: E402


@pytest.mark.parametrize('machine,host,version,allowed', [
    ('x86_64', 'github-hosted', '26.6.1', True),
    ('arm64', 'github-hosted', '26.6.1', False),
    ('x86_64', 'self-hosted', '26.6.1', False),
    ('x86_64', '', '26.6.1', False),
    ('x86_64', 'github-hosted', '27.0', False),
])
def test_icon_service_mitigation_is_restricted_to_affected_disposable_host(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path,
    machine: str, host: str, version: str, allowed: bool,
) -> None:
    monkeypatch.setattr(probe.platform, 'machine', lambda: machine)
    monkeypatch.setenv('RUNNER_ENVIRONMENT', host)
    monkeypatch.setattr(probe.os, 'getuid', lambda: 501, raising=False)
    monkeypatch.setattr(probe.subprocess, 'check_output', lambda *a, **k: version)
    run = Mock(return_value=subprocess.CompletedProcess([], 0, '', ''))
    monkeypatch.setattr(probe.subprocess, 'run', run)
    if allowed:
        probe.mitigate_hosted_icon_service(tmp_path)
        assert [call.args[0] for call in run.call_args_list] == [
            ['launchctl', 'bootout', 'gui/501/com.apple.iconservices.iconservicesagent'],
            ['launchctl', 'disable', 'gui/501/com.apple.iconservices.iconservicesagent'],
        ]
        assert (tmp_path / 'runner-iconservices-mitigation.json').is_file()
    else:
        with pytest.raises(AssertionError):
            probe.mitigate_hosted_icon_service(tmp_path)
        run.assert_not_called()
