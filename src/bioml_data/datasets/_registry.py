"""Static registry for built-in dataset vertical slices."""

from copy import deepcopy
from dataclasses import dataclass, field
from typing import override

from bioml_data._artifact_lineage import ArtifactLineageReceipt
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
from bioml_data.datasets._evidence_validation import valid_split_evidence
from bioml_data.datasets._materialization_verification import materialize_verified
from bioml_data.datasets._models import (
    DatasetMaterialization,
    DatasetRegistration,
)
from bioml_data.datasets._split_contract_validation import (
    valid_definition_compatibility_projection,
    valid_split_capability_contract_mode,
    valid_split_semantics,
)
from bioml_data.datasets.pancreas._registration import PANCREAS_REGISTRATION
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


@dataclass(frozen=True, slots=True, init=False)
class DatasetRegistry:
    """Resolve dataset definitions and their owned implementations."""

    _registrations: tuple[DatasetRegistration, ...] = field(repr=False)

    def __init__(self, registrations: tuple[DatasetRegistration, ...]) -> None:
        """Snapshot caller-owned registrations before registry validation."""
        snapshot = deepcopy(registrations)
        object.__setattr__(self, "_registrations", snapshot)
        seen: set[DatasetSnapshotIdentity] = set()
        for registration in self._registrations:
            registration_snapshot = registration.definition.snapshot
            if registration_snapshot in seen:
                raise DuplicateDatasetRegistrationError(snapshot=registration_snapshot)
            seen.add(registration_snapshot)
            _validate_registration(registration)

    @property
    def registrations(self) -> tuple[DatasetRegistration, ...]:
        """Return detached registration views without exposing registry authority."""
        return deepcopy(self._registrations)

    def resolve(
        self,
        name: str,
        *,
        version: str | None = None,
    ) -> DatasetRegistration:
        """Resolve one explicit registration using public catalog keys."""
        return deepcopy(self._resolve(name, version=version))

    def _resolve(
        self,
        name: str,
        *,
        version: str | None = None,
    ) -> DatasetRegistration:
        """Resolve trusted internal registrations for catalog dispatch."""
        dataset_name = parse_dataset_name(name)
        candidates = tuple(
            registration
            for registration in self._registrations
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
        lineage: ArtifactLineageReceipt,
        *,
        version: str | None = None,
    ) -> DatasetMaterialization:
        """Dispatch an artifact through the adapter owned by its registration."""
        registration = self._resolve(name, version=version)
        return materialize_verified(registration, lineage)

    @property
    def available_names(self) -> tuple[DatasetName, ...]:
        """Return registered dataset names in stable registration order."""
        return tuple(
            dict.fromkeys(
                registration.definition.snapshot.name
                for registration in self._registrations
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
        coherent = (
            capability.dataset == definition.snapshot
            and capability.artifact == registration.artifact_scope
            and capability.task in task_ids
            and capability.required_columns == split_definition.required_metadata
            and capability.grouping_column in capability.required_columns
            and bool(capability.evidence)
            and all(scope == expected_evidence_scope for scope in evidence_scopes)
            and all(evidence.citations for evidence in capability.evidence)
            and all(valid_split_evidence(evidence) for evidence in capability.evidence)
            and valid_split_capability_contract_mode(capability)
            and valid_split_semantics(capability)
            and capability.basis == split_definition.basis
            and capability.strategy == split_definition.strategy
            and capability.held_out_axis == split_definition.held_out_axis
            and capability.leakage_unit == split_definition.leakage_unit
            and capability.grouping_column == split_definition.grouping_column
            and capability.evaluation_target == split_definition.evaluation_target
            and capability.is_canary is split_definition.is_canary
            and valid_definition_compatibility_projection(split_definition)
        )
        if not coherent:
            raise DatasetCapabilityMismatchError(
                snapshot=definition.snapshot,
                detail=f"contract mismatch for {capability.protocol!r}",
            )


DATASET_REGISTRY = DatasetRegistry(
    registrations=(TMS_AORTA_REGISTRATION, PANCREAS_REGISTRATION),
)
publish_registry_capabilities(DATASET_REGISTRY.registrations)


def available_dataset_names() -> tuple[DatasetName, ...]:
    """Return the public names from the process-wide built-in registry."""
    return DATASET_REGISTRY.available_names
