"""Contract-only metadata expectations for the pinned TMS Aorta H5AD."""

from typing import Final

from bioml_data._metadata_concordance_models import (
    MetadataCitation,
    MetadataCount,
    MetadataExpectationScope,
    MetadataMetric,
)
from bioml_data._metadata_expectations import PublicationMetadataExpectation
from bioml_data._split import SplitPartition
from bioml_data.datasets.tms_aorta._identity import (
    TMS_ANIMAL_HELD_OUT_PROTOCOL,
    TMS_AORTA_ARTIFACT_SCOPE,
    TMS_AORTA_SNAPSHOT,
    TMS_CELL_TYPE_TASK,
)

TMS_AORTA_ARTIFACT_AUDIT_CITATION: Final = MetadataCitation(
    title="Tabula Muris Senis Data Objects: Aorta H5AD",
    uri="https://figshare.com/articles/dataset/Tabula_Muris_Senis_Data_Objects/12654728",
)
TMS_AORTA_ARTIFACT_AUDIT_SCOPE: Final = MetadataExpectationScope(
    dataset=TMS_AORTA_SNAPSHOT,
    artifact=TMS_AORTA_ARTIFACT_SCOPE,
    task=TMS_CELL_TYPE_TASK,
    protocol=TMS_ANIMAL_HELD_OUT_PROTOCOL,
    citation=TMS_AORTA_ARTIFACT_AUDIT_CITATION,
)
TMS_AORTA_ARTIFACT_AUDIT_EXPECTATIONS: Final = (
    PublicationMetadataExpectation.count(
        scope=TMS_AORTA_ARTIFACT_AUDIT_SCOPE,
        metric=MetadataMetric.OBSERVATION_COUNT,
        expected=906,
    ),
    PublicationMetadataExpectation.count(
        scope=TMS_AORTA_ARTIFACT_AUDIT_SCOPE,
        metric=MetadataMetric.FEATURE_COUNT,
        expected=22_966,
    ),
    PublicationMetadataExpectation.distribution(
        scope=TMS_AORTA_ARTIFACT_AUDIT_SCOPE,
        metric=MetadataMetric.LABEL_COUNTS,
        expected=(
            MetadataCount(value="aortic endothelial cell", count=467),
            MetadataCount(value="epithelial cell", count=18),
            MetadataCount(value="fibroblast of cardiac tissue", count=215),
            MetadataCount(value="fibrocyte", count=44),
            MetadataCount(value="macrophage", count=32),
            MetadataCount(value="professional antigen presenting cell", count=130),
        ),
    ),
    PublicationMetadataExpectation.set_values(
        scope=TMS_AORTA_ARTIFACT_AUDIT_SCOPE,
        metric=MetadataMetric.TISSUE_VALUES,
        expected=("Aorta",),
    ),
    PublicationMetadataExpectation.not_reported(
        scope=TMS_AORTA_ARTIFACT_AUDIT_SCOPE,
        metric=MetadataMetric.ASSAY_VALUES,
    ),
    PublicationMetadataExpectation.not_reported(
        scope=TMS_AORTA_ARTIFACT_AUDIT_SCOPE,
        partition=SplitPartition.TRAIN,
        metric=MetadataMetric.LABEL_COUNTS,
    ),
    PublicationMetadataExpectation.not_reported(
        scope=TMS_AORTA_ARTIFACT_AUDIT_SCOPE,
        partition=SplitPartition.VALIDATION,
        metric=MetadataMetric.LABEL_COUNTS,
    ),
    PublicationMetadataExpectation.not_reported(
        scope=TMS_AORTA_ARTIFACT_AUDIT_SCOPE,
        partition=SplitPartition.TEST,
        metric=MetadataMetric.LABEL_COUNTS,
    ),
)
