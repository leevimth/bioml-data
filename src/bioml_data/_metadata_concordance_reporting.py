"""Stable identities for complete metadata-concordance evidence reports."""

import json
from dataclasses import asdict
from hashlib import sha256
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from bioml_data._metadata_concordance import MetadataConcordanceReport


def metadata_concordance_identity(report: "MetadataConcordanceReport") -> str:
    """Hash every scoped concordance value in canonical report order."""
    payload = json.dumps(asdict(report), sort_keys=True, separators=(",", ":"))
    return sha256(payload.encode()).hexdigest()
