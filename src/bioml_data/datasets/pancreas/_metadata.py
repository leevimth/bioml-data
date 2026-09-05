"""Publication-scoped metadata expectations for each pancreas LODO fold."""

from typing import Final, final, override

from bioml_data._metadata_concordance import (
    MetadataConcordanceReport,
    compare_metadata_concordance,
)
from bioml_data._metadata_concordance_models import (
    MetadataCitation,
    MetadataExpectationScope,
    MetadataMetric,
)
from bioml_data._metadata_expectations import PublicationMetadataExpectation
from bioml_data._single_cell import CanonicalSingleCellDataset
from bioml_data._split import SplitPartition
from bioml_data.datasets.pancreas._identity import (
    PANCREAS_ARTIFACT_SCOPE,
    PANCREAS_CELL_TYPE_TASK,
    PANCREAS_LODO_PROTOCOL,
    PANCREAS_SNAPSHOT,
)
from bioml_data.datasets.pancreas._metadata_expectations import (
    PANCREAS_LODO_BENCHMARK_METADATA,
)
from bioml_data.datasets.pancreas._splits import (
    PANCREAS_LODO_STUDIES,
    pancreas_lodo_split,
)

_CITATION: Final = MetadataCitation(
    title="Abdelaal et al. (2019) Supplementary Table S2",
    uri="https://link.springer.com/article/10.1186/s13059-019-1795-z",
)


def pancreas_metadata_expectations(
    *,
    held_out_study: str,
) -> tuple[PublicationMetadataExpectation, ...]:
    """Return direct test claims while retaining unreported fields as unknown."""
    if held_out_study not in PANCREAS_LODO_STUDIES:
        raise UnknownPancreasMetadataStudyError(study=held_out_study)
    reported = next(
        item
        for item in PANCREAS_LODO_BENCHMARK_METADATA
        if item.study == held_out_study
    )
    scope = MetadataExpectationScope(
        dataset=PANCREAS_SNAPSHOT,
        artifact=PANCREAS_ARTIFACT_SCOPE,
        task=PANCREAS_CELL_TYPE_TASK,
        protocol=PANCREAS_LODO_PROTOCOL,
        citation=_CITATION,
    )
    return (
        *(
            PublicationMetadataExpectation.not_reported(scope=scope, metric=metric)
            for metric in _METRICS
        ),
        *(
            PublicationMetadataExpectation.not_reported(
                scope=scope,
                partition=SplitPartition.TRAIN,
                metric=metric,
            )
            for metric in _METRICS
        ),
        PublicationMetadataExpectation.count(
            scope=scope,
            partition=SplitPartition.TEST,
            metric=MetadataMetric.OBSERVATION_COUNT,
            expected=reported.sample_count,
        ),
        PublicationMetadataExpectation.not_reported(
            scope=scope,
            partition=SplitPartition.TEST,
            metric=MetadataMetric.FEATURE_COUNT,
        ),
        PublicationMetadataExpectation.distribution(
            scope=scope,
            partition=SplitPartition.TEST,
            metric=MetadataMetric.LABEL_COUNTS,
            expected=reported.label_counts,
        ),
    )


def pancreas_metadata_concordance(
    dataset: CanonicalSingleCellDataset,
    *,
    held_out_study: str,
) -> MetadataConcordanceReport:
    """Compare one realized source-defined LODO fold with Table S2 evidence."""
    return compare_metadata_concordance(
        dataset,
        pancreas_lodo_split(dataset, held_out_study=held_out_study),
        expectations=pancreas_metadata_expectations(held_out_study=held_out_study),
    )


@final
class UnknownPancreasMetadataStudyError(ValueError):
    """Raised when no Supplementary Table S2 row names the requested study."""

    study: str

    def __init__(self, *, study: str) -> None:
        super().__init__(study)
        self.study = study

    @override
    def __str__(self) -> str:
        return f"unknown pancreas publication-metadata study {self.study!r}"


_METRICS: Final = (
    MetadataMetric.OBSERVATION_COUNT,
    MetadataMetric.FEATURE_COUNT,
    MetadataMetric.LABEL_COUNTS,
)
