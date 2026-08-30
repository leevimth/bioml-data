"""Split-aware preparation lifecycle tests."""

from __future__ import annotations

from dataclasses import replace

import pytest

from bioml_data import _preparation as preparation
from bioml_data import _preparation_models as preparation_models
from bioml_data._single_cell import FeatureId, SparseCountMatrix
from bioml_data._split import AssignmentIdentity, SplitPartition
from tests._single_cell_fixtures import make_dataset, make_split


def _protocol() -> preparation.PreparationProtocol:
    return preparation.PreparationProtocol(
        protocol_id="single-cell-canary-preparation",
        version="v1",
        qc=preparation.QcParameters(
            minimum_cell_count=1,
            minimum_feature_cells=1,
        ),
        alignment=preparation.GeneAlignmentParameters(
            feature_ids=(FeatureId("gene-1"), FeatureId("gene-2"), FeatureId("gene-3")),
        ),
        normalization=preparation.NormalizationParameters(target_sum=100.0),
        feature_selection=preparation.FeatureSelectionParameters(max_features=2),
    )


def test_preparation_facade_preserves_consumed_model_bindings() -> None:
    # Given: model contracts consumed through the preparation facade.

    # When: the consumed bindings are resolved from both module surfaces.

    # Then: the facade preserves the exact model objects.
    assert preparation.PreparationProtocol is preparation_models.PreparationProtocol
    assert preparation.QcParameters is preparation_models.QcParameters
    assert (
        preparation.GeneAlignmentParameters
        is preparation_models.GeneAlignmentParameters
    )
    assert (
        preparation.NormalizationParameters
        is preparation_models.NormalizationParameters
    )
    assert (
        preparation.FeatureSelectionParameters
        is preparation_models.FeatureSelectionParameters
    )
    assert (
        preparation.SplitAssignmentRequiredError
        is preparation_models.SplitAssignmentRequiredError
    )
    assert preparation.PreparationRequest is preparation_models.PreparationRequest
    assert (
        preparation.FittedPreparationState is preparation_models.FittedPreparationState
    )


def test_train_fitted_preprocessing_requires_split_assignment() -> None:
    # Given: train-independent preparation completed on a canonical artifact.
    independent = preparation.prepare_train_independent(
        make_dataset(),
        protocol=_protocol(),
        seed=17,
    )

    # When: fitting is attempted without a split assignment.
    with pytest.raises(preparation.SplitAssignmentRequiredError):
        _ = preparation.fit_train_preprocessing(independent, split=None)

    # Then: no full-dataset fitted state is produced.


def test_validation_and_test_changes_do_not_change_fitted_state() -> None:
    # Given: one independent preparation and two receipts with identical train rows.
    dataset = make_dataset()
    independent = preparation.prepare_train_independent(
        dataset,
        protocol=_protocol(),
        seed=17,
    )
    original = make_split(dataset)
    replacement_partition = {
        SplitPartition.TRAIN: SplitPartition.TRAIN,
        SplitPartition.VALIDATION: SplitPartition.TEST,
        SplitPartition.TEST: SplitPartition.VALIDATION,
    }
    changed_assignments = tuple(
        replace(
            assignment,
            partition=replacement_partition[assignment.partition],
        )
        for assignment in original.assignments
    )
    changed = replace(
        original,
        assignments=changed_assignments,
        assignment_identity=AssignmentIdentity("changed-val-test"),
    )

    # When: feature selection is fitted against each receipt.
    first = preparation.fit_train_preprocessing(independent, split=original)
    second = preparation.fit_train_preprocessing(independent, split=changed)

    # Then: fitted identity and selected features depend only on train rows.
    assert first.state_identity == second.state_identity
    assert first.selected_feature_ids == second.selected_feature_ids


def test_held_out_feature_support_does_not_change_fitted_state() -> None:
    # Given: identical train rows and one held-out-only nonzero change.
    dataset = make_dataset()
    changed_counts = SparseCountMatrix(
        format=dataset.counts.format,
        shape=dataset.counts.shape,
        values=dataset.counts.values[:-3] + dataset.counts.values[-2:],
        column_indices=(
            dataset.counts.column_indices[:-3] + dataset.counts.column_indices[-2:]
        ),
        row_offsets=(
            *dataset.counts.row_offsets[:-1],
            len(dataset.counts.values) - 1,
        ),
    )
    changed_dataset = replace(dataset, counts=changed_counts)
    protocol = replace(
        _protocol(),
        qc=preparation.QcParameters(
            minimum_cell_count=1,
            minimum_feature_cells=4,
        ),
        feature_selection=None,
    )
    split = make_split(dataset)

    # When: feature support is fitted after independently preparing each artifact.
    first = preparation.fit_train_preprocessing(
        preparation.prepare_train_independent(dataset, protocol=protocol, seed=17),
        split=split,
    )
    second = preparation.fit_train_preprocessing(
        preparation.prepare_train_independent(
            changed_dataset,
            protocol=protocol,
            seed=17,
        ),
        split=split,
    )

    # Then: held-out counts cannot affect train-fitted state or selected features.
    assert first.state_identity == second.state_identity
    assert first.selected_feature_ids == second.selected_feature_ids


def test_fitted_state_rejects_a_different_split_receipt() -> None:
    # Given: fitted state bound to one exact split receipt.
    dataset = make_dataset()
    split = make_split(dataset)
    independent = preparation.prepare_train_independent(
        dataset,
        protocol=_protocol(),
        seed=17,
    )
    fitted = preparation.fit_train_preprocessing(independent, split=split)
    other_split = replace(
        split,
        assignment_identity=AssignmentIdentity("different-split"),
    )

    # When: the state is applied with a different split identity.
    with pytest.raises(preparation.FittedSplitMismatchError) as captured:
        _ = preparation.apply_fitted_preprocessing(
            independent,
            fitted=fitted,
            split=other_split,
        )

    # Then: the typed failure identifies both split receipts.
    assert captured.value.expected == split.assignment_identity
    assert captured.value.actual == other_split.assignment_identity


def test_prepared_identity_is_deterministic_for_same_inputs() -> None:
    # Given: one artifact, protocol, split, and seed.
    dataset = make_dataset()
    split = make_split(dataset)

    # When: the complete lifecycle is run twice.
    request = preparation.PreparationRequest(
        dataset=dataset,
        protocol=_protocol(),
        split=split,
        seed=17,
    )
    first = preparation.prepare_benchmark(request)
    second = preparation.prepare_benchmark(request)

    # Then: output artifact and receipt identities are stable.
    assert first.output_artifact_identity == second.output_artifact_identity
    assert first.receipt_identity == second.receipt_identity


def test_fitted_state_serializes_and_reapplies() -> None:
    # Given: a fitted train-only feature-selection state.
    dataset = make_dataset()
    split = make_split(dataset)
    independent = preparation.prepare_train_independent(
        dataset,
        protocol=_protocol(),
        seed=17,
    )
    fitted = preparation.fit_train_preprocessing(independent, split=split)

    # When: the state crosses JSON and is reapplied to every partition.
    restored = preparation.FittedPreparationState.model_validate_json(
        fitted.model_dump_json()
    )
    first = preparation.apply_fitted_preprocessing(
        independent,
        fitted=restored,
        split=split,
    )
    second = preparation.apply_fitted_preprocessing(
        independent,
        fitted=fitted,
        split=split,
    )

    # Then: serialization preserves state and deterministic application.
    assert restored == fitted
    assert len(restored.selected_feature_ids) == 2
    assert first == second
