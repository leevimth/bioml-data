"""Publication-boundary validation for split evidence metadata."""

import re
from ipaddress import ip_address
from typing import Final
from urllib.parse import urlsplit

from bioml_data._split_capability_models import (
    SplitEvidenceCitation,
    SplitProtocolEvidence,
)

_MAX_HOSTNAME_LABEL_LENGTH: Final = 63
_INVALID_PERCENT_ESCAPE: Final = re.compile(r"%(?![0-9A-Fa-f]{2})")


def valid_split_evidence(evidence: SplitProtocolEvidence) -> bool:
    """Return whether semantic text and citations are publication-safe."""
    return (
        _canonical_text(evidence.fit_scope)
        and _canonical_text(evidence.leakage_caveat)
        and all(_valid_citation(citation) for citation in evidence.citations)
    )


def _canonical_text(value: str) -> bool:
    return bool(value) and value == value.strip()


def _valid_citation(citation: SplitEvidenceCitation) -> bool:
    if not _canonical_text(citation.title) or not _canonical_text(citation.uri):
        return False
    if any(character.isspace() for character in citation.uri):
        return False
    if _INVALID_PERCENT_ESCAPE.search(citation.uri) is not None:
        return False
    try:
        parsed = urlsplit(citation.uri)
        hostname = parsed.hostname
        _ = parsed.port
    except ValueError:
        return False
    return (
        parsed.scheme == "https"
        and hostname is not None
        and not parsed.netloc.endswith(":")
        and parsed.username is None
        and parsed.password is None
        and _valid_hostname(hostname)
    )


def _valid_hostname(hostname: str) -> bool:
    try:
        address = ip_address(hostname)
    except ValueError:
        labels = hostname.removesuffix(".").split(".")
        return bool(labels) and all(_valid_hostname_label(label) for label in labels)
    return not address.is_loopback and not address.is_private


def _valid_hostname_label(label: str) -> bool:
    return (
        0 < len(label) <= _MAX_HOSTNAME_LABEL_LENGTH
        and label.isascii()
        and label[0].isalnum()
        and label[-1].isalnum()
        and all(character.isalnum() or character == "-" for character in label)
    )
