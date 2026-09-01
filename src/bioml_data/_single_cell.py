"""Canonical sparse single-cell dataset contracts."""

from dataclasses import dataclass
from enum import StrEnum, unique
from typing import NewType

from bioml_data._artifacts import ArtifactManifest
from bioml_data._domain import DatasetSnapshotIdentity
from bioml_data._single_cell_errors import (
    DuplicateIdentifierError,
    InvalidSparseMatrixError,
    MissingIdentifierError,
    MissingMetadataError,
    SparseMatrixViolation,
)
from bioml_data._split import (
    MetadataColumn,
    MetadataValue,
    ObservationId,
    SplitObservation,
)

CellId = NewType("CellId", str)
DatasetMaterializationId = NewType("DatasetMaterializationId", str)
DonorId = NewType("DonorId", str)
FeatureId = NewType("FeatureId", str)
StudyId = NewType("StudyId", str)


@unique
class SparseFormat(StrEnum):
    """Supported sparse count storage layouts."""

    CSR = "csr"


@dataclass(frozen=True, slots=True)
class MatrixShape:
    """Observation-by-feature matrix dimensions."""

    observations: int
    features: int


@dataclass(frozen=True, slots=True)
class SparseCountMatrix:
    """Immutable CSR counts without a dense materialization surface."""

    format: SparseFormat
    shape: MatrixShape
    values: tuple[int, ...]
    column_indices: tuple[int, ...]
    row_offsets: tuple[int, ...]

    def __post_init__(self) -> None:
        if self.shape.observations < 0 or self.shape.features < 0:
            raise InvalidSparseMatrixError(violation=SparseMatrixViolation.SHAPE)
        if len(self.values) != len(self.column_indices):
            raise InvalidSparseMatrixError(
                violation=SparseMatrixViolation.VALUE_INDEX_LENGTH,
            )
        expected_offsets = self.shape.observations + 1
        offsets_are_valid = (
            len(self.row_offsets) == expected_offsets
            and self.row_offsets[0] == 0
            and self.row_offsets[-1] == len(self.values)
            and tuple(sorted(self.row_offsets)) == self.row_offsets
        )
        if not offsets_are_valid:
            raise InvalidSparseMatrixError(
                violation=SparseMatrixViolation.ROW_OFFSETS,
            )
        if any(
            index < 0 or index >= self.shape.features for index in self.column_indices
        ):
            raise InvalidSparseMatrixError(
                violation=SparseMatrixViolation.COLUMN_INDEX,
            )
        for row_index in range(self.shape.observations):
            start = self.row_offsets[row_index]
            end = self.row_offsets[row_index + 1]
            row_columns = self.column_indices[start:end]
            if len(set(row_columns)) != len(row_columns):
                raise InvalidSparseMatrixError(
                    violation=SparseMatrixViolation.DUPLICATE_COORDINATE,
                )
        if any(value < 0 for value in self.values):
            raise InvalidSparseMatrixError(
                violation=SparseMatrixViolation.NEGATIVE_COUNT,
            )


@dataclass(frozen=True, slots=True)
class CanonicalObservation:
    """One cell and its biological split metadata."""

    cell_id: CellId
    donor_id: DonorId
    study_id: StudyId
    assay: str | None
    tissue: str
    cell_type: str

    def validate(self, *, position: int) -> None:
        """Raise a typed error when canonical observation metadata is incomplete."""
        identifiers = (
            ("cell_id", self.cell_id),
            ("donor_id", self.donor_id),
            ("study_id", self.study_id),
        )
        for field, value in identifiers:
            if not value.strip():
                raise MissingIdentifierError(field=field, position=position)
        metadata = (("tissue", self.tissue), ("cell_type", self.cell_type))
        for field, value in metadata:
            if not value.strip():
                raise MissingMetadataError(field=field, record_id=self.cell_id)


@dataclass(frozen=True, slots=True)
class CanonicalFeature:
    """One stable expression feature."""

    feature_id: FeatureId
    feature_name: str

    def validate(self, *, position: int) -> None:
        """Raise a typed error when canonical feature metadata is incomplete."""
        if not self.feature_id.strip():
            raise MissingIdentifierError(field="feature_id", position=position)
        if not self.feature_name.strip():
            raise MissingMetadataError(
                field="feature_name",
                record_id=self.feature_id,
            )


@dataclass(frozen=True, slots=True)
class CanonicalSingleCellDataset:
    """Sparse counts, canonical annotations, and input provenance."""

    identity: DatasetMaterializationId
    snapshot: DatasetSnapshotIdentity
    source: "SingleCellSourcePin"
    artifact: ArtifactManifest
    observations: tuple[CanonicalObservation, ...]
    features: tuple[CanonicalFeature, ...]
    counts: SparseCountMatrix

    def __post_init__(self) -> None:
        for position, observation in enumerate(self.observations):
            observation.validate(position=position)

        for position, feature in enumerate(self.features):
            feature.validate(position=position)

        duplicate_cell = _first_duplicate(
            tuple(observation.cell_id for observation in self.observations)
        )
        if duplicate_cell is not None:
            raise DuplicateIdentifierError(field="cell_id", value=duplicate_cell)
        duplicate_feature = _first_duplicate(
            tuple(feature.feature_id for feature in self.features)
        )
        if duplicate_feature is not None:
            raise DuplicateIdentifierError(
                field="feature_id",
                value=duplicate_feature,
            )
        if self.counts.shape != MatrixShape(
            observations=len(self.observations),
            features=len(self.features),
        ):
            raise InvalidSparseMatrixError(violation=SparseMatrixViolation.SHAPE)

    @property
    def split_observations(self) -> tuple[SplitObservation, ...]:
        """Project canonical rows onto the BIO-11 split input contract."""
        return tuple(
            SplitObservation(
                observation_id=ObservationId(observation.cell_id),
                metadata=(
                    MetadataValue(
                        column=MetadataColumn("donor_id"),
                        value=observation.donor_id,
                    ),
                    MetadataValue(
                        column=MetadataColumn("study_id"),
                        value=observation.study_id,
                    ),
                    *(
                        (
                            MetadataValue(
                                column=MetadataColumn("assay"),
                                value=observation.assay,
                            ),
                        )
                        if observation.assay is not None
                        else ()
                    ),
                    MetadataValue(
                        column=MetadataColumn("tissue"),
                        value=observation.tissue,
                    ),
                    MetadataValue(
                        column=MetadataColumn("cell_type"),
                        value=observation.cell_type,
                    ),
                ),
            )
            for observation in self.observations
        )


@dataclass(frozen=True, slots=True)
class SingleCellSourcePin:
    """Public source family and release represented by a local artifact."""

    source_uri: str
    figshare_article: str
    figshare_release: str
    geo_accession: str
    filename: str


def _first_duplicate(values: tuple[str, ...]) -> str | None:
    seen: set[str] = set()
    for value in values:
        if value in seen:
            return value
        seen.add(value)
    return None
