"""Real H5AD artifact fixtures for loader and notebook scenarios."""

from datetime import UTC, datetime
from hashlib import sha256
from pathlib import Path

import anndata as ad
import numpy as np
from scipy import sparse

from bioml_data._artifacts import ArtifactCache, ArtifactReceipt, ArtifactRequest


def store_tms_aorta_h5ad(cache_root: Path, source_path: Path) -> ArtifactReceipt:
    """Create and store a small sparse TMS-shaped H5AD artifact."""
    matrix = sparse.csr_matrix(
        np.asarray(
            [
                [4.0, 0.0, 1.0],
                [0.0, 3.0, 0.0],
                [2.0, 1.0, 0.0],
                [0.0, 0.0, 5.0],
            ],
        ),
    )
    dataset = ad.AnnData(X=matrix)
    dataset.obs_names = ["cell-1", "cell-2", "cell-3", "cell-4"]
    dataset.var_names = ["GeneA", "GeneB", "GeneC"]
    dataset.obs["mouse.id"] = ["mouse-1", "mouse-1", "mouse-2", "mouse-2"]
    dataset.obs["cell_ontology_class"] = [
        "endothelial cell",
        "macrophage",
        "endothelial cell",
        "macrophage",
    ]
    dataset.write_h5ad(source_path)

    payload = source_path.read_bytes()
    request = ArtifactRequest(
        logical_name=(
            "tabula-muris-senis-facs-processed-official-annotations-Aorta.h5ad"
        ),
        source_uri="https://example.test/tms-aorta.h5ad",
        accession="fixture-tms-aorta",
        release="fixture-v1",
        retrieved_at=datetime(2026, 8, 30, tzinfo=UTC),
        expected_byte_size=len(payload),
        expected_sha256=sha256(payload).hexdigest(),
        tool_version="bioml-data/test",
    )
    return ArtifactCache(cache_root).store(request, (payload,))
