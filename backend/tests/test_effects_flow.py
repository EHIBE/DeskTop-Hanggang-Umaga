import asyncio
import contextlib
from pathlib import Path

import pytest

from db.store import Store
from game.night import AppPhase, GameController, GameError, PhysicalEffect
from rules.resolve import Action, Event, EventType
from state import Pose
from tests.test_night_flow import start_night
from tests.test_tracking_flow import ConfidentSegmenter, controller_for


def reach_effects(controller: GameController) -> None:
    for _ in range(8):
        snapshot = controller.snapshot()
        if snapshot.phase is AppPhase.PHYSICAL_EFFECTS:
            return
        assert snapshot.phase is AppPhase.PLAYER_PHASE
        night = snapshot.night
        assert night is not None
        if night.enemies:
            with contextlib.suppress(GameError):
                controller.add_intent("u_2", Action.ATTACK, night.enemies[0].id)
        asyncio.run(controller.end_turn())
    pytest.fail("no physical effect happened")


def test_effects_wait_then_time_out(tmp_path: Path) -> None:
    store = Store(tmp_path / "db.sqlite")
    controller = controller_for(store, ConfidentSegmenter())
    start_night(controller)
    reach_effects(controller)
    night = controller.snapshot().night
    assert night is not None
    assert night.effects
    assert night.effect_seconds_left == 20
    effect = night.effects[0]
    keys = [key for key, _ in controller.drain_notices()]
    assert ("duw.steal" if effect.kind == "steal" else "tik.push") in keys
    if effect.kind == "steal":
        unit = next(u for u in night.units if u.game_id == effect.unit_id)
        assert any(tag.startswith("stolen_by:") for tag in unit.status)
    turn = night.turn
    assert not controller.enforce_effects()
    with pytest.raises(GameError):
        controller.add_intent("u_3", Action.ATTACK, None)
    controller._effects_started -= 21
    assert controller.enforce_effects()
    assert "effect.timeout" in [key for key, _ in controller.drain_notices()]
    after = controller.snapshot()
    assert after.phase in (AppPhase.PLAYER_PHASE, AppPhase.SUNRISE, AppPhase.DEFEAT)
    if after.phase is AppPhase.PLAYER_PHASE:
        assert after.night is not None
        assert after.night.turn == turn + 1
        assert after.night.effects == ()
    controller.close()
    store.close()


def test_tap_finishes_effects_and_tags_survive_autosave(tmp_path: Path) -> None:
    store = Store(tmp_path / "db.sqlite")
    controller = controller_for(store, ConfidentSegmenter())
    start_night(controller)
    with pytest.raises(GameError):
        controller.finish_effects_now()
    reach_effects(controller)
    effect = controller.snapshot().night.effects[0]  # type: ignore[union-attr]
    controller.finish_effects_now()
    assert controller.snapshot().phase is not AppPhase.PHYSICAL_EFFECTS
    campaign = controller.snapshot().campaign
    assert campaign is not None
    if effect.kind == "steal" and controller.snapshot().phase is AppPhase.PLAYER_PHASE:
        night = store.start_or_resume_night(campaign.id)
        saved = store.saved_night(night.id)
        assert saved is not None
        tags = [tag for save in saved.units.values() for tag in save.status]
        assert any(tag.startswith("stolen_by:") for tag in tags)
    controller.close()
    store.close()


def test_effect_compliance_rules() -> None:
    push = PhysicalEffect("push", "u_2", 10.0, 10.0)
    steal = PhysicalEffect("steal", "u_3", 5.0, 5.0)
    done = GameController._is_effect_done
    assert done(push, {"u_2": Pose("u_2", 11.0, 11.0, False)})
    assert not done(push, {"u_2": Pose("u_2", 13.0, 10.0, False)})
    assert not done(push, {"u_2": Pose("u_2", 10.0, 10.0, True)})
    assert not done(push, {})
    assert done(steal, {})
    assert done(steal, {"u_3": Pose("u_3", 5.0, 5.0, True)})
    assert not done(steal, {"u_3": Pose("u_3", 5.0, 5.0, False)})


def test_one_effect_per_unit_and_steal_wins(tmp_path: Path) -> None:
    store = Store(tmp_path / "db.sqlite")
    controller = controller_for(store, ConfidentSegmenter())
    start_night(controller)
    session = controller._session
    assert session is not None and session.board is not None
    events = (
        Event(EventType.PUSH, "e_tikbalang_1", "u_2", pos=(5.0, 5.0)),
        Event(EventType.PUSH, "e_tikbalang_2", "u_2", pos=(9.0, 9.0)),
        Event(EventType.STEAL, "e_duwende_1", "u_3"),
        Event(EventType.PUSH, "e_tikbalang_1", "u_3", pos=(1.0, 1.0)),
        Event(EventType.PUSH, "u_2", "e_aswang_1", pos=(3.0, 3.0)),
    )
    effects = session._physical_effects(session.board, events)
    assert [(e.kind, e.unit_id, e.x_cm) for e in effects] == [
        ("push", "u_2", 9.0),
        ("steal", "u_3", effects[1].x_cm),
    ]
    controller.close()
    store.close()
