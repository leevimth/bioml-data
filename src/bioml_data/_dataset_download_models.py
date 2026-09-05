"""Compatibility models for the current verified HTTP dataset path."""

from dataclasses import dataclass
from enum import StrEnum, unique

from bioml_data._domain import DatasetSnapshotIdentity


@unique
class DatasetDownloadOutcome(StrEnum):
    """Whether a dataset invocation transferred bytes or reused its cache."""

    CACHE_HIT = "cache_hit"
    DOWNLOADED = "downloaded"


@unique
class Sha256Provenance(StrEnum):
    """Evidence source for a catalog SHA-256 value."""

    PROJECT_VERIFIED = "project_verified_against_official_size_and_md5"


@dataclass(frozen=True, slots=True)
class DatasetDownloadPin:
    """Immutable upstream file identity for the verified HTTP compatibility path."""

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
