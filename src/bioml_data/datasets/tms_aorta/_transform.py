"""Deterministic raw-H5AD to tms-aorta-csr-v1 transformation."""

import json
from hashlib import sha256
from importlib.metadata import version as package_version
from pathlib import Path
from tempfile import TemporaryDirectory
from typing import ClassVar

from pydantic import BaseModel, ConfigDict, ValidationError

from bioml_data._artifact_paths import (
    ArtifactPathIntegrityError,
    ensure_no_symlink_components,
    open_binary_nofollow,
    publish_file_nofollow,
)
from bioml_data._artifact_receipts import (
    ArtifactReceiptFailure,
    ArtifactReceiptLoadError,
    load_artifact_receipt,
)
from bioml_data._artifact_types import Sha256Hex
from bioml_data._artifacts import (
    ArtifactCache,
    ArtifactDerivation,
    ArtifactReceipt,
    ArtifactRequest,
)
from bioml_data._dataset_preparation_models import (
    DatasetPreparationOutcome,
    DatasetPreparationReceipt,
    PreparedDatasetCacheError,
)
from bioml_data._verified_artifact import (
    VerifiedArtifactChangedError,
    VerifiedArtifactInput,
)
from bioml_data.datasets.tms_aorta._h5ad_transform import (
    TMS_AORTA_TRANSFORM_LIMITS,
    InvalidRawTmsArtifactError,
    RawTmsViolation,
    TmsAortaTransformLimits,
    transform_h5ad,
)
from bioml_data.datasets.tms_aorta._identity import (
    TMS_AORTA_TRANSFORM_PARAMETERS,
    TMS_AORTA_TRANSFORM_PROTOCOL,
)
from bioml_data.datasets.tms_aorta._interchange import TmsAortaPayload


class _PreparedLocator(BaseModel):
    model_config: ClassVar[ConfigDict] = ConfigDict(frozen=True, strict=True)

    artifact_sha256: Sha256Hex


def prepare_tms_aorta(
    raw_artifact: ArtifactReceipt,
    *,
    data_dir: Path,
    limits: TmsAortaTransformLimits = TMS_AORTA_TRANSFORM_LIMITS,
) -> DatasetPreparationReceipt:
    """Prepare or reverify one canonical TMS Aorta artifact."""
    raw = load_artifact_receipt(raw_artifact.manifest_path)
    if raw.artifact_id != raw_artifact.artifact_id:
        raise ArtifactReceiptLoadError(
            manifest_path=raw_artifact.manifest_path,
            reason=ArtifactReceiptFailure.CONTENT_INTEGRITY,
        )
    locator_path = _locator_path(data_dir, raw)
    cached = _load_cached(locator_path, data_dir=data_dir, raw=raw)
    if cached is not None:
        return DatasetPreparationReceipt(
            artifact=cached,
            parent_artifacts=(raw,),
            outcome=DatasetPreparationOutcome.CACHE_HIT,
        )

    payload = transform_h5ad(raw, limits)
    content = payload.model_dump_json(by_alias=True).encode()
    if len(content) > limits.maximum_output_bytes:
        raise InvalidRawTmsArtifactError(
            artifact_id=raw.artifact_id,
            violation=RawTmsViolation.RESOURCE_LIMIT,
            field="output_bytes",
        )
    digest = sha256(content).hexdigest()
    derivation = ArtifactDerivation(
        parent_artifacts=(raw.artifact_id,),
        transform_protocol=TMS_AORTA_TRANSFORM_PROTOCOL,
        parameters=TMS_AORTA_TRANSFORM_PARAMETERS,
    )
    request = ArtifactRequest(
        logical_name="tms-aorta-csr-v1.json",
        source_uri=raw.manifest.source_uri,
        accession=f"{raw.manifest.accession}:tms-aorta-csr-v1",
        release=raw.manifest.release,
        retrieved_at=raw.manifest.retrieved_at,
        expected_byte_size=len(content),
        expected_sha256=digest,
        tool_version=f"bioml-data/{package_version('bioml-data')}",
        derivation=derivation,
    )
    prepared = ArtifactCache(data_dir).store(request, (content,))
    _validate_prepared_payload(prepared)
    if not publish_tms_aorta_locator(locator_path, prepared):
        winner = _load_cached(locator_path, data_dir=data_dir, raw=raw)
        if winner is None:
            raise PreparedDatasetCacheError(locator_path)
        return DatasetPreparationReceipt(
            artifact=winner,
            parent_artifacts=(raw,),
            outcome=DatasetPreparationOutcome.CACHE_HIT,
        )
    return DatasetPreparationReceipt(
        artifact=prepared,
        parent_artifacts=(raw,),
        outcome=DatasetPreparationOutcome.TRANSFORMED,
    )


def _locator_path(data_dir: Path, raw: ArtifactReceipt) -> Path:
    return (
        data_dir
        / "prepared"
        / "tms-aorta"
        / raw.manifest.sha256
        / "tms-aorta-csr-v1.json"
    )


def _load_cached(
    locator_path: Path,
    *,
    data_dir: Path,
    raw: ArtifactReceipt,
) -> ArtifactReceipt | None:
    if not locator_path.exists():
        return None
    try:
        with open_binary_nofollow(locator_path) as source:
            locator = _PreparedLocator.model_validate_json(source.read())
        manifest_path = (
            data_dir
            / "sha256"
            / locator.artifact_sha256[:2]
            / locator.artifact_sha256
            / "manifest.json"
        )
        prepared = load_artifact_receipt(manifest_path)
    except (
        ArtifactPathIntegrityError,
        ArtifactReceiptLoadError,
        UnicodeDecodeError,
        ValidationError,
    ) as error:
        raise PreparedDatasetCacheError(locator_path) from error
    derivation = prepared.manifest.derivation
    if (
        derivation is None
        or derivation.parent_artifacts != (raw.artifact_id,)
        or derivation.transform_protocol != TMS_AORTA_TRANSFORM_PROTOCOL
        or derivation.parameters != TMS_AORTA_TRANSFORM_PARAMETERS
    ):
        raise PreparedDatasetCacheError(locator_path)
    _validate_prepared_payload(prepared)
    return prepared


def _validate_prepared_payload(prepared: ArtifactReceipt) -> None:
    try:
        verified = VerifiedArtifactInput.from_receipt(prepared)
        _ = TmsAortaPayload.model_validate_json(verified.read_bytes())
    except (
        ArtifactReceiptLoadError,
        ValidationError,
        VerifiedArtifactChangedError,
    ) as error:
        raise PreparedDatasetCacheError(prepared.manifest_path) from error


def publish_tms_aorta_locator(
    locator_path: Path,
    prepared: ArtifactReceipt,
) -> bool:
    payload = json.dumps(
        {"artifact_sha256": prepared.manifest.sha256},
        separators=(",", ":"),
    )
    try:
        ensure_no_symlink_components(locator_path.parent)
        locator_path.parent.mkdir(parents=True, exist_ok=True)
        ensure_no_symlink_components(locator_path.parent)
        with TemporaryDirectory(
            prefix=".locator-",
            dir=locator_path.parent,
        ) as temporary:
            staged = Path(temporary) / "locator.json"
            _ = staged.write_text(payload, encoding="utf-8")
            publish_file_nofollow(staged, locator_path)
    except FileExistsError:
        return False
    except (ArtifactPathIntegrityError, OSError) as error:
        raise PreparedDatasetCacheError(locator_path) from error
    return True
