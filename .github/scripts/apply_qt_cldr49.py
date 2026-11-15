"""Generate controlled CLDR49 Qt source with current existing language codes."""
from __future__ import annotations

import argparse
import hashlib
import json
import os
import re
import shutil
import subprocess
import sys
import tarfile
import zipfile
from pathlib import Path

from provision_nuitka_scons import apply_source_patch

REPO = Path(__file__).resolve().parents[2]
CODE_ARRAY = r'constexpr std::array<LanguageCodeEntry, ([0-9]+)> languageCodeList \{.*?\n\};'


def locale_keys(header: str) -> set[tuple[int, int, int]]:
    match = re.search(r'constexpr QLocaleData locale_data\[\] = \{(.*?)\n\};', header, re.S)
    if not match:
        raise ValueError('Missing Qt locale data table')
    return {(int(a), int(b), int(c)) for a, b, c in re.findall(r'^\s*\{\s*(\d+),\s*(\d+),\s*(\d+),', match[1], re.M)}


def qualified_generated(spec: dict) -> tuple[dict, dict[str, bytes]]:
    cache = json.loads((REPO / '.github/scripts/qt_cldr49_generated_cache.json').read_text(encoding='utf-8'))
    actual = hashlib.sha256(json.dumps(spec, sort_keys=True, separators=(',', ':')).encode()).hexdigest()
    if actual != cache['source_contract_canonical_sha256']:
        raise ValueError('Changed CLDR generation contract cannot reuse qualified source')
    path = (REPO / cache['archive']).resolve()
    if not path.is_relative_to((REPO / '.github/sources').resolve()):
        raise ValueError('Qualified CLDR archive escapes source directory')
    raw = path.read_bytes()
    if len(raw) != cache['bytes'] or hashlib.sha256(raw).hexdigest() != cache['sha256']:
        raise ValueError('Changed qualified CLDR source archive')
    files = {}
    with tarfile.open(path) as archive:
        members = archive.getmembers()
        if len(members) != len(spec['generated_files']) or {m.name for m in members} != set(spec['generated_files']):
            raise ValueError('Unexpected qualified CLDR source members')
        for member in members:
            if not member.isfile() or Path(member.name).is_absolute() or '..' in Path(member.name).parts:
                raise ValueError('Unsafe qualified CLDR source member')
            payload = archive.extractfile(member).read()
            if hashlib.sha256(payload).hexdigest() != spec['generated_files'][member.name]:
                raise ValueError('Changed qualified CLDR generated file')
            files[member.name] = payload
    return cache, files


def apply_cldr49(source: Path, archives: Path, evidence: Path, *, reuse_generated: bool = False) -> dict:
    source, archives, evidence = source.resolve(), archives.resolve(), evidence.resolve()
    manifest = REPO / '.github/scripts/qt_cldr49_sources.json'
    spec = json.loads(manifest.read_text(encoding='utf-8'))
    for name, digest in spec['original_files'].items():
        if hashlib.sha256((source / name).read_bytes()).hexdigest() != digest:
            raise ValueError('Changed original Qt locale source: ' + name)
    original = (source / 'src/corelib/text/qlocale_data_p.h').read_text(encoding='utf-8')
    keys = locale_keys(original)
    assert len(keys) == spec['baseline_locale_keys']
    codes = re.search(CODE_ARRAY, original, re.S)
    assert codes and int(codes[1]) == spec['retained_code_records']
    assert hashlib.sha256(codes[0].encode()).hexdigest() == spec['retained_code_sha256']
    cache, prepared = qualified_generated(spec) if reuse_generated else (None, {})
    data = source.parent / 'cldr49-generator-input'
    assert not data.exists(), 'Fresh controlled CLDR input directory required'
    data.mkdir()
    evidence.mkdir(parents=True, exist_ok=True)
    for item in spec['sources']:
        raw = (archives / item['name']).read_bytes()
        if (hashlib.sha256(raw).hexdigest() != item['sha256'] or
                hashlib.sha512(raw).hexdigest() != item['sha512']):
            raise ValueError('Changed official CLDR source: ' + item['name'])
        # Full ISO registry data is deliberately not a maintained build input.
        assert item['name'] in {'cldr-common-49.zip', 'cldr-exemplars-delta-49.zip'}
        with zipfile.ZipFile(archives / item['name']) as archive:
            for name in archive.namelist():
                is_license = Path(name).name.upper().startswith(('LICENSE', 'LICENCE', 'COPYING'))
                if reuse_generated and (name.endswith('/') or not is_license):
                    continue
                target = data / name
                if Path(name).is_absolute() or not target.resolve().is_relative_to(data):
                    raise ValueError('CLDR archive path escape')
                if name.endswith('/'):
                    target.mkdir(parents=True, exist_ok=True)
                    continue
                target.parent.mkdir(parents=True, exist_ok=True)
                target.write_bytes(archive.read(name))
                if is_license:
                    legal = evidence / 'legal/qt-cldr49' / item['name'].removesuffix('.zip') / name
                    legal.parent.mkdir(parents=True, exist_ok=True)
                    legal.write_bytes(archive.read(name))
    for patch in spec['patches']:
        apply_source_patch(source, patch)
        shutil.copy2(REPO / patch['path'], evidence)
    # The original localetools module requires its own parent to be named
    # "qtbase". Versioned source archives use a different folder name. Stage
    # only the unchanged/patched generator and identical version metadata;
    # write generated targets into the explicitly supplied real source tree.
    if reuse_generated:
        for name, payload in prepared.items():
            (source / name).write_bytes(payload)
        shutil.copy2(REPO / '.github/scripts/qt_cldr49_generated_cache.json', evidence)
    else:
        generator = source.parent / 'cldr49-generator-work/qtbase'
        assert not generator.exists(), 'Fresh controlled generator directory required'
        shutil.copytree(source / 'util/locale_database', generator / 'util/locale_database',
                        ignore=shutil.ignore_patterns('__pycache__', '*.pyc'))
        shutil.copy2(source / '.cmake.conf', generator)
        env = {**os.environ, 'PYTHONUTF8': '1', 'PYTHONHASHSEED': '0', 'PSAA_CLDR_DATA_DATE': spec['generated_date']}
        xml = data / 'cldr49.xml'
        commands = [([sys.executable, generator / 'util/locale_database/cldr2qlocalexml.py', data, xml], 'xml'),
                    ([sys.executable, generator / 'util/locale_database/qlocalexml2cpp.py', '--reuse-qt-language-codes',
                      xml, '-', source], 'cpp')]
        for command, label in commands:
            result = subprocess.run(list(map(str, command)), env=env, text=True, encoding='utf-8',
                                    stdout=subprocess.PIPE, stderr=subprocess.STDOUT)
            (evidence / ('qt-cldr49-' + label + '.log')).write_text(result.stdout, encoding='utf-8')
            print('CLDR49', label, 'exit', result.returncode, flush=True)
            if result.returncode:
                print(result.stdout[-5000:], flush=True)
                result.check_returncode()
    generated = {}
    for name, expected in spec['generated_files'].items():
        path = source / name
        # Qt's original text writer uses host newlines. Canonical source bytes
        # preserve all table values and make the same recipe reproducible on six hosts.
        payload = path.read_text(encoding='utf-8').encode()
        if hashlib.sha256(payload).hexdigest() != expected:
            raise ValueError('Non-reproducible Qt CLDR output: ' + name)
        path.write_bytes(payload)
        target = evidence / 'qt-cldr49-selected' / name
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_bytes(payload)
        generated[name] = expected
    current = (source / 'src/corelib/text/qlocale_data_p.h').read_text(encoding='utf-8')
    new_keys = locale_keys(current)
    assert keys <= new_keys and len(new_keys) == spec['generated_locale_keys']
    assert re.search(CODE_ARRAY, current, re.S)[0] == codes[0]
    attribution = source / 'src/corelib/text/qt_attribution.json'
    entries = json.loads(attribution.read_text(encoding='utf-8'), strict=False)
    for entry in entries:
        if entry['Id'] == 'unicode-cldr':
            entry.update(Version='v49', DownloadLocation='https://www.unicode.org/Public/cldr/49/')
    attribution.write_bytes((json.dumps(entries, indent=2) + '\n').encode())
    shutil.copy2(manifest, evidence)
    notice = evidence / 'legal/qt-cldr49/qt-cldr49-provenance.txt'
    notice.parent.mkdir(parents=True, exist_ok=True)
    shutil.copy2(REPO / '.github/legal/qt-cldr49-provenance.txt', notice)
    result = {'source_sha': os.environ.get('GITHUB_SHA'), 'cldr_version': '49',
              'original_locale_keys': len(keys), 'current_locale_keys': len(new_keys), 'removed_locale_keys': 0,
              'unchanged_code_records': int(codes[1]), 'code_sha256': spec['retained_code_sha256'],
              'full_iso_registry_input_or_redistribution': False, 'generated_files': generated,
              'result': 'PASS exact qualified source reuse; native Qt/runtime/package tests remain required' if reuse_generated else 'PASS exact reproducible source generation; actual native Qt/runtime/package tests remain required'}
    if reuse_generated:
        result['qualified_source_reuse'] = cache
    (evidence / 'qt-cldr49-source-provenance.json').write_text(json.dumps(result, indent=2) + '\n', encoding='utf-8')
    return result


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--source', type=Path, required=True)
    parser.add_argument('--archives', type=Path, required=True)
    parser.add_argument('--evidence', type=Path, required=True)
    parser.add_argument('--reuse-generated', action='store_true', help='Reuse only the nine hash-qualified source files; never unverified generated output')
    args = parser.parse_args()
    print(json.dumps(apply_cldr49(args.source, args.archives, args.evidence, reuse_generated=args.reuse_generated), indent=2))


if __name__ == '__main__':
    main()
