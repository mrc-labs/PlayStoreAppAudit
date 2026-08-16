from __future__ import annotations

from pathlib import Path

import refactor_behavior_hooks as migration

ROOT = Path(__file__).resolve().parents[1]
_original_replace_once = migration.replace_once


def tolerant_replace_once(relative: str, old: str, new: str) -> None:
    if "Development assistance: OpenAI ChatGPT" not in old:
        _original_replace_once(relative, old, new)
        return
    path = ROOT / relative
    text = path.read_text(encoding="utf-8")
    if old in text:
        path.write_text(text.replace(old, new, 1), encoding="utf-8")
        return
    # Earlier UI layers used slightly different HTML line breaks. Remove the
    # attribution line regardless of that cosmetic variant.
    lines = [
        line
        for line in text.splitlines(keepends=True)
        if "Development assistance: OpenAI ChatGPT" not in line
    ]
    path.write_text("".join(lines), encoding="utf-8")


migration.replace_once = tolerant_replace_once
migration.main()

# Ensure no retired development-assistance attribution survives in any Qt UI
# layer, including an inherited About implementation that the final UI no
# longer calls directly.
for path in (ROOT / "playstore_app_audit" / "ui").glob("*.py"):
    text = path.read_text(encoding="utf-8")
    if "Development assistance: OpenAI ChatGPT" in text:
        text = "".join(
            line
            for line in text.splitlines(keepends=True)
            if "Development assistance: OpenAI ChatGPT" not in line
        )
        path.write_text(text, encoding="utf-8")

print("Behavior-hook refactor wrapper completed.")
