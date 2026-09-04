"""Registered canonical-derivation contract tests for execution receipts."""

from dataclasses import replace
from pathlib import Path

import pytest

import bioml_data.preparation_execution as execution
from bioml_data._artifact_derivation import ArtifactDerivationParameter

from ._execution_receipt_fixtures import execution_context, record


def test_record_rejects_same_id_dataset_and_materialization_contract_forgery(
    tmp_path: Path,
) -> None:
    """An extra derivation parameter cannot be hidden under one artifact ID."""
    # Given: caller-owned manifests agree on an unregistered extra transform choice.
    context = execution_context(tmp_path)
    derivation = context.dataset.artifact.derivation
    assert derivation is not None
    forged_derivation = derivation.model_copy(
        update={
            "parameters": (
                *derivation.parameters,
                ArtifactDerivationParameter(name="unknown_setting", value="forged"),
            )
        }
    )
    forged_manifest = context.dataset.artifact.model_copy(
        update={"derivation": forged_derivation}
    )
    forged_materialization = replace(
        context.materialization,
        artifact=replace(context.materialization.artifact, manifest=forged_manifest),
    )

    # When: execution recording joins the mutually consistent caller objects.
    with pytest.raises(execution.PreparationExecutionReceiptMismatchError) as captured:
        _ = record(
            replace(
                context,
                dataset=replace(context.dataset, artifact=forged_manifest),
                materialization=forged_materialization,
            )
        )

    # Then: the registered complete derivation contract, not caller equality, wins.
    assert captured.value.field == "registered_canonical_derivation"
