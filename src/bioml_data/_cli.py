"""Command-line surface for the TMS Aorta product canary."""

from pathlib import Path
from typing import Annotated

import typer

from bioml_data._artifact_receipts import (
    ArtifactReceiptLoadError,
    load_artifact_receipt,
)
from bioml_data._pipeline import run_tms_aorta_canary
from bioml_data._split import MissingSplitProtocolError

app = typer.Typer(
    add_completion=False,
    help="Run the reproducible bioml-data technical canary.",
)


@app.command()
def run(
    artifact_manifest: Annotated[
        Path,
        typer.Option("--artifact-manifest"),
    ],
    split_protocol: Annotated[
        str | None,
        typer.Option("--split-protocol"),
    ] = None,
    seed: Annotated[int, typer.Option("--seed")] = 17,
) -> None:
    """Run the fixture-scale TMS Aorta canary and emit a JSON receipt."""
    try:
        artifact = load_artifact_receipt(artifact_manifest)
        receipt = run_tms_aorta_canary(
            artifact,
            split_protocol=split_protocol,
            seed=seed,
        )
    except ArtifactReceiptLoadError as error:
        typer.echo(str(error), err=True)
        raise typer.Exit(code=2) from error
    except MissingSplitProtocolError as error:
        typer.echo(str(error), err=True)
        raise typer.Exit(code=2) from error
    typer.echo(receipt.model_dump_json())


if __name__ == "__main__":
    app()
