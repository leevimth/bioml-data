"""Reproducible data protocols for biological machine learning."""

from importlib.metadata import version
from typing import Final

from bioml_data._anndata import load_anndata
from bioml_data._artifact_lineage import ArtifactLineageReceipt
from bioml_data._artifact_receipts import (
    ArtifactReceiptFailure,
    ArtifactReceiptLoadError,
    load_artifact_receipt,
)
from bioml_data._artifacts import (
    ArtifactCache,
    ArtifactCollisionError,
    ArtifactDerivation,
    ArtifactDerivationParameter,
    ArtifactManifest,
    ArtifactReceipt,
    ArtifactRequest,
    ChecksumMismatchError,
    IncompleteDownloadError,
    OversizedDownloadError,
)
from bioml_data._catalog import ArtifactLineageRequiredError, load_dataset
from bioml_data._cli import app as cli_app
from bioml_data._dataset_downloads import (
    FIGSHARE_PROVIDER,
    DatasetDownloadOutcome,
    DatasetDownloadPin,
    DatasetDownloadProvenanceUnavailableError,
    DatasetDownloadReceipt,
    DatasetDownloadUnavailableError,
    Sha256Provenance,
    download_dataset,
    get_dataset_download_pin,
)
from bioml_data._dataset_preparation import (
    DatasetPreparationUnavailableError,
    UnexpectedDatasetSourceError,
    prepare_dataset,
)
from bioml_data._dataset_preparation_models import (
    DatasetPreparationOutcome,
    DatasetPreparationReceipt,
    PreparedDatasetCacheError,
)
from bioml_data._domain import (
    CatalogKeyError,
    DatasetDefinition,
    DatasetLifecycle,
    DatasetSnapshotIdentity,
    DatasetVersionRequiredError,
    SourceReference,
    SplitPlan,
    SplitProtocolDefinition,
    SplitProtocolRole,
    TaskDefinition,
    UnknownDatasetError,
    UnknownDatasetVersionError,
    UnknownTaskError,
    UnsupportedSplitProtocolError,
)
from bioml_data._evaluation import evaluate
from bioml_data._evaluation_models import (
    EvaluationReceipt,
    EvaluationRequest,
    LabelRecord,
    PredictionRecord,
)
from bioml_data._http_artifacts import (
    DEFAULT_HTTP_CLIENT_CONFIGURATION,
    ArtifactHttpError,
    ArtifactTransportError,
    HttpArtifactDownload,
    HttpClientConfiguration,
    InsecureArtifactUrlError,
    create_http_client,
    download_artifact,
)
from bioml_data._leakage_audit import audit_split
from bioml_data._leakage_audit_models import (
    LeakageAuditReport,
    LeakageAuditRequest,
)
from bioml_data._pipeline import BenchmarkRunReceipt, run_tms_aorta_canary
from bioml_data._preparation import (
    apply_fitted_preprocessing,
    fit_train_preprocessing,
    prepare_benchmark,
    prepare_train_independent,
)
from bioml_data._preparation_models import (
    FittedPreparationState,
    PreparationProtocol,
    PreparationRequest,
    PreparedBenchmarkReceipt,
)
from bioml_data._provider_adapters import (
    ProviderAcquisitionReceipt,
    ProviderAcquisitionTarget,
    ProviderAdapter,
    ProviderArtifactExpectation,
    ProviderArtifactIdentityMismatchError,
    ProviderArtifactProvenanceMismatchError,
    ProviderDescriptor,
    ProviderId,
    ProviderReceiptCacheRootMismatchError,
    ProviderReceiptIntegrityMismatchError,
    ProviderReceiptMismatchError,
    ProviderTargetMismatchError,
    ResolvedProviderArtifact,
    ScientificArtifactIdentity,
    acquire_provider_artifact,
)
from bioml_data._single_cell import CanonicalSingleCellDataset
from bioml_data._split import (
    MissingSplitProtocolError,
    SplitAssigner,
    SplitAssignmentReceipt,
)
from bioml_data._split_capability import (
    SplitArtifactScope,
    SplitCapability,
    SplitCapabilityAvailability,
    SplitCapabilityQuery,
    SplitCapabilityResult,
    SplitEvidenceCitation,
    SplitEvidenceScope,
    SplitEvidenceType,
    SplitProtocolEvidence,
    SupportedSplitCapability,
    UnknownSplitCapability,
    UnsupportedSplitCapability,
    query_split_capability,
)
from bioml_data._verified_artifact import VerifiedArtifactChangedError
from bioml_data.datasets._materialization_verification import (
    DatasetMaterializationLineageMismatchError,
    DatasetMaterializationProvenanceMismatchError,
)
from bioml_data.datasets.tms_aorta._adapter import UnlinkedTmsArtifactError
from bioml_data.datasets.tms_aorta._h5ad_transform import (
    InvalidRawTmsArtifactError,
    RawTmsViolation,
)
from bioml_data.datasets.tms_aorta._protocols import tms_aorta_canary_protocol

__version__: Final = version("bioml-data")

__all__ = [
    "DEFAULT_HTTP_CLIENT_CONFIGURATION",
    "FIGSHARE_PROVIDER",
    "ArtifactCache",
    "ArtifactCollisionError",
    "ArtifactDerivation",
    "ArtifactDerivationParameter",
    "ArtifactHttpError",
    "ArtifactLineageReceipt",
    "ArtifactLineageRequiredError",
    "ArtifactManifest",
    "ArtifactReceipt",
    "ArtifactReceiptFailure",
    "ArtifactReceiptLoadError",
    "ArtifactRequest",
    "ArtifactTransportError",
    "BenchmarkRunReceipt",
    "CanonicalSingleCellDataset",
    "CatalogKeyError",
    "ChecksumMismatchError",
    "DatasetDefinition",
    "DatasetDownloadOutcome",
    "DatasetDownloadPin",
    "DatasetDownloadProvenanceUnavailableError",
    "DatasetDownloadReceipt",
    "DatasetDownloadUnavailableError",
    "DatasetLifecycle",
    "DatasetMaterializationLineageMismatchError",
    "DatasetMaterializationProvenanceMismatchError",
    "DatasetPreparationOutcome",
    "DatasetPreparationReceipt",
    "DatasetPreparationUnavailableError",
    "DatasetSnapshotIdentity",
    "DatasetVersionRequiredError",
    "EvaluationReceipt",
    "EvaluationRequest",
    "FittedPreparationState",
    "HttpArtifactDownload",
    "HttpClientConfiguration",
    "IncompleteDownloadError",
    "InsecureArtifactUrlError",
    "InvalidRawTmsArtifactError",
    "LabelRecord",
    "LeakageAuditReport",
    "LeakageAuditRequest",
    "MissingSplitProtocolError",
    "OversizedDownloadError",
    "PredictionRecord",
    "PreparationProtocol",
    "PreparationRequest",
    "PreparedBenchmarkReceipt",
    "PreparedDatasetCacheError",
    "ProviderAcquisitionReceipt",
    "ProviderAcquisitionTarget",
    "ProviderAdapter",
    "ProviderArtifactExpectation",
    "ProviderArtifactIdentityMismatchError",
    "ProviderArtifactProvenanceMismatchError",
    "ProviderDescriptor",
    "ProviderId",
    "ProviderReceiptCacheRootMismatchError",
    "ProviderReceiptIntegrityMismatchError",
    "ProviderReceiptMismatchError",
    "ProviderTargetMismatchError",
    "RawTmsViolation",
    "ResolvedProviderArtifact",
    "ScientificArtifactIdentity",
    "Sha256Provenance",
    "SourceReference",
    "SplitArtifactScope",
    "SplitAssigner",
    "SplitAssignmentReceipt",
    "SplitCapability",
    "SplitCapabilityAvailability",
    "SplitCapabilityQuery",
    "SplitCapabilityResult",
    "SplitEvidenceCitation",
    "SplitEvidenceScope",
    "SplitEvidenceType",
    "SplitPlan",
    "SplitProtocolDefinition",
    "SplitProtocolEvidence",
    "SplitProtocolRole",
    "SupportedSplitCapability",
    "TaskDefinition",
    "UnexpectedDatasetSourceError",
    "UnknownDatasetError",
    "UnknownDatasetVersionError",
    "UnknownSplitCapability",
    "UnknownTaskError",
    "UnlinkedTmsArtifactError",
    "UnsupportedSplitCapability",
    "UnsupportedSplitProtocolError",
    "VerifiedArtifactChangedError",
    "__version__",
    "acquire_provider_artifact",
    "apply_fitted_preprocessing",
    "audit_split",
    "cli_app",
    "create_http_client",
    "download_artifact",
    "download_dataset",
    "evaluate",
    "fit_train_preprocessing",
    "get_dataset_download_pin",
    "load_anndata",
    "load_artifact_receipt",
    "load_dataset",
    "prepare_benchmark",
    "prepare_dataset",
    "prepare_train_independent",
    "query_split_capability",
    "run_tms_aorta_canary",
    "tms_aorta_canary_protocol",
]
