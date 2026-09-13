"""Profile cold Local APK parsing without weakening parser safety checks.

Run from the repository root, for example:

    python tools/profile_local_apk_cold_load.py D:\\APK\\Archive

The profiler uses a temporary empty metadata cache. It does not clear or mutate the
normal application cache, and it keeps the parser's second full-file SHA-256
verification enabled. Timings are intended for diagnostic comparison, not as a
stable benchmark contract.
"""

from __future__ import annotations

import argparse
import statistics
import sys
import tempfile
from collections import defaultdict
from contextlib import contextmanager
from pathlib import Path
from time import perf_counter
from typing import Any, Callable, Iterator

_REPO_ROOT = Path(__file__).resolve().parents[1]
if str(_REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(_REPO_ROOT))

import playstore_app_audit.services.local_apk as local_apk  # noqa: E402
import playstore_app_audit.services.local_package_metadata_cache as metadata_cache  # noqa: E402
from playstore_app_audit.services.local_apk_source import discover_folder_apks  # noqa: E402


class PhaseTimings:
    def __init__(self) -> None:
        self.values: dict[str, list[float]] = defaultdict(list)

    def add(self, phase: str, seconds: float) -> None:
        self.values[phase].append(seconds * 1000)

    def sum(self, phase: str) -> float:
        return sum(self.values.get(phase, ()))


@contextmanager
def _timed_parser_phases(timings: PhaseTimings) -> Iterator[None]:
    original_capture = local_apk._capture_snapshot
    original_preflight = local_apk._preflight_zip_structure
    original_read_member = local_apk._read_member_limited
    original_parse_manifest = local_apk._parse_manifest
    original_arsc_parser = local_apk._ARSCParser
    original_verify_sha = local_apk._sha256_stream
    original_cache_lookup = metadata_cache.lookup
    original_candidate_lookup = metadata_cache._has_content_candidate

    def timed(phase: str, function: Callable[..., Any]) -> Callable[..., Any]:
        def wrapper(*args: Any, **kwargs: Any) -> Any:
            started = perf_counter()
            try:
                return function(*args, **kwargs)
            finally:
                timings.add(phase, perf_counter() - started)

        return wrapper

    def timed_read_member(*args: Any, **kwargs: Any) -> Any:
        info = args[1] if len(args) > 1 else kwargs.get("info")
        name = str(getattr(info, "filename", ""))
        phase = (
            "manifest_read"
            if name == "AndroidManifest.xml"
            else "resources_read"
            if name == "resources.arsc"
            else "selected_member_read"
        )
        started = perf_counter()
        try:
            return original_read_member(*args, **kwargs)
        finally:
            timings.add(phase, perf_counter() - started)

    def timed_arsc_parser(*args: Any, **kwargs: Any) -> Any:
        started = perf_counter()
        try:
            return original_arsc_parser(*args, **kwargs)
        finally:
            timings.add("resources_parse", perf_counter() - started)

    local_apk._capture_snapshot = timed("snapshot_sha", original_capture)  # type: ignore[assignment]
    local_apk._preflight_zip_structure = timed("zip_preflight", original_preflight)  # type: ignore[assignment]
    local_apk._read_member_limited = timed_read_member  # type: ignore[assignment]
    local_apk._parse_manifest = timed("manifest_parse", original_parse_manifest)  # type: ignore[assignment]
    local_apk._ARSCParser = timed_arsc_parser  # type: ignore[assignment]
    local_apk._sha256_stream = timed("second_sha_verify", original_verify_sha)  # type: ignore[assignment]
    metadata_cache.lookup = timed("cache_lookup", original_cache_lookup)  # type: ignore[assignment]
    metadata_cache._has_content_candidate = timed(  # type: ignore[assignment]
        "content_candidate_lookup", original_candidate_lookup
    )
    try:
        yield
    finally:
        local_apk._capture_snapshot = original_capture  # type: ignore[assignment]
        local_apk._preflight_zip_structure = original_preflight  # type: ignore[assignment]
        local_apk._read_member_limited = original_read_member  # type: ignore[assignment]
        local_apk._parse_manifest = original_parse_manifest  # type: ignore[assignment]
        local_apk._ARSCParser = original_arsc_parser  # type: ignore[assignment]
        local_apk._sha256_stream = original_verify_sha  # type: ignore[assignment]
        metadata_cache.lookup = original_cache_lookup  # type: ignore[assignment]
        metadata_cache._has_content_candidate = original_candidate_lookup  # type: ignore[assignment]


def _ms(seconds: float) -> str:
    return f"{seconds * 1000:.1f}"


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("folder", type=Path, help="Folder containing local package files")
    parser.add_argument(
        "--limit",
        type=int,
        default=0,
        help="Profile at most this many discovered files; 0 means all files",
    )
    args = parser.parse_args()

    discovery_started = perf_counter()
    discovery = discover_folder_apks(args.folder)
    discovery_seconds = perf_counter() - discovery_started
    paths = list(discovery.paths)
    if args.limit > 0:
        paths = paths[: args.limit]

    print(
        f"Discovery: {len(discovery.paths)} package(s) in {_ms(discovery_seconds)} ms; "
        f"profiling {len(paths)}."
    )
    if not paths:
        return 0

    totals: list[float] = []
    successful = 0
    failed = 0
    timings = PhaseTimings()

    with tempfile.TemporaryDirectory(prefix="playstore_audit_profile_") as temp_dir:
        temporary_cache = Path(temp_dir) / "local_package_metadata.sqlite3"
        original_cache_path = metadata_cache.cache_path
        metadata_cache.cache_path = lambda: temporary_cache  # type: ignore[assignment]
        try:
            with _timed_parser_phases(timings):
                for index, path in enumerate(paths, start=1):
                    started = perf_counter()
                    result, cache_hit = metadata_cache.parse_cached_local_package(path)
                    elapsed = perf_counter() - started
                    totals.append(elapsed * 1000)
                    status = "OK" if result.artifact is not None else "FAIL"
                    successful += int(result.artifact is not None)
                    failed += int(result.failure is not None)
                    print(
                        f"{index:4d}/{len(paths):4d} {elapsed * 1000:9.1f} ms "
                        f"cache={'hit' if cache_hit else 'miss':4s} {status:4s} {path.name}"
                    )
        finally:
            metadata_cache.cache_path = original_cache_path  # type: ignore[assignment]

    print("\nCold-load phase totals")
    ordered_phases = (
        "cache_lookup",
        "content_candidate_lookup",
        "snapshot_sha",
        "zip_preflight",
        "manifest_read",
        "manifest_parse",
        "resources_read",
        "resources_parse",
        "second_sha_verify",
    )
    for phase in ordered_phases:
        values = timings.values.get(phase, [])
        total = sum(values)
        mean = statistics.fmean(values) if values else 0.0
        print(f"  {phase:26s} total={total:10.1f} ms  mean/call={mean:8.1f} ms  calls={len(values)}")

    overall = sum(totals)
    known = sum(timings.sum(phase) for phase in ordered_phases)
    print(f"  {'other parser/SQLite work':26s} total={max(0.0, overall - known):10.1f} ms")
    print(f"  {'all files':26s} total={overall:10.1f} ms")
    print(
        f"\nResult: {successful} successful, {failed} failed. "
        "The normal application metadata cache was not modified."
    )
    return 0 if failed == 0 else 1


if __name__ == "__main__":
    raise SystemExit(main())
