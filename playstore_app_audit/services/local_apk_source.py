from __future__ import annotations

import os
import stat
import threading
from collections.abc import Callable, Iterable
from dataclasses import dataclass
from pathlib import Path


@dataclass(frozen=True, slots=True)
class LocalApkDiscoveryResult:
    paths: tuple[Path, ...]
    root: Path | None = None
    cancelled: bool = False


def normalise_explicit_apks(paths: Iterable[str | Path]) -> tuple[Path, ...]:
    """Return existing standalone APK files once, in deterministic path order."""

    by_key: dict[str, Path] = {}
    for supplied in paths:
        try:
            path = Path(supplied).expanduser().resolve(strict=True)
        except (OSError, RuntimeError):
            continue
        if not path.is_file() or path.suffix.casefold() != ".apk":
            continue
        by_key.setdefault(os.path.normcase(str(path)), path)
    return tuple(by_key[key] for key in sorted(by_key))


def _is_directory_link(entry: os.DirEntry[str]) -> bool:
    if entry.is_symlink():
        return True
    try:
        attributes = getattr(entry.stat(follow_symlinks=False), "st_file_attributes", 0)
    except OSError:
        return True
    return bool(attributes & getattr(stat, "FILE_ATTRIBUTE_REPARSE_POINT", 0))


def discover_folder_apks(
    root: str | Path,
    *,
    cancel_event: threading.Event | None = None,
    progress_callback: Callable[[int, Path], None] | None = None,
) -> LocalApkDiscoveryResult:
    """Enumerate standalone APKs recursively without following directory links."""

    cancelled = cancel_event or threading.Event()
    supplied_root = Path(root).expanduser()
    root_path = supplied_root.absolute()
    if (
        not root_path.is_dir()
        or root_path.is_symlink()
        or root_path.is_junction()
    ):
        return LocalApkDiscoveryResult((), root_path)
    root_path = root_path.resolve(strict=True)

    found: list[Path] = []
    pending = [root_path]
    while pending:
        if cancelled.is_set():
            return LocalApkDiscoveryResult(tuple(found), root_path, True)
        directory = pending.pop()
        try:
            with os.scandir(directory) as iterator:
                entries = sorted(iterator, key=lambda item: os.path.normcase(item.name))
        except OSError:
            continue
        subdirectories: list[Path] = []
        for entry in entries:
            if cancelled.is_set():
                return LocalApkDiscoveryResult(tuple(found), root_path, True)
            try:
                if entry.is_dir(follow_symlinks=False):
                    if not _is_directory_link(entry):
                        subdirectories.append(Path(entry.path))
                elif entry.is_file(follow_symlinks=False) and Path(entry.name).suffix.casefold() == ".apk":
                    found.append(Path(entry.path).resolve(strict=True))
                    if progress_callback is not None:
                        progress_callback(len(found), Path(entry.path))
            except OSError:
                continue
        pending.extend(reversed(subdirectories))
    found.sort(key=lambda path: os.path.normcase(str(path)))
    return LocalApkDiscoveryResult(tuple(found), root_path)
