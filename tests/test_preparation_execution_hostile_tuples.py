"""Hostile nested-container tests for preparation execution boundaries."""

import json
from dataclasses import asdict, replace
from hashlib import sha256
from pathlib import Path

import pytest

import bioml_data.preparation_execution as execution
from bioml_data._preparation_errors import InvalidPreparedStructureError
from bioml_data._preparation_models import (
    PreparedObservation,
    PreparedValue,
    validate_prepared_observations,
)
from bioml_data._single_cell import FeatureId
from bioml_data._split import ObservationId

from ._execution_receipt_fixtures import execution_context, record


def _rehashed(
    receipt: execution.PreparationExecutionReceipt,
) -> execution.PreparationExecutionReceipt:
    """Return a receipt with an outer identity matching hostile nested content."""
    payload = asdict(receipt)
    del payload["receipt_identity"]
    identity = sha256(
        json.dumps(
            payload, sort_keys=True, separators=(",", ":"), allow_nan=False
        ).encode()
    ).hexdigest()
    return replace(
        receipt,
        receipt_identity=execution.PreparationExecutionReceiptIdentity(identity),
    )


@pytest.mark.parametrize("values", [[], (1,)])
def test_prepared_observation_validation_rejects_non_tuple_or_non_value_items(
    values: list[str] | tuple[int, ...],
) -> None:
    """The public sparse-row validator parses every value before traversal."""
    # Given: one valid sparse row whose nested container is bypass-mutated.
    observation = PreparedObservation(
        observation_id=ObservationId("cell-1"),
        values=(PreparedValue(feature_id=FeatureId("gene-1"), value=1.0),),
    )
    object.__setattr__(observation, "values", values)

    # When: public prepared-row validation receives the hostile row.
    with pytest.raises(InvalidPreparedStructureError):
        validate_prepared_observations((observation,))

    # Then: callers receive the domain error rather than AttributeError.


@pytest.mark.parametrize("values", [[], (1,)])
def test_record_rejects_hostile_prepared_observation_values(
    tmp_path: Path,
    values: list[str] | tuple[int, ...],
) -> None:
    """Recording parses mutated prepared observations before identity work."""
    # Given: a valid prepared output with one bypass-mutated value container.
    context = execution_context(tmp_path)
    observation = context.prepared.observations[0]
    object.__setattr__(observation, "values", values)

    # When: the public execution recorder consumes that prepared output.
    with pytest.raises(InvalidPreparedStructureError):
        _ = record(context)

    # Then: the hostile values never reach the receipt identity renderer.


@pytest.mark.parametrize("observations", [[], (1,)])
def test_record_rejects_hostile_prepared_observation_tuple(
    tmp_path: Path,
    observations: list[str] | tuple[int, ...],
) -> None:
    """Recording requires typed immutable prepared-observation containers."""
    # Given: a valid prepared receipt whose top-level row tuple was mutated.
    context = execution_context(tmp_path)
    object.__setattr__(context.prepared, "observations", observations)

    # When: the public recorder consumes the hostile prepared receipt.
    with pytest.raises(InvalidPreparedStructureError):
        _ = record(context)

    # Then: row identities are never read from untyped nested content.


@pytest.mark.parametrize("dependencies", [[], (1,)])
def test_public_receipt_rejects_hostile_runtime_dependency_tuple(
    tmp_path: Path,
    dependencies: list[str] | tuple[int, ...],
) -> None:
    """Validation and JSON rendering require typed immutable dependencies."""
    # Given: a rehashed receipt whose nested runtime container was bypass-mutated.
    receipt = record(execution_context(tmp_path))
    object.__setattr__(receipt.runtime, "dependencies", dependencies)
    forged = _rehashed(receipt)

    # When: either public receipt consumer receives the hostile nested structure.
    with pytest.raises(execution.PreparationExecutionReceiptMismatchError) as checked:
        execution.validate_preparation_execution_receipt(forged)
    with pytest.raises(execution.PreparationExecutionReceiptMismatchError) as rendered:
        _ = forged.to_json()

    # Then: both reject it at the runtime tuple boundary.
    assert checked.value.field == "runtime_dependencies"
    assert rendered.value.field == "runtime_dependencies"


@pytest.mark.parametrize("feature_ids", [[], ("gene-1", 2)])
def test_record_rejects_hostile_protocol_feature_tuple(
    tmp_path: Path,
    feature_ids: list[str] | tuple[str, int],
) -> None:
    """Execution recording parses alignment features before protocol traversal."""
    # Given: a protocol whose immutable alignment tuple was bypass-mutated.
    context = execution_context(tmp_path)
    object.__setattr__(context.protocol.alignment, "feature_ids", feature_ids)

    # When: the protocol enters the public execution recorder.
    with pytest.raises(execution.PreparationExecutionReceiptMismatchError) as captured:
        _ = record(context)

    # Then: malformed feature containers are rejected by the named boundary.
    assert captured.value.field == "protocol_alignment_feature_ids"


@pytest.mark.parametrize("parameters", [[], (1,)])
def test_record_rejects_hostile_derivation_parameter_tuple(
    tmp_path: Path,
    parameters: list[str] | tuple[int, ...],
) -> None:
    """Execution recording parses derivation parameters before provenance use."""
    # Given: a canonical derivation with a bypass-mutated parameter tuple.
    context = execution_context(tmp_path)
    derivation = context.materialization.artifact.manifest.derivation
    assert derivation is not None
    object.__setattr__(derivation, "parameters", parameters)

    # When: execution recording reads the materialization provenance.
    with pytest.raises(execution.PreparationExecutionReceiptMismatchError) as captured:
        _ = record(context)

    # Then: only typed immutable derivation parameters may cross this boundary.
    assert captured.value.field == "dataset_canonical_derivation_parameters"


@pytest.mark.parametrize("comparisons", [[], (1,)])
def test_record_rejects_hostile_concordance_summary_tuple(
    tmp_path: Path,
    comparisons: list[str] | tuple[int, ...],
) -> None:
    """Concordance summaries are parsed before attachment status aggregation."""
    # Given: a caller report whose dataset comparison tuple was bypass-mutated.
    context = execution_context(tmp_path)
    object.__setattr__(context.concordance, "dataset_comparisons", comparisons)

    # When: the report is attached to an execution receipt.
    with pytest.raises(execution.PreparationExecutionReceiptMismatchError) as captured:
        _ = record(context)

    # Then: malformed evidence items cannot trigger raw attribute failures.
    assert captured.value.field == "concordance_dataset_comparisons"
