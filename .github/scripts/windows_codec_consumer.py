"""Exercise exact private native codecs, including Windows' normally built-in zlib."""
from __future__ import annotations

import argparse
import ctypes
import importlib.util
import json
import os
import platform
import sys
import unittest
from importlib.machinery import ExtensionFileLoader
from pathlib import Path


def load_native_codec(name: str, path: Path):
    if name not in {'zlib', '_lzma'} or path.name != name + '.pyd' or not path.is_file():
        raise ValueError('Exact private codec extension required')
    # sys.path alone cannot override a built-in module. This diagnostic child
    # explicitly loads only the closed, architecture-checked source-built file.
    spec = importlib.util.spec_from_file_location(name, path)
    assert spec is not None and isinstance(spec.loader, ExtensionFileLoader)
    module = importlib.util.module_from_spec(spec)
    sys.modules[name] = module
    spec.loader.exec_module(module)
    assert Path(module.__file__).resolve() == path.resolve()
    return module


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--modules', type=Path, required=True)
    parser.add_argument('--stdlib', type=Path, required=True)
    parser.add_argument('--lzma-dll', required=True)
    parser.add_argument('--output', type=Path, required=True)
    args = parser.parse_args()
    assert platform.python_version() == '3.14.10'
    modules = args.modules.resolve()
    handle = os.add_dll_directory(modules)
    assert handle
    zlib = load_native_codec('zlib', modules / 'zlib.pyd')
    lzma_module = load_native_codec('_lzma', modules / '_lzma.pyd')
    assert zlib.ZLIBNG_VERSION == '2.3.3'
    provider = ctypes.WinDLL(str(modules / args.lzma_dll))
    provider.lzma_version_string.restype = ctypes.c_char_p
    assert provider.lzma_version_string() == b'5.8.4'
    sys.path.append(str(args.stdlib))
    suite = unittest.defaultTestLoader.loadTestsFromNames(['test.test_zlib', 'test.test_lzma'])
    result = unittest.TextTestRunner(verbosity=1).run(suite)
    assert result.testsRun > 0
    assert Path(sys.modules['zlib'].__file__).resolve() == Path(zlib.__file__).resolve()
    assert Path(sys.modules['_lzma'].__file__).resolve() == Path(lzma_module.__file__).resolve()
    report = {'source_sha': os.environ.get('GITHUB_SHA'), 'machine': platform.machine(),
              'python': platform.python_version(), 'zlib_module': zlib.__file__,
              'lzma_module': lzma_module.__file__, 'zlib_ng': zlib.ZLIBNG_VERSION,
              'xz': '5.8.4', 'tests': result.testsRun, 'skipped': len(result.skipped),
              'failures': len(result.failures), 'errors': len(result.errors),
              'result': 'PASS' if result.wasSuccessful() else 'FAIL',
              'scope': 'Private source-built codec C wrappers on unchanged same-patch interpreter; no production loader or runtime replacement'}
    args.output.write_text(json.dumps(report, indent=2) + '\n')
    print(json.dumps(report, indent=2))
    sys.exit(not result.wasSuccessful())


if __name__ == '__main__':
    main()
