"""Preparation-execution receipt scenarios."""

from dataclasses import replace
from pathlib import Path

import pytest

import bioml_data.preparation_execution as execution
from bioml_data._artifacts import ArtifactId, TransformProtocolId
from bioml_data._split_capability_models import SplitArtifactScope

from ._execution_receipt_fixtures import artifact, execution_context, record


def test_record_preparation_execution_commits_to_the_complete_scientific_context(
    tmp_path: Path,
) -> None:
    """A run receipt is stable, path-free, and links every execution layer."""
    # Given: canonical data, its raw parent, a split-aware preparation, and evidence.
    context = execution_context(tmp_path)

    # When: the identical scientific preparation is recorded twice.
    first = record(context)
    second = record(context)

    # Then: canonical JSON and the complete execution identity are deterministic.
    assert first == second
    assert first.to_json() == second.to_json()
    assert first.input_artifact_identity == context.input_artifact.artifact_id
    assert (
        first.canonical_artifact_identity
        == context.materialization.artifact.artifact_id
    )
    assert (
        first.prepared_benchmark_receipt_identity == context.prepared.receipt_identity
    )
    assert (
        first.canonical_materialization_fit_scope is execution.PreparationFitScope.NONE
    )
    assert first.prepared_fit_scope is execution.PreparationFitScope.TRAIN_ONLY
    assert first.semantic_parameters.alignment_feature_ids == (
        "gene-1",
        "gene-2",
        "gene-3",
    )
    assert first.metadata_concordance is not None
    assert (
        first.metadata_concordance.status
        is execution.MetadataConcordanceAttachmentStatus.NOT_REPORTED
    )
    assert str(tmp_path) not in first.to_json()


def test_record_preparation_execution_rejects_cross_receipt_scope_mismatch(
    tmp_path: Path,
) -> None:
    """A receipt cannot silently bind a prepared result to another split."""
    # Given: a valid run context and a forged prepared split identity.
    context = execution_context(tmp_path)
    context = replace(
        context,
        prepared=replace(
            context.prepared,
            split_assignment_identity="forged-assignment",
        ),
    )

    # When: recording tries to join the incompatible receipts.
    with pytest.raises(execution.PreparationExecutionReceiptMismatchError) as captured:
        _ = record(context)

    # Then: the failure names the exact cross-receipt field.
    assert captured.value.field == "prepared_split_assignment_identity"


def test_validate_preparation_execution_receipt_rejects_identity_tampering(
    tmp_path: Path,
) -> None:
    """A mutable-bypass edit cannot retain a valid execution identity."""
    # Given: one verified execution receipt.
    receipt = record(execution_context(tmp_path))
    forged = replace(receipt, seed=18)

    # When: a consumer verifies the altered receipt.
    with pytest.raises(execution.PreparationExecutionReceiptMismatchError) as captured:
        execution.validate_preparation_execution_receipt(forged)

    # Then: identity verification refuses the altered semantic value.
    assert captured.value.field == "receipt_identity"


def test_record_preparation_execution_rejects_unlinked_input_artifact(
    tmp_path: Path,
) -> None:
    """A raw receipt must be an exact parent of the recorded canonical artifact."""
    # Given: a valid context whose supplied raw artifact is substituted.
    context = execution_context(tmp_path)
    unlinked = artifact(
        artifact_id=ArtifactId(
            "sha256:bbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbb"
        ),
        directory=tmp_path / "unlinked",
    )

    # When: execution recording joins that unrelated raw receipt.
    with pytest.raises(execution.PreparationExecutionReceiptMismatchError) as captured:
        _ = record(replace(context, input_artifact=unlinked))

    # Then: it rejects the claimed input before emitting an identity.
    assert captured.value.field == "input_artifact"


def test_record_preparation_execution_rejects_tampered_prepared_identity(
    tmp_path: Path,
) -> None:
    """Prepared output and receipt identities are recomputed before recording."""
    # Given: a valid context with a forged prepared-output identity.
    context = execution_context(tmp_path)
    context = replace(
        context,
        prepared=replace(context.prepared, output_artifact_identity="forged-output"),
    )

    # When: receipt construction checks the existing preparation output.
    with pytest.raises(execution.PreparationExecutionReceiptMismatchError) as captured:
        _ = record(context)

    # Then: tampering is stopped at the cross-receipt validation boundary.
    assert captured.value.field == "prepared_output_artifact_identity"


def test_record_preparation_execution_rejects_concordance_from_another_artifact(
    tmp_path: Path,
) -> None:
    """Metadata evidence cannot be rebound from another canonical transform."""
    # Given: a valid context with publication evidence scoped to another raw artifact.
    context = execution_context(tmp_path)
    forged_scope = replace(
        context.concordance.scope,
        artifact=SplitArtifactScope(
            source_artifact=ArtifactId(
                "sha256:cccccccccccccccccccccccccccccccccccccccccccccccccccccccccccccccc"
            ),
            transform_protocol=TransformProtocolId("tms-aorta-csr-v1"),
        ),
    )
    forged = replace(context.concordance, scope=forged_scope)

    # When: an execution receipt tries to attach the incompatible report.
    with pytest.raises(execution.PreparationExecutionReceiptMismatchError) as captured:
        _ = record(replace(context, concordance=forged))

    # Then: the source artifact mismatch is explicit and receipt construction stops.
    assert captured.value.field == "concordance_source_artifacts"


@pytest.mark.parametrize(
    ("component", "version", "field"),
    [
        ("DATABASE_URL", "1.0.0", "dependency_component"),
        (execution.RuntimeComponent.ANNDATA, "/Users/alice/work", "dependency_version"),
        (execution.RuntimeComponent.ANNDATA, "../secret", "dependency_version"),
        (
            execution.RuntimeComponent.ANNDATA,
            "postgres://alice:secret@host/db",
            "dependency_version",
        ),
        (execution.RuntimeComponent.ANNDATA, "$API_KEY", "dependency_version"),
        (execution.RuntimeComponent.ANNDATA, "1.0.0;rm", "dependency_version"),
        (execution.RuntimeComponent.ANNDATA, "1" * 65, "dependency_version"),
    ],
)
def test_runtime_rejects_untrusted_component_or_version(
    component: execution.RuntimeComponent | str,
    version: str,
    field: str,
) -> None:
    """Runtime receipt values cannot carry paths, secrets, or command text."""
    # Given: one untrusted runtime component or version boundary value.

    # When: a public dependency version is parsed.
    with pytest.raises(execution.PreparationExecutionReceiptMismatchError) as captured:
        _ = execution.DependencyVersion(component=component, version=version)

    # Then: it fails before a receipt can serialize it.
    assert captured.value.field == field


@pytest.mark.parametrize("version", ["0.0.0", "1.2.3.dev4+gabcdef", "1!2.0rc1"])
def test_runtime_accepts_bounded_package_version_forms(version: str) -> None:
    """Ordinary PEP 440 and semver-like package versions remain usable."""
    # Given: one safe bounded package-version representation.

    # When: it is used for both toolkit and a named dependency.
    runtime = execution.PreparationExecutionRuntime(
        toolkit_version=version,
        dependencies=(
            execution.DependencyVersion(
                component=execution.RuntimeComponent.ANNDATA, version=version
            ),
        ),
    )

    # Then: canonical runtime metadata retains the accepted version verbatim.
    assert runtime.toolkit_version == version


def test_runtime_rejects_untrusted_toolkit_version() -> None:
    """Toolkit metadata cannot serialize a path, shell text, or a secret."""
    # Given: a host-local value that is not a compact package version.

    # When: it is used as the toolkit version.
    with pytest.raises(execution.PreparationExecutionReceiptMismatchError) as captured:
        _ = execution.PreparationExecutionRuntime(
            toolkit_version="/Users/alice/work; API_KEY=top-secret",
            dependencies=(),
        )

    # Then: construction fails before this metadata can enter a receipt.
    assert captured.value.field == "toolkit_version"
