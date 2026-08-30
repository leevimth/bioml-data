"""Typed contracts for task-bound classification evaluation."""

from dataclasses import dataclass
from enum import StrEnum, unique
from hashlib import sha256
from typing import ClassVar, NewType

from pydantic import BaseModel, ConfigDict

from bioml_data._domain import DatasetSnapshotIdentity, ProtocolId, TaskId
from bioml_data._preparation_models import (
    PreparationReceiptIdentity,
    PreparedBenchmarkReceipt,
)
from bioml_data._split import (
    AssignmentIdentity,
    GroupId,
    ObservationId,
    SplitAssignmentReceipt,
)

EvaluationReceiptIdentity = NewType("EvaluationReceiptIdentity", str)
MetricProtocolIdentity = NewType("MetricProtocolIdentity", str)


@unique
class MetricName(StrEnum):
    """Supported point-estimate metrics."""

    MACRO_F1 = "macro-f1"


@unique
class AggregationLevel(StrEnum):
    """Unit across which observation-level metric values are aggregated."""

    SAMPLE = "sample"
    CELL = "cell"
    GROUP = "group"


@unique
class MetricEvidence(StrEnum):
    """Evidence classification kept distinct from literature references."""

    PRODUCT_PROTOCOL = "product-protocol"


@unique
class UncertaintyMethod(StrEnum):
    """Supported uncertainty estimators."""

    BOOTSTRAP = "bootstrap"


@unique
class ResamplingUnit(StrEnum):
    """Independent unit sampled with replacement for uncertainty."""

    SAMPLE = "sample"
    CELL = "cell"
    GROUP = "group"


class ResamplingProtocol(BaseModel):
    """Versioned uncertainty parameters embedded in a metric protocol."""

    model_config: ClassVar[ConfigDict] = ConfigDict(frozen=True)

    method: UncertaintyMethod
    unit: ResamplingUnit
    seed: int
    replicates: int
    confidence_level: float


class MetricProtocol(BaseModel):
    """Task-bound metric, aggregation, label, and uncertainty specification."""

    model_config: ClassVar[ConfigDict] = ConfigDict(frozen=True)

    protocol_id: ProtocolId
    version: str
    task: TaskId
    metric: MetricName
    aggregation: AggregationLevel
    evidence: MetricEvidence
    eligible_labels: tuple[str, ...]
    resampling: ResamplingProtocol

    @property
    def identity(self) -> MetricProtocolIdentity:
        """Return the content identity of the complete metric specification."""
        fields = (
            self.protocol_id,
            self.version,
            self.task,
            self.metric,
            self.aggregation,
            self.evidence,
            *self.eligible_labels,
            self.resampling.method,
            self.resampling.unit,
            str(self.resampling.seed),
            str(self.resampling.replicates),
            format(self.resampling.confidence_level, ".17g"),
        )
        return MetricProtocolIdentity(sha256("\0".join(fields).encode()).hexdigest())


class PredictionRecord(BaseModel):
    """One indexed predicted class label."""

    model_config: ClassVar[ConfigDict] = ConfigDict(frozen=True)

    observation_id: ObservationId
    label: str


class LabelRecord(BaseModel):
    """One indexed ground-truth class label."""

    model_config: ClassVar[ConfigDict] = ConfigDict(frozen=True)

    observation_id: ObservationId
    label: str


class ClassMetric(BaseModel):
    """Per-class diagnostics with absent labels marked non-estimable."""

    model_config: ClassVar[ConfigDict] = ConfigDict(frozen=True)

    label: str
    support: int
    predicted_support: int
    estimable: bool
    precision: float | None
    recall: float | None
    f1: float | None


class GroupMetric(BaseModel):
    """One biological group's cell-level macro-F1."""

    model_config: ClassVar[ConfigDict] = ConfigDict(frozen=True)

    group: GroupId
    observation_count: int
    macro_f1: float


class UncertaintyEstimate(BaseModel):
    """Protocol-declared bootstrap interval and full resampling provenance."""

    model_config: ClassVar[ConfigDict] = ConfigDict(frozen=True)

    method: UncertaintyMethod
    unit: ResamplingUnit
    seed: int
    replicates: int
    confidence_level: float
    lower: float
    upper: float


class EvaluationReceipt(BaseModel):
    """Serializable metric result with all consumed protocol identities."""

    model_config: ClassVar[ConfigDict] = ConfigDict(frozen=True)

    receipt_identity: EvaluationReceiptIdentity
    dataset: DatasetSnapshotIdentity
    task: TaskId
    predictions: tuple[PredictionRecord, ...]
    labels: tuple[LabelRecord, ...]
    split_assignment_identity: AssignmentIdentity
    preprocessing_receipt_identity: PreparationReceiptIdentity
    metric_protocol_identity: MetricProtocolIdentity
    metric_protocol_id: ProtocolId
    metric: MetricName
    aggregation: AggregationLevel
    point_estimate: float
    overall_macro_f1: float
    micro_f1: float
    accuracy: float
    group_median: float | None
    per_class: tuple[ClassMetric, ...]
    per_group: tuple[GroupMetric, ...]
    uncertainty: UncertaintyEstimate


@dataclass(frozen=True, slots=True)
class EvaluationRequest:
    """All predictions, labels, and provenance required for one evaluation."""

    predictions: tuple[PredictionRecord, ...]
    labels: tuple[LabelRecord, ...]
    split: SplitAssignmentReceipt
    preprocessing: PreparedBenchmarkReceipt
    protocol: MetricProtocol
