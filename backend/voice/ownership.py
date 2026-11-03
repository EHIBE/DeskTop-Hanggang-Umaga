from dataclasses import dataclass
from enum import StrEnum
from typing import Final

from voice.grammar import Command, CommandKind

UNOWNED_KINDS: Final = frozenset((CommandKind.END_TURN, CommandKind.CANCEL))


class OwnershipOutcome(StrEnum):
    ACCEPT = "accept"
    NEEDS_CONFIRMATION = "needs_confirmation"


@dataclass(frozen=True)
class OwnershipDecision:
    outcome: OwnershipOutcome
    owner: str | None = None
    unit_id: str | None = None

    @property
    def is_accepted(self) -> bool:
        return self.outcome is OwnershipOutcome.ACCEPT


ACCEPT: Final = OwnershipDecision(OwnershipOutcome.ACCEPT)


def check_ownership(
    *,
    strict: bool,
    speaker: str | None,
    owner: str | None,
    command: Command,
) -> OwnershipDecision:
    if not strict:
        return ACCEPT
    if command.kind in UNOWNED_KINDS or command.unit_id is None:
        return ACCEPT
    if owner is None or speaker is None or speaker == owner:
        return ACCEPT
    return OwnershipDecision(
        OwnershipOutcome.NEEDS_CONFIRMATION, owner=owner, unit_id=command.unit_id
    )
