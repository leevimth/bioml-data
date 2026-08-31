"""Dataset-level download and cache-reuse scenarios."""

from dataclasses import replace
from hashlib import sha256
from pathlib import Path

import httpx2
import pytest

import bioml_data as bio
import bioml_data._dataset_downloads as dataset_downloads
from bioml_data._dataset_downloads import download_pinned_dataset
from bioml_data._domain import DatasetName, DatasetVersion
from bioml_data.datasets._registry import DATASET_REGISTRY, DatasetRegistry


def _fixture_pin(content: bytes) -> bio.DatasetDownloadPin:
    return bio.DatasetDownloadPin(
        dataset=bio.DatasetSnapshotIdentity(
            name=DatasetName("tms-aorta"),
            version=DatasetVersion("test-release"),
        ),
        article_id="fixture-article",
        article_doi="10.0000/fixture",
        release="test-v1",
        file_id="fixture-file",
        source_uri="https://example.test/fixture.h5ad",
        filename="fixture.h5ad",
        byte_size=len(content),
        official_md5="2e5d7ea175abe77723b6cb8b09e67095",
        sha256=sha256(content).hexdigest(),
        sha256_provenance=bio.Sha256Provenance.PROJECT_VERIFIED,
        license="MIT",
    )


def test_tms_aorta_download_pin_is_exact_and_provenance_is_explicit() -> None:
    # Given: the implemented TMS Aorta release.
    dataset_name = "tms-aorta"

    # When: its download pin is queried.
    pin = bio.get_dataset_download_pin(dataset_name)

    # Then: official metadata and the separately verified SHA remain distinct.
    assert pin.dataset.version == "figshare-project-64982"
    assert pin.article_id == "12654728"
    assert pin.article_doi == "10.6084/m9.figshare.12654728.v1"
    assert pin.release == "v1"
    assert pin.file_id == "23872460"
    assert pin.source_uri == "https://ndownloader.figshare.com/files/23872460"
    assert pin.filename == (
        "tabula-muris-senis-facs-processed-official-annotations-Aorta.h5ad"
    )
    assert pin.byte_size == 44_547_302
    assert pin.official_md5 == "4b1c150cf856a7406b3293ebdacd72c6"
    assert pin.sha256 == (
        "0fbf73145f2b50f956b9946aa2fa17e5fce0e40ddfc5ba922a1d503d65ced3c3"
    )
    assert pin.sha256_provenance is bio.Sha256Provenance.PROJECT_VERIFIED
    assert pin.license == "MIT"


def test_pinned_download_uses_selected_directory_then_skips_network(
    tmp_path: Path,
) -> None:
    # Given: a pinned payload and an HTTP fake that counts wire requests.
    content = b"fixture h5ad payload"
    pin = _fixture_pin(content)
    request_count = 0

    def handler(_request: httpx2.Request) -> httpx2.Response:
        nonlocal request_count
        request_count += 1
        return httpx2.Response(200, content=content)

    selected = tmp_path / "research-data"
    transport = httpx2.MockTransport(handler)

    # When: the same dataset is resolved twice in the selected cache.
    first = download_pinned_dataset(
        pin,
        data_dir=selected,
        transport=transport,
    )
    second = download_pinned_dataset(
        pin,
        data_dir=selected,
        transport=transport,
    )

    # Then: one request is made and the second outcome reuses the same receipt.
    assert request_count == 1
    assert first.outcome is bio.DatasetDownloadOutcome.DOWNLOADED
    assert second.outcome is bio.DatasetDownloadOutcome.CACHE_HIT
    assert first.artifact == second.artifact
    assert first.artifact.content_path.is_relative_to(selected)


def test_pinned_download_keeps_cache_directories_independent(tmp_path: Path) -> None:
    # Given: one pin and two caller-selected cache roots.
    content = b"fixture h5ad payload"
    pin = _fixture_pin(content)
    request_count = 0

    def handler(_request: httpx2.Request) -> httpx2.Response:
        nonlocal request_count
        request_count += 1
        return httpx2.Response(200, content=content)

    transport = httpx2.MockTransport(handler)

    # When: the pin is downloaded into each independent root.
    first = download_pinned_dataset(
        pin,
        data_dir=tmp_path / "lab-a",
        transport=transport,
    )
    second = download_pinned_dataset(
        pin,
        data_dir=tmp_path / "lab-b",
        transport=transport,
    )

    # Then: each root downloads once while retaining the same content identity.
    assert request_count == 2
    assert first.artifact.artifact_id == second.artifact.artifact_id
    assert first.artifact.content_path != second.artifact.content_path


def test_pinned_download_rejects_corrupt_cache_before_network(tmp_path: Path) -> None:
    # Given: a valid first download followed by local blob corruption.
    content = b"fixture h5ad payload"
    pin = _fixture_pin(content)
    request_count = 0

    def handler(_request: httpx2.Request) -> httpx2.Response:
        nonlocal request_count
        request_count += 1
        return httpx2.Response(200, content=content)

    selected = tmp_path / "research-data"
    transport = httpx2.MockTransport(handler)
    first = download_pinned_dataset(
        pin,
        data_dir=selected,
        transport=transport,
    )
    _ = first.artifact.content_path.write_bytes(b"corrupt payload")

    # When: the same pin is resolved again.
    with pytest.raises(bio.ArtifactCollisionError):
        _ = download_pinned_dataset(
            pin,
            data_dir=selected,
            transport=transport,
        )

    # Then: integrity failure occurs before a replacement HTTP request.
    assert request_count == 1


def test_pinned_download_rejects_manifest_source_tampering_before_network(
    tmp_path: Path,
) -> None:
    # Given: a valid first download whose manifest source is altered locally.
    content = b"fixture h5ad payload"
    pin = _fixture_pin(content)
    request_count = 0

    def handler(_request: httpx2.Request) -> httpx2.Response:
        nonlocal request_count
        request_count += 1
        return httpx2.Response(200, content=content)

    selected = tmp_path / "research-data"
    transport = httpx2.MockTransport(handler)
    first = download_pinned_dataset(
        pin,
        data_dir=selected,
        transport=transport,
    )
    tampered = first.artifact.manifest.model_copy(
        update={"source_uri": "https://attacker.example/fixture.h5ad"},
    )
    _ = first.artifact.manifest_path.write_text(
        tampered.model_dump_json(indent=2),
        encoding="utf-8",
    )

    # When: the original pin resolves against the occupied content address.
    with pytest.raises(bio.ArtifactCollisionError):
        _ = download_pinned_dataset(
            pin,
            data_dir=selected,
            transport=transport,
        )

    # Then: altered immutable provenance is rejected before another wire request.
    assert request_count == 1


def test_public_download_dataset_reuses_selected_cache(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    # Given: a catalog-addressed test pin already stored under a selected root.
    content = b"fixture h5ad payload"
    fixture = _fixture_pin(content)
    pin = bio.DatasetDownloadPin(
        dataset=bio.load_dataset("tms-aorta").snapshot,
        article_id=fixture.article_id,
        article_doi=fixture.article_doi,
        release=fixture.release,
        file_id=fixture.file_id,
        source_uri=fixture.source_uri,
        filename=fixture.filename,
        byte_size=fixture.byte_size,
        official_md5=fixture.official_md5,
        sha256=fixture.sha256,
        sha256_provenance=fixture.sha256_provenance,
        license=fixture.license,
    )
    selected = tmp_path / "not-the-default-cache"
    _ = download_pinned_dataset(
        pin,
        data_dir=selected,
        transport=httpx2.MockTransport(
            lambda _request: httpx2.Response(200, content=content),
        ),
    )
    registration = replace(
        DATASET_REGISTRY.resolve("tms-aorta"),
        download_pin=pin,
    )
    monkeypatch.setattr(
        dataset_downloads,
        "DATASET_REGISTRY",
        DatasetRegistry(registrations=(registration,)),
    )

    # When: the public dataset API targets the same caller-selected directory.
    result = bio.download_dataset("tms-aorta", data_dir=selected)

    # Then: the public outcome reports a verified cache hit at that root.
    assert result.cache_hit
    assert not result.downloaded
    assert result.artifact.content_path.is_relative_to(selected)
