import json
from pathlib import Path

import pytest

from replay.highlights import (
    AnchorSnapshot,
    Highlight,
    RecordingMeta,
    ReplayError,
    TurnLogRow,
    load_recording_meta,
    pick_highlights,
)

START_MS = 10_000


def meta(duration_s: float = 120.0) -> RecordingMeta:
    return RecordingMeta(
        video_path=Path("night.mp4"),
        width=1920,
        height=1080,
        fps=25,
        started_t_ms=START_MS,
        duration_s=duration_s,
        anchors=(AnchorSnapshot(0.0, {"u_1": (10, 10, 50, 50)}),),
        sprites={"u_1": "sprite"},
    )


def row(
    at_s: float,
    event_type: str,
    turn: int = 1,
    **payload: object,
) -> TurnLogRow:
    return TurnLogRow(
        turn=turn,
        phase="enemy",
        event_type=event_type,
        payload=payload,
        t_ms=START_MS + round(at_s * 1000),
    )


def kinds(found: tuple[Highlight, ...]) -> list[str]:
    return [item.kind for item in found]


def test_last_turn_is_always_included_and_anchors_on_the_ending() -> None:
    rows = [
        row(20, "attack", turn=7),
        row(60, "attack", turn=8),
        row(70, "win", turn=8),
    ]
    found = pick_highlights(rows, meta())
    assert kinds(found) == ["last_turn"]
    only = found[0]
    assert only.turn == 8
    assert only.start_s == pytest.approx(67.0)
    assert only.duration_s == pytest.approx(8.0)
    assert [event.type for event in only.events] == ["win"]


def test_kubo_hits_come_before_kills_and_the_cap_applies() -> None:
    rows = [row(10 + 20 * i, "kubo_hit", turn=i + 1, dmg=i + 1) for i in range(5)]
    rows += [row(5, "defeat_enemy"), row(115, "defeat_enemy", turn=8)]
    found = pick_highlights(rows, meta(), max_count=4)
    assert len(found) == 4
    assert "last_turn" in kinds(found)
    assert kinds(found).count("kubo_hit") == 3
    assert "defeat" not in kinds(found)


def test_fr46_priority_order_when_space_is_short() -> None:
    rows = [
        row(10, "push", turn=1),
        row(30, "steal", turn=2),
        row(50, "split", turn=3),
        row(70, "defeat_enemy", turn=4),
        row(90, "kubo_hit", turn=5, dmg=2),
        row(110, "attack", turn=8),
    ]
    found = pick_highlights(rows, meta(), max_count=4)
    assert sorted(kinds(found)) == ["defeat", "kubo_hit", "last_turn", "split"]


def test_all_kinds_fit_in_time_order() -> None:
    rows = [
        row(10, "push", turn=1),
        row(30, "steal", turn=2),
        row(50, "split", turn=3),
        row(70, "defeat_enemy", turn=4),
        row(90, "kubo_hit", turn=5, dmg=2),
        row(110, "win", turn=8),
    ]
    found = pick_highlights(rows, meta())
    assert kinds(found) == [
        "push",
        "steal",
        "split",
        "defeat",
        "kubo_hit",
        "last_turn",
    ]
    starts = [item.start_s for item in found]
    assert starts == sorted(starts)


def test_overlapping_windows_are_skipped_not_doubled() -> None:
    rows = [
        row(30, "kubo_hit", turn=2, dmg=1),
        row(33, "kubo_hit", turn=2, dmg=3),
        row(34, "defeat_enemy", turn=2),
        row(100, "win", turn=8),
    ]
    found = pick_highlights(rows, meta())
    assert kinds(found) == ["kubo_hit", "last_turn"]
    assert found[0].start_s == pytest.approx(30.0)
    assert [event.type for event in found[0].events] == [
        "kubo_hit",
        "kubo_hit",
        "defeat_enemy",
    ]
    assert found[0].events[1].dmg == 3


def test_higher_damage_kubo_hit_is_preferred() -> None:
    rows = [
        row(30, "kubo_hit", turn=2, dmg=1),
        row(33, "kubo_hit", turn=2, dmg=3),
        row(100, "win", turn=8),
    ]
    found = pick_highlights(rows, meta())
    assert found[0].start_s == pytest.approx(30.0)


def test_windows_are_clipped_to_the_recording() -> None:
    rows = [row(1, "defeat_enemy", turn=1), row(118, "win", turn=8)]
    found = pick_highlights(rows, meta(duration_s=120.0))
    assert found[0].start_s == 0.0
    assert found[0].duration_s == pytest.approx(8.0)
    assert found[-1].start_s == pytest.approx(112.0)
    assert found[-1].start_s + found[-1].duration_s <= 120.0


def test_short_recording_clips_the_duration() -> None:
    found = pick_highlights([row(2, "win", turn=8)], meta(duration_s=5.0))
    assert found[0].start_s == 0.0
    assert found[0].duration_s == pytest.approx(5.0)


def test_events_before_the_recording_or_after_it_are_ignored() -> None:
    rows = [
        row(-5, "kubo_hit", turn=1, dmg=9),
        row(200, "kubo_hit", turn=1, dmg=9),
        row(50, "attack", turn=3),
    ]
    found = pick_highlights(rows, meta())
    assert kinds(found) == ["last_turn"]
    assert found[0].turn == 3


def test_event_fields_come_from_the_payload() -> None:
    rows = [row(50, "attack", turn=3, src="u_1", dst="e_1", dmg=4)]
    event = pick_highlights(rows, meta())[0].events[0]
    assert (event.src, event.dst, event.dmg, event.type) == ("u_1", "e_1", 4, "attack")
    assert event.t_s == pytest.approx(50.0)


def test_bad_payload_types_become_none() -> None:
    rows = [row(50, "attack", turn=3, src=7, dst=None, dmg=True)]
    event = pick_highlights(rows, meta())[0].events[0]
    assert (event.src, event.dst, event.dmg) == (None, None, None)


def test_selection_is_deterministic_and_order_independent() -> None:
    rows = [
        row(40, "kubo_hit", turn=2, dmg=2),
        row(80, "split", turn=4),
        row(110, "win", turn=8),
        row(20, "push", turn=1),
    ]
    first = pick_highlights(rows, meta())
    assert pick_highlights(rows, meta()) == first
    assert pick_highlights(list(reversed(rows)), meta()) == first


def test_no_rows_and_bad_limits_give_nothing() -> None:
    assert pick_highlights([], meta()) == ()
    assert pick_highlights([row(5, "win")], meta(), max_count=0) == ()
    assert pick_highlights([row(5, "win")], meta(), window_s=0) == ()


def sidecar_data() -> dict[str, object]:
    return {
        "version": 1,
        "video": "night.mp4",
        "width": 1920,
        "height": 1080,
        "fps": 25,
        "started_t_ms": 10_000,
        "duration_s": 95.5,
        "anchors": [
            {"t_ms": 15_000, "boxes": {"u_2": [10, 20, 110, 220]}},
            {"t_ms": 12_000, "boxes": {"u_1": [1, 2, 3, 4]}},
        ],
        "sprites": {"u_2": "11111111-2222-3333-4444-555555555555"},
    }


def write_sidecar(tmp_path: Path, data: dict[str, object]) -> Path:
    path = tmp_path / "night.json"
    path.write_text(json.dumps(data), encoding="utf-8")
    return path


def test_sidecar_loads_and_converts_anchor_times(tmp_path: Path) -> None:
    loaded = load_recording_meta(write_sidecar(tmp_path, sidecar_data()))
    assert loaded.video_path == tmp_path / "night.mp4"
    assert (loaded.width, loaded.height, loaded.fps) == (1920, 1080, 25)
    assert loaded.started_t_ms == 10_000
    assert loaded.duration_s == 95.5
    assert [a.t_s for a in loaded.anchors] == [2.0, 5.0]
    assert loaded.anchors[1].boxes["u_2"] == (10, 20, 110, 220)
    assert loaded.sprites["u_2"].startswith("1111")


@pytest.mark.parametrize(
    "mutate",
    [
        lambda d: d.update(version=2),
        lambda d: d.update(extra=1),
        lambda d: d.pop("width"),
        lambda d: d.update(width=0),
        lambda d: d.update(duration_s=0),
        lambda d: d.update(video="../night.mp4"),
        lambda d: d.update(video="night.avi"),
        lambda d: d.update(anchors=[{"t_ms": 1, "boxes": {"u": [0, 0, 5]}}]),
        lambda d: d.update(anchors=[{"t_ms": 1, "boxes": {"u": [5, 5, 5, 9]}}]),
        lambda d: d.update(anchors=[{"t_ms": 1, "boxes": {"u": [0, 0, 2000, 9]}}]),
        lambda d: d.update(anchors=[{"t_ms": 1, "boxes": {"u": [0, 0, 5, 9]}, "x": 1}]),
        lambda d: d.update(sprites=[]),
    ],
)
def test_bad_sidecars_raise_replay_error(tmp_path: Path, mutate: object) -> None:
    data = sidecar_data()
    assert callable(mutate)
    mutate(data)
    with pytest.raises(ReplayError):
        load_recording_meta(write_sidecar(tmp_path, data))


def test_missing_and_unparseable_sidecars_raise(tmp_path: Path) -> None:
    with pytest.raises(ReplayError):
        load_recording_meta(tmp_path / "none.json")
    broken = tmp_path / "broken.json"
    broken.write_text("{nope", encoding="utf-8")
    with pytest.raises(ReplayError):
        load_recording_meta(broken)
