"""CLI runner for the isolated Device Specific resolver PoC."""

from __future__ import annotations

import argparse
import json
from collections.abc import Sequence

from .profiles import (
    list_reference_profiles,
)
from .transport import (
    resolve_package,
)


def _parser(
) -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description=(
            "Experimental metadata-only "
            "Device Specific resolver."
        )
    )

    parser.add_argument(
        "--list-profiles",
        action="store_true",
    )

    parser.add_argument(
        "--package",
    )

    parser.add_argument(
        "--profile",
        dest="profile_id",
    )

    parser.add_argument(
        "--auth-mode",
        choices=(
            "anonymous",
            "authenticated",
        ),
        default="anonymous",
    )

    parser.add_argument(
        "--dispenser-url",
        help=(
            "Explicit Aurora-compatible "
            "dispenser endpoint. "
            "There is deliberately no default."
        ),
    )

    parser.add_argument(
        "--country",
        default="CH",
    )

    parser.add_argument(
        "--language",
        default="en",
    )

    return parser


def main(
    argv: Sequence[str]
    | None = None,
) -> int:
    parser = _parser()

    args = parser.parse_args(
        argv
    )

    if args.list_profiles:
        for profile in (
            list_reference_profiles()
        ):
            print(
                f"{profile.profile_id}: "
                f"{profile.display_name}, "
                f"Android "
                f"{profile.android_release}, "
                f"API {profile.api_level}"
            )

        return 0

    if not args.package:
        parser.error(
            "--package is required "
            "unless --list-profiles is used"
        )

    if not args.profile_id:
        parser.error(
            "--profile is required "
            "unless --list-profiles is used"
        )

    result = resolve_package(
        package_name=args.package,
        profile_id=args.profile_id,
        auth_mode=args.auth_mode,
        country=args.country,
        language=args.language,
        dispenser_url=(
            args.dispenser_url
        ),
    )

    print(
        json.dumps(
            result.to_dict(),
            indent=2,
            ensure_ascii=False,
        )
    )

    return (
        0
        if result.resolved
        else 2
    )


if __name__ == "__main__":
    raise SystemExit(
        main()
    )
