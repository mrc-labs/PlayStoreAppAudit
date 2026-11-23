from __future__ import annotations

from datetime import UTC, datetime, timedelta
from pathlib import Path

from cleanup_actions_retention import (
    artifact_profile,
    select_expired_bad_runs,
    select_successful_artifact_deletions,
)


def test_selected_sdk_contracts_protect_original_failed_stage_runs() -> None:
    from cleanup_actions_retention import active_dependency_runs

    selected = active_dependency_runs(Path(__file__).resolve().parents[1] / '.github/scripts')
    assert {43623545058, 43666656687, 43667240760, 45100211225, 43782611872,
            43816542716, 43818005888, 44012330704} <= selected


def test_apply_preserves_active_failed_and_superseded_sdk_inputs(monkeypatch) -> None:
    import cleanup_actions_retention as policy

    deleted = []
    runs = {number: _run(number, f'2026-01-0{number}T00:00:00Z',
                        'failure' if number <= 2 else 'success') for number in range(1, 6)}

    class Client:
        def __init__(self, *args):
            pass

        def artifacts(self):
            return [_artifact(number * 10, number, 'same-profile') for number in runs]

        def run(self, number):
            return runs[number]

        def runs_with_status(self, status):
            return [run for run in runs.values() if run['conclusion'] == status]

        def delete_run(self, number):
            deleted.append(('run', number))

        def delete_artifact(self, number):
            deleted.append(('artifact', number))

    monkeypatch.setattr(policy, 'GitHubClient', Client)
    monkeypatch.setattr(policy, 'active_dependency_runs', lambda _: {1, 3})
    monkeypatch.setenv('GITHUB_REPOSITORY', 'fixture/repository')
    monkeypatch.setenv('GITHUB_TOKEN', 'fixture-token')
    monkeypatch.setattr('sys.argv', ['cleanup', '--apply'])
    assert policy.main() == 0
    assert deleted == [('run', 2), ('run', 4)]


def _run(run_id: int, updated: str, conclusion: str = "success") -> dict:
    return {
        "id": run_id,
        "name": "Build Windows - Qt6",
        "status": "completed",
        "conclusion": conclusion,
        "updated_at": updated,
    }


def _artifact(artifact_id: int, run_id: int, name: str) -> dict:
    return {
        "id": artifact_id,
        "name": name,
        "expired": False,
        "workflow_run": {"id": run_id},
    }


def test_profile_normalizes_version_but_keeps_workflow_and_architecture() -> None:
    first = artifact_profile(
        "Build Windows - Qt6",
        "PlayStoreAppAudit-v1.4.0-windows-x64",
    )
    second = artifact_profile(
        "Build Windows - Qt6",
        "PlayStoreAppAudit-v1.5.0-windows-x64",
    )
    arm64 = artifact_profile(
        "Build Windows - Qt6",
        "PlayStoreAppAudit-v1.5.0-windows-arm64",
    )
    signed = artifact_profile(
        "Sign Windows release candidates",
        "PlayStoreAppAudit-v1.5.0-windows-x64",
    )

    assert first == second
    assert arm64 != first
    assert signed != first


def test_latest_success_is_kept_and_previous_gets_seven_day_grace() -> None:
    now = datetime(2026, 8, 20, 12, tzinfo=UTC)
    runs = {
        1: _run(1, "2026-08-01T12:00:00Z"),
        2: _run(2, "2026-08-19T12:00:00Z"),
    }
    artifacts = [
        _artifact(101, 1, "PlayStoreAppAudit-v1.4.0-windows-x64"),
        _artifact(102, 2, "PlayStoreAppAudit-v1.5.0-windows-x64"),
    ]

    selected = select_successful_artifact_deletions(
        artifacts,
        runs,
        now=now,
        grace=timedelta(days=7),
    )

    assert selected == set()


def test_previous_success_expires_seven_days_after_successor_completed() -> None:
    now = datetime(2026, 8, 27, 12, tzinfo=UTC)
    runs = {
        1: _run(1, "2026-08-01T12:00:00Z"),
        2: _run(2, "2026-08-20T12:00:00Z"),
    }
    artifacts = [
        _artifact(101, 1, "PlayStoreAppAudit-v1.4.0-windows-x64"),
        _artifact(102, 2, "PlayStoreAppAudit-v1.5.0-windows-x64"),
    ]

    selected = select_successful_artifact_deletions(
        artifacts,
        runs,
        now=now,
        grace=timedelta(days=7),
    )

    assert selected == {101}


def test_third_success_deletes_oldest_immediately() -> None:
    now = datetime(2026, 8, 22, 12, tzinfo=UTC)
    runs = {
        1: _run(1, "2026-08-01T12:00:00Z"),
        2: _run(2, "2026-08-20T12:00:00Z"),
        3: _run(3, "2026-08-22T11:00:00Z"),
    }
    artifacts = [
        _artifact(101, 1, "PlayStoreAppAudit-v1.3.0-windows-x64"),
        _artifact(102, 2, "PlayStoreAppAudit-v1.4.0-windows-x64"),
        _artifact(103, 3, "PlayStoreAppAudit-v1.5.0-windows-x64"),
    ]

    selected = select_successful_artifact_deletions(
        artifacts,
        runs,
        now=now,
        grace=timedelta(days=7),
    )

    assert selected == {101}


def test_failed_or_cancelled_run_never_replaces_successful_generation() -> None:
    now = datetime(2026, 8, 30, 12, tzinfo=UTC)
    runs = {
        1: _run(1, "2026-08-01T12:00:00Z"),
        2: _run(2, "2026-08-29T12:00:00Z", "failure"),
    }
    artifacts = [
        _artifact(101, 1, "PlayStoreAppAudit-v1.4.0-windows-x64"),
        _artifact(102, 2, "PlayStoreAppAudit-v1.5.0-windows-x64"),
    ]

    selected = select_successful_artifact_deletions(
        artifacts,
        runs,
        now=now,
        grace=timedelta(days=7),
    )

    assert selected == set()


def test_failed_and_cancelled_runs_expire_after_seven_days() -> None:
    now = datetime(2026, 8, 20, 12, tzinfo=UTC)
    runs = [
        _run(1, "2026-08-12T12:00:00Z", "failure"),
        _run(2, "2026-08-13T12:00:00Z", "cancelled"),
        _run(3, "2026-08-19T12:00:00Z", "failure"),
        _run(4, "2026-08-01T12:00:00Z", "success"),
    ]

    selected = select_expired_bad_runs(
        runs,
        now=now,
        grace=timedelta(days=7),
    )

    assert selected == {1, 2}
