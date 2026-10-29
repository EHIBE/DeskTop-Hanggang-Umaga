import importlib
import json
import sys
from collections.abc import Sequence
from datetime import UTC, datetime
from decimal import Decimal
from pathlib import Path

import cv2
import numpy as np
import numpy.typing as npt
import pytest

from db.store import ApiUsageRecord, Store
from gm.schemas import ContentFilter
from rules.units import Difficulty
from vision.sam import ObjectPrompt, PixelBox, SegmentationResult
from vision.summon import CardText, Detection, KnownObject

EVAL_DIR = Path(__file__).resolve().parents[2] / "eval"
sys.path.insert(0, str(EVAL_DIR))
run_eval = importlib.import_module("run_eval")

FIXED_NOW = datetime(2026, 10, 29, 12, 0, 0, tzinfo=UTC)
SNAPSHOT_SIZE = 200


class FakeMeter:
    def __init__(self, stopped: bool = False) -> None:
        self.spent_usd = Decimal("1.5")
        self.is_stopped = stopped


class FakeDetector:
    is_available = True

    def __init__(self) -> None:
        self.calls = 0

    async def detect(
        self,
        snapshot: npt.NDArray[np.uint8],
        spoken_name: str,
        known: Sequence[KnownObject],
    ) -> Detection:
        self.calls += 1
        return Detection(
            found_new=True,
            label="mug",
            box=PixelBox(50, 50, 150, 150),
            draft=None,
            text=CardText(),
            source="spark",
        )


class FakeSegmenter:
    is_available = True

    def __init__(self) -> None:
        self.calls = 0

    async def segment(
        self, image: npt.NDArray[np.uint8], prompts: Sequence[ObjectPrompt]
    ) -> SegmentationResult:
        self.calls += 1
        return SegmentationResult()


class ServiceBox:
    def __init__(self, stopped: bool = False) -> None:
        self.factory_calls = 0
        self.detector = FakeDetector()
        self.segmenter = FakeSegmenter()
        self.meter = FakeMeter(stopped)

    def __call__(self) -> object:
        self.factory_calls += 1
        return run_eval.PaidServices(
            meter=self.meter,
            detector=self.detector,
            segmenter=self.segmenter,
            content=ContentFilter(),
        )


def make_deps(tmp_path: Path, services: ServiceBox | None = None) -> object:
    box = services if services is not None else ServiceBox()
    return run_eval.Deps(
        out_dir=tmp_path / "results",
        now=lambda: FIXED_NOW,
        git=lambda: ("abc123", False),
        services=box,
    )


def results(tmp_path: Path, prefix: str) -> list[Path]:
    folder = tmp_path / "results"
    return sorted(folder.glob(f"{prefix}-*.json")) if folder.is_dir() else []


def read_result(tmp_path: Path, prefix: str) -> dict[str, object]:
    found = results(tmp_path, prefix)
    assert len(found) == 1
    data: dict[str, object] = json.loads(found[0].read_text(encoding="utf-8"))
    return data


def write_snapshot(path: Path) -> None:
    rng = np.random.default_rng(0)
    image = rng.integers(0, 255, (SNAPSHOT_SIZE, SNAPSHOT_SIZE, 3), dtype=np.uint8)
    assert cv2.imwrite(str(path), image)


def write_e1_labels(folder: Path) -> Path:
    write_snapshot(folder / "snap.png")
    labels = folder / "labels.json"
    labels.write_text(
        json.dumps(
            {
                "box_unit": "grid",
                "items": [
                    {
                        "snapshot": "snap.png",
                        "spoken_name": "Tasa",
                        "condition": "plain mat",
                        "known": [],
                        "expected_box": [250, 250, 750, 750],
                    }
                ],
            }
        ),
        encoding="utf-8",
    )
    return labels


def run_cli(argv: Sequence[str], deps: object) -> int:
    code: int = run_eval.main(list(argv), deps)
    return code


def test_percentile_uses_nearest_rank() -> None:
    values = [float(v) for v in range(100, 1100, 100)]
    assert run_eval.percentile(values, 50) == 500.0
    assert run_eval.percentile(values, 90) == 900.0
    assert run_eval.percentile([7.0], 90) == 7.0


def test_decide_combines_checks() -> None:
    assert run_eval.decide([True, True]) is True
    assert run_eval.decide([True, None]) is None
    assert run_eval.decide([None, False]) is False


def test_e1_not_run_without_labels(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    box = ServiceBox()
    code = run_cli(
        ["e1", "--labels", str(tmp_path / "missing.json"), "--yes"],
        make_deps(tmp_path, box),
    )
    assert code == 2
    assert "e1: not run:" in capsys.readouterr().out
    assert box.factory_calls == 0
    assert results(tmp_path, "e1") == []


def test_e1_refuses_without_yes_and_prints_estimate(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    labels = write_e1_labels(tmp_path)
    box = ServiceBox()
    code = run_cli(["e1", "--labels", str(labels)], make_deps(tmp_path, box))
    out = capsys.readouterr().out
    assert code == 2
    assert "e1 estimated cost: up to $" in out
    assert "--yes" in out
    assert box.factory_calls == 0
    assert box.detector.calls == 0
    assert results(tmp_path, "e1") == []


def test_e1_refuses_when_the_meter_is_stopped(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    labels = write_e1_labels(tmp_path)
    box = ServiceBox(stopped=True)
    code = run_cli(["e1", "--labels", str(labels), "--yes"], make_deps(tmp_path, box))
    assert code == 2
    assert "cost meter is stopped" in capsys.readouterr().out
    assert box.detector.calls == 0
    assert box.segmenter.calls == 0
    assert results(tmp_path, "e1") == []


def test_e1_scores_with_fake_services(tmp_path: Path) -> None:
    labels = write_e1_labels(tmp_path)
    box = ServiceBox()
    code = run_cli(["e1", "--labels", str(labels), "--yes"], make_deps(tmp_path, box))
    assert code == 0
    data = read_result(tmp_path, "e1")
    assert data["eval"] == "e1"
    assert data["metric"] == 1.0
    assert data["commit"] == "abc123"
    assert data["target"] == 0.9
    assert data["target_met"] is None
    assert data["timestamp_utc"] == FIXED_NOW.isoformat()
    assert results(tmp_path, "e1")[0].name == "e1-20261029T120000Z.json"
    assert box.detector.calls == 1


def test_e1_misses_when_the_box_is_elsewhere(tmp_path: Path) -> None:
    labels = write_e1_labels(tmp_path)
    raw = json.loads(labels.read_text(encoding="utf-8"))
    raw["items"][0]["expected_box"] = [0, 0, 100, 100]
    labels.write_text(json.dumps(raw), encoding="utf-8")
    code = run_cli(["e1", "--labels", str(labels), "--yes"], make_deps(tmp_path))
    assert code == 1
    data = read_result(tmp_path, "e1")
    assert data["metric"] == 0.0
    assert data["target_met"] is False


def test_e2_not_run_without_data(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    box = ServiceBox()
    code = run_cli(
        ["e2", "--data", str(tmp_path / "none.jsonl"), "--yes"],
        make_deps(tmp_path, box),
    )
    assert code == 2
    assert "e2: not run:" in capsys.readouterr().out
    assert box.factory_calls == 0
    assert results(tmp_path, "e2") == []


def write_e2_data(folder: Path) -> Path:
    write_snapshot(folder / "frame.png")
    data = folder / "endturns.jsonl"
    case = {
        "case_id": "c1",
        "frame": "frame.png",
        "px_per_cm": 20,
        "targets": [
            {
                "sam_id": 1,
                "label": "mug",
                "tracker_box": [10, 10, 60, 60],
                "expected_box": [10, 10, 60, 60],
            },
            {
                "sam_id": 2,
                "label": "pen",
                "tracker_box": [100, 100, 150, 150],
                "expected_box": [0, 0, 20, 20],
            },
        ],
    }
    data.write_text(json.dumps(case) + "\n", encoding="utf-8")
    return data


def test_e2_refuses_without_yes(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    data = write_e2_data(tmp_path)
    box = ServiceBox()
    code = run_cli(["e2", "--data", str(data)], make_deps(tmp_path, box))
    out = capsys.readouterr().out
    assert code == 2
    assert "e2 estimated cost" in out
    assert "--yes" in out
    assert box.factory_calls == 0
    assert results(tmp_path, "e2") == []


def test_e2_scores_with_fake_segmenter(tmp_path: Path) -> None:
    data = write_e2_data(tmp_path)
    box = ServiceBox()
    code = run_cli(["e2", "--data", str(data), "--yes"], make_deps(tmp_path, box))
    assert code == 1
    result = read_result(tmp_path, "e2")
    counts = result["counts"]
    assert isinstance(counts, dict)
    assert counts["targets"] == 2
    assert counts["correct"] == 1
    assert result["metric"] == 0.5
    assert result["target_met"] is False
    assert box.segmenter.calls == 2


def test_e2_stops_when_the_meter_is_stopped(tmp_path: Path) -> None:
    data = write_e2_data(tmp_path)
    box = ServiceBox(stopped=True)
    code = run_cli(["e2", "--data", str(data), "--yes"], make_deps(tmp_path, box))
    assert code == 2
    assert box.segmenter.calls == 0
    assert results(tmp_path, "e2") == []


def e3_row(
    transcript: str,
    action: str,
    target: str | None,
    recording: str = "rec1",
    unit: str | None = "u_spear",
) -> str:
    return json.dumps(
        {
            "recording": recording,
            "speaker": "s1",
            "transcript": transcript,
            "expected_unit_id": unit,
            "expected_action": action,
            "expected_target_id": target,
            "context": {
                "units": [
                    {
                        "game_id": "u_spear",
                        "name": "Spearman",
                        "unit_class": "reach",
                        "x_cm": 10.0,
                        "y_cm": 10.0,
                    }
                ],
                "enemies": [
                    {"id": "e_aswang_1", "type": "aswang", "x_cm": 12.0, "y_cm": 12.0}
                ],
            },
        }
    )


def test_e3_not_run_without_labels(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    code = run_cli(
        ["e3", "--labels", str(tmp_path / "none.jsonl")], make_deps(tmp_path)
    )
    assert code == 2
    assert "e3: not run:" in capsys.readouterr().out
    assert results(tmp_path, "e3") == []


def test_e3_requires_a_recording_id(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    labels = tmp_path / "labels.jsonl"
    labels.write_text(
        e3_row("Spearman attack aswang", "attack", "e_aswang_1", "") + "\n", "utf-8"
    )
    code = run_cli(["e3", "--labels", str(labels)], make_deps(tmp_path))
    assert code == 2
    assert "recording" in capsys.readouterr().out


def test_e3_scores_all_three_fields(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    labels = tmp_path / "labels.jsonl"
    lines = [
        e3_row("Spearman attack aswang", "attack", "e_aswang_1"),
        e3_row("tapos", "end_turn", None, unit=None),
        e3_row("Spearman attack aswang", "attack", "e_wrong"),
        e3_row("blah blah", "attack", "e_aswang_1"),
    ]
    labels.write_text("\n".join(lines) + "\n", encoding="utf-8")
    code = run_cli(["e3", "--labels", str(labels)], make_deps(tmp_path))
    assert code == 1
    data = read_result(tmp_path, "e3")
    assert data["counts"] == {"total": 4, "correct": 2}
    assert data["metric"] == 0.5
    assert data["target"] == 0.85
    assert data["target_met"] is False
    conditions = data["conditions"]
    assert isinstance(conditions, dict)
    assert conditions["note"] == "transcripts must come from real recordings"
    misses = data["misses"]
    assert isinstance(misses, list)
    assert len(misses) == 2
    assert "real recordings" in capsys.readouterr().out


def build_db(tmp_path: Path) -> tuple[Path, str]:
    path = tmp_path / "data" / "desktop.sqlite"
    store = Store(path)
    campaign = store.create_campaign("eval", Difficulty.NORMAL)
    night = store.start_or_resume_night(campaign.id)
    store.close()
    return path, night.id


def log_rows(
    path: Path,
    night_id: str,
    rows: Sequence[tuple[int, str, str, dict[str, object], int]],
) -> None:
    store = Store(path)
    for turn, phase, event, payload, t_ms in rows:
        store.log_turn(night_id, turn, phase, event, payload, t_ms)
    store.close()


def test_e4_not_run_without_db(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    code = run_cli(["e4"], make_deps(tmp_path))
    assert code == 2
    assert "e4: not run: pass --db" in capsys.readouterr().out
    code = run_cli(["e4", "--db", str(tmp_path / "none.sqlite")], make_deps(tmp_path))
    assert code == 2
    assert results(tmp_path, "e4") == []


def test_e4_not_run_without_narration_rows(tmp_path: Path) -> None:
    path, _ = build_db(tmp_path)
    assert run_cli(["e4", "--db", str(path)], make_deps(tmp_path)) == 2
    assert results(tmp_path, "e4") == []


def test_e4_formula(tmp_path: Path, capsys: pytest.CaptureFixture[str]) -> None:
    path, night = build_db(tmp_path)
    phase = "resolution_then_telegraph"
    spark: dict[str, object] = {"source": "spark", "phase": phase}
    bank: dict[str, object] = {"source": "line_bank", "phase": phase}
    request: dict[str, object] = {"phase": phase}
    invalid: dict[str, object] = {"reason": "gm_invalid:SchemaError"}
    rows: list[tuple[int, str, str, dict[str, object], int]] = [
        (1, "PLAYER_PHASE", "narration_request", request, 0),
        (1, "PLAYER_PHASE", "narration", spark, 0),
        (2, "PLAYER_PHASE", "narration_request", request, 0),
        (2, "PLAYER_PHASE", "gm_invalid", invalid, 0),
        (2, "PLAYER_PHASE", "narration", spark, 0),
        (3, "PLAYER_PHASE", "narration_request", request, 0),
        (3, "PLAYER_PHASE", "narration", spark, 0),
        (4, "PLAYER_PHASE", "narration_request", request, 0),
        (4, "PLAYER_PHASE", "gm_invalid", invalid, 0),
        (4, "PLAYER_PHASE", "gm_invalid", {"reason": "gm_invalid:UnsafeNarration"}, 0),
        (4, "PLAYER_PHASE", "narration", bank, 0),
        (5, "PLAYER_PHASE", "narration_request", request, 0),
        (0, "SUMMON", "gm_invalid", invalid, 0),
        (6, "PLAYER_PHASE", "gm_invalid", {"reason": "SchemaError"}, 0),
    ]
    log_rows(path, night, rows)
    code = run_cli(["e4", "--db", str(path)], make_deps(tmp_path))
    assert code == 1
    data = read_result(tmp_path, "e4")
    counts = data["counts"]
    assert isinstance(counts, dict)
    assert counts["live_spark_attempts"] == 4
    assert counts["gm_invalid_failures"] == 3
    assert counts["gm_invalid_excluded"] == 2
    assert counts["narration_requests"] == 5
    assert counts["narration_requests_without_row"] == 1
    assert data["metric"] == 0.25
    conditions = data["conditions"]
    assert isinstance(conditions, dict)
    assert conditions["non_blocking"] == 0.8
    assert data["target_met"] is False
    out = capsys.readouterr().out
    assert "1 - 3 gm_invalid / 4 live Spark attempts" in out


def test_e4_without_request_rows_is_undecided(tmp_path: Path) -> None:
    path, night = build_db(tmp_path)
    spark: dict[str, object] = {"source": "spark", "phase": "night_start"}
    log_rows(
        path,
        night,
        [(turn, "PLAYER_PHASE", "narration", spark, 0) for turn in range(1, 4)],
    )
    assert run_cli(["e4", "--db", str(path)], make_deps(tmp_path)) == 0
    data = read_result(tmp_path, "e4")
    assert data["metric"] == 1.0
    assert data["target_met"] is None
    conditions = data["conditions"]
    assert isinstance(conditions, dict)
    assert conditions["non_blocking"] is None


def test_e6_not_run_without_db(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    assert run_cli(["e6"], make_deps(tmp_path)) == 2
    assert "e6: not run:" in capsys.readouterr().out
    assert results(tmp_path, "e6") == []


def test_e6_not_run_with_empty_database(tmp_path: Path) -> None:
    path, _ = build_db(tmp_path)
    assert run_cli(["e6", "--db", str(path)], make_deps(tmp_path)) == 2
    assert results(tmp_path, "e6") == []


def test_e6_percentiles_and_end_turn_duration(tmp_path: Path) -> None:
    path, night = build_db(tmp_path)
    store = Store(path)
    for latency in range(100, 1100, 100):
        store.record_api_usage(
            ApiUsageRecord(
                "muse-spark-1.3", "spark", Decimal("0.001"), True, latency_ms=latency
            )
        )
    store.record_api_usage(
        ApiUsageRecord(
            "muse-spark-1.3", "spark", Decimal("0.001"), False, latency_ms=99999
        )
    )
    store.record_api_usage(
        ApiUsageRecord("sam-3.1", "sam_image", Decimal("0.002"), True, latency_ms=700)
    )
    store.close()
    transition: dict[str, object] = {"from": "X", "event": "y"}
    log_rows(
        path,
        night,
        [
            (1, "END_TURN_SNAPSHOT", "transition", transition, 1000),
            (1, "VALIDATE", "transition", transition, 1500),
            (1, "PLAYER_PHASE", "transition", transition, 3000),
            (8, "END_TURN_SNAPSHOT", "transition", transition, 10000),
            (8, "SUNRISE", "transition", transition, 15000),
            (0, "SUMMON", "summon", {"unit": "u_2"}, 3000),
            (0, "SUMMON", "summon", {"unit": "u_3"}, 4000),
            (1, "PLAYER_PHASE", "narration", {"source": "spark"}, 2000),
            (2, "PLAYER_PHASE", "narration", {"source": "spark"}, 7000),
            (2, "PLAYER_PHASE", "narration", {"source": "line_bank"}, 0),
        ],
    )
    code = run_cli(["e6", "--db", str(path)], make_deps(tmp_path))
    assert code == 1
    data = read_result(tmp_path, "e6")
    by_kind = data["api_usage_by_kind"]
    assert isinstance(by_kind, dict)
    assert by_kind["spark"] == {"n": 10, "p50_ms": 500.0, "p90_ms": 900.0}
    assert by_kind["sam_image"] == {"n": 1, "p50_ms": 700.0, "p90_ms": 700.0}
    by_model = data["api_usage_by_model"]
    assert isinstance(by_model, dict)
    assert by_model["muse-spark-1.3"] == {"n": 10, "p50_ms": 500.0, "p90_ms": 900.0}
    table = data["nfr"]
    assert isinstance(table, list)
    by_nfr = {row["nfr"]: row for row in table}
    assert by_nfr["NFR-03"]["p50_ms"] == 2000.0
    assert by_nfr["NFR-03"]["p90_ms"] == 5000.0
    assert by_nfr["NFR-03"]["met"] is False
    assert by_nfr["NFR-01"]["p90_ms"] == 4000.0
    assert by_nfr["NFR-01"]["met"] is True
    assert by_nfr["NFR-05"]["met"] is None
    assert by_nfr["NFR-08"]["n"] == 2
    assert by_nfr["NFR-08"]["met"] is False
    assert data["target_met"] is False


def test_e6_undecided_when_required_nfrs_are_unmeasured(tmp_path: Path) -> None:
    path, night = build_db(tmp_path)
    transition: dict[str, object] = {"from": "X", "event": "y"}
    log_rows(
        path,
        night,
        [
            (1, "END_TURN_SNAPSHOT", "transition", transition, 0),
            (1, "PLAYER_PHASE", "transition", transition, 1200),
        ],
    )
    assert run_cli(["e6", "--db", str(path)], make_deps(tmp_path)) == 0
    data = read_result(tmp_path, "e6")
    assert data["target_met"] is None
    conditions = data["conditions"]
    assert isinstance(conditions, dict)
    assert "NFR-05" in conditions["unmeasured"]


def test_e7_runs_seeded_boards(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    code = run_cli(["e7", "--boards", "5"], make_deps(tmp_path))
    assert code == 0
    data = read_result(tmp_path, "e7")
    assert data["counts"] == {"boards": 5, "identical": 5, "differing_seeds": []}
    assert data["metric"] == 1.0
    assert data["target_met"] is None
    assert "e7: 5/5 = 100.0% identical" in capsys.readouterr().out


def test_e7_full_set_meets_the_target(tmp_path: Path) -> None:
    assert run_cli(["e7"], make_deps(tmp_path)) == 0
    data = read_result(tmp_path, "e7")
    assert data["metric"] == 1.0
    assert data["target_met"] is True


def test_all_runs_only_offline_evals_with_inputs(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    box = ServiceBox()
    code = run_cli(
        ["all", "--voice-labels", str(tmp_path / "none.jsonl"), "--boards", "3"],
        make_deps(tmp_path, box),
    )
    out = capsys.readouterr().out
    assert code == 0
    assert "e3: not run:" in out
    assert "e4: not run:" in out
    assert "e6: not run:" in out
    assert "e7: 3/3" in out
    assert box.factory_calls == 0
    assert results(tmp_path, "e1") == []
    assert results(tmp_path, "e2") == []
    assert len(results(tmp_path, "e7")) == 1
