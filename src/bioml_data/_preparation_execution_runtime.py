"""Bounded, safe runtime metadata for preparation execution receipts."""

import re
from dataclasses import dataclass
from enum import StrEnum, unique
from typing import Final

from bioml_data._preparation_execution_errors import (
    PreparationExecutionReceiptMismatchError,
)

_RUNTIME_VERSION: Final = re.compile(r"^v?[0-9][0-9A-Za-z.!+_-]{0,63}$")


@unique
class RuntimeComponent(StrEnum):
    """Bounded runtime components relevant to single-cell preparation."""

    ANNDATA = "anndata"
    NUMPY = "numpy"
    SCIPY = "scipy"


@dataclass(frozen=True, slots=True)
class DependencyVersion:
    """One allowlisted runtime dependency and a compact version string."""

    component: RuntimeComponent | str
    version: str

    def __post_init__(self) -> None:
        """Parse the allowlisted component and a safe bounded version."""
        object.__setattr__(self, "component", _runtime_component(self.component))
        object.__setattr__(
            self,
            "version",
            _runtime_version(field="dependency_version", value=self.version),
        )


@dataclass(frozen=True, slots=True)
class PreparationExecutionRuntime:
    """Toolkit plus a bounded, canonically ordered dependency version set."""

    toolkit_version: str
    dependencies: tuple[DependencyVersion, ...]

    def __post_init__(self) -> None:
        """Keep runtime metadata small, normalized, unique, and deterministic."""
        components = tuple(item.component for item in self.dependencies)
        object.__setattr__(
            self,
            "toolkit_version",
            _runtime_version(field="toolkit_version", value=self.toolkit_version),
        )
        if components != tuple(sorted(components, key=str)):
            raise PreparationExecutionReceiptMismatchError(
                field="runtime_dependencies",
                expected="sorted by component",
                actual=str(components),
            )
        if len(components) != len(set(components)):
            raise PreparationExecutionReceiptMismatchError(
                field="runtime_dependencies",
                expected="unique components",
                actual=str(components),
            )


def _runtime_component(component: RuntimeComponent | str) -> RuntimeComponent:
    """Parse a dependency name into the bounded runtime component allowlist."""
    try:
        return RuntimeComponent(component)
    except ValueError:
        raise PreparationExecutionReceiptMismatchError(
            field="dependency_component",
            expected="anndata, numpy, or scipy",
            actual=component,
        ) from None


def _runtime_version(*, field: str, value: str) -> str:
    """Reject paths, URIs, secrets, environment text, and command-like values."""
    if _RUNTIME_VERSION.fullmatch(value) is None:
        raise PreparationExecutionReceiptMismatchError(
            field=field,
            expected="safe version syntax up to 64 characters",
            actual=value,
        )
    return value
