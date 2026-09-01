"""Static registry for built-in dataset vertical slices."""

from dataclasses import dataclass
from typing import override

from bioml_data._artifacts import ArtifactManifest, ArtifactReceipt
from bioml_data._domain import (
    DatasetName,
    DatasetSnapshotIdentity,
    DatasetVersionRequiredError,
    UnknownDatasetError,
    UnknownDatasetVersionError,
    parse_dataset_name,
    parse_dataset_version,
)
from bioml_data.datasets._capability_index import publish_registry_capabilities
from bioml_data.datasets._models import (
    DatasetMaterialization,
    DatasetRegistration,
)
from bioml_data.datasets.tms_aorta._registration import TMS_AORTA_REGISTRATION


@dataclass(frozen=True, slots=True)
class DuplicateDatasetRegistrationError(Exception):
    """Raised when an exact snapshot is registered more than once."""

    snapshot: DatasetSnapshotIdentity

    @override
    def __str__(self) -> str:
        return f"duplicate dataset registration for {self.snapshot!r}"


@dataclass(frozen=True, slots=True)
class DatasetCapabilityMismatchError(Exception):
    """Raised when a registered capability leaves its dataset definition."""

    snapshot: DatasetSnapshotIdentity
    detail: str

    @override
    def __str__(self) -> str:
        return f"split capability is incoherent with {self.snapshot!r}: {self.detail}"


@dataclass(frozen=True, slots=True)
class DatasetMaterializationSnapshotMismatchError(Exception):
    """Raised when an adapter returns a different dataset snapshot."""

    expected: DatasetSnapshotIdentity
    actual: DatasetSnapshotIdentity

    @override
    def __str__(self) -> str:
        return f"materialization snapshot {self.actual!r} != {self.expected!r}"


@dataclass(frozen=True, slots=True)
class DatasetMaterializationArtifactMismatchError(Exception):
    """Raised when an adapter substitutes input artifact provenance."""

    expected: ArtifactManifest
    actual: ArtifactManifest

    @override
    def __str__(self) -> str:
        return "materialization artifact manifest differs from its input"


@dataclass(frozen=True, slots=True)
class DatasetRegistry:
    """Resolve dataset definitions and their owned implementations."""

    registrations: tuple[DatasetRegistration, ...]

    def __post_init__(self) -> None:
        seen: set[DatasetSnapshotIdentity] = set()
        for registration in self.registrations:
            snapshot = registration.definition.snapshot
            if snapshot in seen:
                raise DuplicateDatasetRegistrationError(snapshot=snapshot)
            seen.add(snapshot)
            _validate_registration(registration)

    def resolve(
        self,
        name: str,
        *,
        version: str | None = None,
    ) -> DatasetRegistration:
        """Resolve one explicit registration using public catalog keys."""
        dataset_name = parse_dataset_name(name)
        candidates = tuple(
            registration
            for registration in self.registrations
            if registration.definition.snapshot.name == dataset_name
        )
        if not candidates:
            raise UnknownDatasetError(
                name=dataset_name,
                available=self.available_names,
            )

        available_versions = tuple(
            registration.definition.snapshot.version for registration in candidates
        )
        if version is None:
            if len(candidates) == 1:
                return candidates[0]
            raise DatasetVersionRequiredError(
                name=dataset_name,
                available=available_versions,
            )

        requested_version = parse_dataset_version(version)
        for registration in candidates:
            if registration.definition.snapshot.version == requested_version:
                return registration
        raise UnknownDatasetVersionError(
            name=dataset_name,
            requested=requested_version,
            available=available_versions,
        )

    def materialize(
        self,
        name: str,
        artifact: ArtifactReceipt,
        *,
        version: str | None = None,
    ) -> DatasetMaterialization:
        """Dispatch an artifact through the adapter owned by its registration."""
        registration = self.resolve(name, version=version)
        result = registration.materialize(artifact)
        expected_snapshot = registration.definition.snapshot
        if result.snapshot != expected_snapshot:
            raise DatasetMaterializationSnapshotMismatchError(
                expected=expected_snapshot,
                actual=result.snapshot,
            )
        if result.artifact != artifact.manifest:
            raise DatasetMaterializationArtifactMismatchError(
                expected=artifact.manifest,
                actual=result.artifact,
            )
        return result

    @property
    def available_names(self) -> tuple[DatasetName, ...]:
        """Return registered dataset names in stable registration order."""
        return tuple(
            dict.fromkeys(
                registration.definition.snapshot.name
                for registration in self.registrations
            )
        )


def _validate_registration(registration: DatasetRegistration) -> None:
    definition = registration.definition
    task_ids = {task.id for task in definition.tasks}
    split_definitions = {
        (split.task, split.id): split for split in definition.supported_splits
    }
    if len(split_definitions) != len(definition.supported_splits):
        raise DatasetCapabilityMismatchError(
            snapshot=definition.snapshot,
            detail="duplicate split definitions",
        )

    capabilities = {
        (capability.task, capability.protocol): capability
        for capability in registration.split_capabilities
    }
    if len(capabilities) != len(registration.split_capabilities):
        raise DatasetCapabilityMismatchError(
            snapshot=definition.snapshot,
            detail="duplicate split capabilities",
        )
    if capabilities.keys() != split_definitions.keys():
        raise DatasetCapabilityMismatchError(
            snapshot=definition.snapshot,
            detail="split definitions and capabilities differ",
        )

    for capability in registration.split_capabilities:
        split_definition = split_definitions[(capability.task, capability.protocol)]
        expected_evidence_scope = (
            capability.dataset,
            capability.artifact,
            capability.task,
            capability.protocol,
        )
        evidence_scopes = tuple(
            (
                evidence.scope.dataset,
                evidence.scope.artifact,
                evidence.scope.task,
                evidence.scope.protocol,
            )
            for evidence in capability.evidence
        )
        evidence_roles = tuple(evidence.role for evidence in capability.evidence)
        coherent = (
            capability.dataset == definition.snapshot
            and capability.task in task_ids
            and capability.role == split_definition.role
            and capability.required_columns == split_definition.required_metadata
            and capability.grouping_column in capability.required_columns
            and bool(capability.evidence)
            and all(scope == expected_evidence_scope for scope in evidence_scopes)
            and capability.role in evidence_roles
            and len(set(evidence_roles)) == len(evidence_roles)
            and all(evidence.citations for evidence in capability.evidence)
            and capability.evidence_type == capability.evidence[0].evidence_type
        )
        if not coherent:
            raise DatasetCapabilityMismatchError(
                snapshot=definition.snapshot,
                detail=f"contract mismatch for {capability.protocol!r}",
            )


DATASET_REGISTRY = DatasetRegistry(registrations=(TMS_AORTA_REGISTRATION,))
publish_registry_capabilities(DATASET_REGISTRY.registrations)


def available_dataset_names() -> tuple[DatasetName, ...]:
    """Return the public names from the process-wide built-in registry."""
    return DATASET_REGISTRY.available_names
