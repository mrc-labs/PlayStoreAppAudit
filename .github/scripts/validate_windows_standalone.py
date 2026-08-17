from __future__ import annotations

import argparse
from collections import defaultdict
from pathlib import Path

REQUIRED_FILES = {
    "qt6core.dll",
    "qt6gui.dll",
    "qt6widgets.dll",
    "qwindows.dll",
}

FORBIDDEN_FILES = {
    "qtvirtualkeyboardplugin.dll",
    "qt6virtualkeyboard.dll",
    "qpdf.dll",
}


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Validate the Windows standalone package layout."
    )
    parser.add_argument(
        "package_dir",
        type=Path,
        help="Standalone package directory to validate.",
    )
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    root = args.package_dir.resolve()

    if not root.is_dir():
        raise SystemExit(f"Package directory does not exist: {root}")

    files = [path for path in root.rglob("*") if path.is_file()]
    by_name: dict[str, list[Path]] = defaultdict(list)
    for path in files:
        by_name[path.name.casefold()].append(path)

    missing = sorted(
        name for name in REQUIRED_FILES if name.casefold() not in by_name
    )
    forbidden = sorted(
        path
        for name in FORBIDDEN_FILES
        for path in by_name.get(name.casefold(), [])
    )

    qtcore_pyd = [
        path
        for path in files
        if path.name.casefold() == "qtcore.pyd"
    ]
    shiboken_runtime = [
        path
        for path in files
        if path.name.casefold() == "shiboken.pyd"
        or (
            path.name.casefold().startswith("shiboken6")
            and path.suffix.casefold() in {".dll", ".pyd"}
        )
    ]

    errors: list[str] = []
    if missing:
        errors.append(
            "Missing required runtime files: " + ", ".join(missing)
        )
    if forbidden:
        errors.append(
            "Forbidden runtime files found:\n  "
            + "\n  ".join(str(path.relative_to(root)) for path in forbidden)
        )
    if not qtcore_pyd:
        errors.append("PySide6 QtCore.pyd was not found.")
    if not shiboken_runtime:
        errors.append("Shiboken runtime was not found.")

    print(f"Validated package root: {root}")
    print(f"Files inspected: {len(files)}")

    for name in sorted(REQUIRED_FILES):
        matches = by_name.get(name.casefold(), [])
        if matches:
            print(
                f"required PASS: {name} -> "
                + ", ".join(str(path.relative_to(root)) for path in matches)
            )

    for name in sorted(FORBIDDEN_FILES):
        if name.casefold() not in by_name:
            print(f"forbidden PASS: {name} is absent")

    if qtcore_pyd:
        print(
            "PySide6 PASS: "
            + ", ".join(str(path.relative_to(root)) for path in qtcore_pyd)
        )
    if shiboken_runtime:
        print(
            "Shiboken PASS: "
            + ", ".join(
                str(path.relative_to(root)) for path in shiboken_runtime
            )
        )

    if errors:
        print("\nStandalone package validation FAILED:")
        for error in errors:
            print(f"- {error}")
        return 1

    print("\nStandalone package validation PASSED.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
