"""Single source of truth for the TMS Aorta dataset declaration."""

from typing import Final

from bioml_data._domain import (
    DatasetDefinition,
    DatasetLifecycle,
    SourceReference,
    SourceUri,
    SplitProtocolDefinition,
    TaskDefinition,
)
from bioml_data._single_cell import SingleCellSourcePin, StudyId
from bioml_data.datasets._models import (
    DatasetDownloadPin,
    Sha256Provenance,
)
from bioml_data.datasets.tms_aorta._capabilities import (
    TMS_ANIMAL_HELD_OUT_CAPABILITY,
)
from bioml_data.datasets.tms_aorta._identity import (
    TMS_AORTA_SNAPSHOT,
    TMS_CELL_TYPE_TASK,
)

TMS_AORTA_STUDY_ID: Final = StudyId("GSE149590")
TMS_AORTA_SOURCE: Final = SingleCellSourcePin(
    source_uri="https://figshare.com/articles/dataset/Tabula_Muris_Senis_Data_Objects/12654728",
    figshare_article="12654728",
    figshare_release="v1",
    geo_accession="GSE149590",
    filename="tabula-muris-senis-facs-processed-official-annotations-Aorta.h5ad",
)
TMS_AORTA_DEFINITION: Final = DatasetDefinition(
    snapshot=TMS_AORTA_SNAPSHOT,
    source=SourceReference(
        uri=SourceUri("https://figshare.com/projects/Tabula_Muris_Senis/64982"),
    ),
    lifecycle=DatasetLifecycle.PLANNED,
    tasks=(
        TaskDefinition(
            id=TMS_CELL_TYPE_TASK,
            prediction_unit="cell",
            target="cell_type",
        ),
    ),
    supported_splits=(
        SplitProtocolDefinition(
            id=TMS_ANIMAL_HELD_OUT_CAPABILITY.protocol,
            role=TMS_ANIMAL_HELD_OUT_CAPABILITY.role,
            task=TMS_ANIMAL_HELD_OUT_CAPABILITY.task,
            required_metadata=TMS_ANIMAL_HELD_OUT_CAPABILITY.required_columns,
        ),
    ),
)
TMS_AORTA_DOWNLOAD_PIN: Final = DatasetDownloadPin(
    dataset=TMS_AORTA_SNAPSHOT,
    article_id="12654728",
    article_doi="10.6084/m9.figshare.12654728.v1",
    release="v1",
    file_id="23872460",
    source_uri="https://ndownloader.figshare.com/files/23872460",
    filename="tabula-muris-senis-facs-processed-official-annotations-Aorta.h5ad",
    byte_size=44_547_302,
    official_md5="4b1c150cf856a7406b3293ebdacd72c6",
    sha256="0fbf73145f2b50f956b9946aa2fa17e5fce0e40ddfc5ba922a1d503d65ced3c3",
    sha256_provenance=Sha256Provenance.PROJECT_VERIFIED,
    license="MIT",
)
