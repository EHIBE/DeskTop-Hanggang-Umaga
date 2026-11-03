from itertools import product

import pytest

from voice.grammar import Command, CommandKind
from voice.ownership import (
    ACCEPT,
    UNOWNED_KINDS,
    OwnershipDecision,
    OwnershipOutcome,
    check_ownership,
)

STRICT = (True, False)
SPEAKERS = (None, "P1", "P2", "")
OWNERS = (None, "P1", "P2", "")
UNIT_IDS = (None, "u_a")


def expected(
    strict: bool,
    speaker: str | None,
    owner: str | None,
    kind: CommandKind,
    unit_id: str | None,
) -> OwnershipDecision:
    if not strict:
        return ACCEPT
    if kind in (CommandKind.END_TURN, CommandKind.CANCEL):
        return ACCEPT
    if unit_id is None:
        return ACCEPT
    if owner is None or speaker is None:
        return ACCEPT
    if speaker == owner:
        return ACCEPT
    return OwnershipDecision(
        OwnershipOutcome.NEEDS_CONFIRMATION, owner=owner, unit_id=unit_id
    )


def test_unowned_kinds_are_end_turn_and_cancel() -> None:
    assert UNOWNED_KINDS == {CommandKind.END_TURN, CommandKind.CANCEL}


def test_accept_constant() -> None:
    assert ACCEPT.is_accepted
    assert ACCEPT.owner is None
    assert ACCEPT.unit_id is None


def test_full_truth_table() -> None:
    cases = 0
    for strict, speaker, owner, kind, unit_id in product(
        STRICT, SPEAKERS, OWNERS, CommandKind, UNIT_IDS
    ):
        command = Command(kind, unit_id, None)
        got = check_ownership(
            strict=strict, speaker=speaker, owner=owner, command=command
        )
        assert got == expected(strict, speaker, owner, kind, unit_id), (
            strict,
            speaker,
            owner,
            kind,
            unit_id,
        )
        cases += 1
    assert cases == 2 * 4 * 4 * 5 * 2


def test_only_strict_mismatch_on_owned_unit_needs_confirmation() -> None:
    needing = [
        (strict, speaker, owner, kind, unit_id)
        for strict, speaker, owner, kind, unit_id in product(
            STRICT, SPEAKERS, OWNERS, CommandKind, UNIT_IDS
        )
        if not check_ownership(
            strict=strict,
            speaker=speaker,
            owner=owner,
            command=Command(kind, unit_id, None),
        ).is_accepted
    ]
    assert needing
    for strict, speaker, owner, kind, unit_id in needing:
        assert strict is True
        assert kind in (CommandKind.ATTACK, CommandKind.POWER, CommandKind.HEAL)
        assert unit_id == "u_a"
        assert speaker is not None
        assert owner is not None
        assert speaker != owner


@pytest.mark.parametrize("kind", list(CommandKind))
def test_non_strict_always_accepts(kind: CommandKind) -> None:
    decision = check_ownership(
        strict=False, speaker="P1", owner="P2", command=Command(kind, "u_a", "e_x")
    )
    assert decision is ACCEPT


def test_confirmation_carries_owner_and_unit() -> None:
    decision = check_ownership(
        strict=True,
        speaker="P2",
        owner="P1",
        command=Command(CommandKind.ATTACK, "u_a", "e_aswang_1"),
    )
    assert decision.outcome is OwnershipOutcome.NEEDS_CONFIRMATION
    assert not decision.is_accepted
    assert decision.owner == "P1"
    assert decision.unit_id == "u_a"


def test_target_does_not_change_the_decision() -> None:
    for kind in CommandKind:
        base = check_ownership(
            strict=True,
            speaker="P1",
            owner="P2",
            command=Command(kind, "u_a", None),
        )
        for target in ("u_b", "e_aswang_1", "", "anything"):
            assert base == check_ownership(
                strict=True,
                speaker="P1",
                owner="P2",
                command=Command(kind, "u_a", target),
            )
