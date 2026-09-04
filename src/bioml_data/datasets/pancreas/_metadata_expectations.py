"""Publication-reported whole-cohort metadata for the pancreas LODO reference."""

from dataclasses import dataclass
from typing import Final


@dataclass(frozen=True, slots=True)
class PancreasCohortMetadata:
    """Whole-cohort dimensions reported by Abdelaal et al. (2019)."""

    study: str
    sample_count: int
    feature_dimension: int
    distinct_label_count: int


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
