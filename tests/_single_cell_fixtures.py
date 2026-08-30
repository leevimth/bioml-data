"""Shared canonical single-cell fixtures for pipeline contract tests."""

import json
from datetime import UTC, datetime
from hashlib import sha256
from pathlib import Path

from bioml_data._artifacts import (
    ArtifactCache,
    ArtifactDerivation,
    ArtifactId,
    ArtifactManifest,
    ArtifactReceipt,
    ArtifactRequest,
    TransformProtocolId,
)
from bioml_data._domain import (
    DatasetName,
    DatasetSnapshotIdentity,
    DatasetVersion,
    TaskId,
)
from bioml_data._single_cell import (
    CanonicalFeature,
    CanonicalObservation,
    CanonicalSingleCellDataset,
    CellId,
    DatasetMaterializationId,
    DonorId,
    FeatureId,
    MatrixShape,
    SingleCellSourcePin,
    SparseCountMatrix,
    SparseFormat,
    StudyId,
)
from bioml_data._split import SplitAssigner, SplitAssignmentReceipt


def make_dataset() -> CanonicalSingleCellDataset:
    """Return a sparse six-cell, five-animal canonical fixture."""
    observations = (
        _observation("cell-1", "mouse-a", "endothelial"),
        _observation("cell-2", "mouse-a", "endothelial"),
        _observation("cell-3", "mouse-b", "fibroblast"),
        _observation("cell-4", "mouse-c", "fibroblast"),
        _observation("cell-5", "mouse-d", "smooth-muscle"),
        _observation("cell-6", "mouse-e", "smooth-muscle"),
    )
    features = tuple(
        CanonicalFeature(
            feature_id=FeatureId(f"gene-{index}"),
            feature_name=f"Gene {index}",
        )
        for index in range(1, 4)
    )
    return CanonicalSingleCellDataset(
        identity=DatasetMaterializationId("fixture-materialization"),
        snapshot=DatasetSnapshotIdentity(
            name=DatasetName("tms-aorta"),
            version=DatasetVersion("figshare-project-64982"),
        ),
        source=SingleCellSourcePin(
            source_uri="https://example.test/tms",
            figshare_article="12654728",
            figshare_release="v1",
            geo_accession="GSE149590",
            filename="fixture.h5ad",
        ),
        artifact=ArtifactManifest(
            artifact_id=ArtifactId("sha256:" + "1" * 64),
            logical_name="fixture.json",
            source_uri="https://example.test/tms",
            accession="TEST-TMS",
            release="v1",
            retrieved_at=datetime(2026, 8, 30, tzinfo=UTC),
            byte_size=1,
            sha256="1" * 64,
            tool_version="test",
        ),
        observations=observations,
        features=features,
        counts=SparseCountMatrix(
            format=SparseFormat.CSR,
            shape=MatrixShape(observations=6, features=3),
            values=(10, 1, 8, 1, 9, 1, 8, 1, 1, 1, 8, 1, 1, 7),
            column_indices=(0, 2, 0, 2, 1, 2, 1, 2, 0, 1, 2, 0, 1, 2),
            row_offsets=(0, 2, 4, 6, 8, 11, 14),
        ),
    )


def make_split(dataset: CanonicalSingleCellDataset) -> SplitAssignmentReceipt:
    """Assign the fixture through the supported animal-held-out protocol."""
    return SplitAssigner(
        dataset=dataset.snapshot,
        task=TaskId("cell-type-annotation-v1"),
        observations=dataset.split_observations,
    ).split(protocol="animal-held-out-v1", seed=17)


def make_tms_artifact(cache_root: Path) -> ArtifactReceipt:
    """Store a small processed TMS fixture with a linked raw parent."""
    cache = ArtifactCache(cache_root)
    raw_content = b"representative raw sparse fixture"
    raw = cache.store(
        _artifact_request(raw_content, "raw-fixture.bin", None),
        (raw_content,),
    )
    payload = {
        "schema_version": "tms-aorta-csr-v1",
        "observations": [
            {
                "cell_id": observation.cell_id,
                "mouse.id": observation.donor_id,
                "method": observation.assay,
                "tissue": observation.tissue,
                "cell_ontology_class": observation.cell_type,
            }
            for observation in make_dataset().observations
        ],
        "features": [
            {
                "feature_id": feature.feature_id,
                "feature_name": feature.feature_name,
            }
            for feature in make_dataset().features
        ],
        "counts": {
            "format": "csr",
            "data": list(make_dataset().counts.values),
            "indices": list(make_dataset().counts.column_indices),
            "indptr": list(make_dataset().counts.row_offsets),
            "shape": [
                make_dataset().counts.shape.observations,
                make_dataset().counts.shape.features,
            ],
        },
    }
    processed_content = json.dumps(payload, separators=(",", ":")).encode()
    derivation = ArtifactDerivation(
        parent_artifacts=(raw.artifact_id,),
        transform_protocol=TransformProtocolId("tms-aorta-csr-v1"),
    )
    return cache.store(
        _artifact_request(processed_content, "tms-aorta-fixture.json", derivation),
        (processed_content,),
    )


def _artifact_request(
    content: bytes,
    logical_name: str,
    derivation: ArtifactDerivation | None,
) -> ArtifactRequest:
    return ArtifactRequest(
        logical_name=logical_name,
        source_uri="https://example.test/tms-aorta/fixture",
        accession="TEST-TMS-AORTA",
        release="fixture-v1",
        retrieved_at=datetime(2026, 8, 30, 14, tzinfo=UTC),
        expected_byte_size=len(content),
        expected_sha256=sha256(content).hexdigest(),
        tool_version="bioml-data/0.0.0",
        derivation=derivation,
    )


def _observation(
    cell_id: str,
    donor_id: str,
    cell_type: str,
) -> CanonicalObservation:
    return CanonicalObservation(
        cell_id=CellId(cell_id),
        donor_id=DonorId(donor_id),
        study_id=StudyId("GSE149590"),
        assay="FACS",
        tissue="Aorta",
        cell_type=cell_type,
    )
