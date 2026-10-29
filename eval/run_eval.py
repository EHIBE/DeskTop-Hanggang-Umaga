import argparse
import asyncio
import json
import math
import sqlite3
import subprocess
import sys
from collections import Counter
from collections.abc import Callable, Sequence
from dataclasses import dataclass, field
from datetime import UTC, datetime
from decimal import Decimal
from pathlib import Path
from typing import Final, Protocol

REPO_DIR: Final = Path(__file__).resolve().parent.parent
BACKEND_DIR: Final = REPO_DIR / "backend"
EVAL_DIR: Final = REPO_DIR / "eval"
sys.path.insert(0, str(BACKEND_DIR))

import cv2
import numpy as np

from config import COST_STOP_USD, PX_PER_CM, CallKind
from gm.schemas import ContentFilter
from meta_client import Usage, price_usage
from rules.units import Difficulty, UnitClass
from vision.sam import (
    PixelBox,
    ReanchorTarget,
    SegmentationError,
    Segmenter,
    box_iou,
    clamp_box,
)
from vision.summon import (
    Detector,
    Image,
    KnownObject,
    SummonError,
    SummonPipeline,
    SummonRequest,
)
from voice.grammar import (
    Command,
    CommandKind,
    GrammarContext,
    GrammarEnemy,
    GrammarUnit,
    parse_command,
)

JsonObject = dict[str, object]

IOU_ACCEPT: Final = 0.5
GRID_MAX: Final = 1000.0
SUMMON_PHASE: Final = "SUMMON"
GM_INVALID_PREFIX: Final = "gm_invalid:"
NARRATION_EVENT: Final = "narration"
NARRATION_REQUEST_EVENT: Final = "narration_request"
GM_INVALID_EVENT: Final = "gm_invalid"
SUMMON_EVENT: Final = "summon"
TRANSITION_EVENT: Final = "transition"
END_TURN_PHASE: Final = "END_TURN_SNAPSHOT"
END_TURN_CLOSERS: Final = frozenset({"PLAYER_PHASE", "SUNRISE", "DEFEAT"})
SPARK_SOURCE: Final = "spark"
LINE_BANK_SOURCE: Final = "line_bank"

ASSUMED_SPARK_INPUT_TOKENS: Final = 2500
ASSUMED_SPARK_OUTPUT_TOKENS: Final = 600
SPARK_ATTEMPTS_PER_SNAPSHOT: Final = 2
SAM_CALLS_PER_END_TURN: Final = 2

TARGETS: Final = {
    "e1": 0.90,
    "e2": 0.95,
    "e3": 0.85,
    "e4_first_try": 0.97,
    "e4_non_blocking": 1.0,
    "e7": 1.0,
}
FULL_SET: Final = {"e1": 60, "e2": 100, "e3": 50, "e4": 200, "e7": 50}
MIN_SET: Final = {"e1": 20, "e2": 50, "e3": 50, "e4": 200, "e7": 50}

NFR_TARGETS_MS: Final = {
    "NFR-01": 8000,
    "NFR-03": 4000,
    "NFR-05": 3000,
    "NFR-07": 1500,
    "NFR-08": 6000,
}
NFR_REQUIRED: Final = ("NFR-01", "NFR-03", "NFR-05", "NFR-08")

NOT_RUN_EXIT: Final = 2

USAGE_NOTE: Final = (
    "Run from the repo root: backend/.venv/Scripts/python eval/run_eval.py <eval> ... "
    "The runner adds backend to sys.path itself. For mypy run from backend: "
    "mypy --strict --exclude .venv . ../eval/run_eval.py"
)

E1_FORMAT: Final = """\
labels file (JSON), default eval/objects/labels.json. See eval/objects/labels.example.json.
  box_unit: "grid" (0 to 1000) or "pixels", px_per_cm, difficulty
  items[]: snapshot (path relative to the labels file), spoken_name, condition,
           known[] {sam_id, label, unit_class, box}, expected_box
Paid: one Spark call (up to 2 with repair) and one SAM call per snapshot.
The estimated cost is printed first and --yes is required to continue.
Metric: share of snapshots whose registered box has IoU >= 0.5 with expected_box.
"""

E2_FORMAT: Final = """\
data file (JSONL), default eval/objects/endturns.jsonl, one End Turn case per line:
  {"case_id": "...", "frame": "frames/x.png", "px_per_cm": 20,
   "targets": [{"sam_id": 1, "label": "mug", "tracker_box": [l, t, r, b],
                "expected_box": [l, t, r, b], "histogram": [optional floats]}]}
Boxes are warped-frame pixels. Export the cases from recorded nights.
Paid: up to 2 SAM calls per case plus concept fallbacks. --yes is required.
Metric: share of targets whose re-anchored box has IoU >= 0.5 with expected_box.
"""

E3_FORMAT: Final = """\
labels file (JSONL), default eval/voice/labels.jsonl. See eval/voice/labels.example.jsonl.
  transcript: the real recognizer final text captured during a recorded session
  recording: id of the recorded session the transcript came from (required)
  expected_unit_id, expected_action, expected_target_id, context {units, enemies}
Transcripts must come from real recordings. Hand-typed phrases do not count as E3.
Offline. Metric: share where unit, action and target are all correct.
"""

E4_FORMAT: Final = """\
Reads turn_log from --db (opened read only).
  live Spark attempts = narration rows with source spark
                        + narration rows with source line_bank in a night and turn that has a gm_invalid row
  failures            = gm_invalid rows with reason starting "gm_invalid:" and phase not SUMMON
  first-try validity  = 1 - failures / live Spark attempts
                        (a request that fails twice adds two rows, so failures is an upper bound)
  non-blocking        = narration_request rows that have a narration row with the same night, turn and phase,
                        divided by all narration_request rows. Needs narration_request rows in turn_log
"""

E6_FORMAT: Final = """\
Reads api_usage and turn_log from --db (opened read only). Percentiles use nearest rank.
  api_usage: p50 and p90 of latency_ms for ok rows, per kind and per model
  NFR-01: t_ms of turn_log summon rows
  NFR-03: t_ms from the END_TURN_SNAPSHOT transition to the next PLAYER_PHASE, SUNRISE or DEFEAT
          transition in the same night (a proxy that includes the whole resolution)
  NFR-08: turn_log narration rows t_ms (request to caption publish)
  NFR-05, NFR-07: no timing is logged yet, reported as unmeasured
"""


class NotRun(Exception):
    pass


class Meter(Protocol):
    @property
    def spent_usd(self) -> Decimal: ...

    @property
    def is_stopped(self) -> bool: ...


@dataclass(frozen=True)
class PaidServices:
    meter: Meter
    detector: Detector
    segmenter: Segmenter
    content: ContentFilter
    invalid: list[str] = field(default_factory=list)


ServicesFactory = Callable[[], PaidServices]


def live_services() -> PaidServices:
    from smoke import SmokeError, open_smoke_context
    from vision.sam import SamSegmenter
    from vision.summon import SparkDetector

    try:
        context = open_smoke_context()
    except (SmokeError, OSError) as error:
        raise NotRun(str(error)) from error
    content = ContentFilter()
    invalid: list[str] = []
    return PaidServices(
        meter=context.client.meter,
        detector=SparkDetector(context.client, content, invalid.append),
        segmenter=SamSegmenter(context.client),
        content=content,
        invalid=invalid,
    )


def git_state() -> tuple[str, bool]:
    try:
        head = subprocess.run(
            ["git", "rev-parse", "HEAD"],
            cwd=REPO_DIR,
            capture_output=True,
            text=True,
            check=True,
        ).stdout.strip()
        status = subprocess.run(
            ["git", "status", "--porcelain", "--untracked-files=no"],
            cwd=REPO_DIR,
            capture_output=True,
            text=True,
            check=True,
        ).stdout.strip()
    except (OSError, subprocess.CalledProcessError):
        return "unknown", False
    return head, bool(status)


@dataclass(frozen=True)
class Deps:
    out_dir: Path
    now: Callable[[], datetime]
    git: Callable[[], tuple[str, bool]]
    services: ServicesFactory


def default_deps(out_dir: Path) -> Deps:
    return Deps(
        out_dir=out_dir,
        now=lambda: datetime.now(UTC),
        git=git_state,
        services=live_services,
    )


@dataclass(frozen=True)
class Outcome:
    eval_id: str
    summary: str
    payload: JsonObject
    target_met: bool | None


def decide(checks: Sequence[bool | None]) -> bool | None:
    if any(check is False for check in checks):
        return False
    if any(check is None for check in checks):
        return None
    return True


def size_check(eval_id: str, size: int) -> bool | None:
    return True if size >= MIN_SET[eval_id] else None


def share(part: int, whole: int) -> float:
    return part / whole if whole else 0.0


def percentile(values: Sequence[float], pct: float) -> float:
    ordered = sorted(values)
    rank = max(1, math.ceil(pct / 100 * len(ordered)))
    return ordered[rank - 1]


def verdict(target_met: bool | None) -> str:
    if target_met is None:
        return "target undecided"
    return "target met" if target_met else "target missed"


def as_object(value: object, where: str) -> JsonObject:
    if not isinstance(value, dict):
        raise NotRun(f"{where} must be an object")
    return {str(key): item for key, item in value.items()}


def as_list(value: object, where: str) -> list[object]:
    if not isinstance(value, list):
        raise NotRun(f"{where} must be a list")
    return list(value)


def as_text(value: object, where: str) -> str:
    if not isinstance(value, str) or not value.strip():
        raise NotRun(f"{where} must be a non-empty string")
    return value


def as_optional_text(value: object, where: str) -> str | None:
    if value is None:
        return None
    return as_text(value, where)


def as_number(value: object, where: str) -> float:
    if isinstance(value, bool) or not isinstance(value, int | float):
        raise NotRun(f"{where} must be a number")
    return float(value)


def as_box(value: object, where: str) -> tuple[float, float, float, float]:
    items = as_list(value, where)
    if len(items) != 4:
        raise NotRun(f"{where} must hold 4 numbers")
    left, top, right, bottom = (as_number(item, where) for item in items)
    return left, top, right, bottom


def as_unit(value: object, where: str) -> str:
    unit = as_text(value, where)
    if unit not in ("grid", "pixels"):
        raise NotRun(f'{where} must be "grid" or "pixels"')
    return unit


def to_pixel_box(
    box: tuple[float, float, float, float],
    unit: str,
    width: int,
    height: int,
    where: str,
) -> PixelBox:
    left, top, right, bottom = box
    if unit == "grid":
        left, right = left / GRID_MAX * width, right / GRID_MAX * width
        top, bottom = top / GRID_MAX * height, bottom / GRID_MAX * height
    try:
        return clamp_box(
            PixelBox(round(left), round(top), round(right), round(bottom)),
            width,
            height,
        )
    except SegmentationError as error:
        raise NotRun(f"{where} is not a valid box: {error}") from error


def read_json_file(path: Path) -> object:
    if not path.is_file():
        raise NotRun(f"input file not found: {path}")
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except (OSError, ValueError) as error:
        raise NotRun(f"cannot read {path}: {error}") from error


def read_jsonl_file(path: Path) -> list[JsonObject]:
    if not path.is_file():
        raise NotRun(f"input file not found: {path}")
    try:
        lines = path.read_text(encoding="utf-8").splitlines()
    except (OSError, ValueError) as error:
        raise NotRun(f"cannot read {path}: {error}") from error
    rows: list[JsonObject] = []
    for number, line in enumerate(lines, start=1):
        if not line.strip():
            continue
        try:
            rows.append(as_object(json.loads(line), f"{path.name} line {number}"))
        except ValueError as error:
            raise NotRun(f"{path.name} line {number} is not JSON: {error}") from error
    if not rows:
        raise NotRun(f"{path} has no rows")
    return rows


def load_image(path: Path, where: str) -> Image:
    if not path.is_file():
        raise NotRun(f"{where}: image not found: {path}")
    image = cv2.imread(str(path))
    if image is None:
        raise NotRun(f"{where}: cannot decode image: {path}")
    return np.asarray(image, dtype=np.uint8)


@dataclass(frozen=True)
class E1Item:
    name: str
    condition: str
    spoken_name: str
    image: Image
    known: tuple[KnownObject, ...]
    expected: PixelBox


@dataclass(frozen=True)
class E1Set:
    items: tuple[E1Item, ...]
    px_per_cm: float
    difficulty: Difficulty


def load_e1(path: Path) -> E1Set:
    root = as_object(read_json_file(path), path.name)
    default_unit = as_unit(root.get("box_unit", "grid"), "box_unit")
    px_per_cm = as_number(root.get("px_per_cm", PX_PER_CM), "px_per_cm")
    try:
        difficulty = Difficulty(str(root.get("difficulty", "normal")))
    except ValueError as error:
        raise NotRun("difficulty must be madali, normal or mahirap") from error
    raw_items = as_list(root.get("items"), "items")
    if not raw_items:
        raise NotRun(f"{path} has no items")
    items: list[E1Item] = []
    for index, raw in enumerate(raw_items):
        where = f"items[{index}]"
        entry = as_object(raw, where)
        unit = as_unit(entry.get("box_unit", default_unit), f"{where}.box_unit")
        image_path = path.parent / as_text(entry.get("snapshot"), f"{where}.snapshot")
        image = load_image(image_path, where)
        height, width = image.shape[:2]
        known: list[KnownObject] = []
        for known_index, known_raw in enumerate(
            as_list(entry.get("known", []), f"{where}.known")
        ):
            known_where = f"{where}.known[{known_index}]"
            item = as_object(known_raw, known_where)
            sam_id = int(as_number(item.get("sam_id"), f"{known_where}.sam_id"))
            try:
                unit_class = UnitClass(str(item.get("unit_class", "fighter")))
            except ValueError as error:
                raise NotRun(f"{known_where}.unit_class is not a class") from error
            known.append(
                KnownObject(
                    sam_id=sam_id,
                    label=as_text(item.get("label"), f"{known_where}.label"),
                    unit_class=unit_class,
                    box=to_pixel_box(
                        as_box(item.get("box"), f"{known_where}.box"),
                        unit,
                        width,
                        height,
                        known_where,
                    ),
                )
            )
        items.append(
            E1Item(
                name=image_path.name,
                condition=as_text(entry.get("condition"), f"{where}.condition"),
                spoken_name=as_text(entry.get("spoken_name"), f"{where}.spoken_name"),
                image=image,
                known=tuple(known),
                expected=to_pixel_box(
                    as_box(entry.get("expected_box"), f"{where}.expected_box"),
                    unit,
                    width,
                    height,
                    f"{where}.expected_box",
                ),
            )
        )
    return E1Set(tuple(items), px_per_cm, difficulty)


def spark_attempt_usd() -> Decimal:
    return price_usage(
        CallKind.SPARK,
        Usage(
            input_tokens=ASSUMED_SPARK_INPUT_TOKENS,
            output_tokens=ASSUMED_SPARK_OUTPUT_TOKENS,
        ),
    )


def sam_image_usd() -> Decimal:
    return price_usage(CallKind.SAM_IMAGE, Usage(images=1))


def estimate_e1_usd(snapshots: int) -> Decimal:
    per_snapshot = spark_attempt_usd() * SPARK_ATTEMPTS_PER_SNAPSHOT + sam_image_usd()
    return per_snapshot * snapshots


def estimate_e2_usd(cases: int, targets: int) -> tuple[Decimal, Decimal]:
    typical = sam_image_usd() * SAM_CALLS_PER_END_TURN * cases
    worst = sam_image_usd() * (SAM_CALLS_PER_END_TURN * cases + targets)
    return typical, worst


def check_budget(services: PaidServices, estimate_usd: Decimal) -> None:
    if services.meter.is_stopped:
        raise NotRun("cost meter is stopped, paid calls are blocked")
    if services.meter.spent_usd + estimate_usd >= COST_STOP_USD:
        raise NotRun(
            f"spent ${services.meter.spent_usd} plus the estimate ${estimate_usd:.4f} "
            f"would reach the ${COST_STOP_USD} hard stop"
        )


async def score_e1(
    data: E1Set, services: PaidServices
) -> tuple[list[JsonObject], Counter[str], Counter[str]]:
    pipeline = SummonPipeline(services.detector, services.segmenter, services.content)
    details: list[JsonObject] = []
    hits: Counter[str] = Counter()
    totals: Counter[str] = Counter()
    for item in data.items:
        if services.meter.is_stopped:
            raise NotRun(
                f"cost meter stopped after {len(details)} of {len(data.items)} snapshots"
            )
        request = SummonRequest(
            snapshot=item.image,
            spoken_name=item.spoken_name,
            known=item.known,
            difficulty=data.difficulty,
            px_per_cm=data.px_per_cm,
        )
        detection = await pipeline.detect(request)
        iou = 0.0
        error = ""
        try:
            outcome = await pipeline.run(request, detection)
            iou = box_iou(outcome.mask.bounds, item.expected)
        except SummonError as failure:
            error = failure.copy_key
        is_hit = iou >= IOU_ACCEPT
        totals[item.condition] += 1
        hits[item.condition] += int(is_hit)
        details.append(
            {
                "snapshot": item.name,
                "condition": item.condition,
                "source": detection.source,
                "iou": round(iou, 4),
                "hit": is_hit,
                "error": error,
            }
        )
    return details, hits, totals


def run_e1(args: argparse.Namespace, deps: Deps) -> Outcome:
    data = load_e1(args.labels)
    estimate = estimate_e1_usd(len(data.items))
    print(
        f"e1 estimated cost: up to ${estimate:.4f} for {len(data.items)} snapshots "
        f"({SPARK_ATTEMPTS_PER_SNAPSHOT} Spark attempts at an assumed "
        f"{ASSUMED_SPARK_INPUT_TOKENS} input and {ASSUMED_SPARK_OUTPUT_TOKENS} output tokens "
        f"plus 1 SAM image each). This is an estimate, not a measurement"
    )
    if not args.yes:
        raise NotRun("paid calls need --yes after you have read the estimate")
    services = deps.services()
    check_budget(services, estimate)
    if not services.detector.is_available:
        raise NotRun("Spark is unavailable (no credentials, breaker open or budget)")
    if not services.segmenter.is_available:
        raise NotRun("SAM is unavailable (no credentials, breaker open or budget)")
    spent_before = services.meter.spent_usd
    details, hits, totals = asyncio.run(score_e1(data, services))
    total = len(details)
    hit_count = sum(hits.values())
    metric = share(hit_count, total)
    target_met = decide([metric >= TARGETS["e1"], size_check("e1", total)])
    spent = services.meter.spent_usd - spent_before
    payload: JsonObject = {
        "inputs": {"labels": str(args.labels), "snapshots": total},
        "counts": {
            "total": total,
            "hits": hit_count,
            "fallback_detections": sum(
                1 for row in details if row["source"] == "fallback"
            ),
            "spark_invalid_responses": len(services.invalid),
        },
        "metric_name": "share with IoU >= 0.5",
        "metric": metric,
        "target": TARGETS["e1"],
        "target_met": target_met,
        "conditions": {
            "by_condition": {
                name: {"hits": hits[name], "total": totals[name]} for name in totals
            },
            "px_per_cm": data.px_per_cm,
            "difficulty": data.difficulty.value,
            "set_size_full": FULL_SET["e1"],
            "set_size_min_for_verdict": MIN_SET["e1"],
        },
        "cost_usd_measured": str(spent),
        "cost_usd_estimate": str(estimate),
        "details": details,
    }
    summary = (
        f"e1: {hit_count}/{total} = {metric:.1%} IoU>=0.5 "
        f"(target {TARGETS['e1']:.0%}, {verdict(target_met)}), cost ${spent}"
    )
    return Outcome("e1", summary, payload, target_met)


@dataclass(frozen=True)
class E2Case:
    case_id: str
    image: Image
    px_per_cm: float
    targets: tuple[ReanchorTarget, ...]
    expected: dict[int, PixelBox]


def load_e2(path: Path) -> list[E2Case]:
    cases: list[E2Case] = []
    for index, row in enumerate(read_jsonl_file(path), start=1):
        where = f"{path.name} case {index}"
        image = load_image(
            path.parent / as_text(row.get("frame"), f"{where}.frame"), where
        )
        height, width = image.shape[:2]
        targets: list[ReanchorTarget] = []
        expected: dict[int, PixelBox] = {}
        for t_index, raw in enumerate(as_list(row.get("targets"), f"{where}.targets")):
            t_where = f"{where}.targets[{t_index}]"
            entry = as_object(raw, t_where)
            sam_id = int(as_number(entry.get("sam_id"), f"{t_where}.sam_id"))
            raw_hist = as_list(entry.get("histogram", []), f"{t_where}.histogram")
            targets.append(
                ReanchorTarget(
                    sam_id=sam_id,
                    tracker_box=to_pixel_box(
                        as_box(entry.get("tracker_box"), f"{t_where}.tracker_box"),
                        "pixels",
                        width,
                        height,
                        t_where,
                    ),
                    label=as_text(entry.get("label"), f"{t_where}.label"),
                    histogram=tuple(
                        as_number(v, f"{t_where}.histogram") for v in raw_hist
                    ),
                )
            )
            expected[sam_id] = to_pixel_box(
                as_box(entry.get("expected_box"), f"{t_where}.expected_box"),
                "pixels",
                width,
                height,
                t_where,
            )
        if not targets:
            raise NotRun(f"{where} has no targets")
        cases.append(
            E2Case(
                case_id=str(row.get("case_id", index)),
                image=image,
                px_per_cm=as_number(
                    row.get("px_per_cm", PX_PER_CM), f"{where}.px_per_cm"
                ),
                targets=tuple(targets),
                expected=expected,
            )
        )
    return cases


async def score_e2(
    cases: Sequence[E2Case], services: PaidServices
) -> tuple[list[JsonObject], Counter[str], int]:
    from game.night import safe_distance, safe_histogram
    from vision.sam import reanchor

    details: list[JsonObject] = []
    statuses: Counter[str] = Counter()
    correct = 0
    for case in cases:
        if services.meter.is_stopped:
            raise NotRun(
                f"cost meter stopped after {len(details)} of {len(cases)} cases"
            )
        anchors = await reanchor(
            services.segmenter,
            case.image,
            case.targets,
            case.px_per_cm,
            safe_histogram,
            safe_distance,
        )
        case_correct = 0
        for target in case.targets:
            anchor = anchors.get(target.sam_id)
            if anchor is None:
                statuses["missing"] += 1
                continue
            statuses[anchor.status.value] += 1
            if box_iou(anchor.box, case.expected[target.sam_id]) >= IOU_ACCEPT:
                case_correct += 1
        correct += case_correct
        details.append(
            {
                "case_id": case.case_id,
                "targets": len(case.targets),
                "correct": case_correct,
            }
        )
    return details, statuses, correct


def run_e2(args: argparse.Namespace, deps: Deps) -> Outcome:
    cases = load_e2(args.data)
    target_count = sum(len(case.targets) for case in cases)
    typical, worst = estimate_e2_usd(len(cases), target_count)
    print(
        f"e2 estimated cost: about ${typical:.4f} for {len(cases)} End Turns "
        f"({SAM_CALLS_PER_END_TURN} SAM images each), worst case ${worst:.4f} "
        f"if every target needs a concept search. This is an estimate, not a measurement"
    )
    if not args.yes:
        raise NotRun("paid calls need --yes after you have read the estimate")
    services = deps.services()
    check_budget(services, worst)
    if not services.segmenter.is_available:
        raise NotRun("SAM is unavailable (no credentials, breaker open or budget)")
    spent_before = services.meter.spent_usd
    details, statuses, correct = asyncio.run(score_e2(cases, services))
    metric = share(correct, target_count)
    target_met = decide([metric >= TARGETS["e2"], size_check("e2", len(cases))])
    spent = services.meter.spent_usd - spent_before
    payload: JsonObject = {
        "inputs": {"data": str(args.data), "end_turns": len(cases)},
        "counts": {
            "end_turns": len(cases),
            "targets": target_count,
            "correct": correct,
            "anchor_status": dict(statuses),
        },
        "metric_name": "correct id share",
        "metric": metric,
        "target": TARGETS["e2"],
        "target_met": target_met,
        "conditions": {
            "set_size_full": FULL_SET["e2"],
            "set_size_min_for_verdict": MIN_SET["e2"],
        },
        "cost_usd_measured": str(spent),
        "cost_usd_estimate_typical": str(typical),
        "details": details,
    }
    summary = (
        f"e2: {correct}/{target_count} = {metric:.1%} correct ids over {len(cases)} End Turns "
        f"(target {TARGETS['e2']:.0%}, {verdict(target_met)}), cost ${spent}"
    )
    return Outcome("e2", summary, payload, target_met)


@dataclass(frozen=True)
class E3Row:
    transcript: str
    recording: str
    speaker: str
    expected_unit: str | None
    expected_action: str | None
    expected_target: str | None
    context: GrammarContext


def load_e3(path: Path) -> list[E3Row]:
    rows: list[E3Row] = []
    actions = {kind.value for kind in CommandKind}
    for index, raw in enumerate(read_jsonl_file(path), start=1):
        where = f"{path.name} row {index}"
        action = as_optional_text(
            raw.get("expected_action"), f"{where}.expected_action"
        )
        if action is not None and action not in actions:
            raise NotRun(f"{where}.expected_action must be one of {sorted(actions)}")
        context = as_object(raw.get("context"), f"{where}.context")
        units = tuple(
            GrammarUnit(
                game_id=as_text(u.get("game_id"), f"{where}.units.game_id"),
                name=as_text(u.get("name"), f"{where}.units.name"),
                unit_class=as_text(u.get("unit_class"), f"{where}.units.unit_class"),
                x_cm=as_number(u.get("x_cm"), f"{where}.units.x_cm"),
                y_cm=as_number(u.get("y_cm"), f"{where}.units.y_cm"),
            )
            for u in (
                as_object(item, f"{where}.units")
                for item in as_list(context.get("units", []), f"{where}.units")
            )
        )
        enemies = tuple(
            GrammarEnemy(
                id=as_text(e.get("id"), f"{where}.enemies.id"),
                type=as_text(e.get("type"), f"{where}.enemies.type"),
                x_cm=as_number(e.get("x_cm"), f"{where}.enemies.x_cm"),
                y_cm=as_number(e.get("y_cm"), f"{where}.enemies.y_cm"),
            )
            for e in (
                as_object(item, f"{where}.enemies")
                for item in as_list(context.get("enemies", []), f"{where}.enemies")
            )
        )
        transcript = raw.get("transcript")
        if not isinstance(transcript, str):
            raise NotRun(f"{where}.transcript must be a string")
        rows.append(
            E3Row(
                transcript=transcript,
                recording=as_text(raw.get("recording"), f"{where}.recording"),
                speaker=str(raw.get("speaker", "")),
                expected_unit=as_optional_text(
                    raw.get("expected_unit_id"), f"{where}.expected_unit_id"
                ),
                expected_action=action,
                expected_target=as_optional_text(
                    raw.get("expected_target_id"), f"{where}.expected_target_id"
                ),
                context=GrammarContext(units=units, enemies=enemies),
            )
        )
    return rows


def e3_is_correct(row: E3Row, command: Command | None) -> bool:
    if row.expected_action is None:
        return command is None
    return (
        command is not None
        and command.kind.value == row.expected_action
        and command.unit_id == row.expected_unit
        and command.target_id == row.expected_target
    )


def run_e3(args: argparse.Namespace, deps: Deps) -> Outcome:
    rows = load_e3(args.labels)
    correct = 0
    misses: list[JsonObject] = []
    for row in rows:
        command = parse_command(row.transcript, row.context)
        if e3_is_correct(row, command):
            correct += 1
        else:
            misses.append(
                {
                    "recording": row.recording,
                    "transcript": row.transcript,
                    "expected": [
                        row.expected_unit,
                        row.expected_action,
                        row.expected_target,
                    ],
                    "got": None
                    if command is None
                    else [command.unit_id, command.kind.value, command.target_id],
                }
            )
    total = len(rows)
    metric = share(correct, total)
    target_met = decide([metric >= TARGETS["e3"], size_check("e3", total)])
    speakers = {row.speaker for row in rows if row.speaker}
    payload: JsonObject = {
        "inputs": {"labels": str(args.labels), "utterances": total},
        "counts": {"total": total, "correct": correct},
        "metric_name": "unit, action and target all correct",
        "metric": metric,
        "target": TARGETS["e3"],
        "target_met": target_met,
        "conditions": {
            "path": "local grammar parse_command, offline",
            "speakers": len(speakers),
            "recordings": len({row.recording for row in rows}),
            "set_size_full": FULL_SET["e3"],
            "set_size_min_for_verdict": MIN_SET["e3"],
            "note": "transcripts must come from real recordings",
        },
        "misses": misses,
    }
    summary = (
        f"e3: {correct}/{total} = {metric:.1%} all-correct "
        f"(target {TARGETS['e3']:.0%}, {verdict(target_met)}). "
        f"Transcripts must come from real recordings"
    )
    return Outcome("e3", summary, payload, target_met)


def open_db(path: Path | None) -> sqlite3.Connection:
    if path is None:
        raise NotRun("pass --db <path to desktop.sqlite>")
    if not path.is_file():
        raise NotRun(f"database not found: {path}")
    try:
        conn = sqlite3.connect(f"{path.resolve().as_uri()}?mode=ro", uri=True)
        conn.row_factory = sqlite3.Row
        conn.execute("SELECT 1 FROM turn_log LIMIT 1")
        conn.execute("SELECT 1 FROM api_usage LIMIT 1")
    except sqlite3.Error as error:
        raise NotRun(f"cannot read {path} as a DeskTop database: {error}") from error
    return conn


def payload_of(raw: object) -> JsonObject:
    try:
        parsed = json.loads(str(raw))
    except ValueError:
        return {}
    return {str(k): v for k, v in parsed.items()} if isinstance(parsed, dict) else {}


def run_e4(args: argparse.Namespace, deps: Deps) -> Outcome:
    conn = open_db(args.db)
    try:
        rows = conn.execute(
            "SELECT night_id, turn, event_type, phase, payload_json FROM turn_log "
            "WHERE event_type IN (?, ?, ?) ORDER BY id",
            (NARRATION_EVENT, NARRATION_REQUEST_EVENT, GM_INVALID_EVENT),
        ).fetchall()
    finally:
        conn.close()
    sources: Counter[str] = Counter()
    bank_keys: list[tuple[str, int]] = []
    invalid_keys: Counter[tuple[str, int]] = Counter()
    excluded_invalid = 0
    reasons: Counter[str] = Counter()
    requested: Counter[tuple[str, int, str]] = Counter()
    narrated: Counter[tuple[str, int, str]] = Counter()
    for row in rows:
        night, turn = str(row["night_id"]), int(row["turn"])
        payload = payload_of(row["payload_json"])
        event = str(row["event_type"])
        if event == GM_INVALID_EVENT:
            reason = str(payload.get("reason", ""))
            if str(row["phase"]) == SUMMON_PHASE or not reason.startswith(
                GM_INVALID_PREFIX
            ):
                excluded_invalid += 1
                continue
            invalid_keys[(night, turn)] += 1
            reasons[reason] += 1
        elif event == NARRATION_EVENT:
            source = str(payload.get("source", ""))
            sources[source] += 1
            narrated[(night, turn, str(payload.get("phase", "")))] += 1
            if source == LINE_BANK_SOURCE:
                bank_keys.append((night, turn))
        else:
            requested[(night, turn, str(payload.get("phase", "")))] += 1
    bank_after_invalid = sum(1 for key in bank_keys if invalid_keys[key] > 0)
    attempts = sources[SPARK_SOURCE] + bank_after_invalid
    if attempts == 0:
        raise NotRun("turn_log has no live Spark narration attempts")
    failures = sum(invalid_keys.values())
    first_try = max(0.0, 1 - failures / attempts)
    request_total = sum(requested.values())
    missing = sum(max(0, count - narrated[key]) for key, count in requested.items())
    non_blocking = (
        None if request_total == 0 else share(request_total - missing, request_total)
    )
    non_blocking_ok = (
        None if non_blocking is None else non_blocking >= TARGETS["e4_non_blocking"]
    )
    target_met = decide(
        [
            first_try >= TARGETS["e4_first_try"],
            non_blocking_ok,
            size_check("e4", attempts),
        ]
    )
    payload_out: JsonObject = {
        "inputs": {"db": str(args.db)},
        "counts": {
            "live_spark_attempts": attempts,
            "spark_narration_rows": sources[SPARK_SOURCE],
            "line_bank_rows_after_invalid": bank_after_invalid,
            "line_bank_rows": sources[LINE_BANK_SOURCE],
            "gm_invalid_failures": failures,
            "gm_invalid_excluded": excluded_invalid,
            "failure_reasons": dict(reasons),
            "narration_requests": request_total,
            "narration_requests_without_row": missing,
        },
        "metric_name": "first-try validity",
        "metric": first_try,
        "target": TARGETS["e4_first_try"],
        "target_met": target_met,
        "conditions": {
            "formula_first_try": "1 - gm_invalid failures / live Spark narration attempts",
            "formula_attempts": "spark narration rows + line_bank rows in a night and turn with a gm_invalid row",
            "formula_non_blocking": "narration_request rows with a matching narration row / narration_request rows",
            "non_blocking": non_blocking,
            "non_blocking_target": TARGETS["e4_non_blocking"],
            "non_blocking_note": "no narration_request rows in turn_log, not measurable"
            if non_blocking is None
            else "measured",
            "failures_are_upper_bound": "a request that fails twice adds two rows",
            "set_size_full": FULL_SET["e4"],
            "set_size_min_for_verdict": MIN_SET["e4"],
        },
    }
    non_blocking_text = (
        "not measurable" if non_blocking is None else f"{non_blocking:.1%}"
    )
    summary = (
        f"e4: first-try {first_try:.1%} = 1 - {failures} gm_invalid / {attempts} live Spark attempts "
        f"(target {TARGETS['e4_first_try']:.0%}), non-blocking {non_blocking_text} "
        f"(target 100%), {verdict(target_met)}"
    )
    return Outcome("e4", summary, payload_out, target_met)


def latency_stats(values: Sequence[float]) -> JsonObject:
    return {
        "n": len(values),
        "p50_ms": percentile(values, 50),
        "p90_ms": percentile(values, 90),
    }


def end_turn_durations(rows: Sequence[sqlite3.Row]) -> tuple[list[float], int]:
    durations: list[float] = []
    open_start: dict[str, int] = {}
    for row in rows:
        night, phase, t_ms = str(row["night_id"]), str(row["phase"]), int(row["t_ms"])
        if phase == END_TURN_PHASE:
            open_start[night] = t_ms
        elif phase in END_TURN_CLOSERS and night in open_start:
            durations.append(float(t_ms - open_start.pop(night)))
    return durations, len(open_start)


def run_e6(args: argparse.Namespace, deps: Deps) -> Outcome:
    conn = open_db(args.db)
    try:
        usage = conn.execute(
            "SELECT kind, model, latency_ms FROM api_usage "
            "WHERE ok = 1 AND latency_ms IS NOT NULL"
        ).fetchall()
        transitions = conn.execute(
            "SELECT night_id, phase, t_ms FROM turn_log WHERE event_type = ? ORDER BY id",
            (TRANSITION_EVENT,),
        ).fetchall()
        summons = conn.execute(
            "SELECT t_ms FROM turn_log WHERE event_type = ?", (SUMMON_EVENT,)
        ).fetchall()
        narrations = conn.execute(
            "SELECT t_ms FROM turn_log WHERE event_type = ? AND t_ms > 0",
            (NARRATION_EVENT,),
        ).fetchall()
    finally:
        conn.close()
    by_kind: dict[str, list[float]] = {}
    by_model: dict[str, list[float]] = {}
    for row in usage:
        by_kind.setdefault(str(row["kind"]), []).append(float(row["latency_ms"]))
        by_model.setdefault(str(row["model"]), []).append(float(row["latency_ms"]))
    end_turns, unclosed = end_turn_durations(transitions)
    samples: dict[str, list[float]] = {
        "NFR-01": [float(row["t_ms"]) for row in summons],
        "NFR-03": end_turns,
        "NFR-08": [float(row["t_ms"]) for row in narrations],
    }
    sources = {
        "NFR-01": "turn_log summon rows t_ms",
        "NFR-03": "turn_log transition rows, END_TURN_SNAPSHOT to PLAYER_PHASE, SUNRISE or DEFEAT",
        "NFR-05": "no speech end to chip timing is logged yet",
        "NFR-07": "no partial caption timing is logged yet",
        "NFR-08": "turn_log narration rows t_ms, request to caption publish",
    }
    table: list[JsonObject] = []
    checks: list[bool | None] = []
    for nfr, target_ms in NFR_TARGETS_MS.items():
        values = samples.get(nfr, [])
        entry: JsonObject = {
            "nfr": nfr,
            "target_p90_ms": target_ms,
            "source": sources[nfr],
            "n": len(values),
        }
        if values:
            p90 = percentile(values, 90)
            entry["p50_ms"] = percentile(values, 50)
            entry["p90_ms"] = p90
            entry["met"] = p90 <= target_ms
        else:
            entry["p50_ms"] = None
            entry["p90_ms"] = None
            entry["met"] = None
        table.append(entry)
        if nfr in NFR_REQUIRED:
            checks.append(entry["met"] if isinstance(entry["met"], bool) else None)
    if not usage and not samples["NFR-01"] and not end_turns and not samples["NFR-08"]:
        raise NotRun("api_usage and turn_log hold no latency samples")
    target_met = decide(checks)
    measured = [e for e in table if e["met"] is not None]
    unmeasured = [str(e["nfr"]) for e in table if e["met"] is None]
    payload: JsonObject = {
        "inputs": {"db": str(args.db)},
        "counts": {
            "api_usage_ok_rows": len(usage),
            "summon_rows": len(summons),
            "end_turns": len(end_turns),
            "end_turns_unclosed": unclosed,
        },
        "metric_name": "p90 latency per NFR in ms",
        "metric": {str(e["nfr"]): e["p90_ms"] for e in table},
        "target": {nfr: ms for nfr, ms in NFR_TARGETS_MS.items()},
        "target_met": target_met,
        "conditions": {
            "percentile": "nearest rank",
            "required_nfrs": list(NFR_REQUIRED),
            "unmeasured": unmeasured,
            "api_usage_filter": "ok = 1 and latency_ms not null",
            "set_size_full": "3 full nights",
        },
        "nfr": table,
        "api_usage_by_kind": {k: latency_stats(v) for k, v in sorted(by_kind.items())},
        "api_usage_by_model": {
            k: latency_stats(v) for k, v in sorted(by_model.items())
        },
    }
    parts = [
        f"{e['nfr']} p90 {e['p90_ms']:.0f} ms (target {e['target_p90_ms']})"
        for e in measured
        if isinstance(e["p90_ms"], float)
    ]
    summary = (
        f"e6: {'; '.join(parts) or 'no NFR measured'}"
        f"{'; unmeasured ' + ', '.join(unmeasured) if unmeasured else ''}, "
        f"{verdict(target_met)}"
    )
    return Outcome("e6", summary, payload, target_met)


def run_e7(args: argparse.Namespace, deps: Deps) -> Outcome:
    from rules.resolve import begin_turn, resolve_turn
    from tests.test_resolve import random_state

    boards = int(args.boards)
    if boards < 1:
        raise NotRun("--boards must be at least 1")
    identical = 0
    differing: list[int] = []
    for seed in range(boards):
        state, intents = random_state(seed)
        first = resolve_turn(state, intents)
        second = resolve_turn(state, intents)
        chained_a = resolve_turn(begin_turn(first[0])[0], intents)
        chained_b = resolve_turn(begin_turn(second[0])[0], intents)
        if (
            first == second
            and begin_turn(state) == begin_turn(state)
            and chained_a == chained_b
        ):
            identical += 1
        else:
            differing.append(seed)
    metric = share(identical, boards)
    target_met = decide([metric >= TARGETS["e7"], size_check("e7", boards)])
    payload: JsonObject = {
        "inputs": {
            "generator": "backend/tests/test_resolve.py random_state",
            "seeds": boards,
        },
        "counts": {
            "boards": boards,
            "identical": identical,
            "differing_seeds": differing,
        },
        "metric_name": "boards with identical events",
        "metric": metric,
        "target": TARGETS["e7"],
        "target_met": target_met,
        "conditions": {
            "checks": [
                "resolve_turn twice equal",
                "begin_turn twice equal",
                "begin_turn then resolve_turn chained twice equal",
            ],
            "seeds": f"0 to {boards - 1}",
            "set_size_full": FULL_SET["e7"],
            "set_size_min_for_verdict": MIN_SET["e7"],
        },
    }
    summary = (
        f"e7: {identical}/{boards} = {metric:.1%} identical "
        f"(target 100%, {verdict(target_met)})"
    )
    return Outcome("e7", summary, payload, target_met)


def emit(outcome: Outcome, deps: Deps) -> int:
    now = deps.now().astimezone(UTC)
    commit, is_dirty = deps.git()
    record: JsonObject = {
        "eval": outcome.eval_id,
        "timestamp_utc": now.isoformat(),
        "commit": commit,
        "commit_has_uncommitted_changes": is_dirty,
        **outcome.payload,
    }
    deps.out_dir.mkdir(parents=True, exist_ok=True)
    target = deps.out_dir / f"{outcome.eval_id}-{now.strftime('%Y%m%dT%H%M%SZ')}.json"
    target.write_text(
        json.dumps(record, indent=2, ensure_ascii=False, default=str) + "\n",
        encoding="utf-8",
    )
    print(f"{outcome.summary} -> {target}")
    return 0 if outcome.target_met is not False else 1


RUNNERS: Final[dict[str, Callable[[argparse.Namespace, Deps], Outcome]]] = {
    "e1": run_e1,
    "e2": run_e2,
    "e3": run_e3,
    "e4": run_e4,
    "e6": run_e6,
    "e7": run_e7,
}


def execute(name: str, args: argparse.Namespace, deps: Deps) -> int:
    try:
        outcome = RUNNERS[name](args, deps)
    except NotRun as reason:
        print(f"{name}: not run: {reason}")
        return NOT_RUN_EXIT
    return emit(outcome, deps)


def run_all(args: argparse.Namespace, deps: Deps) -> int:
    codes: dict[str, int] = {}
    plan = {
        "e3": argparse.Namespace(labels=args.voice_labels),
        "e4": argparse.Namespace(db=args.db),
        "e6": argparse.Namespace(db=args.db),
        "e7": argparse.Namespace(boards=args.boards),
    }
    for name, namespace in plan.items():
        codes[name] = execute(name, namespace, deps)
    print("all: paid evals e1 and e2 are never run by all")
    if any(code == 1 for code in codes.values()):
        return 1
    if all(code == NOT_RUN_EXIT for code in codes.values()):
        return NOT_RUN_EXIT
    return 0


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="run_eval.py",
        description="DeskTop eval runner. " + USAGE_NOTE,
        epilog="Exit codes: 0 ran and target met or undecided, 1 ran and target missed, "
        "2 not run. A not-run eval writes no result file.",
    )
    parser.add_argument(
        "--out-dir", type=Path, default=EVAL_DIR / "results", help="result folder"
    )
    sub = parser.add_subparsers(dest="eval", required=True)

    def add(name: str, summary: str, detail: str) -> argparse.ArgumentParser:
        child = sub.add_parser(
            name,
            help=summary,
            description=summary + "\n\n" + detail,
            formatter_class=argparse.RawDescriptionHelpFormatter,
        )
        return child

    e1 = add("e1", "E1 registration, paid, needs --yes", E1_FORMAT)
    e1.add_argument("--labels", type=Path, default=EVAL_DIR / "objects" / "labels.json")
    e1.add_argument("--yes", action="store_true", help="authorize the paid calls")
    e2 = add("e2", "E2 re-anchor identity, paid, needs --yes", E2_FORMAT)
    e2.add_argument(
        "--data", type=Path, default=EVAL_DIR / "objects" / "endturns.jsonl"
    )
    e2.add_argument("--yes", action="store_true", help="authorize the paid calls")
    e3 = add("e3", "E3 Taglish commands, offline", E3_FORMAT)
    e3.add_argument("--labels", type=Path, default=EVAL_DIR / "voice" / "labels.jsonl")
    e4 = add("e4", "E4 GM validity from turn_log, offline", E4_FORMAT)
    e4.add_argument("--db", type=Path, default=None)
    e6 = add("e6", "E6 latency from api_usage and turn_log, offline", E6_FORMAT)
    e6.add_argument("--db", type=Path, default=None)
    e7 = add("e7", "E7 determinism on seeded boards, offline", "")
    e7.add_argument("--boards", type=int, default=FULL_SET["e7"])
    every = add("all", "every offline eval that has inputs (not e1, not e2)", "")
    every.add_argument("--db", type=Path, default=None)
    every.add_argument(
        "--voice-labels", type=Path, default=EVAL_DIR / "voice" / "labels.jsonl"
    )
    every.add_argument("--boards", type=int, default=FULL_SET["e7"])
    return parser


def main(argv: Sequence[str] | None = None, deps: Deps | None = None) -> int:
    args = build_parser().parse_args(argv)
    active = deps if deps is not None else default_deps(args.out_dir)
    if args.eval == "all":
        return run_all(args, active)
    return execute(args.eval, args, active)


if __name__ == "__main__":
    sys.exit(main())
