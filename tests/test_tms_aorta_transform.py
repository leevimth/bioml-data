"""TMS Aorta raw-H5AD to canonical-artifact scenarios."""

from concurrent.futures import ThreadPoolExecutor
from dataclasses import replace
from pathlib import Path
from threading import Barrier

import anndata as ad
import pytest

import bioml_data as bio
from bioml_data.datasets.tms_aorta import _transform as transform_module
from bioml_data.datasets.tms_aorta._h5ad_transform import (
    RawTmsViolation,
    TmsAortaTransformLimits,
)
from bioml_data.datasets.tms_aorta._interchange import TmsAortaPayload
from bioml_data.datasets.tms_aorta._transform import prepare_tms_aorta
from tests._anndata_fixtures import TmsH5adVariant, store_tms_aorta_h5ad

_FIXTURE_LIMITS = TmsAortaTransformLimits(
    observations=6,
    features=3,
    maximum_nonzero_counts=20,
    maximum_metadata_length=64,
    maximum_output_bytes=32_000,
)


def _prepare_fixture(
    raw: bio.ArtifactReceipt,
    data_dir: Path,
) -> bio.DatasetPreparationReceipt:
    return prepare_tms_aorta(raw, data_dir=data_dir, limits=_FIXTURE_LIMITS)


def test_prepare_dataset_transforms_raw_counts_and_preserves_parent(
    tmp_path: Path,
) -> None:
    # Given: a verified TMS-shaped H5AD whose processed X differs from raw.X.
    raw = store_tms_aorta_h5ad(tmp_path / "cache", tmp_path / "source.h5ad")

    # When: the public preparation API creates the canonical artifact.
    result = _prepare_fixture(raw, tmp_path / "cache")
    dataset = bio.load_dataset("tms-aorta", artifact=result.artifact)

    # Then: integer raw counts, observation identity, and derivation are explicit.
    assert result.outcome is bio.DatasetPreparationOutcome.TRANSFORMED
    assert dataset.counts.values == (4, 1, 3, 2, 1, 5, 1, 1, 1, 3, 1)
    assert tuple(item.cell_id for item in dataset.observations) == (
        "cell-1",
        "cell-2",
        "cell-3",
        "cell-4",
        "cell-5",
        "cell-6",
    )
    assert tuple(item.donor_id for item in dataset.observations) == (
        "mouse-a",
        "mouse-a",
        "mouse-b",
        "mouse-c",
        "mouse-d",
        "mouse-e",
    )
    assert all(item.assay is None for item in dataset.observations)
    assert result.artifact.manifest.derivation is not None
    assert result.artifact.manifest.derivation.parent_artifacts == (raw.artifact_id,)
    assert (
        result.artifact.manifest.derivation.transform_protocol
        == "tms-aorta-csr-v1"
    )
    assert result.artifact.manifest.derivation.parameters == (
        bio.ArtifactDerivationParameter(
            name="expression_input",
            value="raw.X",
        ),
    )


def test_prepare_dataset_reuses_verified_transform_without_reading_h5ad(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    # Given: one completed canonical transform in the selected data directory.
    raw = store_tms_aorta_h5ad(tmp_path / "cache", tmp_path / "source.h5ad")
    first = _prepare_fixture(raw, tmp_path / "cache")

    def fail_if_reopened(_path: Path) -> None:
        pytest.fail("valid prepared cache must skip H5AD parsing")

    monkeypatch.setattr(ad, "read_h5ad", fail_if_reopened)

    # When: the same parent and protocol are prepared again.
    second = _prepare_fixture(raw, tmp_path / "cache")

    # Then: the verified immutable artifact is reused without duplicate work.
    assert second.outcome is bio.DatasetPreparationOutcome.CACHE_HIT
    assert second.artifact == first.artifact
    assert second.artifact.manifest.derivation is not None
    assert second.artifact.manifest.derivation.parameters == (
        bio.ArtifactDerivationParameter(
            name="expression_input",
            value="raw.X",
        ),
    )


def test_prepare_dataset_rejects_corrupt_prepared_cache(tmp_path: Path) -> None:
    # Given: a completed transform whose immutable canonical blob is corrupted.
    raw = store_tms_aorta_h5ad(tmp_path / "cache", tmp_path / "source.h5ad")
    first = _prepare_fixture(raw, tmp_path / "cache")
    _ = first.artifact.content_path.write_bytes(b"corrupt")

    # When/Then: preparation fails deterministically instead of overwriting evidence.
    with pytest.raises(bio.PreparedDatasetCacheError):
        _ = _prepare_fixture(raw, tmp_path / "cache")


def test_load_dataset_still_rejects_unprepared_raw_h5ad(tmp_path: Path) -> None:
    # Given: a verified upstream H5AD without a canonical derivation edge.
    raw = store_tms_aorta_h5ad(tmp_path / "cache", tmp_path / "source.h5ad")

    # When/Then: canonical loading cannot bypass explicit preparation.
    with pytest.raises(bio.UnlinkedTmsArtifactError):
        _ = bio.load_dataset("tms-aorta", artifact=raw)


def test_public_prepare_rejects_self_consistent_forged_tms_h5ad(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    # Given: a valid TMS-shaped local H5AD that is not the exact pinned Figshare file.
    forged = store_tms_aorta_h5ad(tmp_path / "cache", tmp_path / "source.h5ad")

    def fail_if_parsed(_path: Path) -> None:
        pytest.fail("unbound source must be rejected before H5AD parsing")

    monkeypatch.setattr(ad, "read_h5ad", fail_if_parsed)

    # When/Then: public preparation rejects it before assigning the TMS snapshot.
    with pytest.raises(bio.UnexpectedDatasetSourceError):
        _ = bio.prepare_dataset(
            "tms-aorta",
            artifact=forged,
            data_dir=tmp_path / "prepared",
        )


@pytest.mark.parametrize(
    ("variant", "violation"),
    [
        (TmsH5adVariant.MISSING_RAW, RawTmsViolation.RAW_LAYER_MISSING),
        (TmsH5adVariant.NON_CSR, RawTmsViolation.RAW_MATRIX_NOT_CSR),
        (TmsH5adVariant.SHAPE_MISMATCH, RawTmsViolation.SHAPE_MISMATCH),
        (
            TmsH5adVariant.DUPLICATE_OBSERVATION,
            RawTmsViolation.DUPLICATE_IDENTIFIER,
        ),
        (TmsH5adVariant.DUPLICATE_FEATURE, RawTmsViolation.DUPLICATE_IDENTIFIER),
        (TmsH5adVariant.INVALID_METADATA, RawTmsViolation.INVALID_METADATA),
        (TmsH5adVariant.NONFINITE_COUNT, RawTmsViolation.NONFINITE_COUNT),
        (TmsH5adVariant.NEGATIVE_COUNT, RawTmsViolation.NEGATIVE_COUNT),
        (TmsH5adVariant.NONINTEGER_COUNT, RawTmsViolation.NON_INTEGER_COUNT),
    ],
)
def test_transform_rejects_invalid_h5ad_boundary_variants(
    tmp_path: Path,
    variant: TmsH5adVariant,
    violation: RawTmsViolation,
) -> None:
    # Given: a self-consistent receipt containing one invalid H5AD boundary state.
    raw = store_tms_aorta_h5ad(
        tmp_path / "cache",
        tmp_path / "source.h5ad",
        variant=variant,
    )

    # When: the versioned transform validates before canonical expansion.
    with pytest.raises(bio.InvalidRawTmsArtifactError) as captured:
        _ = _prepare_fixture(raw, tmp_path / "prepared")

    # Then: the machine-readable failure identifies the rejected boundary.
    assert captured.value.violation is violation


def test_transform_rejects_missing_required_observation_column(
    tmp_path: Path,
) -> None:
    # Given: a shape-valid H5AD without the required mouse grouping column.
    raw = store_tms_aorta_h5ad(
        tmp_path / "cache",
        tmp_path / "source.h5ad",
        include_mouse_id=False,
    )

    # When: the transform checks required metadata before row expansion.
    with pytest.raises(bio.InvalidRawTmsArtifactError) as captured:
        _ = _prepare_fixture(raw, tmp_path / "prepared")

    # Then: the missing-column boundary remains machine-readable.
    assert captured.value.violation is RawTmsViolation.REQUIRED_OBSERVATION_COLUMN
    assert captured.value.field == "mouse.id"


@pytest.mark.parametrize(
    ("limits", "field"),
    [
        (replace(_FIXTURE_LIMITS, maximum_nonzero_counts=1), "nonzero_counts"),
        (replace(_FIXTURE_LIMITS, maximum_metadata_length=3), "metadata_length"),
        (replace(_FIXTURE_LIMITS, maximum_output_bytes=1), "output_bytes"),
    ],
)
def test_transform_enforces_resource_envelope(
    tmp_path: Path,
    limits: TmsAortaTransformLimits,
    field: str,
) -> None:
    # Given: valid raw input but a resource envelope below its bounded payload.
    raw = store_tms_aorta_h5ad(tmp_path / "cache", tmp_path / "source.h5ad")

    # When: preparation reaches the applicable bounded expansion stage.
    with pytest.raises(bio.InvalidRawTmsArtifactError) as captured:
        _ = prepare_tms_aorta(raw, data_dir=tmp_path / "prepared", limits=limits)

    # Then: the resource rejection names the exceeded dimension.
    assert captured.value.violation is RawTmsViolation.RESOURCE_LIMIT
    assert captured.value.field == field


def test_concurrent_preparation_reopens_verified_locator_winner(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    # Given: two transforms reach locator publication for the same parent together.
    raw = store_tms_aorta_h5ad(tmp_path / "cache", tmp_path / "source.h5ad")
    prepared_root = tmp_path / "prepared"
    seeded = _prepare_fixture(raw, prepared_root)
    payload = TmsAortaPayload.model_validate_json(
        seeded.artifact.content_path.read_text(encoding="utf-8"),
    )
    locator_path = (
        prepared_root
        / "prepared"
        / "tms-aorta"
        / raw.manifest.sha256
        / "tms-aorta-csr-v1.json"
    )
    locator_path.unlink()
    original_publish = transform_module.publish_tms_aorta_locator
    publication_barrier = Barrier(2)

    def synchronized_publish(
        locator_path: Path,
        prepared: bio.ArtifactReceipt,
    ) -> bool:
        _ = publication_barrier.wait()
        return original_publish(locator_path, prepared)

    def reuse_payload(
        _raw: bio.ArtifactReceipt,
        _limits: TmsAortaTransformLimits,
    ) -> TmsAortaPayload:
        return payload

    monkeypatch.setattr(
        transform_module,
        "publish_tms_aorta_locator",
        synchronized_publish,
    )
    monkeypatch.setattr(transform_module, "transform_h5ad", reuse_payload)

    # When: both callers prepare into the same selected cache.
    with ThreadPoolExecutor(max_workers=2) as executor:
        futures = tuple(
            executor.submit(_prepare_fixture, raw, prepared_root)
            for _ in range(2)
        )
        results = tuple(future.result() for future in futures)

    # Then: one publishes and the loser reopens the same verified winner.
    assert {result.artifact.artifact_id for result in results} == {
        results[0].artifact.artifact_id,
    }
    assert {result.outcome for result in results} == {
        bio.DatasetPreparationOutcome.TRANSFORMED,
        bio.DatasetPreparationOutcome.CACHE_HIT,
    }
