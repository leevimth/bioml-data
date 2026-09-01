"""TMS Aorta raw-H5AD to canonical-artifact scenarios."""

from pathlib import Path

import anndata as ad
import pytest

import bioml_data as bio
from tests._anndata_fixtures import store_tms_aorta_h5ad


def test_prepare_dataset_transforms_raw_counts_and_preserves_parent(
    tmp_path: Path,
) -> None:
    # Given: a verified TMS-shaped H5AD whose processed X differs from raw.X.
    raw = store_tms_aorta_h5ad(tmp_path / "cache", tmp_path / "source.h5ad")

    # When: the public preparation API creates the canonical artifact.
    result = bio.prepare_dataset("tms-aorta", artifact=raw, data_dir=tmp_path / "cache")
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


def test_prepare_dataset_reuses_verified_transform_without_reading_h5ad(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    # Given: one completed canonical transform in the selected data directory.
    raw = store_tms_aorta_h5ad(tmp_path / "cache", tmp_path / "source.h5ad")
    first = bio.prepare_dataset("tms-aorta", artifact=raw, data_dir=tmp_path / "cache")

    def fail_if_reopened(_path: Path) -> None:
        pytest.fail("valid prepared cache must skip H5AD parsing")

    monkeypatch.setattr(ad, "read_h5ad", fail_if_reopened)

    # When: the same parent and protocol are prepared again.
    second = bio.prepare_dataset("tms-aorta", artifact=raw, data_dir=tmp_path / "cache")

    # Then: the verified immutable artifact is reused without duplicate work.
    assert second.outcome is bio.DatasetPreparationOutcome.CACHE_HIT
    assert second.artifact == first.artifact


def test_prepare_dataset_rejects_corrupt_prepared_cache(tmp_path: Path) -> None:
    # Given: a completed transform whose immutable canonical blob is corrupted.
    raw = store_tms_aorta_h5ad(tmp_path / "cache", tmp_path / "source.h5ad")
    first = bio.prepare_dataset("tms-aorta", artifact=raw, data_dir=tmp_path / "cache")
    _ = first.artifact.content_path.write_bytes(b"corrupt")

    # When/Then: preparation fails deterministically instead of overwriting evidence.
    with pytest.raises(bio.PreparedDatasetCacheError):
        _ = bio.prepare_dataset(
            "tms-aorta",
            artifact=raw,
            data_dir=tmp_path / "cache",
        )


def test_load_dataset_still_rejects_unprepared_raw_h5ad(tmp_path: Path) -> None:
    # Given: a verified upstream H5AD without a canonical derivation edge.
    raw = store_tms_aorta_h5ad(tmp_path / "cache", tmp_path / "source.h5ad")

    # When/Then: canonical loading cannot bypass explicit preparation.
    with pytest.raises(bio.UnlinkedTmsArtifactError):
        _ = bio.load_dataset("tms-aorta", artifact=raw)
