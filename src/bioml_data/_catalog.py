"""Built-in dataset catalog."""

from typing import Final, overload

from bioml_data._artifacts import ArtifactReceipt
from bioml_data._domain import (
    DatasetDefinition,
    DatasetLifecycle,
    DatasetName,
    DatasetSnapshotIdentity,
    DatasetVersion,
    DatasetVersionRequiredError,
    SourceReference,
    SourceUri,
    SplitProtocolDefinition,
    TaskDefinition,
    TaskId,
    UnknownDatasetError,
    UnknownDatasetVersionError,
    parse_dataset_name,
    parse_dataset_version,
)
from bioml_data._single_cell import CanonicalSingleCellDataset
from bioml_data._split_capability import (
    SplitCapabilityQuery,
    query_split_capability,
)
from bioml_data._tms_aorta import load_tms_aorta

_TMS_AORTA_SNAPSHOT: Final = DatasetSnapshotIdentity(
    name=DatasetName("tms-aorta"),
    version=DatasetVersion("figshare-project-64982"),
)
_TMS_CELL_TYPE_TASK: Final = TaskId("cell-type-annotation-v1")
_TMS_ANIMAL_HELD_OUT_CAPABILITY: Final = query_split_capability(
    SplitCapabilityQuery(
        dataset=_TMS_AORTA_SNAPSHOT,
        task=_TMS_CELL_TYPE_TASK,
        protocol="animal-held-out-v1",
    )
).require_supported()
_TMS_ANIMAL_HELD_OUT_DEFINITION: Final = SplitProtocolDefinition(
    id=_TMS_ANIMAL_HELD_OUT_CAPABILITY.protocol,
    role=_TMS_ANIMAL_HELD_OUT_CAPABILITY.role,
    task=_TMS_ANIMAL_HELD_OUT_CAPABILITY.task,
    required_metadata=_TMS_ANIMAL_HELD_OUT_CAPABILITY.required_columns,
)

_CATALOG: Final = (
    DatasetDefinition(
        snapshot=_TMS_AORTA_SNAPSHOT,
        source=SourceReference(
            uri=SourceUri("https://figshare.com/projects/Tabula_Muris_Senis/64982"),
        ),
        lifecycle=DatasetLifecycle.PLANNED,
        tasks=(
            TaskDefinition(
                id=_TMS_CELL_TYPE_TASK,
                prediction_unit="cell",
                target="cell_type",
            ),
        ),
        supported_splits=(_TMS_ANIMAL_HELD_OUT_DEFINITION,),
    ),
)


@overload
def load_dataset(
    name: str,
    *,
    version: str | None = None,
    artifact: None = None,
) -> DatasetDefinition: ...


@overload
def load_dataset(
    name: str,
    *,
    version: str | None = None,
    artifact: ArtifactReceipt,
) -> CanonicalSingleCellDataset: ...


def load_dataset(
    name: str,
    *,
    version: str | None = None,
    artifact: ArtifactReceipt | None = None,
) -> DatasetDefinition | CanonicalSingleCellDataset:
    """Resolve a catalog definition or materialize its explicit local artifact."""
    dataset_name = parse_dataset_name(name)
    candidates = tuple(
        definition
        for definition in _CATALOG
        if definition.snapshot.name == dataset_name
    )
    if not candidates:
        raise UnknownDatasetError(
            name=dataset_name,
            available=_available_dataset_names(),
        )

    available_versions = tuple(definition.snapshot.version for definition in candidates)
    if version is None:
        if len(candidates) == 1:
            definition = candidates[0]
        else:
            raise DatasetVersionRequiredError(
                name=dataset_name,
                available=available_versions,
            )
    else:
        requested_version = parse_dataset_version(version)
        selected = tuple(
            definition
            for definition in candidates
            if definition.snapshot.version == requested_version
        )
        if not selected:
            raise UnknownDatasetVersionError(
                name=dataset_name,
                requested=requested_version,
                available=available_versions,
            )
        definition = selected[0]

    if artifact is None:
        return definition
    return load_tms_aorta(artifact)


def _available_dataset_names() -> tuple[DatasetName, ...]:
    return tuple(dict.fromkeys(definition.snapshot.name for definition in _CATALOG))
