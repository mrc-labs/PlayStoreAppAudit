from __future__ import annotations

import json
import threading
import time
from dataclasses import dataclass
from datetime import UTC, datetime

import pytest

import playstore_app_audit.services.alternative_distribution as alternative
from playstore_app_audit.domain.alternative_distribution import (
    AlternativeDistributionResult,
    AlternativeDistributionState,
)


@dataclass
class FakeProvider:
    provider_id: str
    provider_name: str
    state: AlternativeDistributionState = AlternativeDistributionState.AVAILABLE
    cache_namespace: str = "fake"
    calls: int = 0

    def check(self, package_id: str, *, timeout: float) -> AlternativeDistributionResult:
        del timeout
        self.calls += 1
        return AlternativeDistributionResult(
            provider_id=self.provider_id,
            provider_name=self.provider_name,
            queried_package_id=package_id,
            state=self.state,
            checked_at=datetime.now(UTC).isoformat(),
            provenance="live",
        )


def _rows() -> list[dict[str, str]]:
    return [
        {"package_name": "eligible.one", "play_status": "not_found_in_checked_countries"},
        {"package_name": "available", "play_status": "available"},
        {"package_name": "regional", "play_status": "available_in_other_country"},
        {"package_name": "unknown", "play_status": "multi_country_check_inconclusive"},
    ]


def _run(rows, providers, cache_file, **kwargs):
    pause = kwargs.pop("pause_event", None)
    if pause is None:
        pause = threading.Event()
        pause.set()
    return alternative.run_alternative_distribution_phase(
        rows,
        {},
        pause_event=pause,
        cancel_event=kwargs.pop("cancel_event", threading.Event()),
        providers=providers,
        cache_file=cache_file,
        **kwargs,
    )


def test_only_exact_google_play_not_found_is_eligible(tmp_path) -> None:
    provider = FakeProvider("fdroid_main", "F-Droid")
    rows = _rows()

    _run(rows, [provider], tmp_path / "cache.json")

    assert provider.calls == 1
    assert alternative.ROW_FIELD in rows[0]
    assert all(alternative.ROW_FIELD not in row for row in rows[1:])


def test_disabled_and_unconfigured_providers_are_skipped_without_row_noise(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    settings = {
        "alternative_distribution": {
            "fdroid_main": {"enabled": False},
            "aptoide": {"enabled": True, "store_name": "", "api_key_protected": ""},
        }
    }
    rows = _rows()

    issues = alternative.run_alternative_distribution_phase(
        rows,
        settings,
        pause_event=threading.Event(),
        cancel_event=threading.Event(),
    )

    assert issues
    assert alternative.ROW_FIELD not in rows[0]


def test_invalid_aptoide_store_label_is_rejected_before_credential_decryption(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    decrypted = False

    def unexpected_decryption(_value: object):
        nonlocal decrypted
        decrypted = True
        raise AssertionError("credential should not be decrypted")

    monkeypatch.setattr(alternative, "unprotect_secret", unexpected_decryption)
    providers, issues = alternative.configured_providers(
        {
            "alternative_distribution": {
                "fdroid_main": {"enabled": False},
                "aptoide": {
                    "enabled": True,
                    "store_name": "not a domain label",
                    "api_key_protected": "v1:synthetic",
                },
            }
        }
    )

    assert not decrypted
    assert providers == []
    assert issues == ["Aptoide checks skipped: the store name is not a valid domain label."]


def test_provider_failure_is_independent_and_does_not_change_primary_fields(tmp_path) -> None:
    class BrokenProvider(FakeProvider):
        def check(self, package_id: str, *, timeout: float) -> AlternativeDistributionResult:
            raise RuntimeError(f"synthetic provider failure for {package_id}")

    row = {
        "package_name": "eligible.one",
        "play_status": "not_found_in_checked_countries",
        "criticality": "Removed",
        "installer_source": "Google Play",
        "health_score": 40,
    }
    good = FakeProvider("fdroid_main", "F-Droid")

    _run([row], [BrokenProvider("aptoide", "Aptoide"), good], tmp_path / "cache.json")

    states = {item["provider_id"]: item["state"] for item in row[alternative.ROW_FIELD]}
    assert states == {"fdroid_main": "available", "aptoide": "inconclusive"}
    assert row["play_status"] == "not_found_in_checked_countries"
    assert row["criticality"] == "Removed"
    assert row["installer_source"] == "Google Play"
    assert row["health_score"] == 40


def test_total_concurrency_is_bounded_to_two(tmp_path) -> None:
    lock = threading.Lock()
    active = 0
    maximum = 0

    class BlockingProvider(FakeProvider):
        def check(self, package_id: str, *, timeout: float) -> AlternativeDistributionResult:
            nonlocal active, maximum
            with lock:
                active += 1
                maximum = max(maximum, active)
            time.sleep(0.04)
            with lock:
                active -= 1
            return super().check(package_id, timeout=timeout)

    rows = [
        {"package_name": f"eligible.{index}", "play_status": "not_found_in_checked_countries"}
        for index in range(4)
    ]
    providers = [BlockingProvider("fdroid_main", "F-Droid"), BlockingProvider("aptoide", "Aptoide", cache_namespace="aptoide:test")]

    _run(rows, providers, tmp_path / "cache.json", max_workers=8)

    assert maximum == 2


def test_pause_prevents_submission_resume_continues_and_stop_prevents_pending(tmp_path) -> None:
    pause = threading.Event()
    cancel = threading.Event()
    provider = FakeProvider("fdroid_main", "F-Droid")
    rows = _rows()

    thread = threading.Thread(
        target=lambda: alternative.run_alternative_distribution_phase(
            rows,
            {},
            pause_event=pause,
            cancel_event=cancel,
            providers=[provider],
            cache_file=tmp_path / "cache.json",
            phase_budget=1,
        )
    )
    thread.start()
    time.sleep(0.08)
    assert provider.calls == 0
    pause.set()
    thread.join(timeout=2)
    assert provider.calls == 1

    pending_rows = [
        {"package_name": f"pending.{index}", "play_status": "not_found_in_checked_countries"}
        for index in range(3)
    ]
    cancel.set()
    _run(
        pending_rows,
        [FakeProvider("fdroid_main", "F-Droid")],
        tmp_path / "stopped.json",
        cancel_event=cancel,
    )
    assert all(
        item["state"] == "not_checked"
        for row in pending_rows
        for item in row[alternative.ROW_FIELD]
    )


def test_paused_time_does_not_consume_provider_phase_budget(tmp_path) -> None:
    pause = threading.Event()
    provider = FakeProvider("fdroid_main", "F-Droid")
    rows = _rows()[:1]

    thread = threading.Thread(
        target=lambda: alternative.run_alternative_distribution_phase(
            rows,
            {},
            pause_event=pause,
            cancel_event=threading.Event(),
            providers=[provider],
            cache_file=tmp_path / "cache.json",
            phase_budget=0.08,
        )
    )
    thread.start()
    time.sleep(0.12)

    assert thread.is_alive()
    assert provider.calls == 0

    pause.set()
    thread.join(timeout=2)

    assert not thread.is_alive()
    assert provider.calls == 1
    assert rows[0][alternative.ROW_FIELD][0]["state"] == "available"


def test_wall_budget_marks_unsubmitted_checks_not_checked(tmp_path) -> None:
    rows = _rows()

    _run(
        rows,
        [FakeProvider("fdroid_main", "F-Droid")],
        tmp_path / "budget.json",
        phase_budget=0,
    )

    assert rows[0][alternative.ROW_FIELD][0]["state"] == "not_checked"
    assert "time budget" in rows[0][alternative.ROW_FIELD][0]["reason"]


def test_cache_ttl_force_refresh_and_store_namespace_isolation(tmp_path) -> None:
    cache_file = tmp_path / "cache.json"
    row = _rows()[:1]
    first = FakeProvider("aptoide", "Aptoide", cache_namespace="aptoide:store-a")
    _run(row, [first], cache_file)
    assert first.calls == 1

    cached = FakeProvider("aptoide", "Aptoide", cache_namespace="aptoide:store-a")
    second_row = _rows()[:1]
    _run(second_row, [cached], cache_file)
    assert cached.calls == 0
    assert second_row[0][alternative.ROW_FIELD][0]["provenance"] == "cache"

    isolated = FakeProvider("aptoide", "Aptoide", cache_namespace="aptoide:store-b")
    _run(_rows()[:1], [isolated], cache_file)
    assert isolated.calls == 1

    refreshed = FakeProvider("aptoide", "Aptoide", cache_namespace="aptoide:store-a")
    _run(_rows()[:1], [refreshed], cache_file, force_refresh=True)
    assert refreshed.calls == 1
    assert "synthetic" not in json.dumps(json.loads(cache_file.read_text(encoding="utf-8")))


def test_cache_rejects_mismatched_embedded_package_and_provider(tmp_path) -> None:
    cache_file = tmp_path / "mismatched.json"
    original = FakeProvider("fdroid_main", "F-Droid")
    _run(_rows()[:1], [original], cache_file)
    payload = json.loads(cache_file.read_text(encoding="utf-8"))
    entry = next(iter(payload.values()))
    entry["result"]["queried_package_id"] = "different.package"
    entry["result"]["provider_id"] = "aptoide"
    cache_file.write_text(json.dumps(payload), encoding="utf-8")
    refreshed = FakeProvider("fdroid_main", "F-Droid")

    _run(_rows()[:1], [refreshed], cache_file)

    assert refreshed.calls == 1


def test_cache_policy_ttls_are_central_and_expired_evidence_is_refreshed(tmp_path) -> None:
    assert alternative.ALT_CACHE_TTL_SECONDS == {
        AlternativeDistributionState.AVAILABLE: 24 * 60 * 60,
        AlternativeDistributionState.NOT_FOUND: 12 * 60 * 60,
        AlternativeDistributionState.INCONCLUSIVE: 15 * 60,
    }
    cache_file = tmp_path / "expired.json"
    original = FakeProvider("fdroid_main", "F-Droid")
    _run(_rows()[:1], [original], cache_file)
    payload = json.loads(cache_file.read_text(encoding="utf-8"))
    for entry in payload.values():
        entry["fetched_at"] = "2000-01-01T00:00:00Z"
    cache_file.write_text(json.dumps(payload), encoding="utf-8")
    refreshed = FakeProvider(
        "fdroid_main", "F-Droid", state=AlternativeDistributionState.INCONCLUSIVE
    )
    row = _rows()[:1]

    _run(row, [refreshed], cache_file)

    assert refreshed.calls == 1
    assert row[0][alternative.ROW_FIELD][0]["state"] == "inconclusive"
    assert row[0][alternative.ROW_FIELD][0]["provenance"] == "live"


def test_cache_write_failure_is_nonfatal_to_completed_provider_evidence(
    tmp_path, monkeypatch: pytest.MonkeyPatch
) -> None:
    row = _rows()[:1]
    monkeypatch.setattr(
        alternative,
        "_write_cache",
        lambda _path, _payload: (_ for _ in ()).throw(OSError("synthetic write failure")),
    )

    issues = _run(row, [FakeProvider("fdroid_main", "F-Droid")], tmp_path / "cache.json")

    assert row[0][alternative.ROW_FIELD][0]["state"] == "available"
    assert issues == ["Alternative-distribution evidence cache could not be updated."]
