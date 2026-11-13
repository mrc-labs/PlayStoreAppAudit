from __future__ import annotations

import hashlib
import io
import json
import zipfile
from pathlib import Path

import probe_windows_qt_ca_guard as probe
import pytest


@pytest.mark.parametrize('failure', ['distribution', 'version', 'binary', 'execution', None])
def test_stable_ninja_wheel_requires_exact_native_variant_and_bytes(failure: str | None) -> None:
    tool = {'returncode': 0, 'version': probe.NINJA_WHEEL['native_version'] + '\n',
            'sha256': probe.NINJA_WHEEL['binary_sha256']}
    distribution = '1.13.2'
    if failure == 'distribution':
        distribution = '1.13.2rc1'
    elif failure == 'version':
        tool['version'] = '1.13.2.git.unreviewed'
    elif failure == 'binary':
        tool['sha256'] = '0' * 64
    elif failure == 'execution':
        tool['returncode'] = 1
    if failure:
        with pytest.raises(ValueError, match='Unqualified native Ninja'):
            probe.qualify_ninja_identity(tool, distribution)
    else:
        probe.qualify_ninja_identity(tool, distribution)


@pytest.mark.parametrize('name', ['../escape.pem', '/escape.pem', 'C:/escape.pem', r'..\escape.pem'])
def test_chain_archive_traversal_is_rejected_before_extraction(tmp_path: Path, name: str) -> None:
    with zipfile.ZipFile(tmp_path / 'chains.zip', 'w') as archive:
        archive.writestr(name, b'untrusted')
    with pytest.raises(ValueError, match='Unsafe'):
        probe.extract_chains(tmp_path)
    assert not list((tmp_path / 'chains').iterdir())


@pytest.mark.parametrize('failure', ['hash', 'downgrade', 'tls'])
def test_source_download_preserves_tls_and_original_hash(tmp_path: Path, monkeypatch, failure: str) -> None:
    class Response(io.BytesIO):
        def geturl(self):
            return 'http://untrusted.invalid/source' if failure == 'downgrade' else 'https://official.invalid/source'

    def open_url(url, *, context, timeout):
        import ssl

        assert context.check_hostname and context.verify_mode == ssl.CERT_REQUIRED
        if failure == 'tls':
            raise ssl.SSLCertVerificationError('untrusted source')
        return Response(b'changed source')

    monkeypatch.setattr(probe.urllib.request, 'urlopen', open_url)
    target = tmp_path / 'source.tar.xz'
    with pytest.raises((ValueError, probe.ssl.SSLCertVerificationError)):
        probe.verified_download({'url': 'https://official.invalid/source', 'name': 'source',
                                 'sha256': hashlib.sha256(b'original').hexdigest()}, target)
    if failure in {'downgrade', 'tls'}:
        assert not target.exists()


@pytest.mark.parametrize('failure', ['foreign', 'openssl', 'missing_backend', 'foreign_plugin'])
def test_native_consumer_rejects_foreign_framework_or_provider(tmp_path: Path, monkeypatch, failure: str) -> None:
    prefix = tmp_path / 'controlled'
    executable = tmp_path / 'consumer.exe'
    modules = [prefix / 'bin/Qt6Core.dll', prefix / 'bin/Qt6Network.dll',
               prefix / 'plugins/tls/qschannelbackend.dll', executable]
    system = tmp_path / 'Windows/System32'
    monkeypatch.setenv('SYSTEMROOT', str(system.parent))
    modules += [system / name for name in ['secur32.dll', 'sspicli.dll', 'crypt32.dll', 'vcruntime140.dll', 'msvcp140.dll']]
    if failure == 'foreign':
        modules[0] = tmp_path / 'other/Qt6Core.dll'
    elif failure == 'openssl':
        modules.append(tmp_path / 'other/libssl-4-x64.dll')
    elif failure == 'foreign_plugin':
        modules.append(tmp_path / 'other/plugins/tls/qcertonlybackend.dll')
    else:
        modules.pop(2)
    with pytest.raises(AssertionError):
        probe.validate_loaded_origins({'loaded_modules': list(map(str, modules)), 'backend': 'schannel',
            'runtime_library': 'Secure Channel, Windows 10.0.26100'}, prefix, executable)


def test_changed_original_contract_does_not_reach_a_build(tmp_path: Path, monkeypatch) -> None:
    scripts = tmp_path / '.github/scripts'
    scripts.mkdir(parents=True)
    (scripts / 'windows_runtime_pilot_sources.json').write_text(json.dumps({'sources': [{
        'name': 'qtbase-everywhere-src-6.12.0.tar.xz', 'sha256': '0' * 64}]}))
    (scripts / 'linux_x64_native_delta_sources.json').write_text(json.dumps({'qt_ca_patch': {}}))
    monkeypatch.setattr(probe, 'REPO', tmp_path)
    with pytest.raises(ValueError, match='Changed qualified Qt original'):
        probe.source_contract()
@pytest.mark.parametrize('failure', ['artifact', 'source', 'digest', 'bytes', 'cpp', 'expired', None])
def test_compiled_replay_rejects_changed_intake_before_binary_execution(monkeypatch, failure) -> None:
    data = b'immutable diagnostic fixture'
    monkeypatch.setattr(probe, 'COMPILED_ZIP_SHA256', hashlib.sha256(data).hexdigest())
    metadata = {'id': probe.COMPILED_ARTIFACT, 'workflow_run': {'id': 43467086435, 'head_sha': probe.COMPILED_SOURCE},
                'expired': False, 'size_in_bytes': len(data), 'digest': 'sha256:' + hashlib.sha256(data).hexdigest()}
    cpp = b'original\r\nconsumer'
    if failure == 'artifact':
        metadata['id'] += 1
    elif failure == 'source':
        metadata['workflow_run']['head_sha'] = '0' * 40
    elif failure == 'digest':
        metadata['digest'] = 'sha256:' + '0' * 64
    elif failure == 'bytes':
        data = b'changed'
    elif failure == 'cpp':
        cpp = b'changed consumer'
    elif failure == 'expired':
        metadata['expired'] = True
    if failure:
        with pytest.raises(ValueError, match='Changed'):
            probe.verify_compiled_intake(metadata, data, cpp, b'original\nconsumer')
    else:
        probe.verify_compiled_intake(metadata, data, cpp, b'original\nconsumer')


@pytest.mark.parametrize('tls', [False, True])
def test_native_schannel_library_is_required_for_tls_not_certificate_input_parsing(tmp_path: Path, tls: bool) -> None:
    prefix = tmp_path / 'private'
    executable = prefix / 'bin/qt_ca_consumer.exe'
    modules = [executable, prefix / 'bin/Qt6Core.dll', prefix / 'bin/Qt6Network.dll',
               prefix / 'plugins/tls/qschannelbackend.dll']
    modules += [tmp_path / 'system' / name for name in ['crypt32.dll', 'vcruntime140.dll', 'msvcp140.dll']]
    result = {'loaded_modules': list(map(str, modules))}
    if tls:
        with pytest.raises(AssertionError):
            probe.validate_loaded_origins(result, prefix, executable, tls=tls)
    else:
        probe.validate_loaded_origins(result, prefix, executable, tls=tls)


def test_rejected_tls_can_release_schannel_library_but_requires_system_sspi(tmp_path: Path, monkeypatch) -> None:
    prefix = tmp_path / 'private'
    system = tmp_path / 'Windows/System32'
    monkeypatch.setenv('SYSTEMROOT', str(system.parent))
    executable = prefix / 'bin/qt_ca_consumer.exe'
    modules = [executable, prefix / 'bin/Qt6Core.dll', prefix / 'bin/Qt6Network.dll',
               prefix / 'plugins/tls/qschannelbackend.dll']
    modules += [system / name for name in ['crypt32.dll', 'secur32.dll', 'sspicli.dll', 'vcruntime140.dll', 'msvcp140.dll']]
    result = {'loaded_modules': list(map(str, modules)), 'backend': 'schannel',
              'runtime_library': 'Secure Channel, Windows 10.0.26100'}
    probe.validate_loaded_origins(result, prefix, executable)
    result['loaded_modules'] = [str(tmp_path / 'foreign/secur32.dll') if p.name == 'secur32.dll' else str(p) for p in modules]
    with pytest.raises(AssertionError, match='Foreign native'):
        probe.validate_loaded_origins(result, prefix, executable)
