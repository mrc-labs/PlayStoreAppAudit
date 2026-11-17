from __future__ import annotations

import subprocess
import sys
from pathlib import Path

import pytest
import reuse_windows_codec_prerequisites as reuse


@pytest.mark.skipif(sys.platform != 'win32', reason='Native Windows extension loading regression')
def test_explicit_codec_loader_replaces_a_cached_builtin_placeholder():
    scripts = Path(__file__).resolve().parents[1] / '.github/scripts'
    code = (
        'import sys,types; from pathlib import Path; import _lzma; native=Path(_lzma.__file__); '
        'sys.path.insert(0,sys.argv[1]); from windows_codec_consumer import load_native_codec; '
        'sys.modules["_lzma"]=types.SimpleNamespace(__spec__="built-in",marker="old"); '
        'actual=load_native_codec("_lzma",native); '
        'assert Path(actual.__file__).resolve()==native.resolve(); '
        'assert not hasattr(actual,"marker"); assert sys.modules["_lzma"] is actual'
    )
    subprocess.run([sys.executable, '-I', '-c', code, str(scripts)], check=True)


def test_changed_compiled_codec_zip_stops_before_extract_or_load(tmp_path):
    with pytest.raises(ValueError, match='Changed original native codec ZIP'):
        reuse.restore(b'changed ZIP', 'arm64', tmp_path)
    assert not list(tmp_path.iterdir())
