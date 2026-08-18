from __future__ import annotations

from pathlib import Path

import prepare_release_legal_bundle as legal


def test_source_availability_points_to_release_wide_checksum(
    tmp_path: Path,
) -> None:
    bundle = {
        "filename": "PlayStoreAppAudit-v1.3.0-third-party-sources.tar.xz",
        "sha256": "a" * 64,
        "size": 123,
    }

    legal._write_source_availability(
        tmp_path,
        "1.3.0",
        "v1.3.0",
        bundle,
    )

    text = (tmp_path / "SOURCE-AVAILABILITY.md").read_text(
        encoding="utf-8"
    )

    assert bundle["filename"] in text
    assert "SHA256SUMS.txt" in text
    assert bundle["sha256"] not in text
