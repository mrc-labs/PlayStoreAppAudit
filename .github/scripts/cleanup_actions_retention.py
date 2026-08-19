from __future__ import annotations

import argparse
import json
import os
import re
import urllib.request
from collections import defaultdict
from datetime import UTC, datetime, timedelta
from typing import Any

API_VERSION = "2026-03-10"
VERSION_RE = re.compile(r"v\d+\.\d+\.\d+(?:[-+][0-9A-Za-z.-]+)?")
BAD_CONCLUSIONS = {"failure", "cancelled"}


def parse_github_time(value: str) -> datetime:
    return datetime.fromisoformat(value.replace("Z", "+00:00")).astimezone(UTC)


def artifact_profile(workflow_name: str, artifact_name: str) -> str:
    normalized = VERSION_RE.sub("vVERSION", artifact_name)
    return f"{workflow_name}::{normalized}"


def select_successful_artifact_deletions(
    artifacts: list[dict[str, Any]],
    runs: dict[int, dict[str, Any]],
    *,
    now: datetime,
    grace: timedelta,
) -> set[int]:
    by_profile: dict[str, dict[int, list[dict[str, Any]]]] = defaultdict(
        lambda: defaultdict(list)
    )

    for artifact in artifacts:
        if artifact.get("expired"):
            continue
        workflow_run = artifact.get("workflow_run") or {}
        run_id = int(workflow_run.get("id", 0))
        run = runs.get(run_id)
        if not run:
            continue
        if run.get("status") != "completed" or run.get("conclusion") != "success":
            continue
        profile = artifact_profile(str(run.get("name", "")), str(artifact.get("name", "")))
        by_profile[profile][run_id].append(artifact)

    selected: set[int] = set()

    for generations in by_profile.values():
        ordered_run_ids = sorted(
            generations,
            key=lambda run_id: parse_github_time(str(runs[run_id]["updated_at"])),
            reverse=True,
        )
        if not ordered_run_ids:
            continue

        latest_run_id = ordered_run_ids[0]
        latest_completed = parse_github_time(str(runs[latest_run_id]["updated_at"]))

        if len(ordered_run_ids) >= 2 and now - latest_completed >= grace:
            previous_run_id = ordered_run_ids[1]
            selected.update(int(item["id"]) for item in generations[previous_run_id])

        for older_run_id in ordered_run_ids[2:]:
            selected.update(int(item["id"]) for item in generations[older_run_id])

    return selected


def select_expired_bad_runs(
    runs: list[dict[str, Any]],
    *,
    now: datetime,
    grace: timedelta,
) -> set[int]:
    selected: set[int] = set()
    for run in runs:
        if run.get("status") != "completed":
            continue
        if run.get("conclusion") not in BAD_CONCLUSIONS:
            continue
        completed = parse_github_time(str(run["updated_at"]))
        if now - completed >= grace:
            selected.add(int(run["id"]))
    return selected


class GitHubClient:
    def __init__(self, repository: str, token: str) -> None:
        self.repository = repository
        self.base = f"https://api.github.com/repos/{repository}"
        self.headers = {
            "Accept": "application/vnd.github+json",
            "Authorization": f"Bearer {token}",
            "X-GitHub-Api-Version": API_VERSION,
            "User-Agent": "PlayStoreAppAudit-actions-retention",
        }

    def _request(self, path: str, *, method: str = "GET") -> Any:
        request = urllib.request.Request(
            f"{self.base}{path}",
            headers=self.headers,
            method=method,
        )
        with urllib.request.urlopen(request, timeout=60) as response:
            payload = response.read()
        if not payload:
            return None
        return json.loads(payload.decode("utf-8"))

    def paginated(self, path: str, key: str) -> list[dict[str, Any]]:
        items: list[dict[str, Any]] = []
        page = 1
        separator = "&" if "?" in path else "?"
        while True:
            payload = self._request(f"{path}{separator}per_page=100&page={page}")
            batch = list(payload.get(key, []))
            items.extend(batch)
            if len(batch) < 100:
                return items
            page += 1

    def artifacts(self) -> list[dict[str, Any]]:
        return self.paginated("/actions/artifacts", "artifacts")

    def run(self, run_id: int) -> dict[str, Any]:
        return self._request(f"/actions/runs/{run_id}")

    def runs_with_status(self, status: str) -> list[dict[str, Any]]:
        return self.paginated(f"/actions/runs?status={status}", "workflow_runs")

    def delete_artifact(self, artifact_id: int) -> None:
        self._request(f"/actions/artifacts/{artifact_id}", method="DELETE")

    def delete_run(self, run_id: int) -> None:
        self._request(f"/actions/runs/{run_id}", method="DELETE")


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Apply generational GitHub Actions artifact/run retention."
    )
    parser.add_argument("--apply", action="store_true", help="Perform deletions.")
    parser.add_argument("--grace-days", type=int, default=7)
    args = parser.parse_args()

    if args.grace_days < 1:
        raise SystemExit("--grace-days must be at least 1")

    repository = os.environ.get("GITHUB_REPOSITORY", "").strip()
    token = os.environ.get("GITHUB_TOKEN", "").strip()
    if not repository or "/" not in repository:
        raise SystemExit("GITHUB_REPOSITORY must be owner/repository")
    if not token:
        raise SystemExit("GITHUB_TOKEN is required")

    client = GitHubClient(repository, token)
    now = datetime.now(UTC)
    grace = timedelta(days=args.grace_days)

    artifacts = [item for item in client.artifacts() if not item.get("expired")]
    run_ids = {
        int((item.get("workflow_run") or {}).get("id", 0))
        for item in artifacts
        if int((item.get("workflow_run") or {}).get("id", 0)) > 0
    }
    runs = {run_id: client.run(run_id) for run_id in sorted(run_ids)}

    success_artifact_ids = select_successful_artifact_deletions(
        artifacts,
        runs,
        now=now,
        grace=grace,
    )

    failed_runs = client.runs_with_status("failure")
    cancelled_runs = client.runs_with_status("cancelled")
    bad_run_ids = select_expired_bad_runs(
        failed_runs + cancelled_runs,
        now=now,
        grace=grace,
    )

    artifacts_by_run: dict[int, set[int]] = defaultdict(set)
    for artifact in artifacts:
        run_id = int((artifact.get("workflow_run") or {}).get("id", 0))
        if run_id:
            artifacts_by_run[run_id].add(int(artifact["id"]))

    success_runs_to_delete: set[int] = set()
    individual_artifacts_to_delete = set(success_artifact_ids)

    for run_id, artifact_ids in artifacts_by_run.items():
        run = runs.get(run_id)
        if not run or run.get("conclusion") != "success":
            continue
        if artifact_ids and artifact_ids <= success_artifact_ids:
            success_runs_to_delete.add(run_id)
            individual_artifacts_to_delete -= artifact_ids

    print(
        json.dumps(
            {
                "apply": args.apply,
                "grace_days": args.grace_days,
                "active_artifacts": len(artifacts),
                "successful_runs_to_delete": sorted(success_runs_to_delete),
                "individual_artifacts_to_delete": sorted(individual_artifacts_to_delete),
                "failed_cancelled_runs_to_delete": sorted(bad_run_ids),
            },
            indent=2,
            sort_keys=True,
        )
    )

    if not args.apply:
        print("Dry run only. Pass --apply to perform deletions.")
        return 0

    for run_id in sorted(bad_run_ids):
        print(f"Deleting failed/cancelled run {run_id}")
        client.delete_run(run_id)

    for run_id in sorted(success_runs_to_delete):
        print(f"Deleting superseded successful run {run_id}")
        client.delete_run(run_id)

    for artifact_id in sorted(individual_artifacts_to_delete):
        print(f"Deleting superseded artifact {artifact_id}")
        client.delete_artifact(artifact_id)

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
