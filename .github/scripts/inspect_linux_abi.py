"""Record requirements of every packaged ELF, including Qt/plugins/extensions.

Version *definitions* are deliberately excluded: a bundled libstdc++ can export
newer versions than the symbols its consumers actually require.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import os
import platform
import re
import subprocess
from pathlib import Path
from typing import Any


def required_versions(version_info: str) -> list[str]:
    """Read only ELF version needs, never version definitions or symbol indexes."""
    needs = version_info.partition("Version needs section")[2]
    return sorted(set(re.findall(r"Name: (\S+)", needs)))


def version_floor(names: list[str], prefix: str) -> str | None:
    numeric = [name for name in names if re.fullmatch(re.escape(prefix) + r"\d+(?:\.\d+)+", name)]
    return max(numeric, key=lambda name: tuple(map(int, name[len(prefix):].split("."))), default=None)


def readelf(path: Path, option: str) -> str:
    return subprocess.run(
        ["readelf", "--wide", option, str(path)], check=True,
        capture_output=True, text=True, timeout=30,
        env={**os.environ, "LC_ALL": "C"},
    ).stdout


def inspect_package(package: Path, arch: str) -> dict[str, Any]:
    expected = {"x64": "Advanced Micro Devices X86-64", "arm64": "AArch64"}[arch]
    records: list[dict[str, Any]] = []
    for path in sorted(package.rglob("*")):
        if not path.is_file():
            continue
        with path.open("rb") as stream:
            if stream.read(4) != b"\x7fELF":
                continue
        header = readelf(path, "--file-header")
        machine_match = re.search(r"Machine:\s*(.+)", header)
        machine = machine_match.group(1).strip() if machine_match else "missing"
        if machine != expected:
            raise RuntimeError(f"Wrong packaged architecture: {path}: {machine}")
        dynamic = readelf(path, "--dynamic")
        program = readelf(path, "--program-headers")
        versions = required_versions(readelf(path, "--version-info"))
        interpreter = re.search(r"Requesting program interpreter:\s*([^\]]+)", program)
        with path.open("rb") as stream:
            digest = hashlib.file_digest(stream, "sha256").hexdigest()
        records.append({
            "path": path.relative_to(package).as_posix(),
            "sha256": digest,
            "machine": machine,
            "interpreter": interpreter.group(1) if interpreter else None,
            "needed": re.findall(r"\(NEEDED\).*?\[(.*?)\]", dynamic),
            "search_paths": re.findall(r"\((?:RPATH|RUNPATH)\).*?\[(.*?)\]", dynamic),
            "required_versions": versions,
            "glibc": version_floor(versions, "GLIBC_"),
            "glibcxx": version_floor(versions, "GLIBCXX_"),
        })
    paths = [record["path"] for record in records]
    for required in ("PlayStoreAppAudit", "libQt6Core.so", "libpyside6", "libshiboken6"):
        if not any(required in path for path in paths):
            raise RuntimeError(f"Required packaged ELF missing: {required}")
    versions = sorted({name for record in records for name in record["required_versions"]})
    return {
        "schema_version": 1, "source_sha": os.environ.get("GITHUB_SHA"),
        "architecture": arch, "inspection_python": platform.python_version(),
        "glibc": version_floor(versions, "GLIBC_"),
        "glibcxx": version_floor(versions, "GLIBCXX_"),
        "note": "Maximum version needs across all ELFs; bundled providers and runtime smoke must also be assessed.",
        "elf_files": records,
    }


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("package", type=Path)
    parser.add_argument("--arch", choices=("x64", "arm64"), required=True)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    report = inspect_package(args.package, args.arch)
    args.output.write_text(json.dumps(report, indent=2) + "\n", encoding="utf-8")
    print(f"{args.arch}: {len(report['elf_files'])} ELF files; {report['glibc']}; {report['glibcxx']}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
