"""Publication-reported whole-cohort metadata for the pancreas LODO reference."""

from dataclasses import dataclass
from typing import Final

from bioml_data._metadata_concordance_models import MetadataCount


@dataclass(frozen=True, slots=True)
class PancreasCohortMetadata:
    """Whole-cohort dimensions reported by Abdelaal et al. (2019)."""

    study: str
    sample_count: int
    feature_dimension: int
    distinct_label_count: int


@dataclass(frozen=True, slots=True)
class PancreasBenchmarkMetadata:
    """Four-label benchmark subset counts reported in Supplementary Table S2."""

    study: str
    sample_count: int
    label_counts: tuple[MetadataCount, ...]


PANCREAS_LODO_COHORT_METADATA: Final = (
    PancreasCohortMetadata(
        study="Baron Human",
        sample_count=8_569,
        feature_dimension=17_499,
        distinct_label_count=14,
    ),
    PancreasCohortMetadata(
        study="Muraro",
        sample_count=2_122,
        feature_dimension=18_915,
        distinct_label_count=9,
    ),
    PancreasCohortMetadata(
        study="Segerstolpe",
        sample_count=2_133,
        feature_dimension=22_757,
        distinct_label_count=13,
    ),
    PancreasCohortMetadata(
        study="Xin",
        sample_count=1_449,
        feature_dimension=33_889,
        distinct_label_count=4,
    ),
)

PANCREAS_LODO_BENCHMARK_METADATA: Final = (
    PancreasBenchmarkMetadata(
        study="Baron Human",
        sample_count=5_707,
        label_counts=(
            MetadataCount(value="alpha", count=2_326),
            MetadataCount(value="beta", count=2_525),
            MetadataCount(value="delta", count=601),
            MetadataCount(value="gamma", count=255),
        ),
    ),
    PancreasBenchmarkMetadata(
        study="Muraro",
        sample_count=1_554,
        label_counts=(
            MetadataCount(value="alpha", count=812),
            MetadataCount(value="beta", count=448),
            MetadataCount(value="delta", count=193),
            MetadataCount(value="gamma", count=101),
        ),
    ),
    PancreasBenchmarkMetadata(
        study="Segerstolpe",
        sample_count=1_440,
        label_counts=(
            MetadataCount(value="alpha", count=872),
            MetadataCount(value="beta", count=263),
            MetadataCount(value="delta", count=110),
            MetadataCount(value="gamma", count=195),
        ),
    ),
    PancreasBenchmarkMetadata(
        study="Xin",
        sample_count=1_449,
        label_counts=(
            MetadataCount(value="alpha", count=855),
            MetadataCount(value="beta", count=466),
            MetadataCount(value="delta", count=46),
            MetadataCount(value="gamma", count=82),
        ),
    ),
)
