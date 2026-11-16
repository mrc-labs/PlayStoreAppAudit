"""Build only the matching image plugin module on an existing controlled Qt SDK."""
from __future__ import annotations

import hashlib
import io
import json
import os
import platform
import shutil
import subprocess
import tarfile
import urllib.request
import zipfile
from pathlib import Path

SOURCE = {
    'name': 'qtimageformats-everywhere-src-6.12.0.tar.xz',
    'url': 'https://download.qt.io/official_releases/qt/6.12/6.12.0/submodules/qtimageformats-everywhere-src-6.12.0.tar.xz',
    'sha256': '0943132b5db8de6b6a7f1d162682173e8763c7ed94e80fd39113292845f67762',
    'provenance': 'https://download.qt.io/official_releases/qt/6.12/6.12.0/submodules/qtimageformats-everywhere-src-6.12.0.tar.xz.meta4',
}
BASE_FORMATS = set(['bmp', 'cur', 'gif', 'icns', 'ico', 'jpeg', 'jpg', 'pbm', 'pgm', 'png', 'ppm', 'svg', 'svgz', 'tga', 'tif', 'tiff', 'wbmp', 'webp', 'xbm', 'xpm'])


def image_consumers(output: Path) -> dict:
    from PySide6.QtCore import QBuffer, QByteArray, QIODevice, qVersion
    from PySide6.QtGui import QColor, QImage, QImageReader, QImageWriter

    assert qVersion() == '6.12.0'
    readers = {bytes(value).decode() for value in QImageReader.supportedImageFormats()}
    writers = {bytes(value).decode() for value in QImageWriter.supportedImageFormats()}
    assert readers >= BASE_FORMATS, ('Missing existing image format', sorted(BASE_FORMATS - readers))
    rows = []
    for kind in ['webp', 'tiff', 'png', 'ico', 'bmp']:
        assert kind in writers
        image = QImage(16, 16, QImage.Format.Format_ARGB32)
        image.fill(QColor('#ba2519'))
        # QBuffer owns its storage; a borrowed QByteArray can be destroyed before
        # the previous codec/device when the loop replaces Python references.
        buffer = QBuffer()
        assert buffer.open(QIODevice.OpenModeFlag.WriteOnly)
        writer = QImageWriter(buffer, kind.encode())
        writer.setQuality(75 if kind == 'webp' else 100)
        assert writer.write(image), (kind, writer.errorString())
        del writer
        data = bytes(buffer.data())
        buffer.close()
        encoded = QBuffer()
        encoded.setData(QByteArray(data))
        assert encoded.open(QIODevice.OpenModeFlag.ReadOnly)
        reader = QImageReader(encoded, QByteArray(kind.encode()))
        reader.setAutoDetectImageFormat(False)
        decoded = reader.read()
        del reader
        encoded.close()
        assert not decoded.isNull() and decoded.size() == image.size(), kind
        assert decoded.pixelColor(8, 8).alpha() == 255, kind
        if kind != 'webp':
            assert decoded.pixelColor(8, 8) == image.pixelColor(8, 8), kind
        invalid = QBuffer()
        invalid.setData(QByteArray(b'not an encoded image'))
        assert invalid.open(QIODevice.OpenModeFlag.ReadOnly)
        rejection = QImageReader(invalid, QByteArray(kind.encode()))
        rejection.setAutoDetectImageFormat(False)
        assert rejection.read().isNull(), kind
        del rejection
        invalid.close()
        (output / ('roundtrip.' + kind)).write_bytes(data)
        rows.append({'format': kind, 'encoded_bytes': len(data), 'size': [decoded.width(), decoded.height()],
                     'result': 'native encode/decode and invalid input rejection PASS'})
    report = {'source_sha': os.environ.get('GITHUB_SHA'), 'readers': sorted(readers), 'writers': sorted(writers), 'cases': rows,
              'scope': 'Existing image format preservation; not an exploit corpus or final package acceptance'}
    (output / 'image-format-consumers.json').write_text(json.dumps(report, indent=2) + '\n')
    return report


def restore_intel_overlay(work: Path, output: Path) -> dict:
    from download_diagnostic_artifact import fetch_artifact

    spec = json.loads((Path(__file__).parent / 'macos_x64_imageformats_overlay.json').read_text())
    metadata, data = fetch_artifact(spec['artifact'])
    assert not metadata['expired'] and metadata['workflow_run']['head_sha'] == spec['source_sha']
    assert metadata['workflow_run']['id'] == spec['run'] and metadata['workflow_run']['head_repository_id'] == 1334403620
    assert len(data) == spec['zip_bytes'] and hashlib.sha256(data).hexdigest() == spec['zip_sha256']
    with zipfile.ZipFile(io.BytesIO(data)) as original:
        raw = original.read('imageformats/module-provenance.json')
        assert hashlib.sha256(raw).hexdigest() == spec['provenance_sha256']
        provenance = json.loads(raw)
        assert provenance['source_sha'] == spec['source_sha'] and provenance['source'] == SOURCE
        overlay = provenance['installed_module']
        assert overlay['original_work_root'] == str(work)
        payload = original.read('imageformats/installed-module.tar.zst')
        assert hashlib.sha256(payload).hexdigest() == overlay['sha256'] == spec['overlay_sha256']
        with tarfile.open(fileobj=io.BytesIO(payload)) as bundle:
            members = bundle.getmembers()
            assert len(members) == len(overlay['paths']) and {m.name for m in members} == set(overlay['paths'])
            for member in members:
                assert member.isfile() and member.name.startswith('prefix/qt/') and '..' not in Path(member.name).parts
                assert not (work / member.name).exists(), ('Do not overwrite original Qt SDK bytes', member.name)
            bundle.extractall(work, filter='data')
        for name, entry in overlay['paths'].items():
            path = work / name
            assert path.is_file() and not path.is_symlink() and path.resolve().is_relative_to(work)
            assert path.stat().st_size == entry['bytes'] and hashlib.sha256(path.read_bytes()).hexdigest() == entry['sha256']
        evidence = output / 'imageformats'
        evidence.mkdir()
        (evidence / 'module-provenance.json').write_bytes(raw)
        (evidence / 'installed-module.tar.zst').write_bytes(payload)
        (output / 'sources').mkdir(exist_ok=True)
        source = original.read('sources/' + SOURCE['name'])
        assert hashlib.sha256(source).hexdigest() == SOURCE['sha256']
        (output / 'sources' / SOURCE['name']).write_bytes(source)
    (evidence / 'overlay-intake.json').write_text(json.dumps({'original': spec,
        'verified_paths': len(overlay['paths']), 'scope': 'Unchanged matching module build only; original whole pilot failed in GUI. Native decoder/GUI/ABI acceptance remains required.'}, indent=2))
    return provenance


def complete(work: Path, output: Path, cmake_arguments: list[str]) -> dict:
    """Caller supplies its already-qualified native compiler/ABI arguments."""
    assert cmake_arguments, 'Explicit native compiler/ABI profile required'
    prefix = work / 'prefix'
    assert (prefix / 'qt/lib/cmake/Qt6/Qt6Config.cmake').is_file()
    evidence = output / 'imageformats'
    evidence.mkdir()
    sources = output / 'sources'
    sources.mkdir(exist_ok=True)
    archive = sources / SOURCE['name']
    if not archive.exists():
        with urllib.request.urlopen(SOURCE['url'], timeout=180) as response, archive.open('wb') as stream:
            shutil.copyfileobj(response, stream)
    assert hashlib.sha256(archive.read_bytes()).hexdigest() == SOURCE['sha256']
    src = work / 'imageformats-source'
    src.mkdir()
    with tarfile.open(archive) as bundle:
        bundle.extractall(src, filter='data')
    source = src / 'qtimageformats-everywhere-src-6.12.0'
    build = work / 'imageformats-build'
    build.mkdir()
    wrapper = prefix / ('qt/bin/qt-configure-module.bat' if platform.system() == 'Windows' else 'qt/bin/qt-configure-module')
    configure = (['cmd', '/d', '/c', str(wrapper)] if platform.system() == 'Windows' else [str(wrapper)])
    commands = [configure + [str(source), '--', '-DCMAKE_BUILD_TYPE=Release', '-DINPUT_tiff=qt', '-DINPUT_webp=qt', '-DINPUT_jasper=no', '-DINPUT_mng=no',
                 '-DCMAKE_PREFIX_PATH=' + ';'.join(str(prefix / child) for child in ['qt', '.', 'openssl']),
                 '-DZLIB_ROOT=' + str(prefix), *cmake_arguments],
                ['cmake', '--build', str(build), '--parallel', '2'], ['cmake', '--install', str(build)]]
    for number, command in enumerate(commands):
        with (evidence / f'command-{number}.log').open('w') as log:
            result = subprocess.run(command, cwd=build, stdout=log, stderr=subprocess.STDOUT, timeout=1800)
        if result.returncode:
            print((evidence / f'command-{number}.log').read_text(errors='replace')[-6000:], flush=True)
        result.check_returncode()
    shutil.copy2(build / 'CMakeCache.txt', evidence / 'CMakeCache.txt')
    cache = (build / 'CMakeCache.txt').read_text()
    assert 'INPUT_tiff:STRING=qt' in cache and 'INPUT_webp:STRING=qt' in cache
    plugins = [path for path in (prefix / 'qt/plugins/imageformats').iterdir()
               if path.suffix in {'.dll', '.so', '.dylib'} and any(stem in path.name for stem in ['qtiff', 'qwebp', 'qtga', 'qwbmp', 'qicns'])]
    assert len(plugins) == 5, plugins
    report = {'source_sha': os.environ['GITHUB_SHA'], 'source': SOURCE, 'source_patch': None,
              'compiled_module_only': 'QtImageFormats6.12.0; original QtBase/Python/OpenSSL/bindings untouched',
              'native_arguments': cmake_arguments, 'plugins': {str(p): hashlib.sha256(p.read_bytes()).hexdigest() for p in plugins},
              'parent_vendor_providers': {'libtiff': '4.7.2', 'libwebp': '1.6.0'},
              'scope': 'Supported matching module build. Caller must still verify native loaded origins/architecture/ABI and actual image consumers.'}
    installed = sorted(set((build / 'install_manifest.txt').read_text().splitlines()))
    overlay = evidence / 'installed-module.tar.zst'
    index = {}
    with tarfile.open(overlay, 'w:zst') as bundle:
        for name in installed:
            path = Path(name)
            assert path.is_relative_to(prefix) and path.resolve().is_relative_to(prefix), name
            relative = path.relative_to(work).as_posix()
            bundle.add(path, arcname=relative, recursive=False)
            index[relative] = ({'link': os.readlink(path)} if path.is_symlink() else
                               {'bytes': path.stat().st_size, 'sha256': hashlib.sha256(path.read_bytes()).hexdigest()})
    report['installed_module'] = {'archive': overlay.name, 'sha256': hashlib.sha256(overlay.read_bytes()).hexdigest(),
                                  'original_work_root': str(work), 'paths': index}
    (evidence / 'module-provenance.json').write_text(json.dumps(report, indent=2) + '\n')
    return report
