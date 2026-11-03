import asyncio
import json
import logging
import re
from collections.abc import Callable, Mapping
from dataclasses import dataclass
from enum import StrEnum
from typing import Any, Final

import openai

from config import NARRATION_TIMEOUT_S, MetaModel
from gm.glimmer import GlimmerClient
from gm.narrator import GM_SPEC, ID_PATTERN, REPAIR_PREFIX, REPAIR_SUFFIX, LineBank
from gm.prompts import RECAP_SYSTEM_PROMPT, recap_input_text
from gm.schemas import (
    ContentFilter,
    Mood,
    RecapDraft,
    SchemaError,
    parse_recap,
    recap_json_schema,
)
from meta_client import MetaClient, MetaError, response_usage

logger = logging.getLogger("desktop.recap")

SCHEMA_NAME: Final = "night_recap"
RECAP_PREFIX: Final = "Kagabi"
MAX_ATTEMPTS: Final = 2
NUMBER_PATTERN: Final = re.compile(r"\d+")
ALIAS_PATTERN: Final = re.compile(r"\bP[1-4]\b")
ALIAS_EXACT: Final = re.compile(r"P[1-4]")
UNIT_NAME_MAX: Final = 40
BADGE_MAX: Final = 40


class RecapError(ValueError):
    pass


class RecapSource(StrEnum):
    SPARK = "spark"
    LINE_BANK = "line_bank"
    GLIMMER = "glimmer"


class RecapOutcome(StrEnum):
    SUNRISE = "sunrise"
    DEFEAT = "defeat"


@dataclass(frozen=True)
class RecapUnit:
    name: str
    unit_class: str
    owner: str | None = None
    badges: tuple[str, ...] = ()
    scarred: bool = False
    downed: bool = False


@dataclass(frozen=True)
class NightSummary:
    night: int
    outcome: RecapOutcome
    turns_survived: int
    enemies_beaten: int
    units_downed: int
    units: tuple[RecapUnit, ...] = ()
    players: tuple[str, ...] = ()

    def __post_init__(self) -> None:
        aliases = (*self.players, *(u.owner for u in self.units if u.owner))
        if any(not ALIAS_EXACT.fullmatch(alias) for alias in aliases):
            raise RecapError("players must be labeled P1 to P4")

    def prompt_payload(self) -> dict[str, Any]:
        return {
            "night": self.night,
            "outcome": self.outcome.value,
            "turns_survived": self.turns_survived,
            "enemies_beaten": self.enemies_beaten,
            "units_downed": self.units_downed,
            "players": list(self.players),
            "units": [
                {
                    "name": unit.name[:UNIT_NAME_MAX],
                    "class": unit.unit_class,
                    "owner": unit.owner,
                    "badges": [badge[:BADGE_MAX] for badge in unit.badges],
                    "scarred": unit.scarred,
                    "downed": unit.downed,
                }
                for unit in self.units
            ],
        }

    def allowed_numbers(self) -> frozenset[str]:
        found = NUMBER_PATTERN.findall(json.dumps(self.prompt_payload()))
        return frozenset(str(int(number)) for number in found)

    def allowed_aliases(self) -> frozenset[str]:
        owners = {unit.owner for unit in self.units if unit.owner}
        return frozenset({*self.players, *owners})


@dataclass(frozen=True)
class Recap:
    night: int
    text_tl: str
    text_en: str
    mood: Mood
    source: RecapSource

    def to_dict(self) -> dict[str, Any]:
        return {
            "night": self.night,
            "text_tl": self.text_tl,
            "text_en": self.text_en,
            "mood": self.mood.value,
            "source": self.source.value,
        }

    def to_json(self) -> str:
        return json.dumps(self.to_dict(), ensure_ascii=False)

    @classmethod
    def from_dict(cls, data: Mapping[str, Any]) -> "Recap":
        try:
            night = data["night"]
            text_tl = data["text_tl"]
            text_en = data["text_en"]
            mood = Mood(data["mood"])
            source = RecapSource(data["source"])
        except (KeyError, TypeError, ValueError) as error:
            raise RecapError(f"recap unreadable: {error}") from error
        if (
            not isinstance(night, int)
            or isinstance(night, bool)
            or not isinstance(text_tl, str)
            or not isinstance(text_en, str)
            or not text_tl
        ):
            raise RecapError("recap fields have the wrong types")
        return cls(night, text_tl, text_en, mood, source)

    @classmethod
    def from_json(cls, raw: str) -> "Recap":
        try:
            data = json.loads(raw)
        except json.JSONDecodeError as error:
            raise RecapError(f"recap unreadable: {error}") from error
        if not isinstance(data, dict):
            raise RecapError("recap must be a JSON object")
        return cls.from_dict(data)


def restore_recap_names(recap: Recap, players: Mapping[str, str]) -> Recap:
    def swap(text: str) -> str:
        return ALIAS_PATTERN.sub(lambda m: players.get(m.group(0), m.group(0)), text)

    return Recap(
        night=recap.night,
        text_tl=swap(recap.text_tl),
        text_en=swap(recap.text_en),
        mood=recap.mood,
        source=recap.source,
    )


def recap_text_ok(
    texts: tuple[str, str], summary: NightSummary, content: ContentFilter
) -> bool:
    if not texts[0].strip().startswith(RECAP_PREFIX):
        return False
    numbers = summary.allowed_numbers()
    aliases = summary.allowed_aliases()
    for text in texts:
        if ID_PATTERN.search(text) or not content.is_safe_narration(text):
            return False
        if any(str(int(n)) not in numbers for n in NUMBER_PATTERN.findall(text)):
            return False
        if any(a not in aliases for a in ALIAS_PATTERN.findall(text)):
            return False
    return True


def _first_highlight(summary: NightSummary) -> tuple[str, RecapUnit, str] | None:
    for unit in summary.units:
        if unit.badges:
            return "recap_badge", unit, unit.badges[0]
    for unit in summary.units:
        if unit.scarred:
            return "recap_scar", unit, ""
    return None


def build_line_bank_recap(summary: NightSummary, line_bank: LineBank) -> Recap:
    moment = "recap_win" if summary.outcome is RecapOutcome.SUNRISE else "recap_lose"
    values = {
        "turns": str(summary.turns_survived),
        "beaten": str(summary.enemies_beaten),
        "downed": str(summary.units_downed),
    }
    seed = f"recap:{summary.night}"
    tl, en, mood = line_bank.fill(moment, seed, values)
    highlight = _first_highlight(summary)
    if highlight is not None:
        extra_moment, unit, badge = highlight
        extra = {"unit": unit.name[:UNIT_NAME_MAX], "badge": badge[:BADGE_MAX]}
        extra_tl, extra_en, _ = line_bank.fill(extra_moment, seed, extra)
        tl = f"{tl} {extra_tl}"
        en = f"{en} {extra_en}"
    return Recap(summary.night, tl, en, mood, RecapSource.LINE_BANK)


class SparkRecapWriter:
    def __init__(
        self,
        client: MetaClient,
        content: ContentFilter,
        log_invalid: Callable[[str], None],
    ) -> None:
        self._client = client
        self._content = content
        self._log_invalid = log_invalid

    async def write(self, summary: NightSummary) -> RecapDraft | None:
        schema = recap_json_schema()
        prompt = recap_input_text(summary)
        repair = ""
        for _ in range(MAX_ATTEMPTS):
            try:
                raw = await self._ask(prompt + repair, schema)
            except MetaError:
                logger.warning("spark recap unavailable, using the line bank")
                return None
            try:
                draft = parse_recap(raw)
            except SchemaError as error:
                self._log_invalid(f"gm_invalid:{type(error).__name__}")
                repair = f"\n\n{REPAIR_PREFIX}{str(error)[:300]}{REPAIR_SUFFIX}"
                continue
            texts = (draft.recap_tl, draft.recap_en)
            if not recap_text_ok(texts, summary, self._content):
                self._log_invalid("gm_invalid:UnsafeRecap")
                return None
            return draft
        return None

    async def _ask(self, prompt: str, schema: dict[str, object]) -> str:
        async def operation() -> openai.types.responses.Response:
            return await self._client.sdk().responses.create(
                model=MetaModel.SPARK.value,
                instructions=RECAP_SYSTEM_PROMPT,
                input=prompt,
                reasoning={"effort": "low"},
                store=False,
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
        return response.output_text


class RecapBuilder:
    def __init__(
        self,
        line_bank: LineBank,
        content: ContentFilter,
        spark: SparkRecapWriter | None = None,
        glimmer: GlimmerClient | None = None,
        timeout_s: float = NARRATION_TIMEOUT_S,
    ) -> None:
        self._line_bank = line_bank
        self._content = content
        self._spark = spark
        self._glimmer = glimmer
        self._timeout_s = timeout_s

    def build_local(self, summary: NightSummary) -> Recap:
        return build_line_bank_recap(summary, self._line_bank)

    async def build(
        self, summary: NightSummary, is_offline: bool, use_glimmer: bool = True
    ) -> Recap:
        try:
            recap = await asyncio.wait_for(
                self._rewrite(summary, is_offline, use_glimmer), self._timeout_s
            )
        except TimeoutError:
            logger.warning("recap timed out, using the line bank")
            recap = None
        except (
            MetaError,
            openai.OpenAIError,
            ValueError,
            TypeError,
            KeyError,
            OSError,
        ):
            logger.warning("recap failed, using the line bank")
            recap = None
        return recap if recap is not None else self.build_local(summary)

    async def _rewrite(
        self, summary: NightSummary, is_offline: bool, use_glimmer: bool
    ) -> Recap | None:
        if use_glimmer and self._glimmer is not None:
            text = await self._glimmer.recap(summary)
            texts = (text.text_tl, text.text_en) if text is not None else None
            if texts is not None and recap_text_ok(texts, summary, self._content):
                return self._wrap(summary, *texts, RecapSource.GLIMMER)
        if is_offline or self._spark is None:
            return None
        draft = await self._spark.write(summary)
        if draft is None:
            return None
        return self._wrap(summary, draft.recap_tl, draft.recap_en, RecapSource.SPARK)

    @staticmethod
    def _wrap(summary: NightSummary, tl: str, en: str, source: RecapSource) -> Recap:
        mood = Mood.UMAGA if summary.outcome is RecapOutcome.SUNRISE else Mood.KABA
        return Recap(summary.night, tl, en, mood, source)
