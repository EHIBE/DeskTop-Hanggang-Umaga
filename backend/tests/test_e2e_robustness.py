import asyncio
from pathlib import Path
from typing import Any

import pytest

from db.store import Store
from game.night import AppPhase, GameError
from tests.e2e_support import (
    CAMPAIGN_TABLES,
    CONTENT,
    Rig,
    build_rig,
    claim_two_players,
    data_files,
    defend_policy,
    new_night,
    play_to_end,
    play_turn,
    spend,
    start_campaign,
    summon_roster,
    table_counts,
    usage_rows,
)
from tests.test_voice_flow import Voices
from tests.test_voice_session import FakeConnection, FakeConnector, FakeMic
from voice.session import VoiceSession


def board_facts(rig: Rig) -> dict[str, Any]:
    session = rig.controller._session
    assert session is not None and session.board is not None
    board = session.board
    night = rig.snapshot.night
    assert night is not None
    return {
        "turn": night.turn,
        "kubo_hp": night.kubo_hp,
        "units": night.units,
        "enemies": night.enemies,
        "players": night.players,
        "smoke": night.smoke,
        "enemy_counter": board.enemy_counter,
        "defeated": board.enemies_defeated,
        "damage_by_owner": board.damage_by_owner,
        "owners": {u.id: u.owner for u in board.units},
        "hp": {u.id: u.hp for u in board.units},
        "positions": {u.id: u.position for u in board.units},
        "cooldowns": {u.id: u.cooldown for u in board.units},
    }


async def play_turns(rig: Rig, count: int) -> None:
    for _ in range(count):
        await play_turn(rig, defend_policy())


async def resume_and_finish(rig: Rig) -> None:
    rig.align_hands()
    rig.pump()
    await play_to_end(rig, defend_policy())
    await rig.controller.wait_for_background()


def test_pause_quit_continue_restores_the_exact_turn_and_board(tmp_path: Path) -> None:
    rig = build_rig(tmp_path / "data", api_key=False, demo_safe=True)

    async def first_half() -> None:
        rig.controller.bind_loop(asyncio.get_running_loop())
        start_campaign(rig)
        await new_night(rig)
        await play_turns(rig, 3)

    asyncio.run(first_half())
    before = board_facts(rig)
    campaign = rig.snapshot.campaign
    assert campaign is not None and before["turn"] == 4
    rig.controller.pause_night()
    assert rig.phase() is AppPhase.PAUSED
    with pytest.raises(GameError):
        asyncio.run(rig.controller.end_turn())
    rig.controller.quit_paused()
    assert rig.phase() is AppPhase.START
    assert rig.snapshot.campaign is None and rig.snapshot.night is None
    again = build_rig(rig.root, store=rig.store, api_key=False, demo_safe=True)
    rig.controller.close()

    async def second_half() -> None:
        again.controller.bind_loop(asyncio.get_running_loop())
        again.controller.continue_campaign(campaign.id)
        again.controller.select_camera(0)
        assert again.phase() is AppPhase.SUMMON
        assert again.snapshot.resume_turn == 4
        again.controller.begin_night()
        assert again.phase() is AppPhase.PLAYER_PHASE
        assert again.snapshot.resume_turn is None
        assert board_facts(again) == before
        assert ("restore", {}) in again.controller.drain_notices()
        await resume_and_finish(again)

    asyncio.run(second_half())
    assert again.snapshot.phase is AppPhase.SUNRISE

    straight = build_rig(tmp_path / "straight", api_key=False, demo_safe=True)

    async def uninterrupted() -> None:
        straight.controller.bind_loop(asyncio.get_running_loop())
        start_campaign(straight)
        await new_night(straight)
        await play_to_end(straight, defend_policy())
        await straight.controller.wait_for_background()

    asyncio.run(uninterrupted())
    assert again.snapshot.score == straight.snapshot.score
    again.close()
    straight.close()


def test_a_crash_mid_turn_restores_the_start_of_that_turn(tmp_path: Path) -> None:
    rig = build_rig(tmp_path / "data", api_key=False, demo_safe=True)

    async def play() -> None:
        rig.controller.bind_loop(asyncio.get_running_loop())
        start_campaign(rig)
        await new_night(rig)
        await play_turns(rig, 2)

    asyncio.run(play())
    at_turn_start = board_facts(rig)
    campaign = rig.snapshot.campaign
    assert campaign is not None and at_turn_start["turn"] == 3
    defend_policy()(rig)
    rig.pump()
    mid_turn = rig.snapshot.night
    assert mid_turn is not None and mid_turn.chips

    survivor = Store(rig.root / "db.sqlite")
    crashed = build_rig(rig.root, store=survivor, api_key=False, demo_safe=True)

    async def recover() -> None:
        crashed.controller.bind_loop(asyncio.get_running_loop())
        crashed.controller.continue_campaign(campaign.id)
        crashed.controller.select_camera(0)
        assert crashed.snapshot.resume_turn == 3
        crashed.controller.begin_night()
        restored = board_facts(crashed)
        assert crashed.snapshot.night is not None
        assert crashed.snapshot.night.chips == ()
        assert restored == at_turn_start
        await resume_and_finish(crashed)

    asyncio.run(recover())
    assert crashed.snapshot.phase in (AppPhase.SUNRISE, AppPhase.DEFEAT)
    rig.controller.close()
    crashed.close()
    rig.store.close()


async def unplug(rig: Rig) -> None:
    camera = rig.controller._camera
    assert camera is not None
    rig.camera.is_plugged = False
    for _ in range(100):
        if camera.has_failed:
            return
        await asyncio.sleep(0.01)
    raise AssertionError("the camera never reported the failure")


def test_a_replugged_camera_lets_the_night_continue(tmp_path: Path) -> None:
    rig = build_rig(tmp_path / "data", api_key=False, demo_safe=True)

    async def play() -> None:
        rig.controller.bind_loop(asyncio.get_running_loop())
        start_campaign(rig)
        await new_night(rig)
        await play_turn(rig, defend_policy())
        await unplug(rig)
        rig.camera.is_plugged = True
        rig.controller.select_camera(0)
        assert rig.phase() is AppPhase.PLAYER_PHASE
        rig.pump()
        await play_turn(rig, defend_policy())
        assert rig.snapshot.night.turn == 3  # type: ignore[union-attr]
        assert rig.snapshot.night.illegal_units == ()  # type: ignore[union-attr]

    asyncio.run(play())
    rig.close()


@pytest.mark.xfail(
    strict=True,
    reason="BUG: End Turn accepts the last stale frame after the camera feed died",
)
def test_end_turn_refuses_when_the_camera_feed_is_dead(tmp_path: Path) -> None:
    rig = build_rig(tmp_path / "data", api_key=False, demo_safe=True)

    async def play() -> None:
        rig.controller.bind_loop(asyncio.get_running_loop())
        start_campaign(rig)
        await new_night(rig)
        await play_turn(rig, defend_policy())
        await unplug(rig)
        defend_policy()(rig)
        with pytest.raises(GameError):
            await rig.controller.end_turn()
        assert rig.snapshot.night.turn == 2  # type: ignore[union-attr]

    asyncio.run(play())
    rig.close()


def real_voice(rig: Rig, plan: list[Any], mic_error: bool) -> None:
    connector = FakeConnector(plan)

    async def instant(_: float) -> None:
        return None

    def factory(*callbacks: Any) -> VoiceSession:
        keywords, on_caption, on_final, on_overlap, on_status = callbacks
        return VoiceSession(
            "sk-fake",
            keywords,
            lambda: FakeMic(total=None, error=mic_error),
            connector,
            on_caption,
            on_final,
            on_overlap,
            on_status,
            rig.meter,
            rig.clock,
            sleep=instant,
        )

    rig.controller._voice_factory = factory


def test_a_voice_session_error_leaves_tap_play_working(tmp_path: Path) -> None:
    rig = build_rig(tmp_path / "data", api_key=True, demo_safe=False)
    real_voice(rig, [FakeConnection(hang=True), FakeConnection(hang=True)], True)

    async def play() -> None:
        rig.controller.bind_loop(asyncio.get_running_loop())
        start_campaign(rig)
        await summon_roster(rig)
        claim_two_players(rig.controller)
        rig.pump()
        for _ in range(20):
            await asyncio.sleep(0)
            if rig.snapshot.voice.status == "down":
                break
        assert rig.snapshot.voice.status == "down"
        assert ("net.down", {}) in rig.controller.drain_notices()
        await play_turn(rig, defend_policy())
        assert rig.snapshot.night.turn == 2  # type: ignore[union-attr]
        assert rig.phase() is AppPhase.PLAYER_PHASE
        rig.controller.close()
        await rig.controller.wait_for_voice()

    asyncio.run(play())
    rig.store.close()


def test_hard_stop_mid_night_switches_to_demo_safe_and_stops_paid_calls(
    tmp_path: Path,
) -> None:
    rig = build_rig(tmp_path / "data", api_key=True, demo_safe=False)
    stopped_after: dict[str, int] = {}

    async def play() -> None:
        rig.controller.bind_loop(asyncio.get_running_loop())
        start_campaign(rig)
        await new_night(rig)
        await rig.controller.wait_for_narration()
        await play_turns(rig, 2)
        await rig.controller.wait_for_narration()
        assert rig.snapshot.is_demo_safe is False
        assert len(rig.sdk.calls) > 0
        spend(rig.meter, "121")
        assert rig.meter.is_stopped
        stopped_after["calls"] = len(rig.sdk.calls)
        stopped_after["rows"] = len(usage_rows(rig.store))
        rig.drain()
        await play_to_end(rig, defend_policy(), rig.controller.wait_for_narration)
        await rig.controller.wait_for_background()

    asyncio.run(play())
    assert rig.snapshot.is_demo_safe is True
    assert rig.store.get_setting("demo_safe") == "1"
    assert ("credits.low", {}) in rig.controller.drain_notices()
    assert len(rig.sdk.calls) == stopped_after["calls"]
    assert len(usage_rows(rig.store)) == stopped_after["rows"]
    assert rig.snapshot.phase in (AppPhase.SUNRISE, AppPhase.DEFEAT)
    narrations = [m for m in rig.of_type("narration") if m["turn"] != 1]
    assert narrations
    assert narrations[-1]["source"] == "line_bank"
    saved = rig.store.get_recap(rig.snapshot.campaign.id)  # type: ignore[union-attr]
    assert saved is not None and saved.source == "line_bank"
    rig.close()


def say(voices: Voices, text: str, speaker: str) -> None:
    voices.made[0].say(text, speaker)


def test_strict_ownership_confirm_cancel_and_timeout_in_a_night(tmp_path: Path) -> None:
    rig = build_rig(tmp_path / "data", api_key=True, demo_safe=False)
    voices = Voices()
    rig.controller._voice_factory = voices  # type: ignore[assignment]
    order = "Stapler, atake ang aswang!"

    async def play() -> None:
        rig.controller.bind_loop(asyncio.get_running_loop())
        start_campaign(rig)
        await summon_roster(rig)
        rig.controller.set_setting("strict_ownership", True)
        rig.controller.begin_night()
        await asyncio.sleep(0)
        say(voices, "Ako si Migs, hawak ko ang Stapler", "spk_0")
        say(voices, "Ako si Bea, hawak ko ang Phone", "spk_1")
        rig.controller.finish_claims()
        rig.pump()
        night = rig.snapshot.night
        assert night is not None and night.players == ("Migs", "Bea")
        assert {u.game_id: u.owner for u in night.units}["u_2"] == "Migs"

        say(voices, order, "spk_1")
        pending = rig.snapshot.pending_confirm
        assert pending is not None
        assert (pending.owner, pending.unit_id, pending.speaker) == (
            "Migs",
            "u_2",
            "Bea",
        )
        assert rig.snapshot.night.chips == ()  # type: ignore[union-attr]
        rig.controller.confirm_order(pending.confirm_id, False)
        assert rig.snapshot.pending_confirm is None
        assert rig.snapshot.night.chips == ()  # type: ignore[union-attr]

        say(voices, order, "spk_1")
        assert rig.snapshot.pending_confirm is not None
        assert rig.controller.enforce_confirm_timeout() is False
        rig.clock.advance(60.0)
        assert rig.controller.enforce_confirm_timeout() is True
        assert rig.snapshot.pending_confirm is None
        assert rig.snapshot.night.chips == ()

        say(voices, order, "spk_1")
        pending = rig.snapshot.pending_confirm
        assert pending is not None
        rig.controller.confirm_order(pending.confirm_id, True)
        chips = rig.snapshot.night.chips
        assert [(c.unit_id, c.source, c.speaker) for c in chips] == [
            ("u_2", "voice", "Bea")
        ]
        with pytest.raises(GameError):
            rig.controller.confirm_order(pending.confirm_id, True)

        say(voices, order, "spk_0")
        assert rig.snapshot.pending_confirm is None
        say(voices, "Phone, atake ang aswang!", "spk_0")
        assert rig.snapshot.pending_confirm is not None
        rig.pump()
        await rig.controller.end_turn()
        assert rig.snapshot.pending_confirm is None
        assert rig.snapshot.night.turn == 2
        rig.controller.close()
        await rig.controller.wait_for_voice()

    asyncio.run(play())
    rig.store.close()


def test_claim_phase_times_out_into_the_night(tmp_path: Path) -> None:
    rig = build_rig(tmp_path / "data", api_key=False, demo_safe=True)

    async def play() -> None:
        start_campaign(rig)
        await summon_roster(rig)
        rig.controller.begin_night()
        rig.controller.claim("Migs", ["u_2"], CONTENT.clean_player_name)
        assert rig.controller.enforce_claim_timeout() is False
        rig.clock.advance(61.0)
        assert rig.controller.enforce_claim_timeout() is True

    asyncio.run(play())
    assert rig.phase() is AppPhase.PLAYER_PHASE
    assert rig.snapshot.night.players == ("Migs",)  # type: ignore[union-attr]
    rig.close()


def test_deleting_a_campaign_removes_every_row_and_file(tmp_path: Path) -> None:
    rig = build_rig(tmp_path / "data", api_key=True, demo_safe=False)

    async def play() -> None:
        rig.controller.bind_loop(asyncio.get_running_loop())
        start_campaign(rig)
        await new_night(rig)
        await rig.controller.wait_for_sprites()
        await play_to_end(rig, defend_policy(), rig.controller.wait_for_narration)
        await rig.controller.wait_for_background()

    asyncio.run(play())
    campaign = rig.snapshot.campaign
    assert campaign is not None
    with pytest.raises(GameError):
        rig.controller.delete_campaign(campaign.id)
    rig.controller.quit_night()
    root = rig.root
    before = data_files(root)
    assert any(name.startswith("sprites/") for name in before)
    assert any(name.startswith("campaigns/") for name in before)
    populated = table_counts(rig.store)
    assert all(populated[t] > 0 for t in CAMPAIGN_TABLES if t != "voice_map")
    assert [c.id for c in rig.controller.list_campaigns()] == [campaign.id]
    spent = rig.store.total_api_cost()
    rig.controller.delete_campaign(campaign.id)
    assert rig.controller.list_campaigns() == []
    assert table_counts(rig.store) == {t: 0 for t in CAMPAIGN_TABLES}
    assert data_files(root) == [
        name for name in data_files(root) if name.startswith("db.sqlite")
    ]
    assert rig.store.total_api_cost() == spent
    rig.close()
