import asyncio
import logging
import re
import zlib
from collections.abc import Callable, Mapping
from dataclasses import dataclass
from enum import StrEnum
from pathlib import Path
from typing import Final, Protocol

import openai
from pydantic import ValidationError

from config import NARRATION_TIMEOUT_S, CallKind, MetaModel
from gm.prompts import GM_SYSTEM_PROMPT, KUBO_ID, gm_input_text
from gm.schemas import (
    ContentFilter,
    GmTurn,
    Mood,
    SchemaError,
    _StrictModel,
    gm_turn_json_schema,
    parse_gm_turn,
)
from meta_client import CallSpec, MetaClient, MetaError, response_usage
from rules.resolve import Event, EventType

logger = logging.getLogger("desktop.narrator")

LINES_PATH: Final = Path(__file__).resolve().parents[2] / "assets" / "lines.json"
GM_SPEC: Final = CallSpec(
    model=MetaModel.SPARK, kind=CallKind.SPARK, is_idempotent=True
)
SCHEMA_NAME: Final = "gm_turn"
REPAIR_PREFIX: Final = "Your last output failed validation: "
REPAIR_SUFFIX: Final = ". Return only valid JSON."
LAST_TURN: Final = 8
MAX_ATTEMPTS: Final = 2
DEFAULT_UNIT_NAME: Final = "kasama"
ID_PATTERN: Final = re.compile(r"(?<!\w)[ue]_\w+")
REQUIRED_MOMENTS: Final = (
    "night_start",
    "tabi_tabi",
    "spawn_aswang",
    "spawn_aswang_north",
    "spawn_aswang_east",
    "spawn_aswang_south",
    "spawn_aswang_west",
    "spawn_tikbalang",
    "spawn_kapre",
    "spawn_manananggal",
    "spawn_duwende",
    "hit",
    "dodge",
    "kubo_hit",
    "unit_down",
    "last_turn",
    "win",
    "lose",
    "quiet",
)


class NarrationPhase(StrEnum):
    NIGHT_START = "night_start"
    RESOLUTION_THEN_TELEGRAPH = "resolution_then_telegraph"
    SUNRISE = "sunrise"
    DEFEAT = "defeat"


class NarrationSource(StrEnum):
    SPARK = "spark"
    LINE_BANK = "line_bank"


@dataclass(frozen=True)
class NarrationUnit:
    id: str
    name: str
    unit_class: str
    hp: int
    hp_max: int
    owner: str | None = None


@dataclass(frozen=True)
class NarrationEnemy:
    id: str
    type: str
    hp: int


@dataclass(frozen=True)
class NarrationRequest:
    night: int
    turn: int
    phase: str
    difficulty: str
    kubo_hp: int
    kubo_hp_max: int
    units: tuple[NarrationUnit, ...] = ()
    enemies: tuple[NarrationEnemy, ...] = ()
    events: tuple[Event, ...] = ()

    @property
    def allowed_ids(self) -> tuple[str, ...]:
        ids = [KUBO_ID]
        ids.extend(unit.id for unit in self.units)
        ids.extend(enemy.id for enemy in self.enemies)
        for event in self.events:
            ids.extend(
                value
                for value in (event.src, event.dst)
                if value is not None and value.startswith("e_")
            )
        return tuple(dict.fromkeys(ids))


@dataclass(frozen=True)
class Callout:
    entity_id: str
    text_tl: str


@dataclass(frozen=True)
class Narration:
    narration_tl: str
    narration_en: str
    mood: Mood
    callouts: tuple[Callout, ...]
    hint_tl: str
    source: NarrationSource


class Narrator(Protocol):
    async def narrate(self, request: NarrationRequest) -> Narration: ...

    def new_night(self) -> None: ...


class LineBankError(ValueError):
    pass


class _Line(_StrictModel):
    tl: str
    en: str
    mood: Mood


class _LineBankFile(_StrictModel):
    version: int
    moments: Mapping[str, tuple[_Line, ...]]


def _spawn_type(request: NarrationRequest, event: Event) -> str | None:
    for enemy in request.enemies:
        if enemy.id == event.src:
            return enemy.type
    parts = (event.src or "").split("_")
    return parts[1] if len(parts) >= 3 else None


def _first(events: tuple[Event, ...], kind: EventType) -> Event | None:
    return next((event for event in events if event.type is kind), None)


def _spawn_moment(request: NarrationRequest, event: Event) -> str | None:
    enemy_type = _spawn_type(request, event)
    if enemy_type is None:
        return None
    if enemy_type == "aswang" and event.edge is not None:
        return f"spawn_aswang_{event.edge.value}"
    return f"spawn_{enemy_type}"


def _is_player_hit(event: Event) -> bool:
    return (
        event.type is EventType.ATTACK
        and (event.dmg or 0) > 0
        and (event.src or "").startswith("u_")
    )


def pick_moment(request: NarrationRequest, available: Mapping[str, object]) -> str:
    kinds = {event.type for event in request.events}
    if request.phase == NarrationPhase.DEFEAT or EventType.LOSE in kinds:
        return "lose"
    if request.phase == NarrationPhase.SUNRISE or EventType.WIN in kinds:
        return "win"
    if request.phase == NarrationPhase.NIGHT_START:
        return "night_start"
    if EventType.KUBO_HIT in kinds:
        return "kubo_hit"
    if EventType.DOWN in kinds:
        return "unit_down"
    spawn = _first(request.events, EventType.SPAWN)
    if spawn is not None:
        moment = _spawn_moment(request, spawn)
        if moment is not None and moment in available:
            return moment
    if any(_is_player_hit(event) for event in request.events):
        return "hit"
    if EventType.DODGE in kinds:
        return "dodge"
    if request.turn == LAST_TURN:
        return "last_turn"
    return "quiet"


class LineBank:
    def __init__(self, path: Path | None = None) -> None:
        source = path if path is not None else LINES_PATH
        try:
            data = _LineBankFile.model_validate_json(source.read_text(encoding="utf-8"))
        except (OSError, ValidationError) as error:
            raise LineBankError(f"line bank unreadable: {error}") from error
        missing = [name for name in REQUIRED_MOMENTS if not data.moments.get(name)]
        if missing:
            raise LineBankError(f"line bank is missing moments: {', '.join(missing)}")
        self._moments = dict(data.moments)

    @property
    def moments(self) -> tuple[str, ...]:
        return tuple(self._moments)

    def lines(self, moment: str) -> tuple[tuple[str, str, Mood], ...]:
        return tuple((line.tl, line.en, line.mood) for line in self._moments[moment])

    def pick(self, request: NarrationRequest) -> Narration:
        moment = pick_moment(request, self._moments)
        options = self._moments[moment]
        key = f"{request.night}:{request.turn}:{moment}".encode()
        line = options[zlib.crc32(key) % len(options)]
        unit_name = self._down_unit_name(request)
        return Narration(
            narration_tl=self._fill(line.tl, request, unit_name),
            narration_en=self._fill(line.en, request, unit_name),
            mood=line.mood,
            callouts=(),
            hint_tl="",
            source=NarrationSource.LINE_BANK,
        )

    @staticmethod
    def _down_unit_name(request: NarrationRequest) -> str:
        down = _first(request.events, EventType.DOWN)
        if down is None:
            return DEFAULT_UNIT_NAME
        for unit in request.units:
            if unit.id == down.dst:
                return unit.name
        return DEFAULT_UNIT_NAME

    @staticmethod
    def _fill(text: str, request: NarrationRequest, unit_name: str) -> str:
        return text.replace("[HP]", str(request.kubo_hp)).replace("[unit]", unit_name)


class LineBankNarrator:
    def __init__(self, line_bank: LineBank) -> None:
        self._line_bank = line_bank

    async def narrate(self, request: NarrationRequest) -> Narration:
        return self._line_bank.pick(request)

    def new_night(self) -> None:
        return None


def names_unknown_id(text: str, allowed: tuple[str, ...]) -> bool:
    return any(match not in allowed for match in ID_PATTERN.findall(text))


class SparkNarrator:
    def __init__(
        self,
        client: MetaClient,
        content: ContentFilter,
        line_bank: LineBank,
        log_invalid: Callable[[str], None],
    ) -> None:
        self._client = client
        self._content = content
        self._line_bank = line_bank
        self._log_invalid = log_invalid
        self._previous_id: str | None = None

    def new_night(self) -> None:
        self._previous_id = None

    async def narrate(self, request: NarrationRequest) -> Narration:
        allowed = request.allowed_ids
        schema = gm_turn_json_schema(allowed)
        prompt = gm_input_text(request)
        repair = ""
        for _ in range(MAX_ATTEMPTS):
            try:
                raw, response_id = await self._ask(prompt + repair, schema)
            except MetaError:
                logger.warning("spark narration unavailable, using the line bank")
                break
            try:
                turn = parse_gm_turn(raw, allowed)
            except SchemaError as error:
                self._log_invalid(f"gm_invalid:{type(error).__name__}")
                repair = f"\n\n{REPAIR_PREFIX}{str(error)[:300]}{REPAIR_SUFFIX}"
                continue
            narration = self._to_narration(turn, allowed)
            if narration is None:
                self._log_invalid("gm_invalid:UnsafeNarration")
                break
            self._previous_id = response_id
            return narration
        return self._line_bank.pick(request)

    def _to_narration(self, turn: GmTurn, allowed: tuple[str, ...]) -> Narration | None:
        texts = [turn.narration_tl, turn.narration_en, turn.hint_tl]
        texts.extend(callout.text_tl for callout in turn.callouts)
        if any(names_unknown_id(text, allowed) for text in texts):
            return None
        if not all(
            self._content.is_safe_narration(text)
            for text in (turn.narration_tl, turn.narration_en, turn.hint_tl)
        ):
            return None
        callouts = tuple(
            Callout(callout.entity_id, callout.text_tl)
            for callout in turn.callouts
            if self._content.is_safe_narration(callout.text_tl)
        )
        return Narration(
            narration_tl=turn.narration_tl,
            narration_en=turn.narration_en,
            mood=turn.mood,
            callouts=callouts,
            hint_tl=turn.hint_tl,
            source=NarrationSource.SPARK,
        )

    async def _ask(self, prompt: str, schema: dict[str, object]) -> tuple[str, str]:
        previous = self._previous_id

        async def operation() -> openai.types.responses.Response:
            return await self._client.sdk().responses.create(
                model=MetaModel.SPARK.value,
                instructions=GM_SYSTEM_PROMPT,
                input=prompt,
                reasoning={"effort": "low"},
                store=True,
                previous_response_id=previous,
                extra_body={
                    "text": {
                        "format": {
                            "type": "json_schema",
                            "name": SCHEMA_NAME,
                            "schema": schema,
                            "strict": True,
                        }
                    }
                },
            )

        response = await self._client.execute(GM_SPEC, operation, response_usage)
        return response.output_text, response.id


Publish = Callable[[NarrationRequest, Narration], None]


class NarrationService:
    def __init__(
        self,
        line_bank: LineBank,
        live_factory: Callable[[], Narrator] | None = None,
        timeout_s: float = NARRATION_TIMEOUT_S,
    ) -> None:
        self._line_bank = line_bank
        self._live_factory = live_factory
        self._timeout_s = timeout_s
        self._live: Narrator | None = None
        self._sequence = 0
        self._tasks: set[asyncio.Task[None]] = set()

    def new_night(self) -> None:
        self.cancel()
        if self._live is not None:
            self._live.new_night()

    def submit(self, request: NarrationRequest, is_offline: bool, publish: Publish) -> None:
        self._sequence += 1
        sequence = self._sequence
        if is_offline or self._live_factory is None:
            publish(request, self._line_bank.pick(request))
            return
        try:
            loop = asyncio.get_running_loop()
        except RuntimeError:
            publish(request, self._line_bank.pick(request))
            return
        task = loop.create_task(self._run(self._live_narrator(), request, sequence, publish))
        self._tasks.add(task)
        task.add_done_callback(self._tasks.discard)

    def _live_narrator(self) -> Narrator:
        if self._live is None and self._live_factory is not None:
            self._live = self._live_factory()
        if self._live is None:
            return LineBankNarrator(self._line_bank)
        return self._live

    async def _run(
        self, narrator: Narrator, request: NarrationRequest, sequence: int, publish: Publish
    ) -> None:
        try:
            narration = await asyncio.wait_for(narrator.narrate(request), self._timeout_s)
        except TimeoutError:
            logger.warning("narration timed out, using the line bank")
            narration = self._line_bank.pick(request)
        except (MetaError, ValueError):
            logger.exception("narration failed, using the line bank")
            narration = self._line_bank.pick(request)
        if sequence == self._sequence:
            publish(request, narration)

    async def wait(self) -> None:
        if self._tasks:
            await asyncio.gather(*self._tasks, return_exceptions=True)

    def cancel(self) -> None:
        self._sequence += 1
        for task in list(self._tasks):
            task.cancel()
