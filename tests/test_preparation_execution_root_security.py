"""Root-object and error-redaction scenarios for execution recording."""

from dataclasses import replace
from pathlib import Path

import pytest

import bioml_data.preparation_execution as execution
from bioml_data._preparation_errors import InvalidPreparedValueError
from bioml_data._preparation_models import validate_prepared_observations

from ._execution_receipt_fixtures import ExecutionContext, execution_context, record


class _RequestSubclass(execution.PreparationExecutionRequest):
    """Hostile decoded subclass used to prove the exact request type boundary."""


def _request(context: ExecutionContext) -> execution.PreparationExecutionRequest:
    """Build the public execution request from a complete typed fixture."""
    return execution.PreparationExecutionRequest(
        dataset=context.dataset,
        input_artifact=context.input_artifact,
        materialization=context.materialization,
        prepared=context.prepared,
        assignment=context.assignment,
        protocol=context.protocol,
        runtime=context.runtime,
        concordance=context.concordance,
    )


def test_record_rejects_non_exact_request_root_type(tmp_path: Path) -> None:
    """A request subclass cannot bypass the exact public root boundary."""
    # Given: a structurally complete but non-exact request object.
    context = execution_context(tmp_path)
    request = _RequestSubclass(
        dataset=context.dataset,
        input_artifact=context.input_artifact,
        materialization=context.materialization,
        prepared=context.prepared,
        assignment=context.assignment,
        protocol=context.protocol,
        runtime=context.runtime,
        concordance=context.concordance,
    )

    # When: the recorder receives the non-exact root.
    with pytest.raises(execution.PreparationExecutionReceiptMismatchError) as captured:
        _ = execution.record_preparation_execution(request)

    # Then: it fails before any root field is dereferenced.
    assert captured.value.field == "execution_request"


@pytest.mark.parametrize(
    "field",
    [
        "dataset",
        "input_artifact",
        "materialization",
        "prepared",
        "assignment",
        "protocol",
        "runtime",
        "concordance",
    ],
)
def test_record_rejects_string_in_every_request_root_field(
    tmp_path: Path,
    field: str,
) -> None:
    """No root field is dereferenced before exact runtime type parsing."""
    # Given: a public request with one frozen root field bypass-mutated to text.
    request = _request(execution_context(tmp_path))
    object.__setattr__(request, field, "hostile-root")

    # When: execution recording consumes the request.
    with pytest.raises(execution.PreparationExecutionReceiptMismatchError) as captured:
        _ = execution.record_preparation_execution(request)

    # Then: the named root field fails without an AttributeError.
    assert captured.value.field == f"request_{field}"


def test_record_rejects_none_request_root(tmp_path: Path) -> None:
    """Only the optional concordance root may be none."""
    # Given: a valid request with a non-optional root bypass-mutated to none.
    request = _request(execution_context(tmp_path))
    object.__setattr__(request, "protocol", None)

    # When: recording reaches the public request boundary.
    with pytest.raises(execution.PreparationExecutionReceiptMismatchError) as captured:
        _ = execution.record_preparation_execution(request)

    # Then: the typed root guard rejects before attribute traversal.
    assert captured.value.field == "request_protocol"


def test_record_rejects_object_request_root(tmp_path: Path) -> None:
    """An untyped object cannot substitute for a root artifact receipt."""
    # Given: a valid request with its input receipt bypass-mutated to an object.
    request = _request(execution_context(tmp_path))
    object.__setattr__(request, "input_artifact", object())

    # When: recording reaches the public request boundary.
    with pytest.raises(execution.PreparationExecutionReceiptMismatchError) as captured:
        _ = execution.record_preparation_execution(request)

    # Then: the typed root guard rejects before attribute traversal.
    assert captured.value.field == "request_input_artifact"


def test_record_rejects_hostile_nested_artifact_manifest_before_dereference(
    tmp_path: Path,
) -> None:
    """A receipt manifest cannot be changed to a scalar under a valid root type."""
    # Given: an exact ArtifactReceipt whose frozen manifest field was bypass-mutated.
    context = execution_context(tmp_path)
    object.__setattr__(context.input_artifact, "manifest", "hostile-manifest")

    # When: recording checks the input artifact lineage.
    with pytest.raises(execution.PreparationExecutionReceiptMismatchError) as captured:
        _ = record(context)

    # Then: no `.artifact_id` dereference occurs on untyped content.
    assert captured.value.field == "request_input_artifact_manifest"


def test_cross_object_manifest_mismatch_does_not_render_uri_credentials(
    tmp_path: Path,
) -> None:
    """Lineage disagreement emits a category-only mismatch error."""
    # Given: a materialization manifest differing only by a credential-bearing URI.
    context = execution_context(tmp_path)
    secret = "TOP" + "_SECRET"
    altered_manifest = context.materialization.artifact.manifest.model_copy(
        update={"source_uri": f"https://alice:{secret}@example.test/data"}
    )
    altered_artifact = replace(
        context.materialization.artifact, manifest=altered_manifest
    )
    altered_context = replace(
        context,
        materialization=replace(context.materialization, artifact=altered_artifact),
    )

    # When: the mismatched manifests are joined at execution recording.
    with pytest.raises(execution.PreparationExecutionReceiptMismatchError) as captured:
        _ = record(altered_context)

    # Then: the exception identifies the category but contains no URI credential.
    assert captured.value.field == "canonical_artifact_manifest"
    assert secret not in str(captured.value)
    assert secret not in repr(captured.value)


def test_prepared_value_domain_error_does_not_render_hostile_content(
    tmp_path: Path,
) -> None:
    """Prepared sparse-value validation keeps invalid payloads out of error text."""
    # Given: a valid prepared value bypass-mutated to credential-like text.
    context = execution_context(tmp_path)
    value = context.prepared.observations[0].values[0]
    secret = "TOP" + "_SECRET"
    object.__setattr__(value, "value", secret)

    # When: public prepared-row validation parses the hostile value.
    with pytest.raises(InvalidPreparedValueError) as captured:
        validate_prepared_observations(context.prepared.observations)

    # Then: the domain exception identifies the invalid category without content.
    assert secret not in str(captured.value)
    assert secret not in repr(captured.value)
