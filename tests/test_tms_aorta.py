"""TMS Aorta canonical adapter contract tests."""

import json
from dataclasses import dataclass
from datetime import UTC, datetime
from hashlib import sha256
from pathlib import Path

import pytest

import bioml_data as bio
from bioml_data import _single_cell as single_cell
from bioml_data import _tms_aorta as tms
from bioml_data._artifacts import (
    ArtifactCache,
    ArtifactDerivation,
    ArtifactDerivationParameter,
    ArtifactReceipt,
    ArtifactRequest,
    TransformProtocolId,
)
from bioml_data._single_cell_errors import (
    DuplicateIdentifierError,
    MissingIdentifierError,
)


@dataclass(frozen=True, slots=True)
class _MissingCase:
    cell_id: str
    donor_id: str
    field: str


@dataclass(frozen=True, slots=True)
class _DuplicateCase:
    cell_id: str
    feature_id: str
    field: str


def _fixture_payload(
    second_cell_id: str = "cell-2",
    second_donor_id: str = "mouse-2",
    second_feature_id: str = "ENSMUSG0002",
) -> str:
    return json.dumps(
        {
            "schema_version": "tms-aorta-csr-v1",
            "observations": [
                {
                    "cell_id": "cell-1",
                    "mouse.id": "mouse-1",
                    "method": "FACS",
                    "assay": "FACS",
                    "tissue": "Aorta",
                    "cell_ontology_class": "endothelial cell",
                },
                {
                    "cell_id": second_cell_id,
                    "mouse.id": second_donor_id,
                    "method": "FACS",
                    "assay": "FACS",
                    "tissue": "Aorta",
                    "cell_ontology_class": "fibroblast",
                },
                {
                    "cell_id": "cell-3",
                    "mouse.id": "mouse-3",
                    "method": "FACS",
                    "assay": "FACS",
                    "tissue": "Aorta",
                    "cell_ontology_class": "smooth muscle cell",
                },
            ],
            "features": [
                {"feature_id": "ENSMUSG0001", "feature_name": "GeneA"},
                {"feature_id": second_feature_id, "feature_name": "GeneB"},
            ],
            "counts": {
                "format": "csr",
                "data": [2, 1, 3],
                "indices": [0, 1, 0],
                "indptr": [0, 1, 2, 3],
                "shape": [3, 2],
            },
        }
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


def _processed_artifact(tmp_path: Path, payload: str) -> ArtifactReceipt:
    cache = ArtifactCache(tmp_path / "cache")
    raw_content = b"representative raw sparse fixture"
    raw = cache.store(
        _artifact_request(raw_content, "raw-fixture.bin", None),
        (raw_content,),
    )
    derivation = ArtifactDerivation(
        parent_artifacts=(raw.artifact_id,),
        transform_protocol=TransformProtocolId("tms-aorta-csr-v1"),
        parameters=(
            ArtifactDerivationParameter(
                name="expression_input",
                value="raw.X",
            ),
        ),
    )
    processed_content = payload.encode()
    return cache.store(
        _artifact_request(processed_content, "tms-aorta-fixture.json", derivation),
        (processed_content,),
    )


def test_public_loader_materializes_pinned_tms_aorta_artifact(tmp_path: Path) -> None:
    # Given: a local content-addressed export linked to its raw parent artifact.
    artifact = _processed_artifact(tmp_path, _fixture_payload())

    # When: the public dataset loader receives the explicit artifact pin.
    dataset = bio.load_dataset("tms-aorta", artifact=artifact)

    # Then: source, release, and local provenance remain explicit and distinct.
    assert isinstance(dataset, single_cell.CanonicalSingleCellDataset)
    assert dataset.snapshot.version == "figshare-project-64982"
    assert (
        dataset.source.source_uri
        == "https://figshare.com/articles/dataset/Tabula_Muris_Senis_Data_Objects/12654728"
    )
    assert dataset.source.figshare_article == "12654728"
    assert dataset.source.figshare_release == "v1"
    assert dataset.source.geo_accession == "GSE149590"
    assert (
        dataset.source.filename
        == "tabula-muris-senis-facs-processed-official-annotations-Aorta.h5ad"
    )
    assert dataset.artifact == artifact.manifest
    assert dataset.artifact.derivation is not None


def test_adapter_maps_canonical_metadata_for_grouped_splits(tmp_path: Path) -> None:
    # Given: representative upstream TMS observation and feature columns.
    artifact = _processed_artifact(tmp_path, _fixture_payload())

    # When: the artifact is mapped to the canonical schema.
    dataset = tms.load_tms_aorta(artifact)

    # Then: cell, animal, assay, tissue, label, and feature identities are preserved.
    assert dataset.observations[0] == single_cell.CanonicalObservation(
        cell_id=single_cell.CellId("cell-1"),
        donor_id=single_cell.DonorId("mouse-1"),
        study_id=single_cell.StudyId("GSE149590"),
        assay="FACS",
        tissue="Aorta",
        cell_type="endothelial cell",
    )
    assert dataset.features[0] == single_cell.CanonicalFeature(
        feature_id=single_cell.FeatureId("ENSMUSG0001"),
        feature_name="GeneA",
    )
    assert dataset.split_observations[0].observation_id == "cell-1"
    assert tuple(
        (item.column, item.value) for item in dataset.split_observations[0].metadata
    ) == (
        ("donor_id", "mouse-1"),
        ("study_id", "GSE149590"),
        ("assay", "FACS"),
        ("tissue", "Aorta"),
        ("cell_type", "endothelial cell"),
    )


def test_adapter_preserves_sparse_count_storage(tmp_path: Path) -> None:
    # Given: a CSR fixture with three nonzero counts in a three-by-two matrix.
    artifact = _processed_artifact(tmp_path, _fixture_payload())

    # When: the adapter materializes canonical counts.
    counts = tms.load_tms_aorta(artifact).counts

    # Then: only CSR arrays are retained; no dense matrix is constructed.
    assert counts.format is single_cell.SparseFormat.CSR
    assert counts.shape == single_cell.MatrixShape(observations=3, features=2)
    assert counts.values == (2, 1, 3)
    assert counts.column_indices == (0, 1, 0)
    assert counts.row_offsets == (0, 1, 2, 3)


def test_same_artifact_has_stable_dataset_identity(tmp_path: Path) -> None:
    # Given: one pinned processed artifact already materialized once.
    artifact = _processed_artifact(tmp_path, _fixture_payload())
    first = tms.load_tms_aorta(artifact)

    # When: the same artifact is materialized again.
    second = tms.load_tms_aorta(artifact)

    # Then: dataset identity is stable across materializations.
    assert second.identity == first.identity


@pytest.mark.parametrize(
    "case",
    [
        _MissingCase(cell_id="", donor_id="mouse-2", field="cell_id"),
        _MissingCase(cell_id="cell-2", donor_id="", field="donor_id"),
    ],
)
def test_adapter_reports_missing_required_identifiers(
    tmp_path: Path,
    case: _MissingCase,
) -> None:
    # Given: a parsed TMS row with one empty canonical identifier.
    artifact = _processed_artifact(
        tmp_path,
        _fixture_payload(
            second_cell_id=case.cell_id,
            second_donor_id=case.donor_id,
        ),
    )

    # When: the adapter validates canonical identities.
    with pytest.raises(MissingIdentifierError) as captured:
        _ = tms.load_tms_aorta(artifact)

    # Then: the typed error locates the missing canonical field and row.
    assert captured.value.field == case.field
    assert captured.value.position == 1


@pytest.mark.parametrize(
    "case",
    [
        _DuplicateCase(
            cell_id="cell-1",
            feature_id="ENSMUSG0002",
            field="cell_id",
        ),
        _DuplicateCase(
            cell_id="cell-2",
            feature_id="ENSMUSG0001",
            field="feature_id",
        ),
    ],
)
def test_adapter_reports_duplicate_identifiers(
    tmp_path: Path,
    case: _DuplicateCase,
) -> None:
    # Given: a parsed TMS fixture with one repeated canonical identifier.
    artifact = _processed_artifact(
        tmp_path,
        _fixture_payload(
            second_cell_id=case.cell_id,
            second_feature_id=case.feature_id,
        ),
    )

    # When: the adapter validates canonical uniqueness.
    with pytest.raises(DuplicateIdentifierError) as captured:
        _ = tms.load_tms_aorta(artifact)

    # Then: the typed error names the duplicated identity class.
    assert captured.value.field == case.field


def test_adapter_reports_an_invalid_interchange_schema(tmp_path: Path) -> None:
    # Given: a pinned artifact that is not a complete TMS sparse interchange object.
    artifact = _processed_artifact(
        tmp_path,
        '{"schema_version":"tms-aorta-csr-v1"}',
    )

    # When: the adapter parses the artifact boundary.
    with pytest.raises(tms.InvalidTmsSchemaError) as captured:
        _ = tms.load_tms_aorta(artifact)

    # Then: the typed error retains the failing artifact identity.
    assert captured.value.artifact_id == artifact.artifact_id


@pytest.mark.parametrize("expression_input", [None, "X"])
def test_adapter_rejects_missing_or_wrong_expression_input_receipt(
    tmp_path: Path,
    expression_input: str | None,
) -> None:
    # Given: canonical-shaped bytes with an incomplete or incorrect derivation choice.
    cache = ArtifactCache(tmp_path / "cache")
    raw_content = b"representative raw sparse fixture"
    raw = cache.store(
        _artifact_request(raw_content, "raw-fixture.bin", None),
        (raw_content,),
    )
    parameters = (
        ()
        if expression_input is None
        else (
            ArtifactDerivationParameter(
                name="expression_input",
                value=expression_input,
            ),
        )
    )
    content = _fixture_payload().encode()
    artifact = cache.store(
        _artifact_request(
            content,
            "tms-aorta-fixture.json",
            ArtifactDerivation(
                parent_artifacts=(raw.artifact_id,),
                transform_protocol=TransformProtocolId("tms-aorta-csr-v1"),
                parameters=parameters,
            ),
        ),
        (content,),
    )

    # When/Then: protocol identity alone cannot authorize the artifact.
    with pytest.raises(tms.UnlinkedTmsArtifactError):
        _ = tms.load_tms_aorta(artifact)
