from __future__ import annotations

import hashlib
from pathlib import Path


def sha256_bytes(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def store_canonical_legal_payload(
    root: Path,
    data: bytes,
) -> tuple[str, str]:
    """Store identical legal payloads exactly once, byte-for-byte."""

    digest = sha256_bytes(data)

    destination = (
        root
        / "qt-third-party"
        / digest
    )

    destination.parent.mkdir(
        parents=True,
        exist_ok=True,
    )

    if destination.exists():
        if destination.read_bytes() != data:
            raise RuntimeError(
                f"Canonical legal payload collision: {digest}"
            )
    else:
        destination.write_bytes(data)

    return (
        destination.relative_to(root.parent).as_posix(),
        digest,
    )