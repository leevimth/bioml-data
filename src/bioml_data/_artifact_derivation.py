"""Typed scientific parameters recorded on artifact derivation edges."""

from typing import ClassVar

from pydantic import BaseModel, ConfigDict

from bioml_data._artifact_types import NonEmptyText


class ArtifactDerivationParameter(BaseModel):
    """One immutable scientific choice made by a versioned transform."""

    model_config: ClassVar[ConfigDict] = ConfigDict(frozen=True)

    name: NonEmptyText
    value: NonEmptyText
