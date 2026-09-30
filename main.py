"""Source and standalone entry point for the GUI and explicit headless mode."""

from __future__ import annotations

import sys


def main() -> int:
    if len(sys.argv) > 1 and sys.argv[1] == "cli":
        from playstore_app_audit.cli import main as cli_main

        return cli_main(sys.argv[2:])

    from playstore_app_audit.app import main as gui_main

    return gui_main()

if __name__ == "__main__":
    raise SystemExit(main())
