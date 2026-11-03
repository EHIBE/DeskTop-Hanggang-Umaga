import asyncio
import json
from dataclasses import replace
from decimal import Decimal
from pathlib import Path
from typing import Any, cast

import anyio
from fastapi.testclient import TestClient
from starlette.testclient import WebSocketTestSession

from config import AppSettings, CallKind
from game.night import AppPhase, FramePump
from rules.units import UnitClass
from server import Services, create_app
from tests.e2e_support import (
    CONTENT,
    OBJECT_NAMES,
    PLAYERS,
    REAL_NAMES,
    Rig,
    build_rig,
    centre_of,
    claim_two_players,
    defend_policy,
    new_night,
    night_id_of,
    night_result,
    play_to_end,
    saved_turns,
    start_campaign,
    summon_roster,
    transition_targets,
    usage_rows,
)
from tests.test_server import ORIGIN, TOKEN, connect

TURN_CYCLE = [
    "END_TURN_SNAPSHOT",
    "VALIDATE",
    "RESOLVE_PLAYER",
    "RESOLVE_ENEMY",
    "PHYSICAL_EFFECTS",
    "CHECK_END",
]
FULL_PATH = (
    ["VOICE_CLAIM", "SPAWN_TELEGRAPH", "PLAYER_PHASE"]
    + (TURN_CYCLE + ["SPAWN_TELEGRAPH", "PLAYER_PHASE"]) * 7
    + TURN_CYCLE
    + ["SUNRISE"]
)


def fresh(tmp_path: Path, **kwargs: Any) -> Rig:
    return build_rig(tmp_path / "data", **kwargs)


def test_demo_safe_first_night_without_a_key_reaches_sunrise(tmp_path: Path) -> None:
    rig = fresh(tmp_path, api_key=False, demo_safe=True)
    autosaved: list[int] = []

    async def play() -> list[int]:
        rig.controller.bind_loop(asyncio.get_running_loop())
        assert rig.phase() is AppPhase.START
        start_campaign(rig)
        opening = rig.snapshot
        assert opening.phase is AppPhase.SUMMON
        assert opening.is_demo_safe is True
        assert opening.has_api_key is False
        await summon_roster(rig)
        roster = rig.snapshot
        assert [u.card.unit_class for u in roster.units] == [
            UnitClass.KUBO,
            UnitClass.FIGHTER,
            UnitClass.FIGHTER,
            UnitClass.FIGHTER,
        ]
        assert roster.begin_block_key is None
        claim_two_players(rig.controller)
        rig.pump()
        night = rig.snapshot.night
        assert rig.phase() is AppPhase.PLAYER_PHASE
        assert night is not None and night.turn == 1
        assert night.players == PLAYERS
        number = night_id_of(rig.store, 1)

        async def record() -> None:
            autosaved.append(saved_turns(rig.store, number))

        turns = await play_to_end(rig, defend_policy(), record)
        await rig.controller.wait_for_background()
        return turns

    turns = asyncio.run(play())
    final = rig.snapshot
    night_id = night_id_of(rig.store, 1)
    assert turns == [1, 2, 3, 4, 5, 6, 7, 8]
    assert autosaved == [1, 2, 3, 4, 5, 6, 7, 8]
    assert night_result(rig.store, night_id) == "win"
    assert final.phase is AppPhase.SUNRISE
    assert final.score is not None
    assert final.score.kubo_hp == 10
    assert final.score.enemies_defeated == 8
    assert final.score.units_alive == 1
    assert final.score.score == 84
    assert final.score.bayani == ("Migs",)
    assert final.progression is not None
    assert (final.progression.barrio_level, final.progression.nights_survived) == (1, 1)
    assert transition_targets(rig.store, night_id) == FULL_PATH
    assert rig.meta.execute_calls == 0
    assert rig.meta.sdk_calls == 0
    assert rig.sdk.calls == []
    assert usage_rows(rig.store) == []
    assert rig.meter.spent_usd == Decimal(0)
    assert {m["source"] for m in rig.of_type("narration")} == {"line_bank"}
    campaign = final.campaign
    assert campaign is not None
    saved = rig.store.get_recap(campaign.id)
    assert saved is not None and saved.source == "line_bank"
    assert json.loads(saved.text)["text_tl"].startswith("Kagabi")
    rig.close()


def test_paid_night_meters_every_call_and_hides_real_names(tmp_path: Path) -> None:
    rig = fresh(tmp_path, api_key=True, demo_safe=False)

    async def play() -> None:
        rig.controller.bind_loop(asyncio.get_running_loop())
        start_campaign(rig)
        await new_night(rig)
        await rig.controller.wait_for_sprites()

        async def settle() -> None:
            await rig.controller.wait_for_narration()

        await settle()
        await play_to_end(rig, defend_policy(), settle)
        await rig.controller.wait_for_background()

    asyncio.run(play())
    final = rig.snapshot
    assert final.phase is AppPhase.SUNRISE
    calls = rig.sdk.calls
    rows = usage_rows(rig.store)
    assert len(calls) > 20
    assert all(call["store"] is False for call in calls)
    assert rig.meta.execute_calls == len(calls) == len(rows)
    assert {kind for _, kind, _, _ in rows} == {
        CallKind.SPARK.value,
        CallKind.SAM_IMAGE.value,
        CallKind.IMAGE.value,
    }
    assert all(ok == 1 for _, _, _, ok in rows)
    assert rig.meter.spent_usd == rig.store.total_api_cost()
    assert rig.meter.spent_usd > Decimal(0)
    dump = json.dumps(calls, default=str)
    for name in REAL_NAMES:
        assert name not in dump
    prompts = [str(c["input"]) for c in calls if "instructions" in c]
    assert prompts
    assert any("P1" in prompt for prompt in prompts)
    assert any("P2" in prompt for prompt in prompts)
    narrations = rig.of_type("narration")
    assert [m["source"] for m in narrations][:2] == ["spark", "spark"]
    assert narrations[-1]["phase"] == "sunrise"
    assert "Migs" in str(narrations[0]["narration_tl"])
    assert "P1" not in str(narrations[0]["narration_tl"])
    assert rig.invalid == []
    campaign = final.campaign
    assert campaign is not None
    saved = rig.store.get_recap(campaign.id)
    assert saved is not None and saved.source == "spark"
    assert rig.snapshot.is_demo_safe is False
    rig.close()


def test_narration_timeout_falls_back_to_the_line_bank(tmp_path: Path) -> None:
    rig = fresh(tmp_path, api_key=True, demo_safe=False, narration_timeout_s=0.09)
    rig.sdk.delay_s = 5.0
    rig.sdk.slow_narrations = 1

    async def play() -> None:
        rig.controller.bind_loop(asyncio.get_running_loop())
        start_campaign(rig)
        await summon_roster(rig)
        claim_two_players(rig.controller)
        rig.pump()
        await rig.controller.wait_for_narration()
        rig.narration._timeout_s = 20.0
        await play_to_end(rig, defend_policy(), rig.controller.wait_for_narration)
        await rig.controller.wait_for_background()

    asyncio.run(play())
    narrations = rig.of_type("narration")
    assert narrations[0]["phase"] == "night_start"
    assert narrations[0]["source"] == "line_bank"
    assert {m["source"] for m in narrations[1:]} == {"spark"}
    assert rig.snapshot.phase is AppPhase.SUNRISE
    rows = usage_rows(rig.store)
    assert len(rows) == len(rig.sdk.calls)
    cancelled = [row for row in rows if row[3] == 0]
    assert len(cancelled) == 1 and cancelled[0][1] == CallKind.SPARK.value
    assert cancelled[0][2] > 0
    rig.close()


class Wire:
    def __init__(self, ws: WebSocketTestSession) -> None:
        self.ws = ws
        self.notices: list[str] = []
        self.latest: dict[str, Any] = {}

    def send(self, payload: dict[str, object]) -> None:
        self.ws.send_text(json.dumps(payload))

    async def _receive(self) -> dict[str, Any]:
        with anyio.fail_after(8):
            raw = await self.ws._send_rx.receive()
        return cast(dict[str, Any], json.loads(raw["text"]))

    def until(self, wanted: str, predicate: Any = None, limit: int = 600) -> Any:
        for _ in range(limit):
            message = self.ws.portal.call(self._receive)
            if message["type"] == "notice":
                self.notices.append(str(message["copy_key"]))
            if message["type"] == "state":
                self.latest = message
            if message["type"] == wanted and (predicate is None or predicate(message)):
                return message
        raise AssertionError(f"no matching {wanted}")

    def ask(self, payload: dict[str, object], predicate: Any = None) -> Any:
        self.send(payload)
        return self.until("state", predicate)


def test_demo_safe_night_runs_over_the_socket_and_resumes(tmp_path: Path) -> None:
    root = tmp_path / "data"
    rigs: list[Rig] = []

    def factory(settings: AppSettings) -> Services:
        rig = build_rig(root, api_key=False, demo_safe=True)
        rigs.append(rig)
        return Services(
            settings=settings,
            controller=rig.controller,
            pump=FramePump(rig.controller, rig.live),
            live=rig.live,
            content=CONTENT,
            meter=rig.meter,
            broadcast=rig.broadcast,
            close=rig.close,
        )

    settings = AppSettings(token=TOKEN, data_dir=root, port=8765, api_key=None)
    app = create_app(settings, frozenset({ORIGIN}), factory)
    corners = [[820.0, 300.0], [1140.0, 310.0], [1190.0, 760.0], [780.0, 750.0]]
    with TestClient(app) as client, connect(client) as ws:
        wire = Wire(ws)
        wire.until("state")
        wire.ask({"type": "campaign.start", "new": {"name": "Barkada"}})
        wire.ask({"type": "camera.select", "index": 0})
        wire.ask(
            {
                "type": "calibrate.corners",
                "corners": corners,
                "play_w_cm": 60,
                "play_h_cm": 40,
            }
        )
        state = wire.ask({"type": "calibrate.done"}, lambda s: s["phase"] == "SUMMON")
        assert state["demo_safe"] is True
        for name, box in zip(OBJECT_NAMES, rigs[0].boxes, strict=True):
            wire.send({"type": "summon.name", "name": name})
            wire.until("notice", lambda m: m["copy_key"] == "summon.which")
            x, y = centre_of(box)
            wire.send({"type": "summon.tap", "point": [x, y]})
            wire.until("card")
        state = wire.ask({"type": "night.begin"}, lambda s: s["phase"] == "VOICE_CLAIM")
        assert len(state["units"]) == 4
        for player, owned in (("Migs", ["u_kubo", "u_2", "u_4"]), ("Bea", ["u_3"])):
            wire.ask({"type": "claim.tap", "player_name": player, "unit_ids": owned})
        state = wire.ask({"type": "claim.done"}, lambda s: s["phase"] == "PLAYER_PHASE")
        assert state["night"]["turn"] == 1
        for expected in (2, 3):
            enemy = wire.latest["night"]["enemies"][0]["id"]
            wire.ask(
                {
                    "type": "intent.tap",
                    "unit_id": "u_2",
                    "action": "attack",
                    "target_id": enemy,
                }
            )
            assert wire.latest["night"]["chips"][0]["unit_id"] == "u_2"
            state = wire.ask(
                {"type": "end_turn"},
                lambda s, t=expected: (
                    s["night"] is not None
                    and s["night"]["turn"] == t
                    and s["phase"] == "PLAYER_PHASE"
                ),
            )
        before = state["night"]
        wire.ask({"type": "night.pause"}, lambda s: s["phase"] == "PAUSED")
        wire.ask({"type": "pause.quit"}, lambda s: s["phase"] == "START")
        wire.send({"type": "campaign.list"})
        campaigns = wire.until("campaigns")["campaigns"]
        assert len(campaigns) == 1
        state = wire.ask(
            {"type": "campaign.start", "campaign_id": campaigns[0]["id"]},
            lambda s: s["phase"] == "SUMMON",
        )
        assert state["resume_turn"] == 3
        state = wire.ask(
            {"type": "night.begin"}, lambda s: s["phase"] == "PLAYER_PHASE"
        )
        after = state["night"]
        assert after["turn"] == before["turn"] == 3
        assert after["units"] == before["units"]
        assert after["enemies"] == before["enemies"]
        assert after["kubo_hp"] == before["kubo_hp"]
        assert rigs[0].meta.execute_calls == 0
        assert usage_rows(rigs[0].store) == []


def test_the_same_inputs_give_identical_events_and_state(tmp_path: Path) -> None:
    outcomes: list[tuple[Any, ...]] = []
    for run in ("one", "two"):
        rig = build_rig(tmp_path / run, api_key=False, demo_safe=True)

        async def play(rig: Rig = rig) -> None:
            rig.controller.bind_loop(asyncio.get_running_loop())
            start_campaign(rig)
            await new_night(rig)
            await play_to_end(rig, defend_policy())
            await rig.controller.wait_for_background()

        asyncio.run(play())
        final = rig.snapshot
        events = [m["events"] for m in rig.of_type("events")]
        narration = [
            (m["turn"], m["phase"], m["narration_tl"], m["mood"])
            for m in rig.of_type("narration")
        ]
        night_id = night_id_of(rig.store, 1)
        log = [
            (turn, phase, kind, payload)
            for turn, phase, kind, payload, _ in rig.store.turn_log_rows(night_id)
        ]
        assert final.night is not None
        chips = [
            (c.unit_id, c.action, c.target_id, c.source) for c in final.night.chips
        ]
        outcomes.append(
            (
                events,
                narration,
                log,
                replace(final.night, chips=()),
                chips,
                final.score,
                final.progression,
            )
        )
        rig.close()
    assert len(outcomes[0][0]) >= 8
    assert outcomes[0] == outcomes[1]
