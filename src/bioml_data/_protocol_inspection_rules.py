"""Source-of-truth renderings for executable split rules."""

from dataclasses import dataclass

from bioml_data._domain import SplitStrategy
from bioml_data._split import GROUP_HELD_OUT_ALLOCATION_RULE


@dataclass(frozen=True, slots=True)
class SplitRuleInspection:
    """Human and machine-readable details derived from strategy code."""

    strategy: str
    assignment_rule: str
    deterministic_tie_break: str
    requested_group_fractions: tuple[float, float, float] | None
    allocation_policy: str
    validation_policy: str


def inspect_split_rule(strategy: SplitStrategy | None) -> SplitRuleInspection:
    """Describe the executable allocation behavior for a known strategy."""
    match strategy:
        case SplitStrategy.GROUP_HELD_OUT:
            rule = GROUP_HELD_OUT_ALLOCATION_RULE
            return SplitRuleInspection(
                strategy=strategy.value,
                assignment_rule=(
                    "sort grouping-column values by SHA-256(seed + NUL + group_id)"
                ),
                deterministic_tie_break=(
                    "ascending group_id after equal SHA-256 digests"
                ),
                requested_group_fractions=(
                    rule.train_weight / rule.total_weight,
                    rule.validation_weight / rule.total_weight,
                    rule.test_weight / rule.total_weight,
                ),
                allocation_policy=(
                    "minimum one group per partition, weighted floor, then largest "
                    "remainder with train/validation/test index tie-break"
                ),
                validation_policy="present",
            )
        case SplitStrategy.LEAVE_ONE_STUDY_OUT:
            return SplitRuleInspection(
                strategy=strategy.value,
                assignment_rule=(
                    "each fold assigns one complete study to test and all other "
                    "studies to train"
                ),
                deterministic_tie_break="ascending study_id defines fold order",
                requested_group_fractions=None,
                allocation_policy=(
                    "one fold per held-out study; no validation partition is "
                    "synthesized"
                ),
                validation_policy="absent unless the referenced protocol declares one",
            )
        case None:
            return SplitRuleInspection(
                strategy="unspecified",
                assignment_rule="not executable",
                deterministic_tie_break="not applicable",
                requested_group_fractions=None,
                allocation_policy="not executable",
                validation_policy="unspecified",
            )
