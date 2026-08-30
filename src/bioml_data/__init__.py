"""Reproducible data protocols for biological machine learning."""

from importlib.metadata import version
from typing import Final

from bioml_data._anndata import load_anndata
from bioml_data._artifact_receipts import (
    ArtifactReceiptFailure,
    ArtifactReceiptLoadError,
    load_artifact_receipt,
)
from bioml_data._artifacts import (
    ArtifactCache,
    ArtifactCollisionError,
    ArtifactDerivation,
    ArtifactManifest,
    ArtifactReceipt,
    ArtifactRequest,
    ChecksumMismatchError,
    IncompleteDownloadError,
    OversizedDownloadError,
)
from bioml_data._catalog import load_dataset
from bioml_data._cli import app as cli_app
from bioml_data._dataset_downloads import (
    DatasetDownloadOutcome,
    DatasetDownloadPin,
    DatasetDownloadReceipt,
    DatasetDownloadUnavailableError,
    Sha256Provenance,
    download_dataset,
    get_dataset_download_pin,
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
from bioml_data._evaluation import evaluate, tms_aorta_canary_protocol
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
from bioml_data._single_cell import CanonicalSingleCellDataset
from bioml_data._split import (
    MissingSplitProtocolError,
    SplitAssigner,
    SplitAssignmentReceipt,
)

__version__: Final = version("bioml-data")

__all__ = [
    "DEFAULT_HTTP_CLIENT_CONFIGURATION",
    "ArtifactCache",
    "ArtifactCollisionError",
    "ArtifactDerivation",
    "ArtifactHttpError",
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
    "DatasetDownloadReceipt",
    "DatasetDownloadUnavailableError",
    "DatasetLifecycle",
    "DatasetSnapshotIdentity",
    "DatasetVersionRequiredError",
    "EvaluationReceipt",
    "EvaluationRequest",
    "FittedPreparationState",
    "HttpArtifactDownload",
    "HttpClientConfiguration",
    "IncompleteDownloadError",
    "InsecureArtifactUrlError",
    "LabelRecord",
    "LeakageAuditReport",
    "LeakageAuditRequest",
    "MissingSplitProtocolError",
    "OversizedDownloadError",
    "PredictionRecord",
    "PreparationProtocol",
    "PreparationRequest",
    "PreparedBenchmarkReceipt",
    "Sha256Provenance",
    "SourceReference",
    "SplitAssigner",
    "SplitAssignmentReceipt",
    "SplitPlan",
    "SplitProtocolDefinition",
    "SplitProtocolRole",
    "TaskDefinition",
    "UnknownDatasetError",
    "UnknownDatasetVersionError",
    "UnknownTaskError",
    "UnsupportedSplitProtocolError",
    "__version__",
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
    "prepare_train_independent",
    "run_tms_aorta_canary",
    "tms_aorta_canary_protocol",
]
