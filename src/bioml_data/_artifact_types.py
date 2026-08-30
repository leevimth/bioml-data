"""Branded primitive and validated scalar artifact types."""

from typing import Annotated, NewType

from pydantic import Field, StringConstraints

ArtifactId = NewType("ArtifactId", str)
TransformProtocolId = NewType("TransformProtocolId", str)

type ByteSize = Annotated[int, Field(ge=0)]
type NonEmptyText = Annotated[str, StringConstraints(min_length=1)]
type Sha256Hex = Annotated[
    str,
    StringConstraints(pattern=r"^[0-9a-f]{64}$"),
]
type SourceUri = Annotated[
    str,
    StringConstraints(pattern=r"^https://[^\s]+$"),
]
