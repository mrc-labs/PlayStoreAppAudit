from __future__ import annotations

import tomllib
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SPONSOR_URL = "https://github.com/sponsors/mrc-labs"


def test_repository_funding_uses_only_canonical_github_account() -> None:
    assert (ROOT / ".github" / "FUNDING.yml").read_text(encoding="utf-8").strip() == (
        "github: mrc-labs"
    )


def test_sponsorship_metadata_and_readme_placement() -> None:
    project = tomllib.loads((ROOT / "pyproject.toml").read_text(encoding="utf-8"))["project"]
    assert project["urls"]["Sponsor"] == SPONSOR_URL

    readme = (ROOT / "README.md").read_text(encoding="utf-8")
    badge = readme.index("[![GitHub Sponsors]")
    assert badge < readme.index("## What's new")
    assert f"]({SPONSOR_URL})" in readme[badge:readme.index("\n", badge)]
    support = readme.index("## 🍺 Support the project")
    development = readme.index("## Development")
    assert support < development
    assert f"[sponsor the project on GitHub]({SPONSOR_URL})" in readme[support:development]
    assert "No pressure." in readme[support:development]
