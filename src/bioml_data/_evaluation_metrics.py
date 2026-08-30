"""Classification summaries and deterministic bootstrap uncertainty."""

from dataclasses import dataclass
from hashlib import sha256
from math import ceil
from statistics import median

from bioml_data._evaluation_models import (
    ClassMetric,
    GroupMetric,
    MetricProtocol,
    ResamplingUnit,
    UncertaintyEstimate,
)
from bioml_data._split import GroupId, ObservationId


@dataclass(frozen=True, slots=True)
class EvaluationPair:
    """One aligned label/prediction pair with optional biological group."""

    observation_id: ObservationId
    label: str
    prediction: str
    group: GroupId | None


@dataclass(frozen=True, slots=True)
class ClassificationSummary:
    """Primary and descriptive single-label classification metrics."""

    macro_f1: float
    micro_f1: float
    accuracy: float
    per_class: tuple[ClassMetric, ...]


def summarize(
    pairs: tuple[EvaluationPair, ...],
    eligible_labels: tuple[str, ...],
) -> ClassificationSummary:
    """Calculate metrics without assigning artificial zeros to absent labels."""
    class_metrics = tuple(
        _class_metric(pairs, label=label) for label in eligible_labels
    )
    estimable_f1 = tuple(
        item.f1 for item in class_metrics if item.estimable and item.f1 is not None
    )
    true_positives = sum(pair.label == pair.prediction for pair in pairs)
    accuracy = true_positives / len(pairs)
    return ClassificationSummary(
        macro_f1=sum(estimable_f1) / len(estimable_f1),
        micro_f1=accuracy,
        accuracy=accuracy,
        per_class=class_metrics,
    )


def summarize_groups(
    pairs: tuple[EvaluationPair, ...],
    eligible_labels: tuple[str, ...],
) -> tuple[GroupMetric, ...]:
    """Calculate cell-level macro-F1 independently within each group."""
    groups = tuple(sorted({pair.group for pair in pairs if pair.group is not None}))
    return tuple(
        _summarize_group(pairs, group=group, eligible_labels=eligible_labels)
        for group in groups
    )


def group_median(groups: tuple[GroupMetric, ...]) -> float:
    """Return the descriptive median across independent groups."""
    return float(median(item.macro_f1 for item in groups))


def bootstrap_uncertainty(
    pairs: tuple[EvaluationPair, ...],
    groups: tuple[GroupMetric, ...],
    protocol: MetricProtocol,
) -> UncertaintyEstimate:
    """Bootstrap the protocol-declared independent unit deterministically."""
    scores = tuple(
        _bootstrap_score(pairs, groups, protocol, replicate=replicate)
        for replicate in range(protocol.resampling.replicates)
    )
    ordered = tuple(sorted(scores))
    alpha = (1.0 - protocol.resampling.confidence_level) / 2.0
    lower_index = min(len(ordered) - 1, int(alpha * len(ordered)))
    upper_index = min(
        len(ordered) - 1,
        max(0, ceil((1.0 - alpha) * len(ordered)) - 1),
    )
    return UncertaintyEstimate(
        method=protocol.resampling.method,
        unit=protocol.resampling.unit,
        seed=protocol.resampling.seed,
        replicates=protocol.resampling.replicates,
        confidence_level=protocol.resampling.confidence_level,
        lower=ordered[lower_index],
        upper=ordered[upper_index],
    )


def _class_metric(
    pairs: tuple[EvaluationPair, ...],
    *,
    label: str,
) -> ClassMetric:
    true_positive = sum(
        pair.label == label and pair.prediction == label for pair in pairs
    )
    support = sum(pair.label == label for pair in pairs)
    predicted_support = sum(pair.prediction == label for pair in pairs)
    if support == 0:
        return ClassMetric(
            label=label,
            support=0,
            predicted_support=predicted_support,
            estimable=False,
            precision=None,
            recall=None,
            f1=None,
        )
    precision = true_positive / predicted_support if predicted_support else 0.0
    recall = true_positive / support
    denominator = precision + recall
    f1 = 2.0 * precision * recall / denominator if denominator else 0.0
    return ClassMetric(
        label=label,
        support=support,
        predicted_support=predicted_support,
        estimable=True,
        precision=precision,
        recall=recall,
        f1=f1,
    )


def _summarize_group(
    pairs: tuple[EvaluationPair, ...],
    *,
    group: GroupId,
    eligible_labels: tuple[str, ...],
) -> GroupMetric:
    group_pairs = tuple(pair for pair in pairs if pair.group == group)
    return GroupMetric(
        group=group,
        observation_count=len(group_pairs),
        macro_f1=summarize(group_pairs, eligible_labels).macro_f1,
    )


def _bootstrap_score(
    pairs: tuple[EvaluationPair, ...],
    groups: tuple[GroupMetric, ...],
    protocol: MetricProtocol,
    *,
    replicate: int,
) -> float:
    if protocol.resampling.unit is ResamplingUnit.GROUP:
        sampled = tuple(
            groups[
                _sample_index(len(groups), protocol.resampling.seed, replicate, draw)
            ]
            for draw in range(len(groups))
        )
        return sum(item.macro_f1 for item in sampled) / len(sampled)
    sampled_pairs = tuple(
        pairs[_sample_index(len(pairs), protocol.resampling.seed, replicate, draw)]
        for draw in range(len(pairs))
    )
    return summarize(sampled_pairs, protocol.eligible_labels).macro_f1


def _sample_index(size: int, seed: int, replicate: int, draw: int) -> int:
    digest = sha256(f"{seed}\0{replicate}\0{draw}".encode()).digest()
    return int.from_bytes(digest[:8], byteorder="big") % size
