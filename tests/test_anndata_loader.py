"""H5AD loading scenarios through verified artifact receipts."""

from pathlib import Path

import pytest

import bioml_data as bio
from tests._anndata_fixtures import store_tms_aorta_h5ad


def test_load_anndata_opens_verified_h5ad(tmp_path: Path) -> None:
    # Given: an immutable sparse TMS-shaped H5AD receipt.
    receipt = store_tms_aorta_h5ad(tmp_path / "cache", tmp_path / "source.h5ad")

    # When: the public loader opens it.
    dataset = bio.load_anndata(receipt)

    # Then: the real H5AD is available through the public API.
    assert dataset.shape == (6, 3)


def test_load_anndata_rejects_content_changed_after_receipt(tmp_path: Path) -> None:
    # Given: a valid receipt whose content is changed after it was returned.
    receipt = store_tms_aorta_h5ad(tmp_path / "cache", tmp_path / "source.h5ad")
    _ = receipt.content_path.write_bytes(b"not the verified h5ad")

    # When/Then: manifest reopening rejects it before AnnData can parse the file.
    with pytest.raises(bio.ArtifactReceiptLoadError) as captured:
        _ = bio.load_anndata(receipt)

    assert captured.value.reason is bio.ArtifactReceiptFailure.CONTENT_INTEGRITY
