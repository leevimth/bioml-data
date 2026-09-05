"""Versioned metadata envelope for pancreas sparse canonical artifacts."""

from array import array
from io import BytesIO
from typing import Annotated, ClassVar, Literal
from zipfile import ZIP_DEFLATED, ZipFile, ZipInfo

import numpy as np
from pydantic import BaseModel, ConfigDict, Field

_ZIP_TIMESTAMP = (1980, 1, 1, 0, 0, 0)


class _BoundaryModel(BaseModel):
    model_config: ClassVar[ConfigDict] = ConfigDict(frozen=True, strict=True)


class PancreasObservationPayload(_BoundaryModel):
    """One selected cell and its source-study annotation."""

    cell_id: str
    study_id: str
    cell_type: str


class PancreasPayload(_BoundaryModel):
    """Metadata for arrays stored alongside this deterministic ZIP envelope."""

    schema_version: Literal["pancreas-four-study-csr-v1"]
    observations: Annotated[tuple[PancreasObservationPayload, ...], Field(min_length=1)]
    features: Annotated[tuple[str, ...], Field(min_length=1)]


def serialize_payload(
    payload: PancreasPayload,
    values: array[float],
    indices: array[int],
    offsets: array[int],
) -> bytes:
    """Write deterministic sparse arrays alongside their schema-bound metadata."""
    arrays = (
        ("data.npy", np.frombuffer(values, dtype=np.float64)),
        ("indices.npy", np.frombuffer(indices, dtype=np.int64)),
        ("indptr.npy", np.frombuffer(offsets, dtype=np.int64)),
    )
    output = BytesIO()
    with ZipFile(output, "w", compression=ZIP_DEFLATED, compresslevel=9) as archive:
        _write_member(archive, "metadata.json", payload.model_dump_json().encode())
        for name, matrix in arrays:
            encoded = BytesIO()
            np.save(encoded, matrix, allow_pickle=False)
            _write_member(archive, name, encoded.getvalue())
    return output.getvalue()


def _write_member(archive: ZipFile, name: str, content: bytes) -> None:
    member = ZipInfo(name, date_time=_ZIP_TIMESTAMP)
    member.compress_type = ZIP_DEFLATED
    archive.writestr(member, content, compress_type=ZIP_DEFLATED, compresslevel=9)
