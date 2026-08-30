"""Filesystem boundary for reopening immutable artifact receipts."""

from enum import StrEnum, unique
from functools import partial
from hashlib import sha256
from pathlib import Path
from typing import final, override

from pydantic import ValidationError

from bioml_data._artifact_paths import (
    ArtifactPathFailure,
    ArtifactPathIntegrityError,
    open_binary_nofollow,
)
from bioml_data._artifacts import ArtifactManifest, ArtifactReceipt


@unique
class ArtifactReceiptFailure(StrEnum):
    """Machine-readable local receipt loading failures."""

    MANIFEST_IO = "manifest_io"
    INVALID_MANIFEST = "invalid_manifest"
    INVALID_LAYOUT = "invalid_layout"
    MISSING_CONTENT = "missing_content"
    CONTENT_INTEGRITY = "content_integrity"
    SYMLINK = "symlink"


@final
class ArtifactReceiptLoadError(Exception):
    """Raised when a manifest path cannot reconstruct an artifact receipt."""

    __slots__ = ("manifest_path", "reason")

    manifest_path: Path
    reason: ArtifactReceiptFailure

    def __init__(
        self,
        manifest_path: Path,
        reason: ArtifactReceiptFailure,
    ) -> None:
        super().__init__(manifest_path, reason)
        self.manifest_path = manifest_path
        self.reason = reason

    @override
    def __str__(self) -> str:
        return f"cannot load artifact receipt {self.manifest_path}: {self.reason}"


def load_artifact_receipt(manifest_path: Path) -> ArtifactReceipt:
    """Parse and stream-verify one canonical immutable cache receipt."""
    manifest = _read_manifest(manifest_path)
    content_path = _verified_content_path(manifest_path, manifest)
    return ArtifactReceipt(
        manifest=manifest,
        content_path=content_path,
        manifest_path=manifest_path,
    )


def _read_manifest(manifest_path: Path) -> ArtifactManifest:
    try:
        with open_binary_nofollow(manifest_path) as source:
            payload = source.read().decode("utf-8")
    except ArtifactPathIntegrityError as error:
        reason = (
            ArtifactReceiptFailure.SYMLINK
            if error.failure is ArtifactPathFailure.SYMLINK
            else ArtifactReceiptFailure.MANIFEST_IO
        )
        raise ArtifactReceiptLoadError(
            manifest_path=manifest_path,
            reason=reason,
        ) from error
    try:
        manifest = ArtifactManifest.model_validate_json(payload)
    except (UnicodeDecodeError, ValidationError) as error:
        raise ArtifactReceiptLoadError(
            manifest_path=manifest_path,
            reason=ArtifactReceiptFailure.INVALID_MANIFEST,
        ) from error
    return manifest


def _verified_content_path(
    manifest_path: Path,
    manifest: ArtifactManifest,
) -> Path:
    expected_artifact_id = f"sha256:{manifest.sha256}"
    if manifest.artifact_id != expected_artifact_id:
        raise ArtifactReceiptLoadError(
            manifest_path=manifest_path,
            reason=ArtifactReceiptFailure.CONTENT_INTEGRITY,
        )
    canonical_suffix = (
        "sha256",
        manifest.sha256[:2],
        manifest.sha256,
        "manifest.json",
    )
    if manifest_path.parts[-4:] != canonical_suffix:
        raise ArtifactReceiptLoadError(
            manifest_path=manifest_path,
            reason=ArtifactReceiptFailure.INVALID_LAYOUT,
        )
    content_path = manifest_path.parent / "blob"
    digest_builder = sha256()
    byte_size = 0
    try:
        with open_binary_nofollow(content_path) as content:
            for block in iter(partial(content.read, 1024 * 1024), b""):
                byte_size += len(block)
                digest_builder.update(block)
    except ArtifactPathIntegrityError as error:
        reason = (
            ArtifactReceiptFailure.SYMLINK
            if error.failure is ArtifactPathFailure.SYMLINK
            else ArtifactReceiptFailure.MISSING_CONTENT
        )
        raise ArtifactReceiptLoadError(
            manifest_path=manifest_path,
            reason=reason,
        ) from error
    if byte_size != manifest.byte_size or digest_builder.hexdigest() != manifest.sha256:
        raise ArtifactReceiptLoadError(
            manifest_path=manifest_path,
            reason=ArtifactReceiptFailure.CONTENT_INTEGRITY,
        )
    return content_path
