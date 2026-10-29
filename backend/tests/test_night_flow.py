import asyncio
import contextlib
from pathlib import Path

import numpy as np
import pytest

from db.store import Store, StoreError
from game.night import AppPhase, GameController, GameError
from rules.resolve import Action
from rules.units import Difficulty
from state import Broadcast
from tests.test_night import CONTENT
from tests.test_server import SHEET
from tests.test_tracking_flow import ConfidentSegmenter, controller_for, summon_three
from vision.sam import TrackerOnlySegmenter


def start_night(controller: GameController) -> None:
    summon_three(controller)
    controller.begin_night()
    assert controller.snapshot().phase is AppPhase.VOICE_CLAIM
    controller.claim("Migs", ["u_kubo", "u_2"], CONTENT.clean_player_name)
    controller.claim("Bea", ["u_3"], CONTENT.clean_player_name)
    controller.finish_claims()


def play_one_turn(controller: GameController) -> None:
    night = controller.snapshot().night
    assert night is not None
    if night.enemies:
        with contextlib.suppress(GameError):
            controller.add_intent("u_2", Action.ATTACK, night.enemies[0].id)
    asyncio.run(controller.end_turn())
    if controller.snapshot().phase is AppPhase.PHYSICAL_EFFECTS:
        controller.finish_effects_now()


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
        play_one_turn(controller)
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

    async def broken(_: object = None) -> dict[int, object]:
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


def play_turns(controller: GameController, turns: int) -> None:
    for _ in range(turns):
        if controller.snapshot().phase is not AppPhase.PLAYER_PHASE:
            return
        play_one_turn(controller)


def test_restart_resumes_the_saved_turn_exactly(tmp_path: Path) -> None:
    store = Store(tmp_path / "db.sqlite")
    controller = controller_for(store, ConfidentSegmenter())
    start_night(controller)
    play_turns(controller, 2)
    before = controller.snapshot()
    board_before = controller._session.board  # type: ignore[union-attr]
    assert before.phase is AppPhase.PLAYER_PHASE
    assert before.night is not None
    assert before.night.turn == 3
    campaign = before.campaign
    controller.close()
    assert campaign is not None
    again = controller_for(store, ConfidentSegmenter())
    again.continue_campaign(campaign.id)
    again.select_camera(0)
    summon = again.snapshot()
    assert summon.phase is AppPhase.SUMMON
    assert summon.resume_turn == 3
    with pytest.raises(GameError) as info:
        asyncio.run(again.summon("Extra"))
    assert info.value.copy_key == "restore"
    again.begin_night()
    after = again.snapshot()
    assert after.phase is AppPhase.PLAYER_PHASE
    assert after.resume_turn is None
    assert after.night is not None
    assert after.night.turn == 3
    assert after.night.players == before.night.players
    assert after.night.units == before.night.units
    assert after.night.enemies == before.night.enemies
    assert after.night.kubo_hp == before.night.kubo_hp
    board_after = again._session.board  # type: ignore[union-attr]
    assert board_after is not None and board_before is not None
    assert board_after.enemy_counter == board_before.enemy_counter
    assert board_after.enemies_defeated == board_before.enemies_defeated
    assert board_after.damage_by_owner == board_before.damage_by_owner
    assert ("restore", {}) in again.drain_notices()
    night = store.start_or_resume_night(campaign.id)
    assert store.turn_log_count(night.id, "restore") == 1
    play_turns(again, 6)
    assert again.snapshot().phase in (AppPhase.SUNRISE, AppPhase.DEFEAT)
    again.close()
    store.close()


def test_restore_rejects_a_corrupt_board(tmp_path: Path) -> None:
    store = Store(tmp_path / "db.sqlite")
    controller = controller_for(store, ConfidentSegmenter())
    start_night(controller)
    play_turns(controller, 1)
    campaign = controller.snapshot().campaign
    controller.close()
    assert campaign is not None
    night = store.start_or_resume_night(campaign.id)
    with store.transaction() as conn:
        conn.execute(
            "UPDATE night SET board_json = ? WHERE id = ?",
            ('{"enemy_counter": [1, 2]}', night.id),
        )
    again = controller_for(store, ConfidentSegmenter())
    again.continue_campaign(campaign.id)
    again.select_camera(0)
    with pytest.raises(GameError) as info:
        again.begin_night()
    assert info.value.copy_key == "restore"
    assert again.snapshot().phase is AppPhase.SUMMON
    again.close()
    store.close()


def test_interrupted_night_ends_like_an_uninterrupted_one(tmp_path: Path) -> None:
    straight_store = Store(tmp_path / "a" / "db.sqlite")
    straight = controller_for(straight_store, ConfidentSegmenter())
    start_night(straight)
    play_turns(straight, 8)
    expected = straight.snapshot()
    straight.close()
    straight_store.close()
    store = Store(tmp_path / "b" / "db.sqlite")
    first = controller_for(store, ConfidentSegmenter())
    start_night(first)
    play_turns(first, 1)
    assert first.snapshot().phase is AppPhase.PLAYER_PHASE
    campaign = first.snapshot().campaign
    first.close()
    assert campaign is not None
    second = controller_for(store, ConfidentSegmenter())
    second.continue_campaign(campaign.id)
    second.select_camera(0)
    second.begin_night()
    assert second.snapshot().night.turn == 2  # type: ignore[union-attr]
    play_turns(second, 8)
    final = second.snapshot()
    assert final.phase is expected.phase
    assert final.score == expected.score
    second.close()
    store.close()


def test_pause_blocks_orders_until_resume(tmp_path: Path) -> None:
    store = Store(tmp_path / "db.sqlite")
    controller = controller_for(store, ConfidentSegmenter())
    start_night(controller)
    controller.pause_night()
    assert controller.snapshot().phase is AppPhase.PAUSED
    with pytest.raises(GameError):
        asyncio.run(controller.end_turn())
    with pytest.raises(GameError):
        controller.pause_night()
    controller.resume_night(is_forced=False)
    assert controller.snapshot().phase is AppPhase.PLAYER_PHASE
    with pytest.raises(GameError):
        controller.resume_night(is_forced=False)
    asyncio.run(controller.end_turn())
    assert controller.snapshot().night.turn == 2  # type: ignore[union-attr]
    controller.close()
    store.close()


def test_moved_camera_pauses_end_turn(tmp_path: Path) -> None:
    store = Store(tmp_path / "db.sqlite")
    controller = controller_for(store, ConfidentSegmenter())
    start_night(controller)
    baseline = controller._baseline
    assert baseline is not None
    controller._baseline = np.roll(baseline, 120, axis=1)
    asyncio.run(controller.end_turn())
    snapshot = controller.snapshot()
    assert snapshot.phase is AppPhase.PAUSED
    assert snapshot.night is not None
    assert snapshot.night.turn == 1
    assert ("cam.moved", {}) in controller.drain_notices()
    with pytest.raises(GameError) as info:
        controller.resume_night(is_forced=False)
    assert info.value.copy_key == "cam.moved"
    controller.resume_night(is_forced=True)
    assert controller.snapshot().phase is AppPhase.PLAYER_PHASE
    asyncio.run(controller.end_turn())
    assert controller.snapshot().night.turn == 2  # type: ignore[union-attr]
    controller.close()
    store.close()


def test_voice_claim_ends_after_the_timeout(tmp_path: Path) -> None:
    store = Store(tmp_path / "db.sqlite")
    broadcast = Broadcast()
    queue = broadcast.subscribe()
    controller = controller_for(store, ConfidentSegmenter(), broadcast=broadcast)
    summon_three(controller)
    controller.begin_night()
    controller.claim("Migs", ["u_2"], CONTENT.clean_player_name)
    assert not controller.enforce_claim_timeout()
    assert controller.snapshot().phase is AppPhase.VOICE_CLAIM
    controller._claim_started -= 61.0
    assert controller.enforce_claim_timeout()
    assert controller.snapshot().phase is AppPhase.PLAYER_PHASE
    assert controller.snapshot().night.players == ("Migs",)  # type: ignore[union-attr]
    types = []
    while not queue.empty():
        types.append(queue.get_nowait()["type"])
    assert types[-1] == "state.changed"
    assert not controller.enforce_claim_timeout()
    controller.close()
    store.close()


def test_recalibrate_while_paused_resumes_the_same_night(tmp_path: Path) -> None:
    store = Store(tmp_path / "db.sqlite")
    controller = controller_for(store, ConfidentSegmenter())
    start_night(controller)
    play_turns(controller, 1)
    controller.pause_night()
    before = controller.snapshot().night
    controller.restart_calibration()
    assert controller.snapshot().phase is AppPhase.CALIBRATE
    controller.submit_corners(SHEET, 60.0, 40.0)
    controller.confirm_calibration()
    paused = controller.snapshot()
    assert paused.phase is AppPhase.PAUSED
    assert paused.resume_turn is None
    assert paused.night is not None and before is not None
    assert paused.night.turn == before.turn
    assert paused.night.enemies == before.enemies
    controller.resume_night(is_forced=False)
    play_one_turn(controller)
    assert controller.snapshot().night.turn == before.turn + 1  # type: ignore[union-attr]
    controller.close()
    store.close()


def test_recalibrate_is_refused_mid_turn(tmp_path: Path) -> None:
    store = Store(tmp_path / "db.sqlite")
    controller = controller_for(store, ConfidentSegmenter())
    start_night(controller)
    with pytest.raises(GameError):
        controller.restart_calibration()
    assert controller.snapshot().phase is AppPhase.PLAYER_PHASE
    controller.close()
    store.close()
