"""Qualify the five private Jammy x64 providers and independent Qt CA policy."""
from __future__ import annotations

import argparse
import ctypes
import datetime as dt
import hashlib
import json
import os
import platform
import re
import shutil
import struct
import sys
import sysconfig
import xml.etree.ElementTree as ET
import zipfile
from pathlib import Path

from inspect_linux_abi import readelf, required_versions, version_floor
from probe_qt_ca_security import trust_rejected

REPO = Path(__file__).resolve().parents[2]
STEMS = {'sqlite': 'libsqlite3.so', 'libmpdec': 'libmpdec.so', 'libffi': 'libffi.so',
         'liblzma': 'liblzma.so', 'zlib': 'libz.so'}
SUITES = ('test_ctypes', 'test_sqlite3', 'test_decimal', 'test_lzma', 'test_zlib')


def provider_paths(paths: set[Path], prefix: Path) -> dict[str, Path]:
    result = {}
    for name, stem in STEMS.items():
        found = {p.resolve() for p in paths if p.name.startswith(stem)}
        if len(found) != 1 or not all(p.is_relative_to(prefix.resolve()) for p in found):
            raise ValueError(f'Missing, ambiguous or foreign {name} provider: {sorted(found)}')
        result[name] = next(iter(found))
    return result


def executed_native_suites(path: Path) -> dict[str, int]:
    counts = dict.fromkeys(SUITES, 0)
    decimal_c = 0
    for case in ET.parse(path).getroot().iter('testcase'):
        if any(case.find(tag) is not None for tag in ('failure', 'error')):
            raise ValueError('Native CPython regression failure/error')
        if case.find('skipped') is not None or case.get('status') == 'notrun':
            continue
        identity = case.get('classname', '') + '.' + case.get('name', '')
        if re.search(r'(?:^|\.)test_decimal\.C\w+\.', identity):
            decimal_c += 1
        for suite in counts:
            if re.search(rf'(?:^|\.){suite}\.', identity):
                counts[suite] += 1
    if not all(counts.values()) or not decimal_c:
        raise ValueError(f'Native CPython suites did not all execute: {counts}')
    counts['test_decimal_C'] = decimal_c
    return counts


def elf_record(path: Path, output: Path) -> dict:
    header = path.read_bytes()[:64]
    assert header[:6] == b'\x7fELF\x02\x01' and struct.unpack_from('<H', header, 18)[0] == 62, path
    needed = required_versions(readelf(path, '--version-info'))
    for stem, ceiling in [('GLIBC_', (2, 35)), ('GLIBCXX_', (3, 4, 29))]:
        maximum = version_floor(needed, stem)
        assert maximum is None or tuple(map(int, maximum[len(stem):].split('.'))) <= ceiling, (path, maximum)
    digest = hashlib.sha256(path.read_bytes()).hexdigest()
    target = output / 'python-native-binaries'
    target.mkdir(exist_ok=True)
    shutil.copy2(path, target / path.name)
    return {'path': str(path), 'sha256': digest, 'machine': 62, 'needed_versions': needed}


def native_measurements(prefix: Path, output: Path, *, cffi: bool, reuse_python_suites: bool = False) -> dict:
    import _ctypes
    import _decimal
    import _lzma
    import _sqlite3
    import sqlite3
    import zlib

    spec = json.loads((REPO / '.github/scripts/linux_x64_native_delta_sources.json').read_text())
    versions = {'sqlite': sqlite3.sqlite_version, 'libmpdec': _decimal.__libmpdec_version__,
                'zlib': zlib.ZLIB_RUNTIME_VERSION}
    with sqlite3.connect(':memory:') as database:
        sqlite_options = sorted(row[0] for row in database.execute('pragma compile_options'))
    assert 'ENABLE_COLUMN_METADATA' in sqlite_options, 'Qt system-SQLite column-origin API missing'
    for name, symbol in [('libffi', 'ffi_get_version'), ('liblzma', 'lzma_version_string')]:
        lib = ctypes.CDLL(str(prefix / 'lib' / STEMS[name]))
        query = getattr(lib, symbol)
        query.restype = ctypes.c_char_p
        versions[name] = query().decode('ascii')
    assert all(versions[name] == spec['expected'][name] for name in STEMS), versions
    paths = {Path(line.split(maxsplit=5)[5]).resolve()
             for line in Path('/proc/self/maps').read_text().splitlines()
             if '/' in line and not line.endswith(' (deleted)')}
    providers = provider_paths(paths, prefix)
    modules = [_ctypes, _decimal, _lzma, _sqlite3, zlib]
    result = {'source_sha': os.environ['GITHUB_SHA'], 'scope': 'Native source runtime/provider delta; not final package',
              'sqlite_compile_options': sqlite_options,
              'versions': versions, 'providers': {name: elf_record(path, output) for name, path in providers.items()},
              'modules': {module.__name__: elf_record(Path(module.__file__).resolve(), output) for module in modules},
              'executed_upstream': executed_native_suites(output / ('reused-python' if reuse_python_suites else '.') / 'cpython-native-regressions.xml')}
    if reuse_python_suites:
        from reuse_linux_python_evidence import evidence

        result['upstream_reused_provenance'] = evidence(output)
        result['reused_upstream'] = result.pop('executed_upstream')
    if cffi:
        import _cffi_backend
        import cffi as cffi_module

        assert _cffi_backend.__version__ == cffi_module.__version__ == spec['expected']['cffi']
        cases = list(ET.parse(output / 'cffi-tests.xml').getroot().iter('testcase'))
        assert cases and not any(any(c.find(tag) is not None for tag in ('failure', 'error')) for c in cases)
        executed = [c for c in cases if c.find('skipped') is None and c.get('status') != 'notrun']
        assert any(c.get('name') == 'test_call_function_9' for c in executed)
        assert any('callback' in c.get('name', '') for c in executed)
        wheels = list((output / 'cffi-wheel').glob('cffi-*.whl'))
        assert len(wheels) == 1
        module = Path(_cffi_backend.__file__).resolve()
        with zipfile.ZipFile(wheels[0]) as archive:
            name = next(n for n in archive.namelist() if n.startswith('_cffi_backend') and n.endswith('.so'))
            assert archive.read(name) == module.read_bytes(), 'Loaded cffi is not the retained project-built wheel'
        result['cffi'] = {'api': cffi_module.__version__, 'tests': len(cases), 'passed': len(executed),
                          'skipped': len(cases) - len(executed), 'module': elf_record(module, output),
                          'wheel': wheels[0].name, 'wheel_sha256': hashlib.sha256(wheels[0].read_bytes()).hexdigest(),
                          'identity': spec['cffi_identity']}
    return result


def qt_manual_verify_regressions(directory: Path) -> list[dict]:
    """Test OpenSSL manual API fixtures; ordinary default trust is measured separately."""
    from PySide6.QtNetwork import QSslCertificate, QSslConfiguration, QSslSocket

    assert QSslSocket.activeBackend() == 'openssl', 'This Linux regression qualifies the OpenSSL manual API only'
    original = QSslConfiguration.defaultConfiguration()
    ca = QSslCertificate.fromData((directory / 'ca.pem').read_bytes())
    assert len(ca) == 1
    rows = []
    try:
        for label, name, hostname, trusted, reason in [
            ('valid', 'valid', 'localhost', True, None),
            ('hostname', 'valid', 'wrong.invalid', True, 'HostNameMismatch'),
            ('expired', 'expired', 'localhost', True, 'CertificateExpired'),
            ('untrusted', 'valid', 'localhost', False, 'trust rejection'),
        ]:
            config = QSslConfiguration(original)
            if trusted:
                config.setCaCertificates(ca)
            QSslConfiguration.setDefaultConfiguration(config)
            chain = QSslCertificate.fromData((directory / (name + '.pem')).read_bytes()) + ca
            errors = QSslCertificate.verify(chain, hostname)
            labels = [error.error().name for error in errors]
            if reason == 'trust rejection':
                assert trust_rejected(labels), (label, labels)
            elif reason:
                assert reason in labels, (label, labels)
            else:
                assert not errors, labels
            assert 'CertificateBlacklisted' not in labels, 'Healthy fixture overblocked'
            rows.append({'fixture': label, 'errors': labels, 'scope': 'Explicit isolated fixture; not default trust'})
    finally:
        QSslConfiguration.setDefaultConfiguration(original)
    assert QSslConfiguration.defaultConfiguration() == original
    return rows


def qt_ca_security(output: Path) -> dict:
    from cryptography import x509
    from cryptography.hazmat.primitives import serialization
    from PySide6.QtCore import QCryptographicHash
    from PySide6.QtNetwork import QSslCertificate, QSslConfiguration, QSslSocket

    assert QSslSocket.setActiveBackend('openssl') and QSslSocket.activeBackend() == 'openssl'
    assert QSslSocket.sslLibraryVersionString().startswith('OpenSSL 4.0.3 ')
    spec = json.loads((REPO / '.github/scripts/provider_ca_security_sources.json').read_text())
    inputs = output / 'provider-security-inputs'
    for item in spec['sources']:
        assert hashlib.sha256((inputs / item['name']).read_bytes()).hexdigest() == item['sha256']
    compromised = json.loads((inputs / 'impacted-intermediates.json').read_text())
    bad_keys = {item['spki_sha256'].lower() for item in compromised}
    assert len(bad_keys) == 8
    guard = json.loads((output / 'qt-ca-patch-provenance.json').read_text())
    assert set(guard['blocked_spki_sha256']) == bad_keys
    key_checks = []
    for item in compromised:
        certificates = QSslCertificate.fromData(item['pem'].encode())
        assert len(certificates) == 1
        certificate = certificates[0]
        assert bytes(certificate.digest(QCryptographicHash.Algorithm.Sha256)).hex() == item['sha256'].lower()
        actual_key = hashlib.sha256(bytes(certificate.publicKey().toDer())).hexdigest()
        assert actual_key == item['spki_sha256'].lower() and certificate.isBlacklisted()
        key_checks.append({'certificate': item['sha256'].lower(), 'spki': actual_key,
                           'blacklisted': True, 'usage': item['usage']})
    roots = QSslConfiguration.systemCaCertificates()
    root_fingerprints = {bytes(c.digest(QCryptographicHash.Algorithm.Sha256)).hex() for c in roots}
    expected_roots = json.loads((inputs / 'roots.json').read_text())
    membership = {root['name']: root['sha256'].lower() in root_fingerprints for root in expected_roots}
    for item in expected_roots:
        controls = QSslCertificate.fromData(item['pem'].encode())
        assert len(controls) == 1 and not controls[0].isBlacklisted(), 'Healthy root overblocked'
    results = []
    now = dt.datetime.now(dt.UTC)
    with zipfile.ZipFile(inputs / 'chains.zip') as archive:
        names = sorted(n for n in archive.namelist() if n.endswith('.pem'))
        assert len(names) == 16
        for name in names:
            data = archive.read(name)
            certificates = x509.load_pem_x509_certificates(data)
            assert all(c.not_valid_before_utc <= now < c.not_valid_after_utc for c in certificates), ('Stale fixture', name)
            keys = [hashlib.sha256(c.public_key().public_bytes(serialization.Encoding.DER,
                    serialization.PublicFormat.SubjectPublicKeyInfo)).hexdigest() for c in certificates]
            assert any(key in bad_keys for key in keys[1:]), name
            hostname = certificates[0].extensions.get_extension_for_class(x509.SubjectAlternativeName).value.get_values_for_type(x509.DNSName)[0]
            assert not hostname.startswith('*'), ('Explicit host fixture required', hostname)
            chain = QSslCertificate.fromData(data)
            assert len(chain) == len(certificates)
            errors = QSslCertificate.verify(chain, hostname)
            labels = [error.error().name for error in errors]
            assert trust_rejected(labels) and 'CertificateBlacklisted' in labels, (name, labels)
            expected_blocked = {bytes(cert.toDer()) for cert, key in zip(chain, keys, strict=True) if key in bad_keys}
            assert len([error for error in errors if error.error().name == 'CertificateBlacklisted']) == len(expected_blocked)
            results.append({'fixture': name, 'hostname': hostname, 'errors': labels,
                            'compromised_key_positions': [i for i, key in enumerate(keys) if key in bad_keys],
                            'sha256': hashlib.sha256(data).hexdigest(), 'result': 'Qt actual-default chain rejection PASS'})
    assert any('rollover/' in row['fixture'] for row in results)
    return {'provider': QSslSocket.activeBackend(), 'library': QSslSocket.sslLibraryVersionString(),
            'manual_backend_regressions': qt_manual_verify_regressions(output / 'isolated-certificates'),
            'project_guard': guard, 'compromised_certificates': key_checks,
            'default_root_fingerprints': sorted(root_fingerprints), 'incident_root_membership': membership,
            'chains': results, 'scope': 'Actual default Qt/OpenSSL chain policy; ordinary authenticated default handshake separately required by full pilot'}


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--prefix', type=Path, required=True)
    parser.add_argument('--output-dir', type=Path, required=True)
    parser.add_argument('--native-only', action='store_true')
    parser.add_argument('--cffi', action='store_true')
    parser.add_argument('--reuse-python-suites', action='store_true')
    args = parser.parse_args()
    assert sys.platform == 'linux' and platform.machine() == 'x86_64'
    assert platform.python_version() == '3.14.10' and not sysconfig.get_config_var('Py_GIL_DISABLED')
    result = native_measurements(args.prefix.resolve(), args.output_dir, cffi=args.cffi,
                                 reuse_python_suites=args.reuse_python_suites)
    if not args.native_only:
        from PySide6.QtWidgets import QApplication

        app = QApplication([])
        assert app.platformName() == 'xcb'
        log = (args.output_dir / 'qt-sqlite-consumer.log').read_text()
        assert 'Qt 6.12.0 actual SQLite 3.54.1' in log and str(args.prefix.resolve() / 'qt/lib') in log
        assert 'table metadata fixture PASS' in log
        result['qt_sqlite'] = {'executed': log.strip(), 'images': [elf_record(path.resolve(), args.output_dir) for path in
            [args.prefix / 'qt/lib/libQt6Sql.so.6', args.prefix / 'qt/plugins/sqldrivers/libqsqlite.so']]}
        result['qt_security'] = qt_ca_security(args.output_dir)
        (args.output_dir / 'qt-ca-security.json').write_text(json.dumps(result['qt_security'], indent=2) + '\n')
    (args.output_dir / 'python-native-results.json').write_text(json.dumps(result, indent=2) + '\n')
    print(json.dumps(result, indent=2), flush=True)


if __name__ == '__main__':
    main()
