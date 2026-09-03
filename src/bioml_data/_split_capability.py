"""Dataset-specific split capability lookup and compatibility facade."""

from bioml_data._domain import SplitEvidenceBasis, SplitStrategy, parse_protocol_id
from bioml_data._split_capability_models import (
    SplitArtifactScope,
    SplitCapability,
    SplitCapabilityAvailability,
    SplitCapabilityQuery,
    SplitCapabilityResult,
    SplitEvidenceCitation,
    SplitEvidenceScope,
    SplitEvidenceType,
    SplitProtocolEvidence,
    SupportedSplitCapability,
    UnknownSplitCapability,
    UnknownSplitCapabilityError,
    UnsupportedSplitCapability,
)
from bioml_data.datasets._capability_index import get_split_capability_index


def query_split_capability(query: SplitCapabilityQuery) -> SplitCapabilityResult:
    """Return supported, unsupported, or unknown without conflating the states."""
    requested = parse_protocol_id(query.protocol)
    index = get_split_capability_index()
    candidates = tuple(
        capability
        for capability in index.capabilities
        if capability.dataset == query.dataset and capability.task == query.task
    )
    for capability in candidates:
        if capability.protocol == requested:
            return SupportedSplitCapability(capability=capability)
    if (query.dataset, query.task) in index.assessed_scopes:
        return UnsupportedSplitCapability(
            query=query,
            supported_protocols=tuple(capability.protocol for capability in candidates),
        )
    return UnknownSplitCapability(query=query)


__all__ = [
    "SplitArtifactScope",
    "SplitCapability",
    "SplitCapabilityAvailability",
    "SplitCapabilityQuery",
    "SplitCapabilityResult",
    "SplitEvidenceBasis",
    "SplitEvidenceCitation",
    "SplitEvidenceScope",
    "SplitEvidenceType",
    "SplitProtocolEvidence",
    "SplitStrategy",
    "SupportedSplitCapability",
    "UnknownSplitCapability",
    "UnknownSplitCapabilityError",
    "UnsupportedSplitCapability",
    "query_split_capability",
]
