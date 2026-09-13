from __future__ import annotations

import csv
import html
import re
from pathlib import Path

import pytest

from playstore_app_audit.domain.alternative_distribution import (
    AlternativeDistributionResult,
    AlternativeDistributionState,
)
from playstore_app_audit.services import alternative_distribution, device_insights, result_json
from playstore_app_audit.ui import base_window


def _row(
    package_name: str,
    *,
    device_change: str | None,
    play_status: str = "available",
    criticality: str = "Recent",
    criticality_key: str = "green",
    health_score: int = 100,
) -> dict[str, object]:
    row: dict[str, object] = {
        "app_name": f"App {package_name}",
        "package_name": package_name,
        "play_status": play_status,
        "criticality": criticality,
        "criticality_key": criticality_key,
        "health_score": health_score,
    }
    if device_change is not None:
        row["device_change"] = device_change
    return row


def _html_table(path: Path) -> list[dict[str, str]]:
    rendered = path.read_text(encoding="utf-8")
    header_match = re.search(r"<thead><tr>(.*?)</tr></thead>", rendered, re.DOTALL)
    body_match = re.search(r"<tbody>(.*?)</tbody>", rendered, re.DOTALL)
    assert header_match is not None and body_match is not None

    def cells(fragment: str, tag: str) -> list[str]:
        values = re.findall(rf"<{tag}>(.*?)</{tag}>", fragment, re.DOTALL)
        return [
            " ".join(html.unescape(re.sub(r"<[^>]+>", "", value)).split())
            for value in values
        ]

    headers = cells(header_match.group(1), "th")
    return [
        dict(zip(headers, cells(row_html, "td"), strict=True))
        for row_html in re.findall(r"<tr[^>]*>(.*?)</tr>", body_match.group(1), re.DOTALL)
    ]


@pytest.mark.parametrize(
    ("device_change", "expected"),
    [
        ("Same", "Same"),
        ("Installer changed", "Installer changed"),
        ("Version changed", "Version changed"),
        ("New on device", "New on device"),
        (None, ""),
    ],
    ids=("no-change", "installer-changed", "version-changed", "newly-installed", "normal-empty"),
)
def test_html_exports_device_inventory_change(
    tmp_path: Path, device_change: str | None, expected: str
) -> None:
    target = device_insights.write_html_report(
        tmp_path / "report.html",
        [_row("com.example.app", device_change=device_change)],
    )

    exported = _html_table(target)

    assert exported[0]["Device App Inventory Change"] == expected


def test_html_escapes_device_inventory_change(tmp_path: Path) -> None:
    unsafe = 'Installer changed <script>alert("x")</script> & checked'
    target = device_insights.write_html_report(
        tmp_path / "report.html",
        [_row("com.example.escape", device_change=unsafe)],
    )
    rendered = target.read_text(encoding="utf-8")

    assert unsafe not in rendered
    assert "&lt;script&gt;alert(&quot;x&quot;)&lt;/script&gt; &amp; checked" in rendered
    assert _html_table(target)[0]["Device App Inventory Change"] == unsafe


def test_csv_json_html_exports_have_semantic_parity(tmp_path: Path) -> None:
    provider = AlternativeDistributionResult(
        provider_id="fdroid_main",
        provider_name="F-Droid main repository",
        queried_package_id="com.example.removed",
        state=AlternativeDistributionState.AVAILABLE,
        listing_url="https://f-droid.org/packages/com.example.removed/",
        checked_at="2026-09-09T10:00:00Z",
        provenance="cache",
        reason="Deterministic export-parity evidence.",
    ).to_mapping()
    rows = [
        _row("com.example.current", device_change="Same"),
        {
            **_row(
                "com.example.removed",
                device_change="Installer changed",
                play_status="not_found_in_checked_countries",
                criticality="Not Found",
                criticality_key="red",
                health_score=50,
            ),
            alternative_distribution.ROW_FIELD: [provider],
        },
        _row(
            "com.example.other",
            device_change="Version changed",
            play_status="multi_country_check_inconclusive",
            criticality="Anomaly",
            criticality_key="blue",
            health_score=85,
        ),
    ]

    csv_path = tmp_path / "results.csv"
    with csv_path.open("w", newline="", encoding="utf-8-sig") as handle:
        writer = csv.DictWriter(
            handle,
            fieldnames=base_window.EXPORT_FIELDS,
            extrasaction="ignore",
        )
        writer.writeheader()
        writer.writerows(rows)
    with csv_path.open(newline="", encoding="utf-8-sig") as handle:
        csv_rows = list(csv.DictReader(handle))

    json_rows = result_json.build_results_document(rows)["results"]
    html_path = device_insights.write_html_report(tmp_path / "results.html", rows)
    html_rows = _html_table(html_path)

    expected_packages = [row["package_name"] for row in rows]
    assert [row["package_name"] for row in csv_rows] == expected_packages
    assert [row["package_name"] for row in json_rows] == expected_packages
    assert [row["Package"] for row in html_rows] == expected_packages

    expected_changes = ["Same", "Installer changed", "Version changed"]
    assert [row["device_change"] for row in csv_rows] == expected_changes
    assert [row["device_change"] for row in json_rows] == expected_changes
    assert [row["Device App Inventory Change"] for row in html_rows] == expected_changes

    assert [int(row["health_score"]) for row in csv_rows] == [100, 50, 85]
    assert [row["health_score"] for row in json_rows] == [100, 50, 85]
    assert [row["Maintenance Score"].split("/100", 1)[0] for row in html_rows] == [
        "100",
        "50",
        "85",
    ]

    expected_store_statuses = [
        "available",
        "not_found_in_checked_countries",
        "multi_country_check_inconclusive",
    ]
    assert [row["play_status"] for row in csv_rows] == expected_store_statuses
    assert [row["play_status"] for row in json_rows] == expected_store_statuses
    assert [row["Store Status"] for row in html_rows] == [
        "Recent",
        "Not Found",
        "Anomaly",
    ]

    assert alternative_distribution.ROW_FIELD not in base_window.EXPORT_FIELDS
    assert json_rows[1]["alternative_distribution"]["providers"][0]["provider_id"] == "fdroid_main"
    assert "F-Droid main repository" in html_path.read_text(encoding="utf-8")
