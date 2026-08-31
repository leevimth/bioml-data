"""Compatibility facade for the TMS Aorta canary workflow."""

from bioml_data.datasets.tms_aorta._workflow import (
    BenchmarkRunReceipt,
    run_tms_aorta_canary,
)

__all__ = ["BenchmarkRunReceipt", "run_tms_aorta_canary"]
