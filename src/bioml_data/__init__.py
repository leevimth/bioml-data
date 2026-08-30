"""Reproducible data protocols for biological machine learning."""

from importlib.metadata import version
from typing import Final

__version__: Final = version("bioml-data")

__all__ = ["__version__"]
