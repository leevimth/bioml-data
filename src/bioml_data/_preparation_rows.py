"""Train-independent sparse row preparation and identity."""

from dataclasses import dataclass
from hashlib import sha256

from bioml_data._preparation_models import (
    NormalizationParameters,
    PreparationProtocol,
    PreparedArtifactIdentity,
    PreparedObservation,
    PreparedValue,
)
from bioml_data._single_cell import CanonicalSingleCellDataset, FeatureId


@dataclass(frozen=True, slots=True)
class PreparationRun:
    protocol: PreparationProtocol
    seed: int


@dataclass(frozen=True, slots=True)
class SupportedFeatures:
    feature_ids: tuple[FeatureId, ...]
    positions: tuple[int, ...]


def aligned_row(
    dataset: CanonicalSingleCellDataset,
    row_index: int,
    source_positions: tuple[int, ...],
) -> tuple[int, ...]:
    start = dataset.counts.row_offsets[row_index]
    end = dataset.counts.row_offsets[row_index + 1]
    values_by_position = dict(
        zip(
            dataset.counts.column_indices[start:end],
            dataset.counts.values[start:end],
            strict=True,
        )
    )
    return tuple(values_by_position.get(position, 0) for position in source_positions)


def normalize_row(
    row: tuple[int, ...],
    supported: SupportedFeatures,
    normalization: NormalizationParameters,
) -> tuple[PreparedValue, ...]:
    retained_values = tuple(row[position] for position in supported.positions)
    total = sum(retained_values)
    if total == 0:
        return ()
    scale = normalization.target_sum / total
    return tuple(
        PreparedValue(feature_id=feature_id, value=value * scale)
        for feature_id, value in zip(
            supported.feature_ids,
            retained_values,
            strict=True,
        )
        if value > 0
    )


def independent_identity(
    dataset: CanonicalSingleCellDataset,
    run: PreparationRun,
    rows: tuple[PreparedObservation, ...],
) -> PreparedArtifactIdentity:
    protocol = run.protocol
    parameters = (
        f"{protocol.protocol_id}\0{protocol.version}\0{protocol.qc}\0"
        f"{protocol.alignment}\0{protocol.normalization}\0{run.seed}"
    )
    row_values = "".join(
        f"\0{row.observation_id}:"
        + ",".join(f"{value.feature_id}={value.value:.17g}" for value in row.values)
        for row in rows
    )
    return PreparedArtifactIdentity(
        sha256(
            f"{dataset.artifact.artifact_id}\0{parameters}{row_values}".encode()
        ).hexdigest()
    )
