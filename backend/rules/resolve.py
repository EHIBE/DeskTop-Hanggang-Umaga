import math
from collections.abc import Mapping, Sequence
from dataclasses import dataclass, field, replace
from enum import StrEnum
from typing import Final

from rules.enemies import (
    EnemyType,
    Part,
    at_edge,
    enemy_stats,
    flee_point,
    move_toward,
    pick_target,
)
from rules.geometry import (
    ENEMY_RADIUS_CM,
    KUBO_MOVED_WARN_CM,
    Edge,
    Hull,
    Point,
    clamp_point,
    displacement,
    hull_centroid,
    hull_hull_distance,
    hull_point_distance,
    in_range,
    is_move_legal,
    translate_hull,
)
from rules.units import (
    MOVE_CM,
    RANGE_CM,
    Difficulty,
    MoveClass,
    PowerId,
    RangeClass,
    UnitClass,
)
from rules.waves import spawns_for

__all__ = [
    "POWER_COOLDOWN",
    "TURNS_PER_NIGHT",
    "Action",
    "BoardState",
    "Edge",
    "EnemyState",
    "EnemyType",
    "Event",
    "EventType",
    "Intent",
    "Outcome",
    "Part",
    "UnitState",
    "apply_enemy_tags",
    "apply_unit_tags",
    "bayani",
    "begin_turn",
    "check_outcome",
    "enemy_status_tags",
    "illegal_moves",
    "intent_error",
    "moved_kubo",
    "resolve_turn",
    "score",
    "start_night",
    "unit_status_tags",
    "with_positions",
]

TURNS_PER_NIGHT: Final = 8
HEAL_AMOUNT: Final = 2
ALLY_POWER_RADIUS_CM: Final = 10.0
PUSH_CM: Final = 8.0
THROWN_TURNS: Final = 1
OUT_PREFIX: Final = "out_"
STOLEN_PREFIX: Final = "stolen_by:"
CARRYING_PREFIX: Final = "carrying:"
LOST_TAG: Final = "lost"
HAMPAS_RADIUS_CM: Final = 6.0
HAMPAS_DAMAGE: Final = 1
TUSOK_BEHIND_CM: Final = 5.0
KALASAG_SHIELD: Final = 2
BANTAY_SHIELD: Final = 3
SIGAW_BONUS: Final = 1
HABOL_BONUS: Final = 2
ASIN_DAMAGE: Final = 3
REFORM_TURNS: Final = 2
REFORM_OFFSET_CM: Final = 5.0
UNIT_SCORE: Final = 10
KUBO_HP_SCORE: Final = 5
DEFEAT_SCORE: Final = 3
MIN_DAMAGE: Final = 1

POWER_COOLDOWN: Final[Mapping[PowerId, int]] = {
    PowerId.NONE: 0,
    PowerId.P01: 0,
    PowerId.P02: 1,
    PowerId.P03: 1,
    PowerId.P04: 2,
    PowerId.P05: 1,
    PowerId.P06: 2,
    PowerId.P07: 0,
    PowerId.P08: 1,
    PowerId.P09: 1,
    PowerId.P10: 2,
    PowerId.P11: 0,
    PowerId.P12: 2,
}

_ALLY_TARGET_POWERS: Final = frozenset({PowerId.P01, PowerId.P02})
_ENEMY_TARGET_POWERS: Final = frozenset(
    {PowerId.P03, PowerId.P04, PowerId.P09, PowerId.P11}
)
_AREA_POWERS: Final = frozenset({PowerId.P05, PowerId.P08, PowerId.P10})


class Action(StrEnum):
    ATTACK = "attack"
    POWER = "power"
    HEAL = "heal"


class EventType(StrEnum):
    ATTACK = "attack"
    DODGE = "dodge"
    SPAWN = "spawn"
    INTENT = "intent"
    HEAL = "heal"
    POWER = "power"
    SHIELD = "shield"
    DOWN = "down"
    PUSH = "push"
    THROWN = "thrown"
    STEAL = "steal"
    RETURN = "return"
    ESCAPE = "escape"
    SPLIT = "split"
    REFORM = "reform"
    KUBO_HIT = "kubo_hit"
    DEFEAT_ENEMY = "defeat_enemy"
    WIN = "win"
    LOSE = "lose"


class Outcome(StrEnum):
    CONTINUE = "continue"
    WIN = "win"
    LOSE = "lose"


@dataclass(frozen=True)
class UnitState:
    id: str
    unit_class: UnitClass
    hp: int
    hp_max: int
    atk: int
    move: MoveClass
    range: RangeClass
    power_id: PowerId
    cooldown: int
    position: Point
    start: Point
    hull_offsets: Hull
    owner: str | None = None
    shield: int = 0
    atk_bonus: int = 0
    out_turns: int = 0
    stolen_by: str | None = None
    is_lost: bool = False

    @property
    def is_down(self) -> bool:
        return self.hp <= 0

    @property
    def is_absent(self) -> bool:
        return self.stolen_by is not None or self.is_lost

    @property
    def is_out(self) -> bool:
        return self.out_turns > 0 or self.is_absent

    @property
    def can_act(self) -> bool:
        return not self.is_down and not self.is_out

    @property
    def is_targetable(self) -> bool:
        return not self.is_down and not self.is_out

    @property
    def is_kubo(self) -> bool:
        return self.unit_class is UnitClass.KUBO

    @property
    def hull(self) -> Hull:
        return translate_hull(self.hull_offsets, self.position[0], self.position[1])


@dataclass(frozen=True)
class EnemyState:
    id: str
    type: EnemyType
    part: Part | None
    hp: int
    hp_max: int
    atk: int
    move_cm: float
    range_cm: float
    flies: bool
    position: Point
    spawn_turn: int
    target_id: str | None = None
    intent_dmg: int | None = None
    is_stunned: bool = False
    reform_in: int | None = None
    carrying: str | None = None

    @property
    def is_alive(self) -> bool:
        return self.hp > 0


@dataclass(frozen=True)
class Intent:
    unit_id: str
    action: Action
    target_id: str | None


@dataclass(frozen=True)
class Event:
    type: EventType
    src: str | None = None
    dst: str | None = None
    dmg: int | None = None
    edge: Edge | None = None
    pos: Point | None = None


@dataclass(frozen=True)
class BoardState:
    turn: int
    difficulty: Difficulty
    players: int
    play_w_cm: float
    play_h_cm: float
    units: tuple[UnitState, ...]
    enemies: tuple[EnemyState, ...]
    flags: frozenset[str] = field(default_factory=frozenset)
    enemies_defeated: int = 0
    enemy_counter: tuple[tuple[str, int], ...] = ()
    damage_by_owner: tuple[tuple[str, int], ...] = ()

    @property
    def kubo(self) -> UnitState | None:
        for unit in self.units:
            if unit.is_kubo:
                return unit
        return None


def start_night(
    units: Sequence[UnitState],
    difficulty: Difficulty,
    players: int,
    play_w_cm: float,
    play_h_cm: float,
    flags: frozenset[str] = frozenset(),
) -> BoardState:
    return BoardState(
        turn=0,
        difficulty=difficulty,
        players=players,
        play_w_cm=play_w_cm,
        play_h_cm=play_h_cm,
        units=tuple(replace(u, start=u.position) for u in units),
        enemies=(),
        flags=flags,
    )


def _unit_map(state: BoardState) -> dict[str, UnitState]:
    return {u.id: u for u in state.units}


def with_positions(
    state: BoardState,
    positions: Mapping[str, Point],
    hull_offsets: Mapping[str, Hull] | None = None,
) -> BoardState:
    offsets = hull_offsets or {}
    units = tuple(
        u
        if u.is_out
        else replace(
            u,
            position=positions.get(u.id, u.position),
            hull_offsets=offsets.get(u.id, u.hull_offsets),
        )
        for u in state.units
    )
    return replace(state, units=units)


def illegal_moves(state: BoardState) -> tuple[str, ...]:
    return tuple(
        u.id
        for u in state.units
        if not u.is_kubo
        and u.can_act
        and not is_move_legal(u.start, u.position, MOVE_CM[u.move])
    )


def moved_kubo(state: BoardState) -> bool:
    kubo = state.kubo
    return kubo is not None and displacement(kubo.start, kubo.position) > (
        KUBO_MOVED_WARN_CM
    )


def _power_target_error(
    state: BoardState,
    unit: UnitState,
    power: PowerId,
    target_id: str | None,
) -> str | None:
    units = _unit_map(state)
    enemies = {e.id: e for e in state.enemies if e.is_alive}
    if power in _ALLY_TARGET_POWERS:
        target = units.get(target_id) if target_id else None
        ok = target is not None and target.is_targetable
    elif power in _ENEMY_TARGET_POWERS:
        ok = target_id in enemies
    elif power is PowerId.P06:
        kubo = state.kubo
        ok = target_id is None or (kubo is not None and target_id == kubo.id)
    elif power is PowerId.P12:
        enemy = enemies.get(target_id) if target_id else None
        ok = (
            enemy is not None
            and enemy.type is EnemyType.MANANANGGAL
            and enemy.part is Part.LOWER
        )
    elif power in _AREA_POWERS:
        ok = target_id is None or target_id in units or target_id in enemies
    else:
        ok = False
    return None if ok else "cmd.unknown"


def intent_error(state: BoardState, intent: Intent) -> str | None:
    unit = _unit_map(state).get(intent.unit_id)
    if unit is None or not unit.can_act:
        return "cmd.unknown"
    if intent.action is Action.ATTACK:
        if unit.atk <= 0 or unit.range is RangeClass.NONE:
            return "cmd.no_atk"
        alive = {e.id for e in state.enemies if e.is_alive}
        return None if intent.target_id in alive else "cmd.unknown"
    if intent.action is Action.HEAL and unit.power_id is not PowerId.P01:
        return "cmd.unknown"
    if unit.power_id in (PowerId.NONE, PowerId.P07) or unit.cooldown > 0:
        return "cmd.unknown"
    return _power_target_error(state, unit, unit.power_id, intent.target_id)


def _damage_to_unit(unit: UnitState, raw: int) -> tuple[UnitState, int]:
    absorbed = min(unit.shield, raw)
    lost = min(unit.hp, raw - absorbed)
    return replace(unit, shield=unit.shield - absorbed, hp=unit.hp - lost), lost


def _inside(point: Point, width: float, height: float) -> bool:
    x, y = round(point[0], 6), round(point[1], 6)
    return 0.0 <= x <= width and 0.0 <= y <= height


def _unit_damage(unit: UnitState) -> int:
    return max(MIN_DAMAGE, unit.atk + unit.atk_bonus)


class _Round:
    def __init__(self, state: BoardState) -> None:
        self.state = state
        self.units = _unit_map(state)
        self.enemies = {e.id: e for e in state.enemies}
        self.events: list[Event] = []
        self.damage = dict(state.damage_by_owner)
        self.defeated = state.enemies_defeated
        self.used: dict[str, int] = {}
        self.thrown: set[str] = set()

    def emit(self, event: Event) -> None:
        self.events.append(event)

    def edge_dist(self, unit: UnitState, enemy: EnemyState) -> float:
        return hull_point_distance(unit.hull, enemy.position)

    def hurt_enemy(self, unit: UnitState, enemy_id: str, raw: int) -> None:
        enemy = self.enemies[enemy_id]
        lost = min(raw, enemy.hp)
        self.enemies[enemy_id] = replace(enemy, hp=enemy.hp - lost)
        self.emit(Event(EventType.ATTACK, unit.id, enemy_id, lost))
        if unit.owner is not None:
            self.damage[unit.owner] = self.damage.get(unit.owner, 0) + lost
        if enemy.hp - lost <= 0:
            self.defeated += 1
            self.emit(Event(EventType.DEFEAT_ENEMY, unit.id, enemy_id))
            self.release(enemy)

    def release(self, enemy: EnemyState) -> None:
        captive = self.units.get(enemy.carrying) if enemy.carrying else None
        if captive is None or captive.stolen_by != enemy.id:
            return
        self.units[captive.id] = replace(
            captive, stolen_by=None, position=enemy.position
        )
        self.emit(Event(EventType.RETURN, enemy.id, captive.id, pos=enemy.position))

    def dodge(self, src: str, dst: str | None) -> None:
        self.emit(Event(EventType.DODGE, src, dst))

    def alive_enemy(self, enemy_id: str | None) -> EnemyState | None:
        enemy = self.enemies.get(enemy_id) if enemy_id else None
        return enemy if enemy is not None and enemy.is_alive else None

    def living_unit(self, unit_id: str | None) -> UnitState | None:
        unit = self.units.get(unit_id) if unit_id else None
        return unit if unit is not None and unit.is_targetable else None

    def ally_in_reach(self, unit: UnitState, target_id: str | None) -> UnitState | None:
        target = self.living_unit(target_id)
        if target is None:
            return None
        if not in_range(
            hull_hull_distance(unit.hull, target.hull), ALLY_POWER_RADIUS_CM
        ):
            return None
        return target

    def mark_used(self, unit: UnitState) -> None:
        self.used[unit.id] = POWER_COOLDOWN[unit.power_id]

    def power_reach(self, unit: UnitState) -> float:
        reach = RANGE_CM[unit.range]
        return reach if reach > 0 else RANGE_CM[RangeClass.MELEE]

    def enemy_in_reach(
        self, unit: UnitState, target_id: str | None, reach: float
    ) -> EnemyState | None:
        enemy = self.alive_enemy(target_id)
        if enemy is None or not in_range(self.edge_dist(unit, enemy), reach):
            return None
        return enemy

    def run_power(self, unit: UnitState, target_id: str | None) -> None:
        power = unit.power_id
        handlers = {
            PowerId.P02: self.p_shield_ally,
            PowerId.P03: self.p_push,
            PowerId.P04: self.p_stun,
            PowerId.P05: self.p_sweep,
            PowerId.P06: self.p_shield_kubo,
            PowerId.P08: self.p_light,
            PowerId.P09: self.p_pierce,
            PowerId.P10: self.p_shout,
            PowerId.P11: self.p_chase,
            PowerId.P12: self.p_salt,
        }
        handler = handlers.get(power)
        if handler is not None:
            handler(unit, target_id)

    def announce(self, unit: UnitState, target_id: str | None) -> None:
        self.mark_used(unit)
        self.emit(Event(EventType.POWER, unit.id, target_id))

    def p_shield_ally(self, unit: UnitState, target_id: str | None) -> None:
        target = self.ally_in_reach(unit, target_id)
        if target is None:
            self.dodge(unit.id, target_id)
            return
        self.announce(unit, target.id)
        self.units[target.id] = replace(target, shield=target.shield + KALASAG_SHIELD)
        self.emit(Event(EventType.SHIELD, unit.id, target.id, KALASAG_SHIELD))

    def p_shield_kubo(self, unit: UnitState, target_id: str | None) -> None:
        kubo = self.state.kubo
        if kubo is None or kubo.is_down:
            self.dodge(unit.id, target_id)
            return
        self.announce(unit, kubo.id)
        current = self.units[kubo.id]
        self.units[kubo.id] = replace(current, shield=current.shield + BANTAY_SHIELD)
        self.emit(Event(EventType.SHIELD, unit.id, kubo.id, BANTAY_SHIELD))

    def p_push(self, unit: UnitState, target_id: str | None) -> None:
        enemy = self.enemy_in_reach(unit, target_id, RANGE_CM[RangeClass.MELEE])
        if enemy is None:
            self.dodge(unit.id, target_id)
            return
        self.announce(unit, enemy.id)
        dx = enemy.position[0] - unit.position[0]
        dy = enemy.position[1] - unit.position[1]
        length = math.hypot(dx, dy)
        ux, uy = (dx / length, dy / length) if length > 0 else (0.0, -1.0)
        pushed = clamp_point(
            (enemy.position[0] + ux * PUSH_CM, enemy.position[1] + uy * PUSH_CM),
            self.state.play_w_cm,
            self.state.play_h_cm,
        )
        self.enemies[enemy.id] = replace(enemy, position=pushed)
        self.emit(Event(EventType.PUSH, unit.id, enemy.id, pos=pushed))

    def p_stun(self, unit: UnitState, target_id: str | None) -> None:
        enemy = self.enemy_in_reach(unit, target_id, self.power_reach(unit))
        if enemy is None:
            self.dodge(unit.id, target_id)
            return
        self.announce(unit, enemy.id)
        self.enemies[enemy.id] = replace(enemy, is_stunned=True)

    def p_sweep(self, unit: UnitState, target_id: str | None) -> None:
        self.announce(unit, target_id)
        for enemy_id in list(self.enemies):
            enemy = self.enemies[enemy_id]
            if enemy.is_alive and in_range(
                self.edge_dist(unit, enemy), HAMPAS_RADIUS_CM
            ):
                self.hurt_enemy(unit, enemy_id, HAMPAS_DAMAGE)

    def p_light(self, unit: UnitState, target_id: str | None) -> None:
        self.announce(unit, target_id)

    def p_shout(self, unit: UnitState, target_id: str | None) -> None:
        self.announce(unit, target_id)
        for other in list(self.units.values()):
            if other.id == unit.id or not other.is_targetable:
                continue
            if in_range(
                hull_hull_distance(unit.hull, other.hull), ALLY_POWER_RADIUS_CM
            ):
                self.units[other.id] = replace(
                    other, atk_bonus=other.atk_bonus + SIGAW_BONUS
                )

    def p_pierce(self, unit: UnitState, target_id: str | None) -> None:
        enemy = self.enemy_in_reach(unit, target_id, self.power_reach(unit))
        if enemy is None:
            self.dodge(unit.id, target_id)
            return
        self.announce(unit, enemy.id)
        behind = self.pierce_second(unit, enemy)
        raw = _unit_damage(unit)
        self.hurt_enemy(unit, enemy.id, raw)
        if behind is not None:
            self.hurt_enemy(unit, behind, raw)

    def pierce_second(self, unit: UnitState, first: EnemyState) -> str | None:
        first_gap = self.edge_dist(unit, first)
        candidates: list[tuple[float, int, str]] = []
        for index, other in enumerate(self.enemies.values()):
            if other.id == first.id or not other.is_alive:
                continue
            between = max(
                0.0, displacement(first.position, other.position) - 2 * ENEMY_RADIUS_CM
            )
            if in_range(between, TUSOK_BEHIND_CM) and (
                self.edge_dist(unit, other) > first_gap
            ):
                candidates.append((round(between, 6), index, other.id))
        return min(candidates)[2] if candidates else None

    def p_chase(self, unit: UnitState, target_id: str | None) -> None:
        enemy = self.enemy_in_reach(unit, target_id, RANGE_CM[RangeClass.MELEE])
        if enemy is None:
            self.dodge(unit.id, target_id)
            return
        self.announce(unit, enemy.id)
        bonus = HABOL_BONUS if enemy.type is EnemyType.DUWENDE else 0
        self.hurt_enemy(unit, enemy.id, _unit_damage(unit) + bonus)

    def p_salt(self, unit: UnitState, target_id: str | None) -> None:
        enemy = self.enemy_in_reach(unit, target_id, self.power_reach(unit))
        if enemy is None or enemy.part is not Part.LOWER:
            self.dodge(unit.id, target_id)
            return
        self.announce(unit, enemy.id)
        self.hurt_enemy(unit, enemy.id, ASIN_DAMAGE)

    def heal(self, unit: UnitState, target_id: str | None) -> None:
        target = self.ally_in_reach(unit, target_id)
        if target is None:
            self.dodge(unit.id, target_id)
            return
        restored = min(HEAL_AMOUNT, target.hp_max - target.hp)
        self.units[target.id] = replace(target, hp=target.hp + restored)
        self.mark_used(unit)
        self.emit(Event(EventType.HEAL, unit.id, target.id, restored))

    def attack(self, unit: UnitState, target_id: str | None) -> None:
        enemy = self.enemy_in_reach(unit, target_id, RANGE_CM[unit.range])
        if enemy is None:
            self.dodge(unit.id, target_id)
            return
        self.hurt_enemy(unit, enemy.id, _unit_damage(unit))

    def enemy_attack(self, enemy: EnemyState) -> None:
        target = self.living_unit(enemy.target_id)
        if (
            not enemy.is_alive
            or enemy.is_stunned
            or enemy.carrying is not None
            or target is None
        ):
            return
        gap = hull_point_distance(target.hull, enemy.position)
        if not in_range(gap, enemy.range_cm):
            self.dodge(enemy.id, target.id)
            return
        if enemy.type is EnemyType.DUWENDE:
            self.steal(enemy, target)
            return
        hurt, lost = _damage_to_unit(target, max(MIN_DAMAGE, enemy.atk))
        self.units[target.id] = hurt
        self.emit(Event(EventType.ATTACK, enemy.id, target.id, lost))
        if hurt.is_kubo and lost > 0:
            self.emit(Event(EventType.KUBO_HIT, enemy.id, target.id, lost))
        if hurt.is_down:
            self.emit(Event(EventType.DOWN, enemy.id, target.id))
        elif enemy.type is EnemyType.TIKBALANG and not hurt.is_kubo:
            self.knock_back(enemy, hurt)

    def steal(self, enemy: EnemyState, target: UnitState) -> None:
        if target.is_kubo:
            return
        self.units[target.id] = replace(target, stolen_by=enemy.id)
        self.enemies[enemy.id] = replace(
            enemy, carrying=target.id, target_id=None, intent_dmg=None
        )
        self.emit(Event(EventType.STEAL, enemy.id, target.id))

    def knock_back(self, enemy: EnemyState, target: UnitState) -> None:
        centre = hull_centroid(target.hull)
        dx = centre[0] - enemy.position[0]
        dy = centre[1] - enemy.position[1]
        length = math.hypot(dx, dy)
        ux, uy = (dx / length, dy / length) if length > 0 else (0.0, -1.0)
        spot = (target.position[0] + ux * PUSH_CM, target.position[1] + uy * PUSH_CM)
        if not _inside(spot, self.state.play_w_cm, self.state.play_h_cm):
            self.units[target.id] = replace(target, out_turns=THROWN_TURNS)
            self.thrown.add(target.id)
            self.emit(Event(EventType.THROWN, enemy.id, target.id))
            return
        self.units[target.id] = replace(target, position=spot)
        self.emit(Event(EventType.PUSH, enemy.id, target.id, pos=spot))


def _first_valid_intents(state: BoardState, intents: Sequence[Intent]) -> list[Intent]:
    seen: set[str] = set()
    accepted: list[Intent] = []
    for intent in intents:
        if intent.unit_id in seen or intent_error(state, intent) is not None:
            continue
        seen.add(intent.unit_id)
        accepted.append(intent)
    return accepted


def _is_heal(unit: UnitState, intent: Intent) -> bool:
    return intent.action is Action.HEAL or (
        intent.action is Action.POWER and unit.power_id is PowerId.P01
    )


def _player_phase(rnd: _Round, intents: list[Intent]) -> None:
    units = rnd.units
    for intent in intents:
        unit = units[intent.unit_id]
        if intent.action is Action.POWER and not _is_heal(unit, intent):
            rnd.run_power(unit, intent.target_id)
    for intent in intents:
        unit = units[intent.unit_id]
        if _is_heal(unit, intent):
            rnd.heal(unit, intent.target_id)
    for intent in intents:
        if intent.action is Action.ATTACK:
            rnd.attack(units[intent.unit_id], intent.target_id)


def _lower_alive(enemies: Mapping[str, EnemyState]) -> bool:
    return any(
        e.is_alive and e.type is EnemyType.MANANANGGAL and e.part is Part.LOWER
        for e in enemies.values()
    )


def _cleanup_enemies(enemies: dict[str, EnemyState]) -> tuple[EnemyState, ...]:
    lower = _lower_alive(enemies)
    kept: list[EnemyState] = []
    for enemy in enemies.values():
        is_upper = enemy.type is EnemyType.MANANANGGAL and enemy.part is Part.UPPER
        if is_upper and not lower:
            continue
        if enemy.is_alive:
            kept.append(replace(enemy, is_stunned=False))
        elif is_upper:
            kept.append(replace(enemy, reform_in=enemy.reform_in or REFORM_TURNS))
    return tuple(kept)


def _tick_units(rnd: _Round) -> tuple[UnitState, ...]:
    ticked: list[UnitState] = []
    for unit in rnd.units.values():
        if unit.id in rnd.used:
            cooldown = rnd.used[unit.id]
        else:
            cooldown = max(0, unit.cooldown - 1)
        out_turns = (
            unit.out_turns if unit.id in rnd.thrown else max(0, unit.out_turns - 1)
        )
        ticked.append(replace(unit, cooldown=cooldown, out_turns=out_turns))
    return tuple(ticked)


def resolve_turn(
    state: BoardState, intents: Sequence[Intent]
) -> tuple[BoardState, tuple[Event, ...]]:
    rnd = _Round(state)
    _player_phase(rnd, _first_valid_intents(state, intents))
    for enemy_id in list(rnd.enemies):
        rnd.enemy_attack(rnd.enemies[enemy_id])
    new_state = replace(
        state,
        units=_tick_units(rnd),
        enemies=_cleanup_enemies(rnd.enemies),
        enemies_defeated=rnd.defeated,
        damage_by_owner=tuple(rnd.damage.items()),
    )
    events = list(rnd.events)
    outcome = check_outcome(new_state)
    if outcome is Outcome.WIN:
        events.append(Event(EventType.WIN))
    elif outcome is Outcome.LOSE:
        events.append(Event(EventType.LOSE))
    return new_state, tuple(events)


def check_outcome(state: BoardState) -> Outcome:
    kubo = state.kubo
    others = [u for u in state.units if not u.is_kubo]
    kubo_down = kubo is not None and kubo.is_down
    all_down = bool(others) and all(u.is_down or u.is_lost for u in others)
    if kubo_down or all_down:
        return Outcome.LOSE
    if state.turn >= TURNS_PER_NIGHT:
        return Outcome.WIN
    return Outcome.CONTINUE


def score(state: BoardState) -> int:
    alive = sum(
        1 for u in state.units if not u.is_kubo and not u.is_down and not u.is_absent
    )
    kubo = state.kubo
    kubo_hp = max(0, kubo.hp) if kubo is not None else 0
    return (
        alive * UNIT_SCORE
        + kubo_hp * KUBO_HP_SCORE
        + state.enemies_defeated * DEFEAT_SCORE
    )


def bayani(state: BoardState) -> tuple[str, ...]:
    if not state.damage_by_owner:
        return ()
    best = max(total for _, total in state.damage_by_owner)
    if best <= 0:
        return ()
    return tuple(owner for owner, total in state.damage_by_owner if total == best)


def _next_id(counter: dict[str, int], enemy_type: EnemyType) -> str:
    number = counter.get(enemy_type.value, 0) + 1
    counter[enemy_type.value] = number
    return f"e_{enemy_type.value}_{number}"


def _reform(
    enemies: list[EnemyState], state: BoardState
) -> tuple[list[EnemyState], list[Event]]:
    events: list[Event] = []
    result: list[EnemyState] = []
    lower = next(
        (
            e
            for e in enemies
            if e.is_alive and e.type is EnemyType.MANANANGGAL and e.part is Part.LOWER
        ),
        None,
    )
    for enemy in enemies:
        if enemy.reform_in is None:
            result.append(enemy)
            continue
        remaining = enemy.reform_in - 1
        if lower is None:
            continue
        if remaining > 0:
            result.append(replace(enemy, reform_in=remaining))
            continue
        spot = clamp_point(
            (lower.position[0] + REFORM_OFFSET_CM, lower.position[1]),
            state.play_w_cm,
            state.play_h_cm,
        )
        result.append(replace(enemy, hp=enemy.hp_max, position=spot, reform_in=None))
        events.append(Event(EventType.REFORM, enemy.id, lower.id, pos=spot))
    return result, events


def _spawn_wave(
    state: BoardState,
    enemies: list[EnemyState],
    counter: dict[str, int],
) -> list[Event]:
    kubo = state.kubo
    kubo_at = kubo.position if kubo else (state.play_w_cm / 2, state.play_h_cm / 2)
    events: list[Event] = []
    lower_id: str | None = None
    for spawn in spawns_for(
        state.turn,
        state.difficulty,
        state.players,
        state.flags,
        kubo_at,
        state.play_w_cm,
        state.play_h_cm,
    ):
        hp, atk, move_cm, range_cm, flies = enemy_stats(
            spawn.type, spawn.part, state.difficulty
        )
        enemy = EnemyState(
            id=_next_id(counter, spawn.type),
            type=spawn.type,
            part=spawn.part,
            hp=hp,
            hp_max=hp,
            atk=atk,
            move_cm=move_cm,
            range_cm=range_cm,
            flies=flies,
            position=spawn.position,
            spawn_turn=state.turn,
        )
        enemies.append(enemy)
        events.append(
            Event(EventType.SPAWN, enemy.id, edge=spawn.edge, pos=spawn.position)
        )
        if spawn.part is Part.LOWER:
            lower_id = enemy.id
        elif spawn.part is Part.UPPER and lower_id is not None:
            events.append(
                Event(EventType.SPLIT, enemy.id, lower_id, pos=spawn.position)
            )
    return events


def begin_turn(state: BoardState) -> tuple[BoardState, tuple[Event, ...]]:
    units = tuple(
        replace(u, shield=0, atk_bonus=0, start=u.position) for u in state.units
    )
    current = replace(state, turn=state.turn + 1, units=units)
    enemies, events = _reform(list(state.enemies), current)
    counter = dict(state.enemy_counter)
    events.extend(_spawn_wave(current, enemies, counter))
    current = replace(current, enemies=tuple(enemies))
    by_id = _unit_map(current)
    moved: list[EnemyState] = []
    for enemy in current.enemies:
        if not enemy.is_alive:
            moved.append(enemy)
            continue
        if enemy.carrying is not None:
            if at_edge(enemy.position, current.play_w_cm, current.play_h_cm):
                captive = by_id.get(enemy.carrying)
                if captive is not None:
                    by_id[captive.id] = replace(captive, stolen_by=None, is_lost=True)
                    events.append(
                        Event(
                            EventType.ESCAPE,
                            enemy.id,
                            captive.id,
                            pos=enemy.position,
                        )
                    )
                continue
            fled = flee_point(enemy, current.play_w_cm, current.play_h_cm)
            moved.append(replace(enemy, position=fled, target_id=None, intent_dmg=None))
            continue
        target_id = pick_target(enemy, current)
        if target_id is None:
            moved.append(replace(enemy, target_id=None, intent_dmg=None))
            continue
        target = by_id[target_id]
        position = move_toward(enemy, target.hull, current)
        intent = 0 if enemy.type is EnemyType.DUWENDE else max(MIN_DAMAGE, enemy.atk)
        moved.append(
            replace(enemy, position=position, target_id=target_id, intent_dmg=intent)
        )
        events.append(
            Event(EventType.INTENT, enemy.id, target_id, intent, pos=position)
        )
    new_state = replace(
        current,
        units=tuple(by_id[u.id] for u in current.units),
        enemies=tuple(moved),
        enemy_counter=tuple(counter.items()),
    )
    return new_state, tuple(events)


def unit_status_tags(unit: UnitState) -> tuple[str, ...]:
    tags: list[str] = []
    if unit.out_turns > 0:
        tags.append(f"{OUT_PREFIX}{unit.out_turns}")
    if unit.stolen_by is not None:
        tags.append(f"{STOLEN_PREFIX}{unit.stolen_by}")
    if unit.is_lost:
        tags.append(LOST_TAG)
    return tuple(tags)


def apply_unit_tags(unit: UnitState, tags: Sequence[str]) -> UnitState:
    out_turns = 0
    stolen_by: str | None = None
    is_lost = False
    for tag in tags:
        if tag.startswith(OUT_PREFIX) and tag[len(OUT_PREFIX) :].isdigit():
            out_turns = int(tag[len(OUT_PREFIX) :])
        elif tag.startswith(STOLEN_PREFIX) and len(tag) > len(STOLEN_PREFIX):
            stolen_by = tag[len(STOLEN_PREFIX) :]
        elif tag == LOST_TAG:
            is_lost = True
    return replace(unit, out_turns=out_turns, stolen_by=stolen_by, is_lost=is_lost)


def enemy_status_tags(enemy: EnemyState) -> tuple[str, ...]:
    if enemy.carrying is None:
        return ()
    return (f"{CARRYING_PREFIX}{enemy.carrying}",)


def apply_enemy_tags(enemy: EnemyState, tags: Sequence[str]) -> EnemyState:
    carrying: str | None = None
    for tag in tags:
        if tag.startswith(CARRYING_PREFIX) and len(tag) > len(CARRYING_PREFIX):
            carrying = tag[len(CARRYING_PREFIX) :]
    return replace(enemy, carrying=carrying)
