import pytest

from game.state_machine import (
    TRANSITIONS,
    IllegalTransitionError,
    Transition,
    TurnEvent,
    TurnState,
    TurnStateMachine,
)

ONE_TURN = [
    TurnEvent.TELEGRAPHED,
    TurnEvent.END_TURN,
    TurnEvent.SNAPSHOT_DONE,
    TurnEvent.MOVES_LEGAL,
    TurnEvent.PLAYER_RESOLVED,
    TurnEvent.ENEMY_RESOLVED,
    TurnEvent.EFFECTS_DONE,
]


def test_scripted_night_visits_every_transition_in_order() -> None:
    log: list[Transition] = []
    machine = TurnStateMachine(on_transition=log.append)
    machine.transition(TurnEvent.CALIBRATED)
    machine.transition(TurnEvent.BEGIN_NIGHT)
    machine.transition(TurnEvent.CLAIMS_DONE)
    for turn in range(1, 9):
        machine.transition(TurnEvent.TELEGRAPHED)
        if turn == 2:
            machine.transition(TurnEvent.PAUSE)
            machine.transition(TurnEvent.RESUME)
            machine.transition(TurnEvent.END_TURN)
            machine.transition(TurnEvent.SNAPSHOT_DONE)
            machine.transition(TurnEvent.MOVES_ILLEGAL)
        for event in ONE_TURN[1:]:
            machine.transition(event)
        machine.transition(TurnEvent.NEXT_TURN if turn < 8 else TurnEvent.SURVIVED)
    machine.transition(TurnEvent.REPLAY_REQUESTED)
    assert machine.state is TurnState.REPLAY
    visited = {(t.source, t.event) for t in log}
    missing = set(TRANSITIONS) - visited - {(TurnState.CHECK_END, TurnEvent.FELL)}
    assert missing == set()
    assert log[0] == Transition(
        TurnState.CALIBRATE, TurnEvent.CALIBRATED, TurnState.SUMMON
    )


def test_defeat_path() -> None:
    machine = TurnStateMachine(initial=TurnState.CHECK_END)
    assert machine.transition(TurnEvent.FELL) is TurnState.DEFEAT


@pytest.mark.parametrize(
    ("state", "event"),
    [
        (TurnState.SUMMON, TurnEvent.END_TURN),
        (TurnState.PLAYER_PHASE, TurnEvent.MOVES_LEGAL),
        (TurnState.RESOLVE_PLAYER, TurnEvent.PAUSE),
        (TurnState.DEFEAT, TurnEvent.REPLAY_REQUESTED),
        (TurnState.SUNRISE, TurnEvent.NEXT_TURN),
        (TurnState.PAUSED, TurnEvent.END_TURN),
    ],
)
def test_illegal_transitions_are_rejected(state: TurnState, event: TurnEvent) -> None:
    machine = TurnStateMachine(initial=state)
    assert not machine.can(event)
    with pytest.raises(IllegalTransitionError):
        machine.transition(event)
    assert machine.state is state


def test_force_sets_state_without_logging() -> None:
    log: list[Transition] = []
    machine = TurnStateMachine(on_transition=log.append)
    machine.force(TurnState.PLAYER_PHASE)
    assert machine.state is TurnState.PLAYER_PHASE
    assert log == []


def test_fifteen_states() -> None:
    assert len(TurnState) == 15
