"""Typed contracts shared by built-in dataset registrations."""

from collections.abc import Callable
from dataclasses import dataclass
from enum import StrEnum, unique
from typing import Protocol

from bioml_data._artifacts import ArtifactManifest, ArtifactReceipt
from bioml_data._domain import DatasetDefinition, DatasetSnapshotIdentity
from bioml_data._split_capability_models import SplitCapability


class DatasetMaterialization(Protocol):
    """Minimum common surface returned by a registered dataset adapter."""

    @property
    def snapshot(self) -> DatasetSnapshotIdentity:
        """Return the immutable dataset snapshot identity."""
        ...

    @property
    def artifact(self) -> ArtifactManifest:
        """Return the materialization's input artifact manifest."""
        ...


type DatasetAdapter = Callable[[ArtifactReceipt], DatasetMaterialization]


@unique
class Sha256Provenance(StrEnum):
    """Evidence source for a catalog SHA-256 value."""

    PROJECT_VERIFIED = "project_verified_against_official_size_and_md5"


@dataclass(frozen=True, slots=True)
class DatasetDownloadPin:
    """Immutable upstream file identity and checksum evidence."""

    dataset: DatasetSnapshotIdentity
    article_id: str
    article_doi: str
    release: str
    file_id: str
    source_uri: str
    filename: str
    byte_size: int
    official_md5: str
    sha256: str
    sha256_provenance: Sha256Provenance
    license: str


@dataclass(frozen=True, slots=True)
class DatasetRegistration:
    """One catalog definition and the implementations owned by its dataset."""

    definition: DatasetDefinition
    materialize: DatasetAdapter
    split_capabilities: tuple[SplitCapability, ...]
    download_pin: DatasetDownloadPin | None
