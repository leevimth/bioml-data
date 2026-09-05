"""Assemble the pancreas definition and runtime adapter."""

from bioml_data.datasets._models import DatasetRegistration
from bioml_data.datasets.pancreas._adapter import load_pancreas
from bioml_data.datasets.pancreas._capabilities import PANCREAS_LODO_CAPABILITY
from bioml_data.datasets.pancreas._definition import PANCREAS_DEFINITION
from bioml_data.datasets.pancreas._identity import (
    PANCREAS_ARTIFACT_SCOPE,
    PANCREAS_CANONICAL_DERIVATION,
)

PANCREAS_REGISTRATION = DatasetRegistration(
    definition=PANCREAS_DEFINITION,
    materialize=load_pancreas,
    split_capabilities=(PANCREAS_LODO_CAPABILITY,),
    artifact_scope=PANCREAS_ARTIFACT_SCOPE,
    canonical_derivation=PANCREAS_CANONICAL_DERIVATION,
)
