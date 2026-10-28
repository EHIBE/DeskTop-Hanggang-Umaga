from collections.abc import Callable, Mapping
from dataclasses import dataclass
from enum import StrEnum
from typing import Final


class TurnState(StrEnum):
    CALIBRATE = "CALIBRATE"
    SUMMON = "SUMMON"
    VOICE_CLAIM = "VOICE_CLAIM"
    SPAWN_TELEGRAPH = "SPAWN_TELEGRAPH"
    PLAYER_PHASE = "PLAYER_PHASE"
    END_TURN_SNAPSHOT = "END_TURN_SNAPSHOT"
    VALIDATE = "VALIDATE"
    RESOLVE_PLAYER = "RESOLVE_PLAYER"
    RESOLVE_ENEMY = "RESOLVE_ENEMY"
    PHYSICAL_EFFECTS = "PHYSICAL_EFFECTS"
    CHECK_END = "CHECK_END"
    SUNRISE = "SUNRISE"
    DEFEAT = "DEFEAT"
    REPLAY = "REPLAY"
    PAUSED = "PAUSED"


class TurnEvent(StrEnum):
    CALIBRATED = "calibrated"
    BEGIN_NIGHT = "begin_night"
    CLAIMS_DONE = "claims_done"
    TELEGRAPHED = "telegraphed"
    END_TURN = "end_turn"
    SNAPSHOT_DONE = "snapshot_done"
    MOVES_ILLEGAL = "moves_illegal"
    MOVES_LEGAL = "moves_legal"
    PLAYER_RESOLVED = "player_resolved"
    ENEMY_RESOLVED = "enemy_resolved"
    EFFECTS_DONE = "effects_done"
    NEXT_TURN = "next_turn"
    SURVIVED = "survived"
    FELL = "fell"
    REPLAY_REQUESTED = "replay_requested"
    PAUSE = "pause"
    RESUME = "resume"


TRANSITIONS: Final[Mapping[tuple[TurnState, TurnEvent], TurnState]] = {
    (TurnState.CALIBRATE, TurnEvent.CALIBRATED): TurnState.SUMMON,
    (TurnState.SUMMON, TurnEvent.BEGIN_NIGHT): TurnState.VOICE_CLAIM,
    (TurnState.VOICE_CLAIM, TurnEvent.CLAIMS_DONE): TurnState.SPAWN_TELEGRAPH,
    (TurnState.SPAWN_TELEGRAPH, TurnEvent.TELEGRAPHED): TurnState.PLAYER_PHASE,
    (TurnState.PLAYER_PHASE, TurnEvent.END_TURN): TurnState.END_TURN_SNAPSHOT,
    (TurnState.END_TURN_SNAPSHOT, TurnEvent.SNAPSHOT_DONE): TurnState.VALIDATE,
    (TurnState.VALIDATE, TurnEvent.MOVES_ILLEGAL): TurnState.PLAYER_PHASE,
    (TurnState.VALIDATE, TurnEvent.MOVES_LEGAL): TurnState.RESOLVE_PLAYER,
    (TurnState.RESOLVE_PLAYER, TurnEvent.PLAYER_RESOLVED): TurnState.RESOLVE_ENEMY,
    (TurnState.RESOLVE_ENEMY, TurnEvent.ENEMY_RESOLVED): TurnState.PHYSICAL_EFFECTS,
    (TurnState.PHYSICAL_EFFECTS, TurnEvent.EFFECTS_DONE): TurnState.CHECK_END,
    (TurnState.CHECK_END, TurnEvent.NEXT_TURN): TurnState.SPAWN_TELEGRAPH,
    (TurnState.CHECK_END, TurnEvent.SURVIVED): TurnState.SUNRISE,
    (TurnState.CHECK_END, TurnEvent.FELL): TurnState.DEFEAT,
    (TurnState.SUNRISE, TurnEvent.REPLAY_REQUESTED): TurnState.REPLAY,
    (TurnState.PLAYER_PHASE, TurnEvent.PAUSE): TurnState.PAUSED,
    (TurnState.PAUSED, TurnEvent.RESUME): TurnState.PLAYER_PHASE,
}

NIGHT_STATES: Final = frozenset(
    {
        TurnState.VOICE_CLAIM,
        TurnState.SPAWN_TELEGRAPH,
        TurnState.PLAYER_PHASE,
        TurnState.END_TURN_SNAPSHOT,
        TurnState.VALIDATE,
        TurnState.RESOLVE_PLAYER,
        TurnState.RESOLVE_ENEMY,
        TurnState.PHYSICAL_EFFECTS,
        TurnState.CHECK_END,
        TurnState.PAUSED,
    }
)


class IllegalTransitionError(Exception):
    def __init__(self, state: TurnState, event: TurnEvent) -> None:
        super().__init__(f"{event.value} is not valid in {state.value}")
        self.state = state
        self.event = event


@dataclass(frozen=True)
class Transition:
    source: TurnState
    event: TurnEvent
    target: TurnState


TransitionListener = Callable[[Transition], None]


class TurnStateMachine:
    def __init__(
        self,
        initial: TurnState = TurnState.CALIBRATE,
        on_transition: TransitionListener | None = None,
    ) -> None:
        self._state = initial
        self._on_transition = on_transition

    @property
    def state(self) -> TurnState:
        return self._state

    def can(self, event: TurnEvent) -> bool:
        return (self._state, event) in TRANSITIONS

    def transition(self, event: TurnEvent) -> TurnState:
        target = TRANSITIONS.get((self._state, event))
        if target is None:
            raise IllegalTransitionError(self._state, event)
        change = Transition(source=self._state, event=event, target=target)
        self._state = target
        if self._on_transition is not None:
            self._on_transition(change)
        return target

    def force(self, state: TurnState) -> None:
        self._state = state
