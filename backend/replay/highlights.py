import json
from collections.abc import Mapping, Sequence
from dataclasses import dataclass
from pathlib import Path
from typing import Final

from pydantic import BaseModel, ConfigDict, Field, ValidationError

HIGHLIGHT_WINDOW_S: Final = 8.0
HIGHLIGHT_LEAD_S: Final = 3.0
MAX_HIGHLIGHTS: Final = 6
SIDECAR_VERSION: Final = 1
MS_PER_S: Final = 1000.0

KIND_LAST_TURN: Final = "last_turn"
KIND_KUBO_HIT: Final = "kubo_hit"
KIND_DEFEAT: Final = "defeat"
KIND_SPLIT: Final = "split"
KIND_STEAL: Final = "steal"
KIND_PUSH: Final = "push"

EVENT_KINDS: Final[Mapping[str, str]] = {
    "kubo_hit": KIND_KUBO_HIT,
    "defeat_enemy": KIND_DEFEAT,
    "split": KIND_SPLIT,
    "steal": KIND_STEAL,
    "push": KIND_PUSH,
}
KIND_PRIORITY: Final[Mapping[str, int]] = {
    KIND_LAST_TURN: 0,
    KIND_KUBO_HIT: 1,
    KIND_DEFEAT: 2,
    KIND_SPLIT: 3,
    KIND_STEAL: 4,
    KIND_PUSH: 5,
}
ENDING_EVENTS: Final = frozenset({"win", "lose"})


class ReplayError(Exception):
    pass


@dataclass(frozen=True)
class ReelEvent:
    t_s: float
    type: str
    src: str | None
    dst: str | None
    dmg: int | None


@dataclass(frozen=True)
class Highlight:
    kind: str
    turn: int
    start_s: float
    duration_s: float
    events: tuple[ReelEvent, ...]


@dataclass(frozen=True)
class AnchorSnapshot:
    t_s: float
    boxes: Mapping[str, tuple[int, int, int, int]]


@dataclass(frozen=True)
class RecordingMeta:
    video_path: Path
    width: int
    height: int
    fps: int
    started_t_ms: int
    duration_s: float
    anchors: tuple[AnchorSnapshot, ...]
    sprites: Mapping[str, str]


@dataclass(frozen=True)
class TurnLogRow:
    turn: int
    phase: str
    event_type: str
    payload: Mapping[str, object]
    t_ms: int


class _AnchorModel(BaseModel):
    model_config = ConfigDict(extra="forbid")

    t_ms: int
    boxes: dict[str, tuple[int, int, int, int]]


class _SidecarModel(BaseModel):
    model_config = ConfigDict(extra="forbid")

    version: int
    video: str = Field(min_length=1)
    width: int = Field(gt=0)
    height: int = Field(gt=0)
    fps: int = Field(gt=0)
    started_t_ms: int = Field(ge=0)
    duration_s: float = Field(gt=0)
    anchors: list[_AnchorModel]
    sprites: dict[str, str]


def load_recording_meta(sidecar_path: Path) -> RecordingMeta:
    try:
        raw = json.loads(sidecar_path.read_text(encoding="utf-8"))
    except (OSError, ValueError) as error:
        raise ReplayError("recording sidecar could not be read") from error
    try:
        model = _SidecarModel.model_validate(raw)
    except ValidationError as error:
        raise ReplayError(f"recording sidecar is invalid: {error}") from error
    if model.version != SIDECAR_VERSION:
        raise ReplayError("recording sidecar version is not supported")
    video = Path(model.video)
    if video.name != model.video or video.suffix.lower() != ".mp4":
        raise ReplayError("recording sidecar video must be a plain mp4 file name")
    for anchor in model.anchors:
        for game_id, (left, top, right, bottom) in anchor.boxes.items():
            if left < 0 or top < 0 or right <= left or bottom <= top:
                raise ReplayError(f"anchor box for {game_id} has no area")
            if right > model.width or bottom > model.height:
                raise ReplayError(f"anchor box for {game_id} is outside the frame")
    anchors = tuple(
        sorted(
            (
                AnchorSnapshot(
                    t_s=(anchor.t_ms - model.started_t_ms) / MS_PER_S,
                    boxes=dict(anchor.boxes),
                )
                for anchor in model.anchors
            ),
            key=lambda snapshot: snapshot.t_s,
        )
    )
    return RecordingMeta(
        video_path=sidecar_path.parent / model.video,
        width=model.width,
        height=model.height,
        fps=model.fps,
        started_t_ms=model.started_t_ms,
        duration_s=model.duration_s,
        anchors=anchors,
        sprites=dict(model.sprites),
    )


@dataclass(frozen=True)
class _Timed:
    t_s: float
    row: TurnLogRow


@dataclass(frozen=True)
class _Candidate:
    kind: str
    turn: int
    anchor_s: float
    dmg: int


def _text_or_none(value: object) -> str | None:
    return value if isinstance(value, str) else None


def _int_or_none(value: object) -> int | None:
    if isinstance(value, bool) or not isinstance(value, int):
        return None
    return value


def _reel_event(item: _Timed) -> ReelEvent:
    payload = item.row.payload
    return ReelEvent(
        t_s=item.t_s,
        type=item.row.event_type,
        src=_text_or_none(payload.get("src")),
        dst=_text_or_none(payload.get("dst")),
        dmg=_int_or_none(payload.get("dmg")),
    )


def _timed_rows(rows: Sequence[TurnLogRow], meta: RecordingMeta) -> tuple[_Timed, ...]:
    ordered = sorted(enumerate(rows), key=lambda pair: (pair[1].t_ms, pair[0]))
    timed: list[_Timed] = []
    for _, row in ordered:
        t_s = (row.t_ms - meta.started_t_ms) / MS_PER_S
        if t_s < 0 or t_s > meta.duration_s:
            continue
        timed.append(_Timed(t_s=t_s, row=row))
    return tuple(timed)


def _last_turn_candidate(timed: Sequence[_Timed]) -> _Candidate | None:
    if not timed:
        return None
    last_turn = max(item.row.turn for item in timed)
    in_turn = [item for item in timed if item.row.turn == last_turn]
    endings = [item for item in in_turn if item.row.event_type in ENDING_EVENTS]
    anchor = endings[-1] if endings else in_turn[-1]
    return _Candidate(KIND_LAST_TURN, last_turn, anchor.t_s, 0)


def _event_candidates(timed: Sequence[_Timed]) -> list[_Candidate]:
    candidates: list[_Candidate] = []
    for item in timed:
        kind = EVENT_KINDS.get(item.row.event_type)
        if kind is None:
            continue
        dmg = _int_or_none(item.row.payload.get("dmg")) or 0
        candidates.append(_Candidate(kind, item.row.turn, item.t_s, dmg))
    return candidates


def _rank(candidate: _Candidate) -> tuple[int, int, float]:
    return (
        KIND_PRIORITY[candidate.kind],
        -candidate.dmg if candidate.kind == KIND_KUBO_HIT else 0,
        candidate.anchor_s,
    )


def _window(anchor_s: float, window_s: float, duration_s: float) -> tuple[float, float]:
    start = max(0.0, anchor_s - HIGHLIGHT_LEAD_S)
    if start + window_s > duration_s:
        start = max(0.0, duration_s - window_s)
    return start, min(window_s, duration_s - start)


def _overlaps(start: float, end: float, taken: Sequence[tuple[float, float]]) -> bool:
    return any(
        start < other_end and end > other_start for other_start, other_end in taken
    )


def pick_highlights(
    rows: Sequence[TurnLogRow],
    meta: RecordingMeta,
    max_count: int = MAX_HIGHLIGHTS,
    window_s: float = HIGHLIGHT_WINDOW_S,
) -> tuple[Highlight, ...]:
    if max_count <= 0 or window_s <= 0 or meta.duration_s <= 0:
        return ()
    timed = _timed_rows(rows, meta)
    candidates: list[_Candidate] = []
    last = _last_turn_candidate(timed)
    if last is not None:
        candidates.append(last)
    candidates.extend(_event_candidates(timed))
    candidates.sort(key=_rank)
    chosen: list[tuple[_Candidate, float, float]] = []
    taken: list[tuple[float, float]] = []
    for candidate in candidates:
        if len(chosen) >= max_count:
            break
        start, length = _window(candidate.anchor_s, window_s, meta.duration_s)
        if length <= 0 or _overlaps(start, start + length, taken):
            continue
        chosen.append((candidate, start, length))
        taken.append((start, start + length))
    chosen.sort(key=lambda entry: (entry[1], KIND_PRIORITY[entry[0].kind]))
    return tuple(
        Highlight(
            kind=candidate.kind,
            turn=candidate.turn,
            start_s=start,
            duration_s=length,
            events=tuple(
                _reel_event(item)
                for item in timed
                if start <= item.t_s <= start + length
            ),
        )
        for candidate, start, length in chosen
    )
