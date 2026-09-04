"""Opt-in verification of the checked TMS Aorta metadata evidence."""

from __future__ import annotations

import os
from collections import Counter
from pathlib import Path
from typing import TYPE_CHECKING, Final, assert_never

import pytest
from pydantic import JsonValue, TypeAdapter

import bioml_data as bio
from bioml_data.datasets.tms_aorta._metadata_expectations import (
    TMS_AORTA_ARTIFACT_AUDIT_EXPECTATIONS,
)

if TYPE_CHECKING:
    from collections.abc import Iterable

    from bioml_data._metadata_concordance import MetadataComparison

_LIVE_FLAG: Final = "BIOML_RUN_LIVE_TMS"
_CACHE_ENV: Final = "BIOML_TMS_DATA_DIR"
_EVIDENCE_PATH: Final = (
    Path(__file__).parents[1] / "docs/evidence/tms-aorta-real-metadata-v1.json"
)
_VERIFIED_CODE_COMMIT: Final = "67cb61dfafb739fa85504b6bf27eee52eb617d0f"
_JSON_OBJECT = TypeAdapter(dict[str, JsonValue])


def _json_strings(values: Iterable[str]) -> list[JsonValue]:
    result: list[JsonValue] = []
    result.extend(values)
    return result


def _observed(comparison: MetadataComparison) -> JsonValue:
    metric = comparison.expectation.metric
    match metric:
        case bio.MetadataMetric.OBSERVATION_COUNT | bio.MetadataMetric.FEATURE_COUNT:
            return comparison.observed.count
        case (
            bio.MetadataMetric.STUDY_IDS
            | bio.MetadataMetric.DONOR_IDS
            | bio.MetadataMetric.GROUP_IDS
            | bio.MetadataMetric.LABEL_VALUES
            | bio.MetadataMetric.ASSAY_VALUES
            | bio.MetadataMetric.TISSUE_VALUES
        ):
            return _json_strings(comparison.observed.values)
        case (
            bio.MetadataMetric.LABEL_COUNTS | bio.MetadataMetric.OBSERVATIONS_PER_GROUP
        ):
            return {item.value: item.count for item in comparison.observed.distribution}
    assert_never(metric)


def _observations(
    comparisons: tuple[MetadataComparison, ...],
) -> dict[str, JsonValue]:
    return {item.expectation.metric.value: _observed(item) for item in comparisons}


def _comparison_statuses(
    comparisons: tuple[MetadataComparison, ...],
) -> dict[str, JsonValue]:
    return {item.expectation.metric.value: item.status.value for item in comparisons}


def _partition(item: bio.MetadataPartitionReport) -> dict[str, JsonValue]:
    return {
        "held_out_groups": list(item.held_out_groups),
        "observed": _observations(item.comparisons),
        "comparison_statuses": _comparison_statuses(item.comparisons),
    }


@pytest.mark.skipif(
    os.environ.get(_LIVE_FLAG) != "1",
    reason=f"set {_LIVE_FLAG}=1 to run the official TMS artifact verification",
)
def test_official_tms_aorta_matches_checked_metadata_evidence() -> None:
    # Given: explicit live-data authorization, a selected cache, and checked evidence.
    cache_value = os.environ.get(_CACHE_ENV)
    assert cache_value is not None, f"{_CACHE_ENV} is required for live verification"
    expected = _JSON_OBJECT.validate_json(_EVIDENCE_PATH.read_bytes())
    cache = Path(cache_value)
    definition = bio.load_dataset("tms-aorta")
    split_definition = definition.supported_splits[0]

    # When: the public download, prepare, load, split, and concordance path is run.
    download = bio.download_dataset("tms-aorta", data_dir=cache)
    prepared = bio.prepare_dataset(
        "tms-aorta",
        artifact=download.artifact,
        data_dir=cache,
    )
    dataset = bio.load_dataset("tms-aorta", artifact=prepared.lineage)
    assignment = bio.SplitAssigner(
        dataset=dataset.snapshot,
        task=split_definition.task,
        observations=dataset.split_observations,
    ).split(protocol=str(split_definition.id), seed=17)
    report = bio.compare_metadata_concordance(
        dataset,
        assignment,
        expectations=TMS_AORTA_ARTIFACT_AUDIT_EXPECTATIONS,
    )
    pin = bio.get_dataset_download_pin("tms-aorta")
    derivation = prepared.artifact.manifest.derivation
    assert derivation is not None
    whole_dataset: dict[str, JsonValue] = {
        "observation_count": len(dataset.observations),
        "feature_count": len(dataset.features),
        "nonzero_count": len(dataset.counts.values),
        "study_ids": _json_strings(
            sorted({str(item.study_id) for item in dataset.observations})
        ),
        "donor_ids": _json_strings(
            sorted({str(item.donor_id) for item in dataset.observations})
        ),
        "assay_values": _json_strings(
            sorted(
                {item.assay for item in dataset.observations if item.assay is not None}
            )
        ),
        "tissue_values": _json_strings(
            sorted({item.tissue for item in dataset.observations})
        ),
        "label_counts": dict(
            sorted(Counter(item.cell_type for item in dataset.observations).items())
        ),
        "comparison_statuses": _comparison_statuses(report.dataset_comparisons),
    }
    partitions: dict[str, JsonValue] = {
        item.partition.value: _partition(item) for item in report.partition_reports
    }
    actual: dict[str, JsonValue] = {
        "schema_version": "tms-aorta-real-metadata-v1",
        "verification": {
            "date": "2026-09-04",
            "implementation_commit": _VERIFIED_CODE_COMMIT,
            "dataset": {
                "name": str(dataset.snapshot.name),
                "version": str(dataset.snapshot.version),
            },
            "task": str(assignment.task),
            "protocol": str(assignment.protocol),
            "seed": assignment.seed,
            "assignment_identity": str(assignment.assignment_identity),
        },
        "source": {
            "provider": "figshare",
            "article_id": pin.article_id,
            "article_doi": pin.article_doi,
            "file_id": pin.file_id,
            "url": pin.source_uri,
            "filename": pin.filename,
            "byte_size": download.artifact.manifest.byte_size,
            "official_md5": pin.official_md5,
            "sha256": download.artifact.manifest.sha256,
            "artifact_id": str(download.artifact.artifact_id),
        },
        "rights": {
            "reported_license": pin.license,
            "license_scope": "figshare_article_record",
            "file_level_rights_matrix": "unresolved",
            "redistribution_authorization": "not_claimed",
        },
        "readiness": {
            "dataset_support": "unresolved",
            "publication_partition_values": "not_reported",
            "partition_interpretation": "observed_only_not_publication_match",
        },
        "canonical_artifact": {
            "artifact_id": str(prepared.artifact.artifact_id),
            "sha256": prepared.artifact.manifest.sha256,
            "byte_size": prepared.artifact.manifest.byte_size,
            "transform_protocol": str(derivation.transform_protocol),
            "parent_artifacts": [str(item) for item in derivation.parent_artifacts],
            "materialization_identity": str(dataset.identity),
        },
        "whole_dataset": whole_dataset,
        "split": {
            "covered_observation_count": report.covered_observation_count,
            "cross_partition_groups": list(report.cross_partition_groups),
            "realized_group_counts": {
                "train": assignment.realized_group_counts.train,
                "validation": assignment.realized_group_counts.validation,
                "test": assignment.realized_group_counts.test,
            },
            "partitions": partitions,
        },
    }

    # Then: live official bytes reproduce the path-free checked evidence exactly.
    assert actual == expected
