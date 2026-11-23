from __future__ import annotations

from pathlib import Path
from types import SimpleNamespace

import prepare_release_legal_bundle as legal
import pytest


@pytest.mark.parametrize("vendor_last", [False, True])
def test_nuitka_licenses_use_distribution_metadata_not_inline_namesakes(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, vendor_last: bool
) -> None:
    package = tmp_path / "installed"
    names = ["LICENSE.txt", "LICENSE-RUNTIME.txt", "NOTICE.txt"]
    own = [Path("nuitka-4.3.5.dist-info/licenses") / name for name in names]
    vendor = Path("nuitka/build/inline_copy/zstd/LICENSE.txt")
    for entry in own:
        path = package / entry
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text("Nuitka original " + path.name, encoding="utf-8")
    (package / vendor).parent.mkdir(parents=True)
    (package / vendor).write_text("Different vendor BSD license", encoding="utf-8")
    entries = [*own, vendor] if vendor_last else [vendor, *own]
    distribution = SimpleNamespace(
        version="4.3.5", files=[p.as_posix() for p in entries],
        locate_file=lambda entry: package / entry,
    )
    monkeypatch.setattr(legal.metadata, "distribution", lambda _: distribution)
    destination = tmp_path / "licenses"

    version, copied = legal._copy_nuitka_legal_files(destination)

    assert version == "4.3.5" and len(copied) == 3
    for name in names:
        assert (destination / "nuitka" / name).read_text() == "Nuitka original " + name


def test_inline_licenses_cannot_satisfy_missing_compiler_license(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    entry = Path("nuitka/build/inline_copy/zstd/LICENSE.txt")
    path = tmp_path / entry
    path.parent.mkdir(parents=True)
    path.write_text("Vendor license", encoding="utf-8")
    distribution = SimpleNamespace(version="4.3.5", files=[entry.as_posix()],
                                   locate_file=lambda item: tmp_path / item)
    monkeypatch.setattr(legal.metadata, "distribution", lambda _: distribution)
    with pytest.raises(RuntimeError, match="Nuitka legal files missing"):
        legal._copy_nuitka_legal_files(tmp_path / "licenses")
