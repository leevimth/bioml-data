"""Pancreas Zenodo source and archive inspection scenarios."""

from hashlib import sha256
from io import BytesIO
from pathlib import Path
from zipfile import ZIP_DEFLATED, ZipFile

import httpx2
import pytest

import bioml_data as bio
import bioml_data.datasets.pancreas._source as pancreas_source


def _archive_bytes() -> bytes:
    """Build the smallest archive with the four published cohort layouts."""
    buffer = BytesIO()
    with ZipFile(buffer, "w", compression=ZIP_DEFLATED) as archive:
        for study, matrix_name, labels, features in (
            (
                "Baron Human",
                "Filtered_Baron_HumanPancreas_data.csv",
                ("alpha", "beta"),
                ("G1", "G2"),
            ),
            (
                "Muraro",
                "Filtered_Muraro_HumanPancreas_data.csv",
                ("alpha", "pp"),
                ("G1",),
            ),
            (
                "Segerstolpe",
                "Filtered_Segerstolpe_HumanPancreas_data.csv",
                ("delta", "gamma"),
                ("G1", "G2", "G3"),
            ),
            (
                "Xin",
                "Filtered_Xin_HumanPancreas_data.csv",
                ("beta",),
                ("G1", "G2", "G3", "G4"),
            ),
        ):
            prefix = f"Intra-dataset/Pancreatic_data/{study}"
            archive.writestr(f"{prefix}/Labels.csv", '"x"\n' + "\n".join(labels))
            archive.writestr(
                f"{prefix}/{matrix_name}",
                '""' + "," + ",".join(f'"{item}"' for item in features) + "\n",
            )
    return buffer.getvalue()


def _fixture_pin(content: bytes) -> bio.PancreasArchiveSourcePin:
    """Create one independently checkable small Zenodo-shaped pin."""
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


def test_pancreas_zenodo_source_pin_is_exact() -> None:
    # Given: the official Abdelaal benchmark record.
    pin = bio.PANCREAS_ZENODO_ARCHIVE

    # When: the fetch-only source identity is read.
    actual = (
        pin.record_id,
        pin.file_id,
        pin.filename,
        pin.byte_size,
        pin.official_md5,
        pin.sha256,
        pin.license,
    )

    # Then: provider and locally verified content identities stay explicit.
    assert actual == (
        "3357167",
        "4282cdc9-55cd-4b4d-aa13-2ff780c742bf",
        "scRNAseq_Benchmark_datasets.zip",
        3_671_466_589,
        "b799a660b8bcaf5f3580a9b6f9372e5b",
        "038d0a61ed3891c3d5f4ebd1dab5956465223e38b89859e1bf4792a9aeffbf06",
        "CC-BY-4.0",
    )


def test_fetch_pancreas_archive_reuses_the_verified_cache(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    # Given: a pinned archive and an HTTP transport that counts transfers.
    content = _archive_bytes()
    monkeypatch.setattr(
        pancreas_source,
        "PANCREAS_ZENODO_ARCHIVE",
        _fixture_pin(content),
    )
    requests = 0

    def handler(_request: httpx2.Request) -> httpx2.Response:
        nonlocal requests
        requests += 1
        return httpx2.Response(200, content=content)

    transport = httpx2.MockTransport(handler)

    # When: the same selected cache is fetched twice.
    first = bio.fetch_pancreas_archive(data_dir=tmp_path, transport=transport)
    second = bio.fetch_pancreas_archive(data_dir=tmp_path, transport=transport)

    # Then: the first receipt stores bytes and the second verifies and reuses them.
    assert requests == 1
    assert first.outcome is bio.DatasetDownloadOutcome.DOWNLOADED
    assert second.outcome is bio.DatasetDownloadOutcome.CACHE_HIT
    assert first.artifact == second.artifact


def test_inspect_pancreas_archive_normalizes_pp_to_gamma(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    # Given: a verified four-study archive with the paper's Muraro pp label.
    content = _archive_bytes()
    monkeypatch.setattr(
        pancreas_source,
        "PANCREAS_ZENODO_ARCHIVE",
        _fixture_pin(content),
    )
    receipt = bio.fetch_pancreas_archive(
        data_dir=tmp_path,
        transport=httpx2.MockTransport(
            lambda _request: httpx2.Response(200, content=content),
        ),
    )

    # When: the archive's labels and one matrix header per cohort are inspected.
    inspection = bio.inspect_pancreas_archive(receipt.artifact)

    # Then: sample counts, feature counts, and four-label counts are structured.
    actual = tuple(
        (
            cohort.study,
            cohort.sample_count,
            cohort.feature_dimension,
            tuple((item.value, item.count) for item in cohort.four_label_counts),
        )
        for cohort in inspection.cohorts
    )
    assert actual == (
        ("Baron Human", 2, 2, (("alpha", 1), ("beta", 1))),
        ("Muraro", 2, 1, (("alpha", 1), ("gamma", 1))),
        ("Segerstolpe", 2, 3, (("delta", 1), ("gamma", 1))),
        ("Xin", 1, 4, (("beta", 1),)),
    )
