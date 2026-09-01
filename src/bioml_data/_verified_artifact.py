"""Verified artifact reads for eager and lazy dataset adapters."""

from dataclasses import dataclass, field
from functools import partial
from hashlib import sha256
from pathlib import Path
from typing import override

from bioml_data._artifact_paths import open_binary_nofollow
from bioml_data._artifact_receipts import load_artifact_receipt
from bioml_data._artifact_types import ArtifactId
from bioml_data._artifacts import ArtifactManifest, ArtifactReceipt


@dataclass(frozen=True, slots=True)
class VerifiedArtifactChangedError(Exception):
    """Raised when cached bytes no longer match their verified identity."""

    artifact_id: ArtifactId

    @override
    def __str__(self) -> str:
        return f"cached bytes changed for verified artifact {self.artifact_id}"


@dataclass(frozen=True, slots=True)
class VerifiedArtifactInput:
    """Artifact identity with reads that return only freshly verified bytes."""

    manifest: ArtifactManifest
    _content_path: Path = field(repr=False)

    @property
    def artifact_id(self) -> ArtifactId:
        return self.manifest.artifact_id

    @classmethod
    def from_receipt(cls, receipt: ArtifactReceipt) -> "VerifiedArtifactInput":
        """Reopen a cache receipt before constructing a verified read handle."""
        verified = load_artifact_receipt(receipt.manifest_path)
        if verified != receipt:
            raise VerifiedArtifactChangedError(artifact_id=receipt.artifact_id)
        return cls.from_verified_receipt(verified)

    @classmethod
    def from_verified_receipt(
        cls,
        receipt: ArtifactReceipt,
    ) -> "VerifiedArtifactInput":
        """Construct from a receipt already reopened at the current boundary."""
        return cls(
            manifest=receipt.manifest,
            _content_path=receipt.content_path,
        )

    def read_bytes(self) -> bytes:
        """Capture bytes and verify that exact capture before returning it."""
        digest = sha256()
        chunks: list[bytes] = []
        byte_size = 0
        with open_binary_nofollow(self._content_path) as source:
            for chunk in iter(partial(source.read, 1024 * 1024), b""):
                chunks.append(chunk)
                byte_size += len(chunk)
                digest.update(chunk)
        if (
            byte_size != self.manifest.byte_size
            or digest.hexdigest() != self.manifest.sha256
        ):
            raise VerifiedArtifactChangedError(artifact_id=self.artifact_id)
        return b"".join(chunks)

    def read_text(self, *, encoding: str = "utf-8") -> str:
        """Decode a freshly verified immutable byte capture."""
        return self.read_bytes().decode(encoding)
