"""Pancreas four-study canonical-materialization scenarios."""

from hashlib import sha256
from io import BytesIO
from pathlib import Path
from zipfile import ZIP_DEFLATED, ZipFile

import pytest

import bioml_data as bio
import bioml_data.datasets.pancreas._source as pancreas_source
from bioml_data.datasets.pancreas._adapter import load_pancreas
from bioml_data.datasets.pancreas._materialization import prepare_pancreas
from bioml_data.datasets.pancreas._splits import pancreas_lodo_split


def _archive_bytes() -> bytes:
    """Build source-defined combined rows plus distracting cohort-local members."""
    buffer = BytesIO()
    with ZipFile(buffer, "w", compression=ZIP_DEFLATED) as archive:
        labels = tuple("pp" if row == 5_707 else "alpha" for row in range(10_150))
        rows = "\n".join(f'"cell-{row + 1}",{row % 3},0,1' for row in range(10_150))
        archive.writestr(
            "Inter-dataset/Pancreatic/Labels.csv",
            '"x"\n' + "\n".join(f'"{label}"' for label in labels),
        )
        archive.writestr(
            "Inter-dataset/Pancreatic/Combined_HumanPancreas_data.csv",
            '"","G1","G2","G3"\n' + rows,
        )
        archive.writestr(
            "Intra-dataset/Pancreatic_data/Muraro/Filtered_Muraro_HumanPancreas_data.csv",
            '"","wrong-local-feature"\n"local",999',
        )
    return buffer.getvalue()


def _fixture_pin(content: bytes) -> bio.PancreasArchiveSourcePin:
    """Create a small exact-source pin for the fixture archive."""
    return bio.PancreasArchiveSourcePin(
        record_id="fixture-record",
        file_id="fixture-file",
        source_uri="https://example.test/pancreas.zip",
        filename="pancreas.zip",
        byte_size=len(content),
        official_md5="fixture-md5",
        sha256=sha256(content).hexdigest(),
        license="CC-BY-4.0",
    )


def test_prepare_pancreas_materializes_four_labels_and_reuses_cache(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    # Given: a verified four-study archive with Muraro's source-specific pp label.
    content = _archive_bytes()
    monkeypatch.setattr(
        pancreas_source, "PANCREAS_ZENODO_ARCHIVE", _fixture_pin(content)
    )
    archive_path = tmp_path / "source.zip"
    _ = archive_path.write_bytes(content)
    raw = bio.cache_pancreas_archive(archive_path, data_dir=tmp_path / "raw")

    # When: the exact four-label canonical artifact is prepared twice.
    first = prepare_pancreas(raw, data_dir=tmp_path / "prepared")
    second = prepare_pancreas(raw, data_dir=tmp_path / "prepared")
    dataset = load_pancreas(first.artifact)

    # Then: pp becomes gamma; source feature order is retained and cache reuses.
    assert first.outcome is bio.DatasetPreparationOutcome.TRANSFORMED
    assert second.outcome is bio.DatasetPreparationOutcome.CACHE_HIT
    assert dataset.observations[5_707].cell_type == "gamma"
    assert tuple(item.study_id for item in dataset.observations[5_706:5_708]) == (
        "Baron Human",
        "Muraro",
    )
    assert tuple(item.feature_id for item in dataset.features) == ("G1", "G2", "G3")
    assert dataset.counts.shape == bio.MatrixShape(observations=10_150, features=3)
    assert dataset.counts.values[:6] == (1, 1, 1, 2, 1, 1)
    assert dataset.counts.column_indices[:6] == (2, 0, 2, 0, 2, 2)
    assert dataset.counts.row_offsets[:4] == (0, 1, 3, 5)


def test_pancreas_lodo_split_holds_out_only_selected_study(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    # Given: a canonical pancreas fixture with all four source studies.
    content = _archive_bytes()
    monkeypatch.setattr(
        pancreas_source, "PANCREAS_ZENODO_ARCHIVE", _fixture_pin(content)
    )
    archive_path = tmp_path / "source.zip"
    _ = archive_path.write_bytes(content)
    raw = bio.cache_pancreas_archive(archive_path, data_dir=tmp_path / "raw")
    dataset = load_pancreas(
        prepare_pancreas(raw, data_dir=tmp_path / "prepared").artifact
    )

    # When: Muraro is explicitly selected as the held-out study.
    receipt = pancreas_lodo_split(dataset, held_out_study="Muraro")

    # Then: only Muraro observations are tests and no implicit validation set exists.
    assert {item.group for item in receipt.assignments if item.partition == "test"} == {
        "Muraro"
    }
    assert receipt.realized_group_counts.train == 3
    assert receipt.realized_group_counts.validation == 0
    assert receipt.realized_group_counts.test == 1
