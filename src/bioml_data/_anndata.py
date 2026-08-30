"""Verified H5AD loading with canonical single-cell metadata aliases."""

from typing import Final

import anndata as ad

from bioml_data._artifact_receipts import (
    ArtifactReceiptFailure,
    ArtifactReceiptLoadError,
    load_artifact_receipt,
)
from bioml_data._artifacts import ArtifactReceipt

_OBS_ALIASES: Final = (
    ("mouse.id", "donor_id"),
    ("cell_ontology_class", "cell_type"),
)


def load_anndata(artifact: ArtifactReceipt) -> ad.AnnData:
    """Reverify an immutable artifact and load it without densifying its matrix."""
    verified = load_artifact_receipt(artifact.manifest_path)
    if verified.artifact_id != artifact.artifact_id:
        raise ArtifactReceiptLoadError(
            manifest_path=artifact.manifest_path,
            reason=ArtifactReceiptFailure.CONTENT_INTEGRITY,
        )
    dataset = ad.read_h5ad(verified.content_path)
    for source, canonical in _OBS_ALIASES:
        if source in dataset.obs:
            dataset.obs[canonical] = dataset.obs[source]
    return dataset
