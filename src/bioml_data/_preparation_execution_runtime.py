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
        object.__setattr__(
            self,
            "toolkit_version",
            _runtime_version(field="toolkit_version", value=self.toolkit_version),
        )
        normalized_dependencies = _validated_dependencies(self.dependencies)
        object.__setattr__(self, "dependencies", normalized_dependencies)
        validate_runtime_metadata(self)


def validate_runtime_metadata(runtime: PreparationExecutionRuntime) -> None:
    """Revalidate public runtime fields after hostile frozen-object mutation."""
    _ = _runtime_version(field="toolkit_version", value=runtime.toolkit_version)
    dependencies = _validated_dependencies(runtime.dependencies)
    components = tuple(item.component for item in dependencies)
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


def _validated_dependency(dependency: DependencyVersion) -> DependencyVersion:
    """Parse every nested dependency while preserving its immutable payload."""
    _require_dependency(dependency)
    component = _runtime_component(dependency.component)
    version = _runtime_version(field="dependency_version", value=dependency.version)
    if component is not dependency.component or version != dependency.version:
        raise PreparationExecutionReceiptMismatchError(
            field="runtime_dependency",
            expected="canonical RuntimeComponent and version",
            actual=f"{dependency.component!r}:{dependency.version!r}",
        )
    return dependency


def _validated_dependencies(
    dependencies: tuple[DependencyVersion, ...],
) -> tuple[DependencyVersion, ...]:
    """Parse the immutable dependency tuple before traversing its items."""
    if type(dependencies) is not tuple:
        raise PreparationExecutionReceiptMismatchError(
            field="runtime_dependencies",
            expected="tuple of DependencyVersion items",
            actual=type(dependencies).__name__,
        )
    return tuple(_validated_dependency(item) for item in dependencies)


def _require_dependency(value: DependencyVersion) -> None:
    """Narrow an untrusted nested item before reading dependency fields."""
    if type(value) is not DependencyVersion:
        raise PreparationExecutionReceiptMismatchError(
            field="runtime_dependencies",
            expected="DependencyVersion items",
            actual=type(value).__name__,
        )


def _runtime_component(component: RuntimeComponent | str) -> RuntimeComponent:
    """Parse a dependency name into the bounded runtime component allowlist."""
    try:
        return RuntimeComponent(component)
    except (TypeError, ValueError):
        raise PreparationExecutionReceiptMismatchError(
            field="dependency_component",
            expected="anndata, numpy, or scipy",
            actual=component,
        ) from None


def _runtime_version(*, field: str, value: str) -> str:
    """Reject paths, URIs, secrets, environment text, and command-like values."""
    if type(value) is not str or _RUNTIME_VERSION.fullmatch(value) is None:
        raise PreparationExecutionReceiptMismatchError(
            field=field,
            expected="safe version syntax up to 64 characters",
            actual=value,
        )
    return value
