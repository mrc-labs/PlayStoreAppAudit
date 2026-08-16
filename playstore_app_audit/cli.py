from __future__ import annotations

import argparse
from datetime import datetime
from pathlib import Path

from playstore_app_audit.services.audit_engine import AuditConfig, audit_apps, load_apps, write_results


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Controlla disponibilità e ultima data di aggiornamento delle app su Google Play."
    )
    parser.add_argument("input_file", help="CSV, TSV o TXT con i package Android")
    parser.add_argument("--output-dir", default=".", help="Cartella output")
    parser.add_argument("--workers", type=int, default=16, help="Richieste parallele")
    parser.add_argument("--country", default="it", help="Paese principale, es. it o ch")
    parser.add_argument("--language", default="it", help="Lingua principale")
    args = parser.parse_args()
    input_path = Path(args.input_file)
    output_dir = Path(args.output_dir)
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    stem = input_path.stem
    output_file = output_dir / f"{stem}_playstore_audit_{timestamp}.csv"
    problems_file = output_dir / f"{stem}_playstore_problems_{timestamp}.csv"
    apps = load_apps(input_path)
    config = AuditConfig(
        country=args.country.lower(), language=args.language.lower(), max_workers=max(1, args.workers)
    )

    def progress(done: int, total: int, package_name: str) -> None:
        print(f"\rCompletate {done}/{total}: {package_name:<60}", end="", flush=True)

    rows = audit_apps(apps, config, progress)
    print()
    write_results(rows, output_file, problems_file)
    print(f"Output completo: {output_file.resolve()}")
    print(f"Solo problemi:   {problems_file.resolve()}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
