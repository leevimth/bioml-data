"""Executable constants and allocation rules for grouped train/val/test splits."""

from dataclasses import dataclass
from hashlib import sha256
from typing import Final


@dataclass(frozen=True, slots=True)
class GroupHeldOutAllocationRule:
    """Weights and minimum cardinality for the versioned group allocation."""

    train_weight: int
    validation_weight: int
    test_weight: int
    total_weight: int
    minimum_group_count: int


@dataclass(frozen=True, slots=True)
class GroupHeldOutPartitionCounts:
    """Realized group counts produced by the group allocation rule."""

    train: int
    validation: int
    test: int


GROUP_HELD_OUT_ALLOCATION_RULE: Final = GroupHeldOutAllocationRule(
    train_weight=8,
    validation_weight=1,
    test_weight=1,
    total_weight=10,
    minimum_group_count=3,
)


def ordered_group_ids(groups: tuple[str, ...], *, seed: int) -> tuple[str, ...]:
    """Return deterministic seeded group order with a collision tie-break."""
    return tuple(
        sorted(
            set(groups),
            key=lambda group: (sha256(f"{seed}\0{group}".encode()).digest(), group),
        )
    )


def group_held_out_partition_counts(group_count: int) -> GroupHeldOutPartitionCounts:
    """Allocate non-empty partitions with weighted floor and largest remainder."""
    rule = GROUP_HELD_OUT_ALLOCATION_RULE
    counts = [
        max(1, group_count * rule.train_weight // rule.total_weight),
        max(1, group_count * rule.validation_weight // rule.total_weight),
        max(1, group_count * rule.test_weight // rule.total_weight),
    ]
    counts[0] -= max(0, sum(counts) - group_count)
    remaining = group_count - sum(counts)
    remainders = (
        group_count * rule.train_weight % rule.total_weight,
        group_count * rule.validation_weight % rule.total_weight,
        group_count * rule.test_weight % rule.total_weight,
    )
    allocation_order = sorted(
        range(len(counts)), key=lambda index: (-remainders[index], index)
    )
    for index in allocation_order[:remaining]:
        counts[index] += 1
    return GroupHeldOutPartitionCounts(
        train=counts[0], validation=counts[1], test=counts[2]
    )
