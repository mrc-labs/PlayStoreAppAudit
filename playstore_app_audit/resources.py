"""Packaged runtime resources."""

from __future__ import annotations

import sys
from pathlib import Path

from app_icon import ensure_runtime_icon

CANONICAL_HELP_IMAGE_DIMENSIONS: dict[str, tuple[int, int]] = {
    "store-app-audit-phone-maintenance.png": (1560, 900),
    "store-app-audit-local-apk.png": (1560, 900),
    "store-app-audit-changes-history.png": (820, 720),
    "store-app-audit-mass-rename.png": (1080, 640),
}

CANONICAL_HELP_IMAGE_NAMES = tuple(
    CANONICAL_HELP_IMAGE_DIMENSIONS
)


def _compiled_runtime() -> bool:
    return bool(
        getattr(sys, "frozen", False)
        or globals().get("__compiled__")
    )


def canonical_help_image_path(
    filename: str,
) -> Path:
    """Return one canonical screenshot from source or packaged runtime data."""

    if filename not in CANONICAL_HELP_IMAGE_DIMENSIONS:
        raise KeyError(
            f"Unknown canonical help image: {filename}"
        )

    candidates: list[Path] = []

    if not _compiled_runtime():
        candidates.append(
            Path(__file__).resolve().parents[1]
            / "docs"
            / "images"
            / filename
        )

    executable_dir = (
        Path(sys.executable)
        .resolve()
        .parent
    )

    candidates.extend(
        (
            executable_dir
            / "help-images"
            / filename,
            executable_dir.parent
            / "Resources"
            / "help-images"
            / filename,
        )
    )

    for candidate in candidates:
        if candidate.is_file():
            return candidate.resolve()

    rendered = ", ".join(
        str(candidate)
        for candidate in candidates
    )

    raise FileNotFoundError(
        "Canonical help image is unavailable: "
        f"{filename}. Checked: {rendered}"
    )


def canonical_help_image_uri(
    filename: str,
) -> str:
    return canonical_help_image_path(
        filename
    ).as_uri()


__all__ = [
    "CANONICAL_HELP_IMAGE_DIMENSIONS",
    "CANONICAL_HELP_IMAGE_NAMES",
    "canonical_help_image_path",
    "canonical_help_image_uri",
    "ensure_runtime_icon",
]
