"""Public-boundary adversarial tests for preparation-execution receipts."""

import json
from dataclasses import asdict, replace
from hashlib import sha256
from pathlib import Path

import pytest

import bioml_data as bio
import bioml_data.preparation_execution as execution
from bioml_data._artifact_derivation import ArtifactDerivationParameter
from bioml_data._artifacts import ArtifactDerivation

from ._execution_receipt_fixtures import execution_context, record


def _rehashed(
    receipt: execution.PreparationExecutionReceipt,
) -> execution.PreparationExecutionReceipt:
    """Return a receipt whose public hash matches hostile nested values."""
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


@pytest.mark.parametrize(
    ("field", "value"),
    [
        ("minimum_cell_count", -1),
        ("minimum_cell_count", 0),
        ("minimum_cell_count", True),
        ("minimum_cell_count", "1"),
        ("minimum_cell_count", 1.0),
        ("minimum_feature_cells", -1),
        ("minimum_feature_cells", 0),
        ("minimum_feature_cells", True),
        ("minimum_feature_cells", "1"),
        ("minimum_feature_cells", 1.0),
        ("max_features", -1),
        ("max_features", 0),
        ("max_features", True),
        ("max_features", "oops"),
        ("max_features", 1.0),
        ("alignment_feature_count", True),
        ("alignment_feature_count", "3"),
        ("alignment_feature_count", 3.0),
        ("alignment_feature_count", -1),
        ("alignment_feature_ids", ("gene-1", 2)),
        ("alignment_feature_identity", 2),
        ("normalization_target_sum", True),
        ("normalization_target_sum", "100"),
    ],
)
def test_public_receipt_rejects_rehashed_invalid_semantic_parameter_types(
    tmp_path: Path,
    field: str,
    value: bool | float | str | tuple[str, int],
) -> None:
    """Both consumers parse every nested semantic field at their boundary."""
    # Given: a hostile decoded receipt with a recomputed outer identity.
    receipt = record(execution_context(tmp_path))
    parameters = receipt.semantic_parameters
    object.__setattr__(parameters, field, value)
    forged = _rehashed(replace(receipt, semantic_parameters=parameters))

    # When: either public receipt consumer receives the forged content.
    with pytest.raises(execution.PreparationExecutionReceiptMismatchError) as checked:
        execution.validate_preparation_execution_receipt(forged)
    with pytest.raises(execution.PreparationExecutionReceiptMismatchError) as rendered:
        _ = forged.to_json()

    # Then: the exact nested field is rejected before it can be consumed.
    expected_field = (
        "alignment_feature_id" if field == "alignment_feature_ids" else field
    )
    assert checked.value.field == expected_field
    assert rendered.value.field == expected_field


def test_public_receipt_accepts_boundary_valid_semantic_counts(tmp_path: Path) -> None:
    """Minimum positive integer contracts retain their valid lower boundary."""
    # Given: a receipt rehashed with the smallest valid semantic count values.
    receipt = record(execution_context(tmp_path))
    parameters = replace(
        receipt.semantic_parameters,
        minimum_cell_count=1,
        minimum_feature_cells=1,
        max_features=1,
    )
    forged = _rehashed(replace(receipt, semantic_parameters=parameters))

    # When: a public consumer validates and renders it.
    execution.validate_preparation_execution_receipt(forged)
    rendered = forged.to_json()

    # Then: valid boundary values remain serializable.
    assert '"max_features":1' in rendered


def test_receipt_errors_do_not_echo_rejected_runtime_secrets() -> None:
    """A rejected runtime token cannot escape through exception rendering."""
    # Given: a credential-bearing string that is invalid runtime metadata.
    credential = "top" + "-secret"
    unsafe_runtime_value = f"postgres://alice:{credential}@host.example/db"

    # When: runtime parsing rejects the unsafe version value.
    with pytest.raises(execution.PreparationExecutionReceiptMismatchError) as captured:
        _ = execution.DependencyVersion(
            component=execution.RuntimeComponent.NUMPY,
            version=unsafe_runtime_value,
        )

    # Then: neither display nor exception arguments reproduce the secret.
    assert unsafe_runtime_value not in str(captured.value)
    assert credential not in repr(captured.value)


def test_record_rejects_same_id_forged_canonical_manifest(tmp_path: Path) -> None:
    """A materialization cannot substitute derivation fields beneath one ID."""
    # Given: a canonical receipt whose content ID is retained but manifest differs.
    context = execution_context(tmp_path)
    derivation = context.materialization.artifact.manifest.derivation
    assert derivation is not None
    altered_derivation = derivation.model_copy(
        update={
            "parameters": (
                ArtifactDerivationParameter(name="expression_input", value="X"),
            )
        }
    )
    altered_manifest = context.materialization.artifact.manifest.model_copy(
        update={"derivation": altered_derivation}
    )
    altered_artifact = replace(
        context.materialization.artifact, manifest=altered_manifest
    )
    forged = replace(context.materialization, artifact=altered_artifact)

    # When: execution recording consumes the substituted materialization receipt.
    with pytest.raises(execution.PreparationExecutionReceiptMismatchError) as captured:
        _ = record(replace(context, materialization=forged))

    # Then: exact canonical manifest provenance, not only its artifact ID, is bound.
    assert captured.value.field == "canonical_artifact_manifest"


def test_record_rejects_unsupported_expression_input_even_when_manifest_matches(
    tmp_path: Path,
) -> None:
    """The current preparation pipeline has one raw.X matrix contract."""
    # Given: matching dataset and materialization manifests declaring X, not raw.X.
    context = execution_context(tmp_path)
    derivation = context.materialization.artifact.manifest.derivation
    assert derivation is not None
    updated_derivation = ArtifactDerivation(
        parent_artifacts=derivation.parent_artifacts,
        transform_protocol=derivation.transform_protocol,
        parameters=(ArtifactDerivationParameter(name="expression_input", value="X"),),
    )
    updated_manifest = context.dataset.artifact.model_copy(
        update={"derivation": updated_derivation}
    )
    updated_artifact = replace(
        context.materialization.artifact, manifest=updated_manifest
    )

    # When: the actual pipeline is asked to record an unsupported matrix choice.
    with pytest.raises(execution.PreparationExecutionReceiptMismatchError) as captured:
        _ = record(
            replace(
                context,
                dataset=replace(context.dataset, artifact=updated_manifest),
                materialization=replace(
                    context.materialization, artifact=updated_artifact
                ),
            )
        )

    # Then: the registered transform contract rejects an unsupported matrix source.
    assert captured.value.field == "registered_canonical_derivation"


def test_record_recomputes_concordance_statuses_before_attachment(
    tmp_path: Path,
) -> None:
    """A caller cannot relabel not-reported evidence as a metadata match."""
    # Given: a complete report with one declared-not-reported comparison relabeled.
    context = execution_context(tmp_path)
    comparison = context.concordance.dataset_comparisons[0]
    forged_report = replace(
        context.concordance,
        dataset_comparisons=(
            replace(comparison, status=bio.MetadataConcordance.MATCH),
            *context.concordance.dataset_comparisons[1:],
        ),
    )

    # When: execution recording receives the rehashed caller-supplied report.
    with pytest.raises(execution.PreparationExecutionReceiptMismatchError) as captured:
        _ = record(replace(context, concordance=forged_report))

    # Then: attachment status is derived from a full canonical report replay.
    assert captured.value.field == "concordance_report"
