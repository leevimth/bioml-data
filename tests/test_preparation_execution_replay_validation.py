"""Replay-backed integrity tests for prepared execution inputs."""

import json
from dataclasses import asdict, replace
from hashlib import sha256
from pathlib import Path
from typing import Literal, assert_never

import pytest

import bioml_data as bio
import bioml_data.preparation_execution as execution
from bioml_data._preparation_identities import (
    PreparedOutputIdentityInput,
    prepared_benchmark_receipt_identity,
    prepared_output_artifact_identity,
)
from bioml_data._preparation_models import (
    InvalidNormalizationTargetError,
    NormalizationParameters,
)
from bioml_data._split import ObservationId

from ._execution_receipt_fixtures import execution_context, record


def _rehashed_execution(
    receipt: execution.PreparationExecutionReceipt,
) -> execution.PreparationExecutionReceipt:
    payload = asdict(receipt)
    del payload["receipt_identity"]
    identity = sha256(
        json.dumps(
            payload,
            sort_keys=True,
            separators=(",", ":"),
            allow_nan=False,
        ).encode()
    ).hexdigest()
    return replace(
        receipt,
        receipt_identity=execution.PreparationExecutionReceiptIdentity(identity),
    )


def _coherently_rehashed_prepared(
    prepared: bio.PreparedBenchmarkReceipt,
    *,
    fitted: bio.FittedPreparationState,
) -> bio.PreparedBenchmarkReceipt:
    provisional = replace(
        prepared,
        fitted_state=fitted,
        output_artifact_identity=prepared_output_artifact_identity(
            PreparedOutputIdentityInput(
                input_artifact_identity=prepared.input_artifact_identity,
                independent_artifact_identity=fitted.independent_artifact_identity,
                fitted_state=fitted,
                protocol_semantic_identity=prepared.protocol_semantic_identity,
                split_assignment_identity=prepared.split_assignment_identity,
                seed=prepared.seed,
                observations=prepared.observations,
            )
        ),
    )
    return replace(
        provisional,
        receipt_identity=prepared_benchmark_receipt_identity(provisional),
    )


def test_record_rejects_stale_selected_features_even_when_state_id_is_retained(
    tmp_path: Path,
) -> None:
    """Mutating selected features cannot reuse a stale fitted-state identity."""
    context = execution_context(tmp_path)
    stale_state = context.prepared.fitted_state.model_copy(
        update={"selected_feature_ids": ("gene-1",)}
    )
    forged = replace(context.prepared, fitted_state=stale_state)

    with pytest.raises(execution.PreparationExecutionReceiptMismatchError) as captured:
        _ = record(replace(context, prepared=forged))

    assert captured.value.field == "prepared_output_artifact_identity"


def test_record_rejects_coherently_rehashed_arbitrary_fitted_state(
    tmp_path: Path,
) -> None:
    """Rehashing all receipt-level identities cannot replace canonical fitting."""
    context = execution_context(tmp_path)
    arbitrary_state = context.prepared.fitted_state.model_copy(
        update={"selected_feature_ids": ("gene-1",)}
    )
    forged = _coherently_rehashed_prepared(
        context.prepared,
        fitted=arbitrary_state,
    )

    with pytest.raises(execution.PreparationExecutionReceiptMismatchError) as captured:
        _ = record(replace(context, prepared=forged))

    assert captured.value.field == "fitted_preparation_state"


@pytest.mark.parametrize(
    ("kind", "field"),
    [
        ("empty", "prepared_observations"),
        ("missing", "prepared_output_artifact_identity"),
        ("extra", "prepared_output_artifact_identity"),
        ("duplicate", "prepared_observations"),
    ],
)
def test_record_rejects_incomplete_or_duplicate_prepared_rows(
    tmp_path: Path,
    kind: Literal["empty", "missing", "extra", "duplicate"],
    field: str,
) -> None:
    """The supplied output must cover exactly the canonical prepared rows."""
    context = execution_context(tmp_path)
    source_rows = context.prepared.observations
    match kind:
        case "empty":
            rows = ()
        case "missing":
            rows = source_rows[:-1]
        case "extra":
            extra = replace(
                source_rows[0], observation_id=ObservationId("unknown-cell")
            )
            rows = (*source_rows, extra)
        case "duplicate":
            rows = (*source_rows, source_rows[0])
        case _:
            assert_never(kind)
    forged = replace(context.prepared, observations=rows)

    with pytest.raises(execution.PreparationExecutionReceiptMismatchError) as captured:
        _ = record(replace(context, prepared=forged))

    assert captured.value.field == field


def test_nonfinite_normalization_is_a_typed_domain_error() -> None:
    """Protocol construction never leaks JSON's bare non-finite ValueError."""
    with pytest.raises(InvalidNormalizationTargetError):
        _ = NormalizationParameters(target_sum=float("nan"))


@pytest.mark.parametrize(
    ("field", "value"),
    [
        ("preparation_protocol_id", "/Users/alice/private-token"),
        ("split_protocol", "https://alice:secret@example.test/split"),
        ("task", "API_KEY=top-secret"),
    ],
)
def test_public_receipt_boundaries_reject_rehashed_unsafe_identifiers(
    tmp_path: Path,
    field: str,
    value: str,
) -> None:
    """Paths, URIs, and environment-like identifier values cannot serialize."""
    receipt = record(execution_context(tmp_path))
    forged = _rehashed_execution(replace(receipt, **{field: value}))

    with pytest.raises(execution.PreparationExecutionReceiptMismatchError) as captured:
        execution.validate_preparation_execution_receipt(forged)
    with pytest.raises(
        execution.PreparationExecutionReceiptMismatchError
    ) as json_error:
        _ = forged.to_json()

    assert captured.value.field == field
    assert json_error.value.field == field
