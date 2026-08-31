"""Low-dependency index of capabilities declared by built-in datasets."""

from bioml_data.datasets.tms_aorta._capabilities import (
    TMS_ANIMAL_HELD_OUT_CAPABILITY,
)

BUILTIN_SPLIT_CAPABILITIES = (TMS_ANIMAL_HELD_OUT_CAPABILITY,)
ASSESSED_SPLIT_SCOPES = tuple(
    dict.fromkeys(
        (capability.dataset, capability.task)
        for capability in BUILTIN_SPLIT_CAPABILITIES
    )
)
