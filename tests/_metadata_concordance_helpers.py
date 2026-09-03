"""Shared fixtures for metadata concordance tests."""

from dataclasses import replace

import bioml_data as bio
from bioml_data._artifacts import ArtifactDerivation, TransformProtocolId
from bioml_data.datasets.tms_aorta._identity import (
    TMS_AORTA_ARTIFACT_SCOPE,
    TMS_AORTA_SOURCE_ARTIFACT,
)

from ._single_cell_fixtures import make_dataset, make_split


def metadata_scope() -> bio.MetadataExpectationScope:
    """Return the exact fixture protocol scope with a stable citation."""
    return bio.MetadataExpectationScope(
        dataset=make_dataset().snapshot,
        artifact=TMS_AORTA_ARTIFACT_SCOPE,
        task=make_split(make_dataset()).task,
        protocol=make_split(make_dataset()).protocol,
        citation=bio.MetadataCitation(
            title="Tabula Muris Senis data objects",
            uri="https://figshare.com/articles/dataset/Tabula_Muris_Senis_Data_Objects/12654728",
        ),
    )


def metadata_dataset() -> bio.CanonicalSingleCellDataset:
    """Return the fixture with exact raw-parent and transform scope attached."""
    dataset = make_dataset()
    return replace(
        dataset,
        artifact=dataset.artifact.model_copy(
            update={
                "derivation": ArtifactDerivation(
                    parent_artifacts=(TMS_AORTA_SOURCE_ARTIFACT,),
                    transform_protocol=TransformProtocolId("tms-aorta-csr-v1"),
                )
            }
        ),
    )
