"""Publication-boundary validation for split evidence metadata."""

import re
from ipaddress import ip_address
from typing import Final
from urllib.parse import urlsplit

from bioml_data._split_capability_models import SplitProtocolEvidence

_MAX_HOSTNAME_LABEL_LENGTH: Final = 63
_MINIMUM_PUBLIC_HOSTNAME_LABELS: Final = 2
_INVALID_PERCENT_ESCAPE: Final = re.compile(r"%(?![0-9A-Fa-f]{2})")


def valid_split_evidence(evidence: SplitProtocolEvidence) -> bool:
    """Return whether semantic text and citations are publication-safe."""
    return (
        _canonical_text(evidence.fit_scope)
        and _canonical_text(evidence.leakage_caveat)
        and all(
            valid_https_citation(citation.title, citation.uri)
            for citation in evidence.citations
        )
    )


def _canonical_text(value: str) -> bool:
    return bool(value) and value == value.strip()


def valid_https_citation(title: str, uri: str) -> bool:
    """Return whether an uncredentialed public HTTPS citation is safe to publish."""
    if not _canonical_text(title) or not _canonical_text(uri):
        return False
    if any(character.isspace() for character in uri):
        return False
    if _INVALID_PERCENT_ESCAPE.search(uri) is not None:
        return False
    try:
        parsed = urlsplit(uri)
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
        and not parsed.query
        and not parsed.fragment
        and _valid_hostname(hostname)
    )


def _valid_hostname(hostname: str) -> bool:
    try:
        address = ip_address(hostname)
    except ValueError:
        labels = hostname.removesuffix(".").split(".")
        return (
            len(labels) >= _MINIMUM_PUBLIC_HOSTNAME_LABELS
            and hostname.lower() not in {"localhost", "local"}
            and all(_valid_hostname_label(label) for label in labels)
        )
    return address.is_global and not address.is_multicast and not address.is_reserved


def _valid_hostname_label(label: str) -> bool:
    return (
        0 < len(label) <= _MAX_HOSTNAME_LABEL_LENGTH
        and label.isascii()
        and label[0].isalnum()
        and label[-1].isalnum()
        and all(character.isalnum() or character == "-" for character in label)
    )
