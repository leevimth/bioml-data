"""Real H5AD artifact fixtures for loader and notebook scenarios."""

from collections.abc import Callable
from datetime import UTC, datetime
from enum import StrEnum, unique
from hashlib import sha256
from pathlib import Path
from typing import Final

import anndata as ad
import numpy as np
from scipy import sparse

from bioml_data._artifacts import ArtifactCache, ArtifactReceipt, ArtifactRequest


@unique
class TmsH5adVariant(StrEnum):
    """Boundary variants used by transform rejection scenarios."""

    VALID = "valid"
    MISSING_RAW = "missing_raw"
    NON_CSR = "non_csr"
    SHAPE_MISMATCH = "shape_mismatch"
    DUPLICATE_OBSERVATION = "duplicate_observation"
    DUPLICATE_FEATURE = "duplicate_feature"
    INVALID_METADATA = "invalid_metadata"
    NONFINITE_COUNT = "nonfinite_count"
    NEGATIVE_COUNT = "negative_count"
    NONINTEGER_COUNT = "noninteger_count"


def store_tms_aorta_h5ad(
    cache_root: Path,
    source_path: Path,
    *,
    variant: TmsH5adVariant = TmsH5adVariant.VALID,
    include_mouse_id: bool = True,
) -> ArtifactReceipt:
    """Create and store a small sparse TMS-shaped H5AD artifact."""
    matrix = sparse.csr_matrix(
        np.asarray(
            [
                [4.0, 0.0, 1.0],
                [0.0, 3.0, 0.0],
                [2.0, 1.0, 0.0],
                [0.0, 0.0, 5.0],
                [1.0, 1.0, 1.0],
                [3.0, 0.0, 1.0],
            ],
        ),
    )
    dataset = ad.AnnData(X=matrix)
    dataset.obs_names = [
        "cell-1",
        "cell-2",
        "cell-3",
        "cell-4",
        "cell-5",
        "cell-6",
    ]
    dataset.var_names = ["GeneA", "GeneB", "GeneC"]
    if include_mouse_id:
        dataset.obs["mouse.id"] = [
            "mouse-a",
            "mouse-a",
            "mouse-b",
            "mouse-c",
            "mouse-d",
            "mouse-e",
        ]
    dataset.obs["cell_ontology_class"] = [
        "endothelial cell",
        "endothelial cell",
        "fibroblast",
        "fibroblast",
        "smooth muscle cell",
        "smooth muscle cell",
    ]
    dataset.obs["cell"] = [f"source-{index}" for index in range(1, 7)]
    dataset.obs["method"] = ["facs"] * 6
    dataset.obs["tissue"] = ["Aorta"] * 6
    dataset.obs["cell_ontology_id"] = [
        "nan",
        "nan",
        "CL:0000057",
        "CL:0000057",
        "nan",
        "nan",
    ]
    _VARIANT_APPLIERS[variant](dataset, matrix)
    dataset.X = matrix.multiply(0.5)
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


type _VariantApplier = Callable[[ad.AnnData, sparse.csr_matrix[np.float64]], None]


def _valid(dataset: ad.AnnData, _matrix: sparse.csr_matrix[np.float64]) -> None:
    dataset.raw = dataset.copy()


def _missing_raw(_dataset: ad.AnnData, _matrix: sparse.csr_matrix[np.float64]) -> None:
    return


def _non_csr(dataset: ad.AnnData, matrix: sparse.csr_matrix[np.float64]) -> None:
    raw = dataset.copy()
    raw.X = matrix.toarray()
    dataset.raw = raw


def _shape_mismatch(
    dataset: ad.AnnData,
    _matrix: sparse.csr_matrix[np.float64],
) -> None:
    dataset.raw = dataset[:, :2]


def _duplicate_observation(
    dataset: ad.AnnData,
    _matrix: sparse.csr_matrix[np.float64],
) -> None:
    dataset.obs_names = ["duplicate"] * dataset.n_obs
    dataset.raw = dataset


def _duplicate_feature(
    dataset: ad.AnnData,
    _matrix: sparse.csr_matrix[np.float64],
) -> None:
    dataset.var_names = ["duplicate"] * dataset.n_vars
    dataset.raw = dataset


def _invalid_metadata(
    dataset: ad.AnnData,
    _matrix: sparse.csr_matrix[np.float64],
) -> None:
    dataset.obs["mouse.id"] = list(range(dataset.n_obs))
    dataset.raw = dataset


def _count_variant(
    dataset: ad.AnnData,
    matrix: sparse.csr_matrix[np.float64],
    value: float,
) -> None:
    changed = matrix.copy()
    changed.data[0] = value
    raw = dataset.copy()
    raw.X = changed
    dataset.raw = raw


_VARIANT_APPLIERS: Final[dict[TmsH5adVariant, _VariantApplier]] = {
    TmsH5adVariant.VALID: _valid,
    TmsH5adVariant.MISSING_RAW: _missing_raw,
    TmsH5adVariant.NON_CSR: _non_csr,
    TmsH5adVariant.SHAPE_MISMATCH: _shape_mismatch,
    TmsH5adVariant.DUPLICATE_OBSERVATION: _duplicate_observation,
    TmsH5adVariant.DUPLICATE_FEATURE: _duplicate_feature,
    TmsH5adVariant.INVALID_METADATA: _invalid_metadata,
    TmsH5adVariant.NONFINITE_COUNT: lambda dataset, matrix: _count_variant(
        dataset, matrix, np.nan
    ),
    TmsH5adVariant.NEGATIVE_COUNT: lambda dataset, matrix: _count_variant(
        dataset, matrix, -1.0
    ),
    TmsH5adVariant.NONINTEGER_COUNT: lambda dataset, matrix: _count_variant(
        dataset, matrix, 0.5
    ),
}
