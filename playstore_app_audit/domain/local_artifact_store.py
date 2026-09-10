from __future__ import annotations

from collections.abc import Mapping
from dataclasses import dataclass
from typing import Any

from playstore_app_audit.domain.alternative_distribution import AlternativeDistributionResult
from playstore_app_audit.domain.local_artifacts import LocalArtifact


@dataclass(frozen=True, slots=True)
class PackageStoreEvidence:
    """Store/provider evidence shared by artifacts with one exact package ID."""

    package_lookup_key: str
    store_result: Mapping[str, Any]
    alternative_distribution: tuple[AlternativeDistributionResult, ...] = ()

    @property
    def play_status(self) -> str:
        return str(self.store_result.get("play_status") or "")


@dataclass(frozen=True, slots=True)
class LocalArtifactStoreAssociation:
    """One artifact and the package-level evidence available for it."""

    artifact: LocalArtifact
    package_evidence: PackageStoreEvidence | None


@dataclass(frozen=True, slots=True)
class LocalArtifactStoreFanoutResult:
    """Ordered artifact associations plus first-seen package evidence."""

    associations: tuple[LocalArtifactStoreAssociation, ...]
    packages: tuple[PackageStoreEvidence, ...]
    issues: tuple[str, ...] = ()
