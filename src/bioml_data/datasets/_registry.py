"""Static registry for built-in dataset vertical slices."""

import re
from dataclasses import dataclass
from typing import Final, assert_never, override

from bioml_data._artifact_lineage import ArtifactLineageReceipt
from bioml_data._domain import (
    DatasetName,
    DatasetSnapshotIdentity,
    DatasetVersionRequiredError,
    SplitEvidenceBasis,
    SplitProtocolDefinition,
    SplitProtocolRole,
    SplitStrategy,
    UnknownDatasetError,
    UnknownDatasetVersionError,
    parse_dataset_name,
    parse_dataset_version,
)
from bioml_data._split_capability_models import SplitCapability
from bioml_data.datasets._capability_index import publish_registry_capabilities
from bioml_data.datasets._evidence_validation import valid_split_evidence
from bioml_data.datasets._materialization_verification import materialize_verified
from bioml_data.datasets._models import (
    DatasetMaterialization,
    DatasetRegistration,
)
from bioml_data.datasets.tms_aorta._registration import TMS_AORTA_REGISTRATION

_SEMANTIC_TOKEN: Final[re.Pattern[str]] = re.compile(r"[a-z][a-z0-9-]*\Z")
_METADATA_COLUMN: Final[re.Pattern[str]] = re.compile(r"[a-z][a-z0-9_]*\Z")


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
        lineage: ArtifactLineageReceipt,
        *,
        version: str | None = None,
    ) -> DatasetMaterialization:
        """Dispatch an artifact through the adapter owned by its registration."""
        registration = self.resolve(name, version=version)
        return materialize_verified(registration, lineage)

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
            and _valid_contract_mode(capability)
            and _valid_semantics(capability)
            and capability.basis == split_definition.basis
            and capability.strategy == split_definition.strategy
            and capability.held_out_axis == split_definition.held_out_axis
            and capability.leakage_unit == split_definition.leakage_unit
            and capability.grouping_column == split_definition.grouping_column
            and capability.evaluation_target == split_definition.evaluation_target
            and capability.is_canary is split_definition.is_canary
            and _valid_definition_compatibility_projection(split_definition)
        )
        if not coherent:
            raise DatasetCapabilityMismatchError(
                snapshot=definition.snapshot,
                detail=f"contract mismatch for {capability.protocol!r}",
            )


def _valid_contract_mode(capability: SplitCapability) -> bool:
    return (
        type(capability.basis) is SplitEvidenceBasis
        and capability.role is None
        and capability.evidence_type is None
        and capability.basis
        in tuple(evidence.basis for evidence in capability.evidence)
        and all(
            evidence.role is None
            and evidence.evidence_type is None
            and type(evidence.basis) is SplitEvidenceBasis
            for evidence in capability.evidence
        )
        and len({evidence.basis for evidence in capability.evidence})
        == len(capability.evidence)
    )


def _valid_semantics(capability: SplitCapability) -> bool:
    if type(capability.strategy) is not SplitStrategy:
        return False

    common_semantics = (
        _valid_semantic_token(capability.held_out_axis)
        and _valid_semantic_token(capability.leakage_unit)
        and _valid_metadata_column(capability.grouping_column)
        and capability.evaluation_target == f"unseen {capability.held_out_axis}"
    )
    match capability.strategy:
        case SplitStrategy.GROUP_HELD_OUT:
            return common_semantics
        case SplitStrategy.LEAVE_ONE_STUDY_OUT:
            return (
                common_semantics
                and capability.held_out_axis == "study"
                and capability.grouping_column == "study_id"
                and capability.leakage_unit == "study"
            )
    assert_never(capability.strategy)


def _valid_definition_compatibility_projection(
    definition: SplitProtocolDefinition,
) -> bool:
    if type(definition.basis) is not SplitEvidenceBasis:
        return False
    expected_role = SplitProtocolRole.CANARY if definition.is_canary else None
    return definition.role is expected_role


def _valid_semantic_token(value: str) -> bool:
    return _SEMANTIC_TOKEN.fullmatch(value) is not None


def _valid_metadata_column(value: str) -> bool:
    return _METADATA_COLUMN.fullmatch(value) is not None


DATASET_REGISTRY = DatasetRegistry(registrations=(TMS_AORTA_REGISTRATION,))
publish_registry_capabilities(DATASET_REGISTRY.registrations)


def available_dataset_names() -> tuple[DatasetName, ...]:
    """Return the public names from the process-wide built-in registry."""
    return DATASET_REGISTRY.available_names
