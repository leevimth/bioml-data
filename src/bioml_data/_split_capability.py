"""Dataset-specific split capability lookup and compatibility facade."""

from bioml_data._domain import parse_protocol_id
from bioml_data._split_capability_models import (
    SplitCapability,
    SplitCapabilityAvailability,
    SplitCapabilityQuery,
    SplitCapabilityResult,
    SplitEvidenceType,
    SupportedSplitCapability,
    UnknownSplitCapability,
    UnknownSplitCapabilityError,
    UnsupportedSplitCapability,
)
from bioml_data.datasets._capabilities import (
    ASSESSED_SPLIT_SCOPES,
    BUILTIN_SPLIT_CAPABILITIES,
)


def query_split_capability(query: SplitCapabilityQuery) -> SplitCapabilityResult:
    """Return supported, unsupported, or unknown without conflating the states."""
    requested = parse_protocol_id(query.protocol)
    candidates = tuple(
        capability
        for capability in BUILTIN_SPLIT_CAPABILITIES
        if capability.dataset == query.dataset and capability.task == query.task
    )
    for capability in candidates:
        if capability.protocol == requested:
            return SupportedSplitCapability(capability=capability)
    if (query.dataset, query.task) in ASSESSED_SPLIT_SCOPES:
        return UnsupportedSplitCapability(
            query=query,
            supported_protocols=tuple(capability.protocol for capability in candidates),
        )
    return UnknownSplitCapability(query=query)


__all__ = [
    "SplitCapability",
    "SplitCapabilityAvailability",
    "SplitCapabilityQuery",
    "SplitCapabilityResult",
    "SplitEvidenceType",
    "SupportedSplitCapability",
    "UnknownSplitCapability",
    "UnknownSplitCapabilityError",
    "UnsupportedSplitCapability",
    "query_split_capability",
]
