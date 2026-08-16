from __future__ import annotations

from pathlib import Path

script = Path(__file__).with_name("refactor_v012_foundations.py")
source = script.read_text(encoding="utf-8")
old = "updated, count = re.subn(pattern, replacement, text, count=1, flags=flags)"
new = "updated, count = re.subn(pattern, lambda _match: replacement, text, count=1, flags=flags)"
if old not in source:
    raise RuntimeError("Expected regex helper implementation was not found")
source = source.replace(old, new, 1)
namespace = {"__name__": "__main__", "__file__": str(script)}
exec(compile(source, str(script), "exec"), namespace)
