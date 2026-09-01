"""Headless execution of the researcher-facing TMS Aorta notebook."""

import subprocess
import sys
from pathlib import Path
from typing import ClassVar

import pytest
from pydantic import BaseModel, ConfigDict

from bioml_data.datasets.tms_aorta._h5ad_transform import TmsAortaTransformLimits
from bioml_data.datasets.tms_aorta._transform import prepare_tms_aorta
from tests._anndata_fixtures import store_tms_aorta_h5ad


class _NotebookSummary(BaseModel):
    model_config: ClassVar[ConfigDict] = ConfigDict(frozen=True)

    cells: int
    genes: int
    donors: int
    cell_types: int
    sparse: bool


def test_tms_aorta_notebook_loads_fixture_and_writes_eda_artifacts(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    # Given: a verified local H5AD and a headless notebook environment.
    receipt = store_tms_aorta_h5ad(tmp_path / "cache", tmp_path / "source.h5ad")
    prepared = prepare_tms_aorta(
        receipt,
        data_dir=tmp_path / "prepared-cache",
        limits=TmsAortaTransformLimits(
            observations=6,
            features=3,
            maximum_nonzero_counts=20,
            maximum_metadata_length=64,
            maximum_output_bytes=32_000,
        ),
    )
    output_dir = tmp_path / "eda-output"
    monkeypatch.setenv("BIOML_ARTIFACT_MANIFEST", str(receipt.manifest_path))
    monkeypatch.setenv("BIOML_DATA_DIR", str(tmp_path / "prepared-cache"))
    monkeypatch.setenv(
        "BIOML_CANONICAL_ARTIFACT_MANIFEST",
        str(prepared.artifact.manifest_path),
    )
    monkeypatch.setenv("BIOML_EDA_OUTPUT_DIR", str(output_dir))
    monkeypatch.setenv("MPLBACKEND", "Agg")
    monkeypatch.setenv("IPYTHONDIR", str(tmp_path / "ipython"))
    monkeypatch.setenv("PYTHONPATH", str(Path("src").resolve()))
    notebook_path = Path("examples/tms_aorta_eda.ipynb")
    executed_path = tmp_path / "executed.ipynb"
    jupyter = Path(sys.executable).with_name("jupyter")

    # When: nbclient's CLI runs every notebook cell in a real Jupyter kernel.
    _ = subprocess.run(  # noqa: S603 -- executable is the active venv's Jupyter.
        [
            jupyter,
            "execute",
            notebook_path,
            "--timeout=120",
            f"--output={executed_path}",
        ],
        check=True,
        capture_output=True,
        text=True,
        timeout=150,
    )

    # Then: execution completed and emitted machine-readable EDA artifacts.
    assert executed_path.stat().st_size > 0
    summary = _NotebookSummary.model_validate_json(
        (output_dir / "summary.json").read_text(encoding="utf-8"),
    )
    assert summary.cells == 6
    assert summary.genes == 3
    assert summary.donors == 5
    assert summary.cell_types == 3
    assert summary.sparse
    assert (output_dir / "tms_aorta_eda.png").stat().st_size > 0
