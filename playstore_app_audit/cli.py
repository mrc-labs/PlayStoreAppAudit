"""Scriptable, Qt-independent audit entry point."""

from __future__ import annotations

import argparse
import io
import json
import os
import re
import signal
import sys
import tempfile
import threading
from pathlib import Path
from typing import TextIO

from playstore_app_audit.services import (
    device_specific_settings,
    presentation,
    re_audit,
    result_csv,
    result_json,
    state,
)
from playstore_app_audit.services.headless_audit import AuditSource, InvalidAuditInput, run_audit

EXIT_SUCCESS = 0
EXIT_INVALID = 2
EXIT_RUNTIME = 3
EXIT_INTERRUPTED = 130


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="playstore-app-audit-cli",
        description="Audit Android packages without the Qt interface.",
    )
    operation = parser.add_subparsers(dest="operation", required=True)
    audit = operation.add_parser("audit", help="Run one headless audit")
    source = audit.add_subparsers(dest="source", required=True)
    source.add_parser("app-list", help="Audit a CSV, TSV, or TXT package list").add_argument("path", type=Path)
    source.add_parser("apk-files", help="Audit explicit APK/APKS/APKM/XAPK files").add_argument(
        "paths", nargs="+", type=Path
    )
    source.add_parser("apk-folder", help="Discover and audit package files in a folder").add_argument(
        "path", type=Path
    )
    phone = source.add_parser("phone", help="Audit one authorised connected phone")
    phone.add_argument("--include-system", action="store_true", help="Include system packages")
    for subparser in source.choices.values():
        subparser.add_argument("--country", help="Two-letter Google Play country")
        subparser.add_argument("--language", help="Store language or auto")
        subparser.add_argument("--workers", type=int, help="Concurrent Store workers (1-32)")
        subparser.add_argument("--fresh", action="store_true", help="Bypass healthy Store result cache")
        subparser.add_argument("--format", choices=("json", "csv"), default="json")
        subparser.add_argument("--output", type=Path, help="Output file; omit for stdout")
        subparser.add_argument("--force", action="store_true", help="Replace an existing output file")
        subparser.add_argument(
            "--device-provider", choices=tuple(provider.value for provider in device_specific_settings.DeviceSpecificProvider),
            help="Device Specific provider",
        )
        subparser.add_argument("--device-profile", help="Built-in or saved Personal Device profile ID")
        subparser.add_argument("--device-endpoint", help="Validated Custom Dispenser endpoint")
    return parser


def _source(args: argparse.Namespace) -> AuditSource:
    if args.source == "app-list":
        return AuditSource("app_list", path=args.path)
    if args.source == "apk-files":
        return AuditSource("local_files", files=tuple(args.paths))
    if args.source == "apk-folder":
        return AuditSource("local_folder", path=args.path)
    return AuditSource("phone", include_system=args.include_system)


def _validate(args: argparse.Namespace, source: AuditSource) -> None:
    if args.country and not re.fullmatch(r"[A-Za-z]{2}", args.country):
        raise InvalidAuditInput("Country must be a two-letter code.")
    if args.language and not re.fullmatch(r"auto|[A-Za-z]{2,3}(?:[-_][A-Za-z]{2})?", args.language, re.I):
        raise InvalidAuditInput("Language must be a language code or auto.")
    if args.workers is not None and not 1 <= args.workers <= 32:
        raise InvalidAuditInput("Workers must be between 1 and 32.")
    if args.force and args.output is None:
        raise InvalidAuditInput("--force requires --output.")
    if args.device_endpoint and args.device_provider not in (None, "custom_dispenser"):
        raise InvalidAuditInput("A Device Specific endpoint requires the Custom Dispenser provider.")
    if source.kind == "app_list" and (source.path is None or not source.path.is_file()):
        raise InvalidAuditInput("The App List input file does not exist.")
    if source.kind == "local_folder" and (source.path is None or not source.path.is_dir()):
        raise InvalidAuditInput("The Local APK folder does not exist.")
    if source.kind == "local_files" and not source.files:
        raise InvalidAuditInput("At least one local package file is required.")
    if args.output is not None:
        target = args.output.expanduser().resolve()
        inputs = (source.path,) if source.path is not None else source.files
        if any(path is not None and path.expanduser().resolve() == target for path in inputs):
            raise InvalidAuditInput("Output must differ from the input.")
        if target.exists() and not args.force:
            raise InvalidAuditInput("Output already exists; pass --force to replace it.")
        if not target.parent.is_dir():
            raise InvalidAuditInput("The output directory does not exist.")


def _render(rows: list[dict[str, object]], context: dict[str, object], settings: dict[str, object], format_name: str, handle: TextIO) -> None:
    if format_name == "json":
        document = result_json.build_results_document(rows, context={
            **context, "audit_policy": re_audit.policy_context(settings),
        })
        json.dump(document, handle, ensure_ascii=False, indent=2)
        handle.write("\n")
    else:
        result_csv.write_csv(
            handle, rows, date_style=str(settings.get("date_format") or presentation.DEFAULT_DATE_FORMAT)
        )


def _write_output(
    path: Path, rows: list[dict[str, object]], context: dict[str, object],
    settings: dict[str, object], format_name: str, *, force: bool,
    cancel_event: threading.Event,
) -> None:
    target = path.expanduser().resolve()
    temporary: Path | None = None
    try:
        with tempfile.NamedTemporaryFile(
            mode="w", encoding="utf-8-sig" if format_name == "csv" else "utf-8",
            newline="", dir=target.parent, prefix=f".{target.name}.", suffix=".tmp",
            delete=False,
        ) as handle:
            temporary = Path(handle.name)
            _render(rows, context, settings, format_name, handle)
            handle.flush()
            os.fsync(handle.fileno())
        if target.exists() and not force:
            raise InvalidAuditInput("Output already exists; pass --force to replace it.")
        if cancel_event.is_set():
            raise InterruptedError("Audit output was cancelled.")
        os.replace(temporary, target)
    finally:
        if temporary is not None:
            temporary.unlink(missing_ok=True)


def main(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    source = _source(args)
    cancelled = threading.Event()
    previous_handler = None
    try:
        _validate(args, source)
        settings = state.load_settings(persist_migrations=False)
        if args.device_provider is not None:
            settings[device_specific_settings.SETTING_PROVIDER] = args.device_provider
        if args.device_profile is not None:
            settings[device_specific_settings.SETTING_PROFILE_ID] = args.device_profile
        if args.device_endpoint is not None:
            settings[device_specific_settings.SETTING_ENDPOINT] = args.device_endpoint
        if (args.device_profile or args.device_endpoint) and (
            device_specific_settings.provider_from_settings(settings)
            is device_specific_settings.DeviceSpecificProvider.DISABLED
        ):
            raise InvalidAuditInput("Device Specific options require an enabled provider.")
        explicit_device_options = any(value is not None for value in (
            args.device_provider, args.device_profile, args.device_endpoint,
        ))
        if args.device_endpoint is not None and (
            device_specific_settings.provider_from_settings(settings)
            is not device_specific_settings.DeviceSpecificProvider.CUSTOM_DISPENSER
        ):
            raise InvalidAuditInput("A Device Specific endpoint requires the Custom Dispenser provider.")

        def interrupt(_signum: int, _frame: object) -> None:
            cancelled.set()
            print("Cancellation requested; finishing active operations...", file=sys.stderr)

        if threading.current_thread() is threading.main_thread():
            previous_handler = signal.signal(signal.SIGINT, interrupt)

        def progress(done: int, total: int, _item: str) -> None:
            print(f"Progress: {done}/{total}", file=sys.stderr)

        rows, context = run_audit(
            source, settings, cancelled,
            country=args.country, language=args.language, workers=args.workers,
            fresh=args.fresh, progress=progress,
            validate_device_options=explicit_device_options,
        )
        if cancelled.is_set():
            return EXIT_INTERRUPTED
        if args.output is None:
            buffer = io.StringIO()
            _render(rows, context, settings, args.format, buffer)
            if cancelled.is_set():
                return EXIT_INTERRUPTED
            sys.stdout.write(buffer.getvalue())
        else:
            _write_output(
                args.output, rows, context, settings, args.format,
                force=args.force, cancel_event=cancelled,
            )
        print(f"Audit complete: {len(rows)} result(s).", file=sys.stderr)
        return EXIT_SUCCESS
    except (InvalidAuditInput, FileNotFoundError, ValueError):
        if cancelled.is_set():
            return EXIT_INTERRUPTED
        print("Invalid audit input or configuration. Check paths and options.", file=sys.stderr)
        return EXIT_INVALID
    except Exception:
        if cancelled.is_set():
            return EXIT_INTERRUPTED
        print("Audit failed. No final output was written.", file=sys.stderr)
        return EXIT_RUNTIME
    finally:
        if previous_handler is not None:
            signal.signal(signal.SIGINT, previous_handler)


if __name__ == "__main__":
    raise SystemExit(main())
