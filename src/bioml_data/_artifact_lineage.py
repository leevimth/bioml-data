"""Receipts binding a derived artifact to verified parent receipts."""

from dataclasses import dataclass

from bioml_data._artifacts import ArtifactReceipt


@dataclass(frozen=True, slots=True)
class ArtifactLineageReceipt:
    """Derived artifact plus the parent receipts required for materialization."""

    artifact: ArtifactReceipt
    parent_artifacts: tuple[ArtifactReceipt, ...]
