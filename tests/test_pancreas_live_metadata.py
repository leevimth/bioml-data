"""Opt-in concordance check against the official Zenodo pancreas archive."""

import os
from pathlib import Path

import pytest

import bioml_data as bio
from bioml_data.datasets.pancreas import (
    PANCREAS_LODO_BENCHMARK_METADATA,
    PANCREAS_LODO_COHORT_METADATA,
)

_LIVE_FLAG = "BIOML_RUN_LIVE_PANCREAS"
_CACHE_ENV = "BIOML_PANCREAS_DATA_DIR"
_ARCHIVE_ENV = "BIOML_PANCREAS_ARCHIVE"


@pytest.mark.skipif(
    os.environ.get(_LIVE_FLAG) != "1",
    reason=f"set {_LIVE_FLAG}=1 to inspect the official Pancreas archive",
)
def test_official_pancreas_archive_matches_publication_metadata() -> None:
    # Given: explicit live authorization, source archive, and selected cache root.
    cache_value = os.environ.get(_CACHE_ENV)
    archive_value = os.environ.get(_ARCHIVE_ENV)
    assert cache_value is not None, f"{_CACHE_ENV} is required for live verification"
    assert archive_value is not None, (
        f"{_ARCHIVE_ENV} is required for live verification"
    )
    archive = bio.cache_pancreas_archive(
        Path(archive_value),
        data_dir=Path(cache_value),
    )

    # When: the fixed CSV paths, labels, and matrix headers are inspected.
    inspection = bio.inspect_pancreas_archive(archive)

    # Then: whole cohorts and each study-held-out four-label test set match.
    whole_actual = tuple(
        (
            cohort.study,
            cohort.sample_count,
            cohort.feature_dimension,
            cohort.distinct_label_count,
        )
        for cohort in inspection.cohorts
    )
    whole_expected = tuple(
        (
            cohort.study,
            cohort.sample_count,
            cohort.feature_dimension,
            cohort.distinct_label_count,
        )
        for cohort in PANCREAS_LODO_COHORT_METADATA
    )
    test_actual = tuple(
        (
            cohort.study,
            sum(item.count for item in cohort.four_label_counts),
            tuple((item.value, item.count) for item in cohort.four_label_counts),
        )
        for cohort in inspection.cohorts
    )
    test_expected = tuple(
        (
            cohort.study,
            cohort.sample_count,
            tuple((item.value, item.count) for item in cohort.label_counts),
        )
        for cohort in PANCREAS_LODO_BENCHMARK_METADATA
    )
    assert whole_actual == whole_expected
    assert test_actual == test_expected
