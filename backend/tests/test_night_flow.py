import asyncio
from pathlib import Path

import pytest

from db.store import Store, StoreError
from game.night import AppPhase, GameController, GameError
from rules.resolve import Action
from rules.units import Difficulty
from tests.test_night import CONTENT
from tests.test_tracking_flow import ConfidentSegmenter, controller_for, summon_three
from vision.sam import TrackerOnlySegmenter


def start_night(controller: GameController) -> None:
    summon_three(controller)
    controller.begin_night()
    assert controller.snapshot().phase is AppPhase.VOICE_CLAIM
    controller.claim("Migs", ["u_kubo", "u_2"], CONTENT.clean_player_name)
    controller.claim("Bea", ["u_3"], CONTENT.clean_player_name)
    controller.finish_claims()


def test_full_night_reaches_sunrise_or_defeat(tmp_path: Path) -> None:
    store = Store(tmp_path / "db.sqlite")
    controller = controller_for(store, ConfidentSegmenter())
    start_night(controller)
    snapshot = controller.snapshot()
    assert snapshot.phase is AppPhase.PLAYER_PHASE
    assert snapshot.night is not None
    assert snapshot.night.turn == 1
    assert snapshot.night.players == ("Migs", "Bea")
    assert [e.type for e in snapshot.night.enemies] == ["aswang"]
    owners = {u.game_id: u.owner for u in snapshot.night.units}
    assert owners == {"u_kubo": "Migs", "u_2": "Migs", "u_3": "Bea"}
    for _ in range(8):
        if controller.snapshot().phase is not AppPhase.PLAYER_PHASE:
            break
        night = controller.snapshot().night
        assert night is not None
        target = night.enemies[0].id if night.enemies else None
        if target is not None:
            controller.add_intent("u_2", Action.ATTACK, target)
        asyncio.run(controller.end_turn())
    final = controller.snapshot()
    assert final.phase in (AppPhase.SUNRISE, AppPhase.DEFEAT)
    assert final.score is not None
    assert final.campaign is not None
    night_record = store.start_or_resume_night(final.campaign.id)
    assert night_record.number == 2
    controller.close()
    store.close()


def test_turn_log_records_every_transition(tmp_path: Path) -> None:
    store = Store(tmp_path / "db.sqlite")
    controller = controller_for(store, ConfidentSegmenter())
    start_night(controller)
    asyncio.run(controller.end_turn())
    snapshot = controller.snapshot()
    assert snapshot.campaign is not None
    night = store.start_or_resume_night(snapshot.campaign.id)
    assert store.turn_log_count(night.id, "transition") >= 11
    assert (
        store.turn_log_count(night.id, "attack")
        + store.turn_log_count(night.id, "dodge")
        >= 1
    )
    controller.close()
    store.close()


def test_illegal_move_blocks_end_turn(tmp_path: Path) -> None:
    store = Store(tmp_path / "db.sqlite")
    segmenter = ConfidentSegmenter()
    controller = controller_for(store, segmenter)
    start_night(controller)
    segmenter._shift = 400
    asyncio.run(controller.end_turn())
    snapshot = controller.snapshot()
    assert snapshot.phase is AppPhase.PLAYER_PHASE
    assert snapshot.night is not None
    assert set(snapshot.night.illegal_units) >= {"u_2"}
    assert "u_kubo" not in snapshot.night.illegal_units
    assert ("endturn.blocked", {}) in controller.drain_notices()
    assert snapshot.night.turn == 1
    controller.close()
    store.close()


def test_intents_are_validated_server_side(tmp_path: Path) -> None:
    store = Store(tmp_path / "db.sqlite")
    controller = controller_for(store, ConfidentSegmenter())
    start_night(controller)
    night = controller.snapshot().night
    assert night is not None
    enemy = night.enemies[0].id
    with pytest.raises(GameError) as info:
        controller.add_intent("u_kubo", Action.ATTACK, enemy)
    assert info.value.copy_key == "cmd.no_atk"
    with pytest.raises(GameError):
        controller.add_intent("u_9", Action.ATTACK, enemy)
    with pytest.raises(GameError):
        controller.add_intent("u_2", Action.ATTACK, "e_kapre_9")
    controller.add_intent("u_2", Action.ATTACK, enemy)
    controller.add_intent("u_2", Action.ATTACK, enemy)
    chips = controller.snapshot().night.chips  # type: ignore[union-attr]
    assert len(chips) == 1
    controller.cancel_chip(chips[0].chip_id)
    assert controller.snapshot().night.chips == ()  # type: ignore[union-attr]
    with pytest.raises(GameError):
        controller.cancel_chip(chips[0].chip_id)
    controller.close()
    store.close()


def test_night_actions_are_phase_checked(tmp_path: Path) -> None:
    store = Store(tmp_path / "db.sqlite")
    controller = controller_for(store, ConfidentSegmenter())
    summon_three(controller)
    with pytest.raises(GameError):
        controller.finish_claims()
    with pytest.raises(GameError):
        asyncio.run(controller.end_turn())
    controller.begin_night()
    with pytest.raises(GameError):
        controller.begin_night()
    with pytest.raises(GameError):
        controller.add_intent("u_2", Action.ATTACK, None)
    with pytest.raises(GameError):
        controller.next_night()
    controller.close()
    store.close()


def test_begin_night_needs_a_valid_roster(tmp_path: Path) -> None:
    store = Store(tmp_path / "db.sqlite")
    controller = controller_for(store, TrackerOnlySegmenter())
    from tests.test_night import ready_for_summon

    ready_for_summon(controller)
    asyncio.run(controller.summon("Mug"))
    with pytest.raises(GameError) as info:
        controller.begin_night()
    assert info.value.copy_key == "summon.need_units"
    controller.close()
    store.close()


def test_campaign_switch_is_refused_mid_night(tmp_path: Path) -> None:
    store = Store(tmp_path / "db.sqlite")
    controller = controller_for(store, ConfidentSegmenter())
    start_night(controller)
    with pytest.raises(GameError):
        controller.start_new_campaign("Other", Difficulty.NORMAL)
    assert controller.snapshot().phase is AppPhase.PLAYER_PHASE
    controller.close()
    store.close()


def test_end_turn_failure_returns_to_player_phase(tmp_path: Path) -> None:
    store = Store(tmp_path / "db.sqlite")
    controller = controller_for(store, ConfidentSegmenter())
    start_night(controller)

    async def broken() -> dict[int, object]:
        raise OSError("camera unplugged")

    controller.reanchor_all = broken  # type: ignore[method-assign,assignment]
    with pytest.raises(GameError) as info:
        asyncio.run(controller.end_turn())
    assert info.value.copy_key == "restore"
    assert controller.snapshot().phase is AppPhase.PLAYER_PHASE
    controller.close()
    store.close()


def test_autosave_failure_keeps_the_night_playing(tmp_path: Path) -> None:
    store = Store(tmp_path / "db.sqlite")
    controller = controller_for(store, ConfidentSegmenter())
    start_night(controller)

    def failing_autosave(*args: object, **kwargs: object) -> None:
        raise StoreError("disk full")

    store.autosave = failing_autosave  # type: ignore[method-assign]
    asyncio.run(controller.end_turn())
    snapshot = controller.snapshot()
    assert snapshot.phase in (AppPhase.PLAYER_PHASE, AppPhase.DEFEAT)
    assert ("restore", {}) in controller.drain_notices()
    controller.close()
    store.close()


def test_empty_claim_does_not_take_a_player_slot(tmp_path: Path) -> None:
    store = Store(tmp_path / "db.sqlite")
    controller = controller_for(store, ConfidentSegmenter())
    summon_three(controller)
    controller.begin_night()
    with pytest.raises(GameError) as info:
        controller.claim("Ghost", [], CONTENT.clean_player_name)
    assert info.value.copy_key == "claim.who"
    controller.claim("Migs", ["u_2"], CONTENT.clean_player_name)
    controller.claim("Bea", ["u_3"], CONTENT.clean_player_name)
    controller.claim("Migs", [], CONTENT.clean_player_name)
    controller.finish_claims()
    night = controller.snapshot().night
    assert night is not None
    assert night.players == ("Bea",)
    controller.close()
    store.close()


def test_begin_night_refuses_a_half_played_night(tmp_path: Path) -> None:
    store = Store(tmp_path / "db.sqlite")
    controller = controller_for(store, ConfidentSegmenter())
    start_night(controller)
    asyncio.run(controller.end_turn())
    campaign = controller.snapshot().campaign
    controller.close()
    assert campaign is not None
    again = controller_for(store, ConfidentSegmenter())
    again.continue_campaign(campaign.id)
    again.select_camera(0)
    assert again.snapshot().phase is AppPhase.SUMMON
    with pytest.raises(GameError) as info:
        again.begin_night()
    assert info.value.copy_key == "restore"
    again.close()
    store.close()
