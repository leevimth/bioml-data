"""Canonical identities for complete split assignment receipts."""

import json
from dataclasses import dataclass
from hashlib import sha256


@dataclass(frozen=True, slots=True)
class AssignmentReceiptIdentityFields:
    """Primitive receipt fields that must commit to one split identity."""

    dataset_name: str
    dataset_version: str
    task: str
    protocol: str
    seed: int
    assignments: tuple[tuple[str, str, str], ...]
    requested_group_fractions: tuple[float, float, float]
    realized_group_counts: tuple[int, int, int]
    observation_count: int
    group_count: int


def canonical_assignment_receipt_identity(
    fields: AssignmentReceiptIdentityFields,
) -> str:
    """Hash every receipt field rendered as realized split evidence."""
    payload = {
        "assignments": fields.assignments,
        "dataset": (fields.dataset_name, fields.dataset_version),
        "group_count": fields.group_count,
        "observation_count": fields.observation_count,
        "protocol": fields.protocol,
        "realized_group_counts": fields.realized_group_counts,
        "requested_group_fractions": fields.requested_group_fractions,
        "seed": fields.seed,
        "task": fields.task,
    }
    encoded = json.dumps(payload, sort_keys=True, separators=(",", ":"))
    return sha256(encoded.encode()).hexdigest()
