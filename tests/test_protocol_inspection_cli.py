"""Protocol-inspection command error scenarios."""

from typing import NoReturn

import pytest
from typer.testing import CliRunner

import bioml_data as bio
from bioml_data import _cli as cli_module


@pytest.mark.parametrize(
    ("arguments", "expected_fragment"),
    [
        (
            [
                "inspect",
                "unknown",
                "--task",
                "cell-type-annotation-v1",
                "--protocol",
                "animal-held-out-v1",
            ],
            "unknown dataset",
        ),
        (
            [
                "inspect",
                "tms-aorta",
                "--version",
                "unknown-version",
                "--task",
                "cell-type-annotation-v1",
                "--protocol",
                "animal-held-out-v1",
            ],
            "unknown version",
        ),
        (
            [
                "inspect",
                "tms-aorta",
                "--task",
                "unknown-task",
                "--protocol",
                "animal-held-out-v1",
            ],
            "unknown task",
        ),
        (
            [
                "inspect",
                "tms-aorta",
                "--task",
                "cell-type-annotation-v1",
                "--protocol",
                "unknown-protocol",
            ],
            "unsupported split protocol",
        ),
    ],
)
def test_cli_inspect_reports_invalid_contract_without_traceback(
    arguments: list[str], expected_fragment: str
) -> None:
    """Catalog selection failures stay concise at the CLI boundary."""
    # Given: one invalid protocol-inspection selection.
    # When: the public CLI parses it.
    result = CliRunner().invoke(bio.cli_app, arguments)

    # Then: it emits exactly one actionable error line and no result.
    assert result.exit_code == 2
    assert result.stdout == ""
    assert expected_fragment in result.stderr
    assert result.stderr.count("\n") == 1


def test_cli_inspect_reports_receipt_mismatch_without_traceback(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """An inspection receipt mismatch is translated at the CLI boundary."""

    # Given: the inspection boundary reports a typed receipt mismatch.
    def reject_inspection(
        name: str,
        *,
        task: str,
        protocol: str,
        request: bio.ProtocolInspectionRequest | None = None,
    ) -> NoReturn:
        _ = (name, task, protocol, request)
        raise bio.ProtocolInspectionReceiptMismatchError(
            field="assignment_identity", expected="expected", actual="actual"
        )

    monkeypatch.setattr(cli_module, "inspect_protocol", reject_inspection)

    # When: the public CLI encounters that expected domain failure.
    result = CliRunner().invoke(
        bio.cli_app,
        [
            "inspect",
            "tms-aorta",
            "--task",
            "cell-type-annotation-v1",
            "--protocol",
            "animal-held-out-v1",
        ],
    )

    # Then: it emits one typed line without a traceback or output report.
    assert result.exit_code == 2
    assert result.stdout == ""
    assert result.stderr == (
        "protocol inspection receipt mismatch for assignment_identity: "
        "expected 'expected', received 'actual'\n"
    )
