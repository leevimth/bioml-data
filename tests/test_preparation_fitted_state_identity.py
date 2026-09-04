"""Scientific identity boundaries for train-fitted preparation state."""

from dataclasses import replace

import pytest

from bioml_data import _preparation as preparation
from bioml_data._preparation_errors import InvalidPreparedValueError
from bioml_data._preparation_identities import prepared_benchmark_receipt_identity
from bioml_data._preparation_models import PreparedValue
from bioml_data._single_cell import FeatureId
from bioml_data._split import SplitPartition, assignment_receipt_identity

from ._single_cell_fixtures import make_dataset, make_split


def _protocol() -> preparation.PreparationProtocol:
    """Return the small fixture's complete train-fitted protocol."""
    return preparation.PreparationProtocol(
        protocol_id="single-cell-canary-preparation",
        version="v1",
        qc=preparation.QcParameters(
            minimum_cell_count=1,
            minimum_feature_cells=1,
        ),
        alignment=preparation.GeneAlignmentParameters(
            feature_ids=(
                FeatureId("gene-1"),
                FeatureId("gene-2"),
                FeatureId("gene-3"),
            ),
        ),
        normalization=preparation.NormalizationParameters(target_sum=100.0),
        feature_selection=preparation.FeatureSelectionParameters(max_features=2),
    )


def test_fitted_state_identity_changes_when_training_membership_changes() -> None:
    """Changing a train row changes the train-fitted state identity."""
    # Given: one canonical preparation and a split with a held-out row.
    dataset = make_dataset()
    independent = preparation.prepare_train_independent(
        dataset,
        protocol=_protocol(),
        seed=17,
    )
    original = make_split(dataset)
    held_out = next(
        item
        for item in original.assignments
        if item.partition is not SplitPartition.TRAIN
    )
    changed = replace(
        original,
        assignments=tuple(
            replace(item, partition=SplitPartition.TRAIN) if item == held_out else item
            for item in original.assignments
        ),
    )

    # When: state is fitted with one additional training observation.
    first = preparation.fit_train_preprocessing(independent, split=original)
    second = preparation.fit_train_preprocessing(independent, split=changed)

    # Then: the membership-sensitive state identity changes.
    assert first.state_identity != second.state_identity


def test_fitted_state_identity_ignores_held_out_only_artifact_changes() -> None:
    """Held-out-only independent bytes do not change train-fitted state identity."""
    # Given: independent rows that differ only by their content-addressed identity.
    dataset = make_dataset()
    original = preparation.prepare_train_independent(
        dataset,
        protocol=_protocol(),
        seed=17,
    )
    held_out_only = replace(
        original,
        output_artifact_identity="held-out-only-artifact-change",
    )
    split = make_split(dataset)

    # When: fitting uses the identical canonical training rows.
    first = preparation.fit_train_preprocessing(original, split=split)
    second = preparation.fit_train_preprocessing(held_out_only, split=split)
    first_receipt = preparation.apply_fitted_preprocessing(
        original,
        fitted=first,
        split=split,
    )
    second_receipt = preparation.apply_fitted_preprocessing(
        held_out_only,
        fitted=second,
        split=split,
    )

    # Then: only outer prepared receipts, not fitted-state semantics, change.
    assert first.state_identity == second.state_identity
    assert (
        first_receipt.independent_artifact_identity
        != second_receipt.independent_artifact_identity
    )
    assert (
        first_receipt.output_artifact_identity
        != second_receipt.output_artifact_identity
    )


def test_prepared_receipt_binds_held_out_split_reassignment() -> None:
    """Validation/test reassignment changes outer receipt but not fitted state."""
    # Given: a fitted state and another valid split with the same train rows.
    dataset = make_dataset()
    independent = preparation.prepare_train_independent(
        dataset,
        protocol=_protocol(),
        seed=17,
    )
    original = make_split(dataset)
    reassigned = replace(
        original,
        assignments=tuple(
            replace(
                assignment,
                partition={
                    SplitPartition.TRAIN: SplitPartition.TRAIN,
                    SplitPartition.VALIDATION: SplitPartition.TEST,
                    SplitPartition.TEST: SplitPartition.VALIDATION,
                }[assignment.partition],
            )
            for assignment in original.assignments
        ),
    )
    changed = replace(
        reassigned,
        assignment_identity=assignment_receipt_identity(reassigned),
    )
    fitted = preparation.fit_train_preprocessing(independent, split=original)

    # When: the state is applied under both held-out assignment configurations.
    first = preparation.apply_fitted_preprocessing(
        independent,
        fitted=fitted,
        split=original,
    )
    second = preparation.apply_fitted_preprocessing(
        independent,
        fitted=fitted,
        split=changed,
    )

    # Then: train fitting is reusable and output lineage records full split state.
    assert second.split_assignment_identity == changed.assignment_identity
    assert first.output_artifact_identity != second.output_artifact_identity


@pytest.mark.parametrize("value", [float("nan"), float("inf"), float("-inf")])
def test_prepared_value_rejects_nonfinite_domain_values(value: float) -> None:
    """A sparse prepared value cannot carry a non-finite numeric payload."""
    # Given: one non-finite expression value.

    # When: it crosses the prepared-value domain boundary.
    with pytest.raises(InvalidPreparedValueError):
        _ = PreparedValue(feature_id=FeatureId("gene-1"), value=value)

    # Then: no identity or replay can receive it.


@pytest.mark.parametrize("value", [float("nan"), float("inf"), float("-inf")])
def test_prepared_receipt_identity_rejects_mutated_nonfinite_values(
    value: float,
) -> None:
    """Frozen-value bypasses are rejected before identity rendering."""
    # Given: an otherwise valid completed prepared benchmark receipt.
    dataset = make_dataset()
    receipt = preparation.prepare_benchmark(
        preparation.PreparationRequest(
            dataset=dataset,
            protocol=_protocol(),
            split=make_split(dataset),
            seed=17,
        )
    )
    prepared_value = receipt.observations[0].values[0]
    object.__setattr__(prepared_value, "value", value)

    # When: receipt identity recomputation consumes the hostile nested value.
    with pytest.raises(InvalidPreparedValueError):
        _ = prepared_benchmark_receipt_identity(receipt)

    # Then: JSON hashing is never reached with NaN or infinity.
