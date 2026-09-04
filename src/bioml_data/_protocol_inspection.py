"""Deterministic, plan-time inspection of registered dataset protocols."""

from bioml_data._domain import TaskDefinition
from bioml_data._metadata_concordance import MetadataConcordanceReport
from bioml_data._metadata_concordance_models import MetadataConcordance
from bioml_data._metadata_concordance_reporting import metadata_concordance_identity
from bioml_data._protocol_inspection_concordance import validate_concordance_attachment
from bioml_data._protocol_inspection_models import (
    ConcordanceInspection,
    ConcordanceVerification,
    ProtocolCitationInspection,
    ProtocolEvidenceInspection,
    ProtocolInspection,
    ProtocolInspectionReceiptMismatchError,
    ProtocolInspectionRequest,
    ProtocolReadiness,
    RealizedAssignmentInspection,
)
from bioml_data._protocol_inspection_rules import inspect_split_rule
from bioml_data._protocol_inspection_validation import (
    InspectionAttachmentContract,
    validate_assignment_attachment,
)
from bioml_data._split import (
    SplitAssignmentReceipt,
    SplitPartition,
)
from bioml_data._split_capability import SplitCapabilityQuery, query_split_capability
from bioml_data.datasets._registry import DATASET_REGISTRY


def inspect_protocol(
    name: str,
    *,
    task: str,
    protocol: str,
    request: ProtocolInspectionRequest | None = None,
) -> ProtocolInspection:
    """Inspect a declared protocol without downloading, preparing, or splitting data."""
    inputs = ProtocolInspectionRequest() if request is None else request
    registration = DATASET_REGISTRY.resolve(name, version=inputs.version)
    definition = registration.definition
    plan = definition.plan_split(task=task, protocol=protocol)
    task_definition = _task_definition(definition.tasks, plan.task)
    capability = query_split_capability(
        SplitCapabilityQuery(
            dataset=plan.dataset,
            task=plan.task,
            protocol=str(plan.protocol),
        )
    ).require_supported()
    rule = inspect_split_rule(capability.strategy)
    attachment_contract = InspectionAttachmentContract(
        dataset=plan.dataset,
        task=str(plan.task),
        protocol=str(plan.protocol),
        capability=capability,
    )
    validate_assignment_attachment(attachment_contract, inputs.assignment)
    if inputs.concordance is not None:
        validate_concordance_attachment(
            attachment_contract,
            inputs.assignment,
            inputs.concordance,
        )
    return ProtocolInspection(
        dataset_name=str(plan.dataset.name),
        dataset_version=str(plan.dataset.version),
        source_uri=str(definition.source.uri),
        lifecycle=definition.lifecycle.value,
        readiness=ProtocolReadiness.UNRESOLVED,
        readiness_note=(
            "BIO-31 support-readiness evaluation has not yet evaluated this "
            "registration"
        ),
        task_id=str(task_definition.id),
        prediction_unit=task_definition.prediction_unit,
        target=task_definition.target,
        protocol_id=str(capability.protocol),
        source_artifact=str(capability.artifact.source_artifact),
        transform_protocol=str(capability.artifact.transform_protocol),
        evidence_basis=tuple(
            record.basis.value for record in capability.evidence if record.basis
        ),
        evidence=tuple(
            ProtocolEvidenceInspection(
                basis=record.basis.value if record.basis else "legacy_unspecified",
                citations=tuple(
                    ProtocolCitationInspection(title=item.title, uri=item.uri)
                    for item in record.citations
                ),
                fit_scope=record.fit_scope,
                leakage_caveat=record.leakage_caveat,
            )
            for record in capability.evidence
        ),
        strategy=rule.strategy,
        held_out_axis=capability.held_out_axis,
        leakage_unit=capability.leakage_unit,
        grouping_column=capability.grouping_column,
        evaluation_target=capability.evaluation_target,
        required_metadata=capability.required_columns,
        assignment_rule=rule.assignment_rule,
        deterministic_tie_break=rule.deterministic_tie_break,
        seed_policy="caller-supplied; the assignment identity commits the seed",
        requested_group_fractions=rule.requested_group_fractions,
        allocation_policy=rule.allocation_policy,
        validation_policy=rule.validation_policy,
        group_overlap_invariant=(
            "each grouping-column value is assigned to exactly one partition"
        ),
        preprocessing_fit_scope=tuple(
            record.fit_scope for record in capability.evidence
        ),
        limitations=tuple(record.leakage_caveat for record in capability.evidence),
        is_canary=capability.is_canary,
        realized_assignment=_realized_assignment(inputs.assignment),
        concordance=_concordance_summary(inputs.concordance),
    )


def _task_definition(
    definitions: tuple[TaskDefinition, ...], task: str
) -> TaskDefinition:
    for definition in definitions:
        if str(definition.id) == task:
            return definition
    raise ProtocolInspectionReceiptMismatchError(
        field="task", expected="registered task", actual=task
    )


def _realized_assignment(
    assignment: SplitAssignmentReceipt | None,
) -> RealizedAssignmentInspection | None:
    if assignment is None:
        return None
    rows_by_partition = {
        partition: tuple(
            item for item in assignment.assignments if item.partition is partition
        )
        for partition in SplitPartition
    }
    partitions_by_group: dict[str, set[SplitPartition]] = {}
    for item in assignment.assignments:
        partitions_by_group.setdefault(str(item.group), set()).add(item.partition)
    return RealizedAssignmentInspection(
        caller_supplied=True,
        validation_scope="protocol-contract-and-internal-consistency-only",
        identity=str(assignment.assignment_identity),
        seed=assignment.seed,
        observation_count=assignment.observation_count,
        group_count=assignment.group_count,
        train_observation_count=len(rows_by_partition[SplitPartition.TRAIN]),
        validation_observation_count=len(rows_by_partition[SplitPartition.VALIDATION]),
        test_observation_count=len(rows_by_partition[SplitPartition.TEST]),
        train_group_count=len(
            {item.group for item in rows_by_partition[SplitPartition.TRAIN]}
        ),
        validation_group_count=len(
            {item.group for item in rows_by_partition[SplitPartition.VALIDATION]}
        ),
        test_group_count=len(
            {item.group for item in rows_by_partition[SplitPartition.TEST]}
        ),
        test_group_ids=tuple(
            sorted({str(item.group) for item in rows_by_partition[SplitPartition.TEST]})
        ),
        cross_partition_group_ids=tuple(
            sorted(
                group
                for group, partitions in partitions_by_group.items()
                if len(partitions) > 1
            )
        ),
    )


def _concordance_summary(
    concordance: MetadataConcordanceReport | None,
) -> ConcordanceInspection | None:
    if concordance is None:
        return None
    comparisons = (
        *concordance.dataset_comparisons,
        *tuple(
            comparison
            for partition in concordance.partition_reports
            for comparison in partition.comparisons
        ),
    )
    statuses = tuple(item.status for item in comparisons)
    return ConcordanceInspection(
        caller_supplied=True,
        validation_scope="structural-receipt-binding-only; outcomes-not-recomputed",
        verification=ConcordanceVerification.CALLER_SUPPLIED_UNVERIFIED,
        identity=metadata_concordance_identity(concordance),
        match_count=statuses.count(MetadataConcordance.MATCH),
        mismatch_count=statuses.count(MetadataConcordance.MISMATCH),
        not_reported_count=statuses.count(MetadataConcordance.NOT_REPORTED),
    )
