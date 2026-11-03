import asyncio
import json
from pathlib import Path
from typing import Any

import pytest

from game.night import AppPhase, GameError
from gm.narrator import LineBank
from gm.recap import Recap, RecapSource
from rules.progression import Badge
from rules.resolve import Action
from server import state_json
from tests.e2e_support import (
    CARD_FIGHTER,
    CARD_SCOUT,
    FALL_LAYOUT,
    OBJECT_NAMES,
    Rig,
    build_rig,
    centre_of,
    claim_two_players,
    defend_policy,
    idle_policy,
    install_anchor_override,
    new_night,
    night_id_of,
    play_to_end,
    play_turn,
    start_campaign,
    view_units,
)


def reopen(rig: Rig) -> Rig:
    rig.controller.close()
    return build_rig(rig.root, store=rig.store, api_key=False, demo_safe=True)


async def first_night(rig: Rig) -> None:
    rig.controller.bind_loop(asyncio.get_running_loop())
    start_campaign(rig)
    await new_night(rig)
    await play_to_end(rig, defend_policy())
    await rig.controller.wait_for_background()


def after_first_night(root: Path) -> Rig:
    rig = build_rig(root / "data", api_key=False, demo_safe=True)
    asyncio.run(first_night(rig))
    assert rig.phase() is AppPhase.SUNRISE
    return rig


async def summon_again(rig: Rig) -> dict[str, Any]:
    views: dict[str, Any] = {}
    for name, box in zip(OBJECT_NAMES, rig.boxes, strict=True):
        try:
            views[name] = await rig.controller.summon(name)
        except GameError as error:
            assert error.copy_key == "summon.which"
            views[name] = await rig.controller.summon_tap(centre_of(box))
    return views


def test_second_night_recaps_matches_returning_objects_and_levels_up(
    tmp_path: Path,
) -> None:
    rig = after_first_night(tmp_path)
    first = rig.snapshot
    assert first.campaign is not None and first.progression is not None
    campaign_id = first.campaign.id
    assert (first.campaign.barrio_level, first.campaign.nights_survived) == (1, 1)
    first_units = view_units(first)
    downed = sorted(g for g, u in first_units.items() if u.is_down and g != "u_kubo")
    survivors = sorted(
        g for g, u in first_units.items() if not u.is_down and g != "u_kubo"
    )
    assert downed == ["u_3", "u_4"] and survivors == ["u_2"]
    offers = {o.unit_id: o.choices for o in first.progression.badge_offers}
    assert offers == {"u_kubo": ("hp",), "u_2": ("hp", "cooldown")}
    rig.controller.pick_badge("u_kubo", Badge.HP)
    rig.controller.pick_badge("u_2", Badge.COOLDOWN)
    records = {u.card.name: u for u in rig.controller._units}
    scarred = {records["Phone"].unit_id, records["Mug"].unit_id}
    for record in records.values():
        scars = rig.store.get_unit_progress(record.unit_id).scars
        assert scars == (("s1",) if record.unit_id in scarred else ())
    saved = rig.store.get_recap(campaign_id)
    assert saved is not None
    recap = Recap.from_json(saved.text)
    assert recap.text_tl.startswith("Kagabi")
    assert recap.source is RecapSource.LINE_BANK

    again = reopen(rig)

    async def second_night() -> None:
        again.controller.bind_loop(asyncio.get_running_loop())
        again.controller.continue_campaign(campaign_id)
        assert again.snapshot.recap == recap
        assert state_json(again.snapshot)["recap"] == recap.to_dict()
        assert again.snapshot.campaign is not None
        assert again.snapshot.campaign.barrio_level == 1
        again.controller.select_camera(0)
        assert again.phase() is AppPhase.SUMMON
        assert again.snapshot.recap == recap
        views = await summon_again(again)
        for name, view in views.items():
            assert view.is_returning is True
            assert view.unit_id == records[name].unit_id
            assert view.scars == (1 if records[name].unit_id in scarred else 0)
        assert views["Bahay Kubo"].badges == ("hp",)
        assert views["Stapler"].badges == ("cooldown",)
        claim_two_players(again.controller)
        again.pump()
        assert again.snapshot.recap is None
        assert again.store.get_recap(campaign_id) is None
        night = again.snapshot.night
        assert night is not None and night.number == 2 and night.turn == 1
        now = view_units(again.snapshot)
        assert now["u_kubo"].hp_max == first_units["u_kubo"].hp_max + 1
        assert now["u_kubo"].badges == ("hp",)
        assert now["u_2"].cooldown_cut == 1
        for game_id in downed:
            assert now[game_id].scars == 1
            assert now[game_id].hp_max == first_units[game_id].hp_max - 1
            assert now[game_id].hp == now[game_id].hp_max
        assert again.snapshot.progression is not None
        assert again.snapshot.progression.barrio_level == 1
        await play_to_end(again, defend_policy())
        await again.controller.wait_for_background()

    asyncio.run(second_night())
    final = again.snapshot
    assert final.phase is AppPhase.SUNRISE
    assert final.progression is not None
    assert (final.progression.barrio_level, final.progression.nights_survived) == (2, 2)
    assert final.campaign is not None
    assert (final.campaign.barrio_level, final.campaign.nights_survived) == (2, 2)
    assert night_id_of(again.store, 2) != night_id_of(again.store, 1)
    newer = again.store.get_recap(campaign_id)
    assert newer is not None and json.loads(newer.text)["night"] == 2
    again.close()


def test_next_night_in_the_same_session_levels_the_barrio_up(tmp_path: Path) -> None:
    rig = after_first_night(tmp_path)
    rig.controller.pick_badge("u_kubo", Badge.HP)
    rig.controller.next_night()
    assert rig.phase() is AppPhase.SUMMON
    rig.hands.reset(rig.boxes)

    async def second() -> None:
        rig.controller.bind_loop(asyncio.get_running_loop())
        await new_night(rig)
        assert rig.snapshot.progression is not None
        assert rig.snapshot.progression.barrio_level == 1
        await play_to_end(rig, defend_policy())
        await rig.controller.wait_for_background()

    asyncio.run(second())
    final = rig.snapshot
    assert final.phase is AppPhase.SUNRISE
    assert final.progression is not None
    assert (final.progression.barrio_level, final.progression.nights_survived) == (2, 2)
    rig.close()


def test_defeat_when_the_kubo_falls_saves_the_recap_and_scars(tmp_path: Path) -> None:
    rig = build_rig(
        tmp_path / "data", api_key=False, demo_safe=True, layout=FALL_LAYOUT
    )

    async def play() -> list[int]:
        rig.controller.bind_loop(asyncio.get_running_loop())
        start_campaign(rig)
        await new_night(rig)
        turns = await play_to_end(rig, idle_policy)
        await rig.controller.wait_for_background()
        return turns

    turns = asyncio.run(play())
    final = rig.snapshot
    assert final.phase is AppPhase.DEFEAT
    assert turns[-1] < 8
    assert final.night is not None
    units = view_units(final)
    assert final.night.kubo_hp == 0 and units["u_kubo"].is_down
    assert final.score is not None and final.score.kubo_hp == 0
    assert final.progression is not None
    assert final.progression.nights_survived == 0
    assert final.progression.badge_offers == ()
    assert final.campaign is not None
    assert (final.campaign.barrio_level, final.campaign.nights_survived) == (0, 0)
    saved = rig.store.get_recap(final.campaign.id)
    assert saved is not None
    recap = Recap.from_json(saved.text)
    assert recap.text_tl.startswith("Kagabi")
    assert recap.night == 1
    assert recap.mood in {mood for _, _, mood in LineBank().lines("recap_lose")}
    by_game = {
        "u_kubo" if u.sam_object_id == 1 else f"u_{u.sam_object_id}": u
        for u in rig.controller._units
    }
    downed = [g for g, u in units.items() if u.is_down and g != "u_kubo"]
    assert downed
    for game_id, view in units.items():
        if game_id == "u_kubo":
            continue
        scars = rig.store.get_unit_progress(by_game[game_id].unit_id).scars
        assert scars == (("s1",) if view.is_down else ())
    rig.controller.quit_night()
    rig.controller.continue_campaign(final.campaign.id)
    assert rig.snapshot.recap == recap
    rig.close()


def test_kapre_smoke_comes_on_its_turns_and_p08_clears_it(tmp_path: Path) -> None:
    rig = build_rig(
        tmp_path / "data",
        api_key=True,
        demo_safe=False,
        drafts=(CARD_FIGHTER, CARD_SCOUT, CARD_FIGHTER, CARD_FIGHTER),
    )
    smoke_at: dict[int, int] = {}
    kapre_at: dict[int, bool] = {}
    base = defend_policy(spare=("kapre",))

    def clear_smoke(rig: Rig) -> None:
        base(rig)
        night = rig.snapshot.night
        assert night is not None
        if night.turn != 5:
            return
        cloud = night.smoke[0]
        scout = next(u for u in night.units if u.game_id == "u_2")
        dx, dy = cloud.x_cm - scout.start[0], cloud.y_cm - scout.start[1]
        length = max((dx * dx + dy * dy) ** 0.5, 1e-6)
        step = min(scout.move_cm * 0.8, max(0.0, length - 4.0))
        rig.hands.move_cm(
            2, scout.start[0] + dx / length * step, scout.start[1] + dy / length * step
        )
        rig.controller.add_intent("u_2", Action.POWER, None)

    async def play() -> None:
        rig.controller.bind_loop(asyncio.get_running_loop())
        start_campaign(rig)
        await new_night(rig)
        while rig.phase() is AppPhase.PLAYER_PHASE:
            night = rig.snapshot.night
            assert night is not None
            smoke_at[night.turn] = len(night.smoke)
            kapre_at[night.turn] = any(e.type == "kapre" for e in night.enemies)
            await play_turn(rig, clear_smoke)

    asyncio.run(play())
    assert kapre_at[5] is True
    assert smoke_at[5] == 1
    assert {turn for turn, count in smoke_at.items() if count} <= {5, 7}
    assert smoke_at[6] == 0
    events = rig.event_types()
    assert "smoke" in events
    assert "smoke_cleared" in events
    assert "kapre_smoke_telegraph" in [m["moment"] for m in rig.of_type("moment")]
    rig.close()


async def lose_the_stapler(rig: Rig) -> dict[str, bool]:
    rig.controller.bind_loop(asyncio.get_running_loop())
    start_campaign(rig)
    await new_night(rig)
    mode = install_anchor_override(rig, 2, -8.0, 10.0)
    await play_turn(rig, defend_policy())
    mode["on"] = True
    rig.drain()
    await play_turn(rig, idle_policy)
    mode["on"] = False
    return mode


def test_off_desk_object_becomes_lost_and_stays_lost_through_a_crash(
    tmp_path: Path,
) -> None:
    rig = build_rig(tmp_path / "data", api_key=False, demo_safe=True)
    asyncio.run(lose_the_stapler(rig))
    status = {u.game_id: u.status for u in rig.snapshot.night.units}  # type: ignore[union-attr]
    assert "off_desk" in status["u_2"]
    assert "lost" in rig.event_types()
    assert ("unit.lost", {"unit": "Stapler"}) in rig.controller.drain_notices()
    assert "unit_lost" in [m["moment"] for m in rig.of_type("moment")]
    campaign = rig.snapshot.campaign
    assert campaign is not None
    turn = rig.snapshot.night.turn  # type: ignore[union-attr]
    crashed = build_rig(rig.root, store=rig.store, api_key=False, demo_safe=True)
    crashed.controller.continue_campaign(campaign.id)
    crashed.controller.select_camera(0)
    crashed.controller.begin_night()
    restored = crashed.snapshot.night
    assert restored is not None and restored.turn == turn
    assert "off_desk" in {u.game_id: u.status for u in restored.units}["u_2"]
    crashed.controller.close()
    rig.controller.close()
    rig.store.close()


def test_a_lost_object_returns_when_the_anchor_is_back_after_a_crash(
    tmp_path: Path,
) -> None:
    rig = build_rig(tmp_path / "data", api_key=False, demo_safe=True)
    asyncio.run(lose_the_stapler(rig))
    campaign = rig.snapshot.campaign
    assert campaign is not None
    rig.controller.close()
    crashed = build_rig(rig.root, store=rig.store, api_key=False, demo_safe=True)

    async def recover() -> None:
        crashed.controller.bind_loop(asyncio.get_running_loop())
        crashed.controller.continue_campaign(campaign.id)
        crashed.controller.select_camera(0)
        crashed.controller.begin_night()
        crashed.align_hands()
        crashed.pump()
        mode = install_anchor_override(crashed, 2, 20.0, 20.0)
        mode["on"] = True
        await play_turn(crashed, idle_policy)

    asyncio.run(recover())
    assert "found" in crashed.event_types()
    status = {u.game_id: u.status for u in crashed.snapshot.night.units}  # type: ignore[union-attr]
    assert "off_desk" not in status["u_2"]
    assert "unit_returned" in [m["moment"] for m in crashed.of_type("moment")]
    crashed.close()


@pytest.mark.xfail(
    strict=True,
    reason="BUG: reanchor_all skips off-desk units so they are never found again",
)
def test_a_lost_object_put_back_on_the_desk_is_found(tmp_path: Path) -> None:
    rig = build_rig(tmp_path / "data", api_key=False, demo_safe=True)

    async def play() -> None:
        await lose_the_stapler(rig)
        night = rig.snapshot.night
        assert night is not None
        assert "off_desk" in {u.game_id: u.status for u in night.units}["u_2"]
        rig.hands.move_cm(2, 20.0, 20.0)
        rig.pump()
        rig.drain()
        await play_turn(rig, idle_policy)

    asyncio.run(play())
    assert "found" in rig.event_types()
    rig.close()
