"""Command-line surface for reproducible dataset protocols."""

import json
from pathlib import Path
from typing import Annotated

import typer

from bioml_data._artifact_receipts import (
    ArtifactReceiptLoadError,
    load_artifact_receipt,
)
from bioml_data._catalog import load_dataset
from bioml_data._dataset_definition import (
    UnknownTaskError,
    UnsupportedSplitProtocolError,
)
from bioml_data._dataset_downloads import download_dataset
from bioml_data._dataset_preparation import (
    UnexpectedDatasetSourceError,
    prepare_dataset,
)
from bioml_data._dataset_preparation_models import PreparedDatasetCacheError
from bioml_data._domain import (
    CatalogKeyError,
    UnknownDatasetError,
    UnknownDatasetVersionError,
)
from bioml_data._pipeline import run_tms_aorta_canary
from bioml_data._protocol_inspection import inspect_protocol
from bioml_data._protocol_inspection_models import (
    ProtocolInspectionReceiptMismatchError,
    ProtocolInspectionRequest,
)
from bioml_data._split import MissingSplitProtocolError
from bioml_data.datasets.pancreas._metadata import pancreas_metadata_concordance
from bioml_data.datasets.pancreas._splits import UnknownPancreasStudyError
from bioml_data.datasets.tms_aorta._h5ad_transform import InvalidRawTmsArtifactError

app = typer.Typer(
    add_completion=False,
    help="Inspect or run reproducible bioml-data protocols.",
    invoke_without_command=True,
)


@app.callback()
def run(
    context: typer.Context,
    artifact_manifest: Annotated[
        Path | None,
        typer.Option("--artifact-manifest"),
    ] = None,
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
    if context.invoked_subcommand is not None:
        return
    if artifact_manifest is None:
        typer.echo("--artifact-manifest is required to run the canary", err=True)
        raise typer.Exit(code=2)
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


@app.command()
def inspect(
    dataset: Annotated[str, typer.Argument()],
    task: Annotated[str, typer.Option("--task")],
    protocol: Annotated[str, typer.Option("--protocol")],
    version: Annotated[str | None, typer.Option("--version")] = None,
    as_json: Annotated[bool, typer.Option("--json")] = False,
) -> None:
    """Describe one declared dataset protocol without executing it."""
    try:
        report = inspect_protocol(
            dataset,
            task=task,
            protocol=protocol,
            request=ProtocolInspectionRequest(version=version),
        )
    except (
        CatalogKeyError,
        ProtocolInspectionReceiptMismatchError,
        UnknownDatasetError,
        UnknownDatasetVersionError,
        UnknownTaskError,
        UnsupportedSplitProtocolError,
    ) as error:
        typer.echo(str(error), err=True)
        raise typer.Exit(code=2) from error
    typer.echo(report.to_json() if as_json else report.to_text())


@app.command()
def pancreas(
    data_dir: Annotated[Path, typer.Option("--data-dir")],
    held_out_study: Annotated[str, typer.Option("--held-out-study")],
) -> None:
    """Prepare one cached pancreas reference and inspect an explicit LODO fold."""
    try:
        raw = download_dataset("pancreas-four-study", data_dir=data_dir).artifact
        prepared = prepare_dataset(
            "pancreas-four-study",
            artifact=raw,
            data_dir=data_dir,
        )
        dataset = load_dataset("pancreas-four-study", artifact=prepared.lineage)
        report = pancreas_metadata_concordance(dataset, held_out_study=held_out_study)
    except (
        PreparedDatasetCacheError,
        UnexpectedDatasetSourceError,
        UnknownPancreasStudyError,
    ) as error:
        typer.echo(str(error), err=True)
        raise typer.Exit(code=2) from error
    test = next(item for item in report.partition_reports if item.partition == "test")
    typer.echo(
        json.dumps(
            {
                "artifact_id": str(prepared.artifact.artifact_id),
                "held_out_study": held_out_study,
                "preparation_outcome": prepared.outcome.value,
                "test_cells": test.observation_count,
                "test_metadata": [item.status.value for item in test.comparisons],
            },
            separators=(",", ":"),
        )
    )


if __name__ == "__main__":
    app()
