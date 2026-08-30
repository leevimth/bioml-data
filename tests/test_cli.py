"""Command-line end-to-end canary scenarios."""

from pathlib import Path

from typer.testing import CliRunner, Result

import bioml_data as bio
from tests._single_cell_fixtures import make_tms_artifact


def _run_cli(manifest_path: Path) -> Result:
    return CliRunner().invoke(
        bio.cli_app,
        [
            "--artifact-manifest",
            str(manifest_path),
            "--split-protocol",
            "animal-held-out-v1",
        ],
    )


def _assert_receipt_failure(
    result: Result,
    manifest_path: Path,
    reason: bio.ArtifactReceiptFailure,
) -> None:
    assert result.exit_code == 2
    assert result.stdout == ""
    assert result.stderr == f"cannot load artifact receipt {manifest_path}: {reason}\n"


def test_cli_canary_matches_python_identity_chain(tmp_path: Path) -> None:
    # Given: one local artifact receipt and the equivalent Python invocation.
    artifact = make_tms_artifact(tmp_path / "cache")
    expected = bio.run_tms_aorta_canary(
        artifact,
        split_protocol="animal-held-out-v1",
        seed=17,
    )

    # When: the same artifact, protocol, and seed run through the CLI.
    result = CliRunner().invoke(
        bio.cli_app,
        [
            "--artifact-manifest",
            str(artifact.manifest_path),
            "--split-protocol",
            "animal-held-out-v1",
            "--seed",
            "17",
        ],
    )

    # Then: the CLI emits the exact shared pipeline receipt.
    assert result.exit_code == 0
    assert bio.BenchmarkRunReceipt.model_validate_json(result.stdout) == expected


def test_cli_omitted_split_protocol_fails_clearly(tmp_path: Path) -> None:
    # Given: a valid local artifact manifest and no split selection.
    artifact = make_tms_artifact(tmp_path / "cache")

    # When: the CLI runs without --split-protocol.
    result = CliRunner().invoke(
        bio.cli_app,
        ["--artifact-manifest", str(artifact.manifest_path)],
    )

    # Then: the command fails without emitting a result receipt.
    assert result.exit_code == 2
    assert "split protocol required" in result.stderr
    assert result.stdout == ""


def test_cli_reports_manifest_io_without_traceback(tmp_path: Path) -> None:
    # Given: a manifest path that cannot be read.
    manifest_path = tmp_path / "missing-manifest.json"

    # When: the installed CLI receives that path.
    result = _run_cli(manifest_path)

    # Then: one typed actionable line replaces Typer/Rich diagnostics.
    _assert_receipt_failure(
        result,
        manifest_path,
        bio.ArtifactReceiptFailure.MANIFEST_IO,
    )


def test_cli_reports_invalid_manifest_without_traceback(
    tmp_path: Path,
) -> None:
    # Given: a readable file that is not an artifact manifest.
    manifest_path = tmp_path / "invalid-manifest.json"
    _ = manifest_path.write_text("{not-json", encoding="utf-8")

    # When: the installed CLI parses the malformed boundary input.
    result = _run_cli(manifest_path)

    # Then: one typed actionable line replaces a validation traceback.
    _assert_receipt_failure(
        result,
        manifest_path,
        bio.ArtifactReceiptFailure.INVALID_MANIFEST,
    )


def test_cli_reports_missing_content_without_traceback(
    tmp_path: Path,
) -> None:
    # Given: a valid manifest whose sibling immutable blob is absent.
    artifact = make_tms_artifact(tmp_path / "cache")
    artifact.content_path.unlink()

    # When: the installed CLI reopens the incomplete receipt.
    result = _run_cli(artifact.manifest_path)

    # Then: one typed actionable line identifies the missing content state.
    _assert_receipt_failure(
        result,
        artifact.manifest_path,
        bio.ArtifactReceiptFailure.MISSING_CONTENT,
    )
