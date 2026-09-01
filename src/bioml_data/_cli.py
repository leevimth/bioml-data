"""Command-line surface for the TMS Aorta product canary."""

from pathlib import Path
from typing import Annotated

import typer

from bioml_data._artifact_receipts import (
    ArtifactReceiptLoadError,
    load_artifact_receipt,
)
from bioml_data._dataset_preparation import (
    UnexpectedDatasetSourceError,
    prepare_dataset,
)
from bioml_data._dataset_preparation_models import PreparedDatasetCacheError
from bioml_data._pipeline import run_tms_aorta_canary
from bioml_data._split import MissingSplitProtocolError
from bioml_data.datasets.tms_aorta._h5ad_transform import InvalidRawTmsArtifactError

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
    prepare_data_dir: Annotated[
        Path | None,
        typer.Option("--prepare-data-dir"),
    ] = None,
) -> None:
    """Optionally prepare a raw H5AD, then run the TMS Aorta canary."""
    try:
        artifact = load_artifact_receipt(artifact_manifest)
        if prepare_data_dir is not None:
            artifact = prepare_dataset(
                "tms-aorta",
                artifact=artifact,
                data_dir=prepare_data_dir,
            ).artifact
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
    except (
        InvalidRawTmsArtifactError,
        PreparedDatasetCacheError,
        UnexpectedDatasetSourceError,
    ) as error:
        typer.echo(str(error), err=True)
        raise typer.Exit(code=2) from error
    typer.echo(receipt.model_dump_json())


if __name__ == "__main__":
    app()
