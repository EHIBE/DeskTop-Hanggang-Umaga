import asyncio
from pathlib import Path

from db.store import Store
from game.demo_safe import DemoSafeMode
from game.night import AppPhase
from gm.narrator import LineBank, NarrationService
from state import Broadcast
from tests.test_narration_flow import FixedNarrator, claimed, narrations
from tests.test_night_flow import play_one_turn
from tests.test_tracking_flow import ConfidentSegmenter, controller_for


class MemorySettings:
    def __init__(self) -> None:
        self.values: dict[str, str] = {}

    def get_setting(self, key: str) -> str | None:
        return self.values.get(key)

    def set_setting(self, key: str, value: str) -> None:
        self.values[key] = value


def test_defaults_allow_every_paid_call() -> None:
    mode = DemoSafeMode.load(MemorySettings())
    assert mode == DemoSafeMode(is_on=False, is_sam_reanchor_on=True)
    assert mode.allows_spark and mode.allows_image and mode.allows_voice
    assert mode.allows_sam_recovery and mode.allows_sam_reanchor


def test_on_blocks_paid_calls_but_keeps_reanchor_by_default() -> None:
    mode = DemoSafeMode().with_on(True)
    assert not mode.allows_spark
    assert not mode.allows_image
    assert not mode.allows_voice
    assert not mode.allows_sam_recovery
    assert mode.allows_sam_reanchor
    assert not mode.with_sam_reanchor(False).allows_sam_reanchor


def test_reanchor_toggle_only_matters_when_on() -> None:
    assert DemoSafeMode(is_on=False, is_sam_reanchor_on=False).allows_sam_reanchor


def test_settings_round_trip() -> None:
    settings = MemorySettings()
    DemoSafeMode(is_on=True, is_sam_reanchor_on=False).save(settings)
    assert settings.values == {"demo_safe": "1", "demo_safe_sam": "0"}
    assert DemoSafeMode.load(settings) == DemoSafeMode(
        is_on=True, is_sam_reanchor_on=False
    )


def test_demo_safe_night_runs_eight_turns_without_paid_calls(tmp_path: Path) -> None:
    store = Store(tmp_path / "db.sqlite")
    broadcast = Broadcast()
    queue = broadcast.subscribe()
    segmenter = ConfidentSegmenter()
    live = FixedNarrator()
    controller = controller_for(
        store,
        segmenter,
        narration=NarrationService(LineBank(), lambda: live),
        broadcast=broadcast,
    )
    controller.set_demo_safe(True)
    controller.set_demo_safe_sam(False)
    snapshot = controller.snapshot()
    assert snapshot.is_demo_safe and not snapshot.is_demo_safe_sam
    claimed(controller)
    turns = 0
    while controller.snapshot().phase is AppPhase.PLAYER_PHASE:
        play_one_turn(controller)
        turns += 1
    assert controller.snapshot().phase in (AppPhase.SUNRISE, AppPhase.DEFEAT)
    assert 1 <= turns <= 8
    assert segmenter.calls == 0
    assert live.requests == []
    assert {m["source"] for m in narrations(queue)} == {"line_bank"}
    controller.close()
    store.close()


def test_demo_safe_still_reanchors_with_sam_by_default(tmp_path: Path) -> None:
    store = Store(tmp_path / "db.sqlite")
    segmenter = ConfidentSegmenter()
    controller = controller_for(store, segmenter)
    controller.set_demo_safe(True)
    claimed(controller)
    before = segmenter.calls
    asyncio.run(controller.end_turn())
    assert segmenter.calls == before + 1
    controller.close()
    store.close()
