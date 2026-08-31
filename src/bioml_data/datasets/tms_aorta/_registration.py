"""Assemble the TMS Aorta definition and its runtime adapter."""

from bioml_data.datasets._models import DatasetRegistration
from bioml_data.datasets.tms_aorta._adapter import load_tms_aorta
from bioml_data.datasets.tms_aorta._capabilities import (
    TMS_ANIMAL_HELD_OUT_CAPABILITY,
)
from bioml_data.datasets.tms_aorta._definition import TMS_AORTA_DEFINITION

TMS_AORTA_REGISTRATION = DatasetRegistration(
    definition=TMS_AORTA_DEFINITION,
    materialize=load_tms_aorta,
    split_capabilities=(TMS_ANIMAL_HELD_OUT_CAPABILITY,),
)
