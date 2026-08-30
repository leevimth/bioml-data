"""Public end-to-end canary pipeline scenarios."""

from pathlib import Path

import pytest

import bioml_data as bio
from tests._single_cell_fixtures import make_tms_artifact


def test_python_canary_pipeline_records_complete_identity_chain(
    tmp_path: Path,
) -> None:
    # Given: a small content-addressed TMS artifact suitable for CI.
    artifact = make_tms_artifact(tmp_path / "cache")

    # When: the public pipeline runs with an explicit product-canary split.
    first = bio.run_tms_aorta_canary(
        artifact,
        split_protocol="animal-held-out-v1",
        seed=17,
    )
    second = bio.run_tms_aorta_canary(
        artifact,
        split_protocol="animal-held-out-v1",
        seed=17,
    )

    # Then: every stage is identity-bound and repeatable.
    assert first == second
    assert first.artifact_identity == artifact.artifact_id
    assert first.split_protocol_id == "animal-held-out-v1"
    assert first.seed == 17
    assert first.split_assignment_identity
    assert first.preparation_receipt_identity
    assert first.audit_report_identity
    assert first.evaluation_receipt_identity
    assert first.metric_protocol_identity


def test_python_canary_pipeline_requires_explicit_split_protocol(
    tmp_path: Path,
) -> None:
    # Given: a valid local canary artifact but no split choice.
    artifact = make_tms_artifact(tmp_path / "cache")

    # When: the public pipeline is called without a split protocol.
    with pytest.raises(bio.MissingSplitProtocolError):
        _ = bio.run_tms_aorta_canary(
            artifact,
            split_protocol=None,
            seed=17,
        )

    # Then: no implicit protocol is selected.
