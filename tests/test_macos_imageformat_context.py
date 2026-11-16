from __future__ import annotations

import os
from pathlib import Path

import pytest
from reuse_macos_arm64_compiled_sdk import imageformats_environment


def test_module_consumer_has_report_context_without_foreign_loaders_or_tokens(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path,
) -> None:
    unsafe = ['GH_TOKEN', 'GITHUB_TOKEN', 'DYLD_LIBRARY_PATH', 'DYLD_FRAMEWORK_PATH',
              'SSL_CERT_FILE', 'SSL_CERT_DIR', 'PYTHONHOME', 'PYTHONPATH']
    for key in unsafe:
        monkeypatch.setenv(key, 'inherited-value-must-not-reach-native-consumer')
    monkeypatch.setenv('PILOT_EVIDENCE', 'stale-other-run')
    work, output = tmp_path / 'native sdk', tmp_path / 'current reports'
    environment = imageformats_environment(work, output)
    assert environment['PILOT_EVIDENCE'] == str(output)
    assert environment['PILOT_WORK'] == str(work)
    assert environment['PILOT_PREFIX'] == str(work / 'prefix')
    assert environment['QT_QPA_PLATFORM'] == 'cocoa'
    assert environment['QT_PLUGIN_PATH'] == str(work / 'prefix/qt/plugins')
    assert not set(unsafe) & environment.keys()
    assert os.environ['PILOT_EVIDENCE'] == 'stale-other-run'
