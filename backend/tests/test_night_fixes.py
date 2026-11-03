import asyncio
import threading
import time
from collections.abc import Callable
from dataclasses import replace
from pathlib import Path

import pytest

from db.store import Store
from game.night import (
    FALLBACK_COOLDOWN_S,
    GameController,
    GameError,
    PendingConfirm,
    looks_like_command,
)
from game.state_machine import TurnState
from rules.progression import Badge
from rules.resolve import UnitState
from rules.units import Difficulty
from state import Broadcast
from tests.test_barrio_map import ScriptedService, generated
from tests.test_night import ready_for_summon
from tests.test_night_flow import start_night
from tests.test_tracking_flow import ConfidentSegmenter, controller_for
from tests.test_wiring import (
    begin_two_players,
    drain,
    finish_night,
    fresh_detector,
    spark_setup,
)
from voice.grammar import (
    Command,
    CommandKind,
    GrammarContext,
    GrammarEnemy,
    GrammarUnit,
)

CONTEXT = GrammarContext(
    units=(GrammarUnit("u_2", "Stapler", "fighter", 10.0, 10.0),),
    enemies=(GrammarEnemy("e_1", "aswang", 20.0, 20.0),),
)


class SlowService(ScriptedService):
    def __init__(self, maps_dir: Path) -> None:
        super().__init__(maps_dir, [])
        self.started = asyncio.Event()
        self.release = asyncio.Event()

    async def _call(
        self, reference_png: bytes, style_anchor_png: bytes | None
    ) -> bytes:
        self.started.set()
        await self.release.wait()
        return generated()


def test_continue_is_refused_outside_start(tmp_path: Path) -> None:
    store = Store(tmp_path / "db.sqlite")
    controller = controller_for(store, ConfidentSegmenter())
    ready_for_summon(controller)
    other = store.create_campaign("Other", Difficulty.NORMAL)
    with pytest.raises(GameError):
        controller.continue_campaign(other.id)
    with pytest.raises(GameError):
        controller.start_new_campaign("Third")
    assert [c.name for c in store.list_campaigns()].count("Third") == 0
    controller.close()
    store.close()


def test_off_desk_unit_is_not_absent_but_stolen_and_escaped_are(
    tmp_path: Path,
) -> None:
    store = Store(tmp_path / "db.sqlite")
    controller = controller_for(store, ConfidentSegmenter())
    start_night(controller)
    session = controller._session
    assert session is not None and session.board is not None
    board = session.board

    def mark(change: Callable[[UnitState], UnitState]) -> None:
        units = tuple(change(u) if u.id == "u_2" else u for u in board.units)
        session._board = replace(board, units=units)

    mark(lambda u: replace(u, off_desk=True))
    assert controller._absent_sam_ids() == set()
    mark(lambda u: replace(u, is_lost=True))
    assert controller._absent_sam_ids() == {2}
    mark(lambda u: replace(u, stolen_by="e_1"))
    assert controller._absent_sam_ids() == {2}
    controller.close()
    store.close()


def test_end_turn_refuses_and_pauses_on_a_stale_frame(tmp_path: Path) -> None:
    store = Store(tmp_path / "db.sqlite")
    controller = controller_for(store, ConfidentSegmenter())
    start_night(controller)
    camera = controller._camera
    assert camera is not None
    assert camera.frame_age_s() is not None
    camera._stop.set()
    assert camera.join(2.0)
    camera._clock = lambda: time.monotonic() + 600.0

    async def run() -> None:
        with pytest.raises(GameError) as caught:
            await controller.end_turn()
        assert caught.value.copy_key == "cam.busy"

    asyncio.run(run())
    session = controller._session
    assert session is not None and session.state is TurnState.PAUSED
    assert controller.snapshot().night.turn == 1  # type: ignore[union-attr]
    controller.close()
    store.close()


def test_looks_like_command_uses_the_grammar_vocabulary() -> None:
    assert looks_like_command("atake mo yung aswang", CONTEXT)
    assert looks_like_command("stapler please", CONTEXT)
    assert looks_like_command("iatake", CONTEXT)
    assert looks_like_command("yung tikbalang oh", CONTEXT)
    assert not looks_like_command("what a lovely evening", CONTEXT)
    assert not looks_like_command("   ", CONTEXT)


def say(controller: GameController, voices: object, text: str) -> None:
    voices.made[0].say(text, "spk_0")  # type: ignore[attr-defined]


def test_fallback_skips_transcripts_that_are_not_commands(tmp_path: Path) -> None:
    store, controller, voices, calls = spark_setup(tmp_path, lambda _: None)

    async def play() -> None:
        begin_two_players(controller)
        await asyncio.sleep(0)
        controller.drain_notices()
        say(controller, voices, "kumain na ba kayo ng hapunan")
        await controller.wait_for_voice_end_turns()
        assert calls == []
        assert ("cmd.unknown", {}) in controller.drain_notices()
        controller.close()
        await controller.wait_for_voice()

    asyncio.run(play())
    store.close()


def test_fallback_has_a_cooldown_between_calls(tmp_path: Path) -> None:
    store, controller, voices, calls = spark_setup(tmp_path, lambda _: None)
    clock = {"now": 100.0}
    controller._clock = lambda: clock["now"]

    async def play() -> None:
        begin_two_players(controller)
        await asyncio.sleep(0)
        say(controller, voices, "Stapler plugh one")
        await controller.wait_for_voice_end_turns()
        clock["now"] += FALLBACK_COOLDOWN_S / 2
        controller.drain_notices()
        say(controller, voices, "Stapler plugh two")
        await controller.wait_for_voice_end_turns()
        assert calls == ["Stapler plugh one"]
        assert ("cmd.unknown", {}) in controller.drain_notices()
        clock["now"] += FALLBACK_COOLDOWN_S
        say(controller, voices, "Stapler plugh three")
        await controller.wait_for_voice_end_turns()
        assert calls == ["Stapler plugh one", "Stapler plugh three"]
        controller.close()
        await controller.wait_for_voice()

    asyncio.run(play())
    store.close()


def test_fallback_is_capped_per_night(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setattr("game.night.FALLBACK_MAX_PER_NIGHT", 2)
    store, controller, voices, calls = spark_setup(tmp_path, lambda _: None)
    clock = {"now": 100.0}
    controller._clock = lambda: clock["now"]

    async def play() -> None:
        begin_two_players(controller)
        await asyncio.sleep(0)
        for i in range(4):
            clock["now"] += FALLBACK_COOLDOWN_S + 1
            say(controller, voices, f"Stapler plugh {i}")
            await controller.wait_for_voice_end_turns()
        assert len(calls) == 2
        controller.close()
        await controller.wait_for_voice()

    asyncio.run(play())
    store.close()


def test_fallback_allows_one_call_in_flight(tmp_path: Path) -> None:
    store, controller, voices, calls = spark_setup(tmp_path, lambda _: None, delay=0.05)
    clock = {"now": 100.0}
    controller._clock = lambda: clock["now"]

    async def play() -> None:
        begin_two_players(controller)
        await asyncio.sleep(0)
        say(controller, voices, "Stapler plugh one")
        clock["now"] += FALLBACK_COOLDOWN_S + 1
        say(controller, voices, "Stapler plugh two")
        await controller.wait_for_voice_end_turns()
        assert calls == ["Stapler plugh one"]
        controller.close()
        await controller.wait_for_voice()

    asyncio.run(play())
    store.close()


def test_fallback_is_skipped_while_a_confirm_is_open(tmp_path: Path) -> None:
    store, controller, voices, calls = spark_setup(tmp_path, lambda _: None)

    async def play() -> None:
        begin_two_players(controller)
        await asyncio.sleep(0)
        controller._confirm = PendingConfirm(
            "c1", Command(CommandKind.ATTACK, "u_2", None), "Bea", "Migs", 0.0
        )
        controller.drain_notices()
        say(controller, voices, "Stapler plugh")
        await controller.wait_for_voice_end_turns()
        assert calls == []
        assert ("cmd.unknown", {}) in controller.drain_notices()
        controller.close()
        await controller.wait_for_voice()

    asyncio.run(play())
    store.close()


def test_fallback_result_is_dropped_when_the_turn_changed(tmp_path: Path) -> None:
    def attack(controller: GameController) -> Command:
        night = controller.snapshot().night
        assert night is not None
        return Command(CommandKind.ATTACK, "u_2", night.enemies[0].id)

    store, controller, voices, calls = spark_setup(tmp_path, attack, delay=0.05)

    async def play() -> None:
        begin_two_players(controller)
        await asyncio.sleep(0)
        say(controller, voices, "Stapler plugh")
        await asyncio.sleep(0.01)
        session = controller._session
        assert session is not None and session.board is not None
        session._board = replace(session.board, turn=session.board.turn + 1)
        await controller.wait_for_voice_end_turns()
        assert calls == ["Stapler plugh"]
        assert controller.snapshot().night.chips == ()  # type: ignore[union-attr]
        controller.close()
        await controller.wait_for_voice()

    asyncio.run(play())
    store.close()


def test_unpicked_badge_offers_survive_next_night(tmp_path: Path) -> None:
    store = Store(tmp_path / "db.sqlite")
    controller = controller_for(store, ConfidentSegmenter())
    start_night(controller)
    finish_night(controller)
    unit_ids = {u.sam_object_id: u.unit_id for u in controller._units}
    campaign = controller.snapshot().campaign
    assert campaign is not None
    waiting = store.start_or_resume_night(campaign.id)
    assert waiting.flags["pending_offers"][unit_ids[1]] == ["hp"]  # type: ignore[index]
    controller.next_night()
    fresh_detector(controller)
    asyncio.run(controller.summon("Bahay Kubo"))
    offers = controller.snapshot().progression.badge_offers  # type: ignore[union-attr]
    assert [o.unit_id for o in offers] == ["u_kubo"]
    controller.pick_badge("u_kubo", Badge.HP)
    assert controller.snapshot().progression.badge_offers == ()  # type: ignore[union-attr]
    assert store.get_unit_progress(unit_ids[1]).badges == ("hp",)
    assert "pending_offers" in store.start_or_resume_night(campaign.id).flags
    with pytest.raises(GameError):
        controller.pick_badge("u_kubo", Badge.HP)
    controller.close()
    store.close()


def test_unpicked_badge_offers_survive_quit_and_continue(tmp_path: Path) -> None:
    store = Store(tmp_path / "db.sqlite")
    controller = controller_for(store, ConfidentSegmenter())
    start_night(controller)
    finish_night(controller)
    campaign = controller.snapshot().campaign
    assert campaign is not None
    controller.quit_night()
    controller.close()
    again = controller_for(store, ConfidentSegmenter())
    again.continue_campaign(campaign.id)
    again.select_camera(0)
    asyncio.run(again.summon("Bahay Kubo"))
    offers = again.snapshot().progression.badge_offers  # type: ignore[union-attr]
    assert [o.unit_id for o in offers] == ["u_kubo"]
    again.close()
    store.close()


def test_a_badge_pick_updates_the_stored_offers_and_the_cached_night(
    tmp_path: Path,
) -> None:
    store = Store(tmp_path / "db.sqlite")
    controller = controller_for(store, ConfidentSegmenter())
    start_night(controller)
    finish_night(controller)
    controller.next_night()
    fresh_detector(controller)
    asyncio.run(controller.summon("Bahay Kubo"))
    controller.pick_badge("u_kubo", Badge.HP)
    night = controller._night
    assert night is not None
    kubo = next(u for u in controller._units if u.sam_object_id == 1)
    pending = night.flags["pending_offers"]
    assert kubo.unit_id not in pending  # type: ignore[operator]
    assert store.start_or_resume_night(night.campaign_id).flags == night.flags
    controller.close()
    store.close()


def test_a_thread_spawned_task_is_tracked_and_cancelled_on_close(
    tmp_path: Path,
) -> None:
    store = Store(tmp_path / "db.sqlite")
    controller = controller_for(store, ConfidentSegmenter())

    async def play() -> None:
        controller.bind_loop(asyncio.get_running_loop())
        started = asyncio.Event()

        async def work() -> None:
            started.set()
            await asyncio.sleep(30)

        result: list[bool] = []
        worker = threading.Thread(
            target=lambda: result.append(controller._spawn(work()))
        )
        worker.start()
        await asyncio.to_thread(worker.join)
        await asyncio.wait_for(started.wait(), 2)
        assert result == [True]
        assert len(controller._bg_tasks) == 1
        task = next(iter(controller._bg_tasks))
        controller.close()
        await asyncio.sleep(0)
        await asyncio.sleep(0)
        assert task.cancelled()
        assert controller._bg_tasks == set()

    asyncio.run(play())
    store.close()


def test_spawn_after_close_refuses_and_leaves_no_task(tmp_path: Path) -> None:
    store = Store(tmp_path / "db.sqlite")
    controller = controller_for(store, ConfidentSegmenter())

    async def play() -> None:
        controller.bind_loop(asyncio.get_running_loop())
        controller.close()

        async def work() -> None:
            return None

        coroutine = work()
        outcome = await asyncio.to_thread(controller._spawn, coroutine)
        await asyncio.sleep(0)
        assert outcome is False
        assert controller._bg_tasks == set()

    asyncio.run(play())
    store.close()


def test_a_failing_map_task_is_logged_and_still_pushes_state(
    tmp_path: Path, caplog: pytest.LogCaptureFixture
) -> None:
    store = Store(tmp_path / "db.sqlite")
    broadcast = Broadcast()
    queue = broadcast.subscribe()
    controller = controller_for(store, ConfidentSegmenter(), broadcast=broadcast)
    controller._map_service = ScriptedService(tmp_path / "maps", [RuntimeError("boom")])

    async def play() -> None:
        controller.bind_loop(asyncio.get_running_loop())
        ready_for_summon(controller)
        drain(queue)
        controller.set_setting("generated_map", True)
        await controller.wait_for_background()
        assert controller._maps_working == set()
        assert any(m["type"] == "state.changed" for m in drain(queue))

    asyncio.run(play())
    assert "barrio map task failed" in caplog.text
    controller.close()
    store.close()


def test_another_campaign_can_make_its_map_while_one_is_in_flight(
    tmp_path: Path,
) -> None:
    store = Store(tmp_path / "db.sqlite")
    controller = controller_for(store, ConfidentSegmenter())
    service = ScriptedService(tmp_path / "maps", [generated()])
    controller._map_service = service
    controller._maps_working.add("some-other-campaign")

    async def play() -> None:
        ready_for_summon(controller)
        controller.set_setting("generated_map", True)
        assert controller.snapshot().map.is_working is True
        await controller.wait_for_background()

    asyncio.run(play())
    assert len(service.references) == 1
    assert controller._maps_working == {"some-other-campaign"}
    controller.close()
    store.close()


def test_leaving_a_campaign_cancels_its_map_in_flight(tmp_path: Path) -> None:
    store = Store(tmp_path / "db.sqlite")
    controller = controller_for(store, ConfidentSegmenter())
    service = SlowService(tmp_path / "maps")
    controller._map_service = service

    async def play() -> None:
        controller.bind_loop(asyncio.get_running_loop())
        controller.set_setting("generated_map", True)
        ready_for_summon(controller)
        await asyncio.wait_for(service.started.wait(), 2)
        campaign = controller.snapshot().campaign
        assert campaign is not None
        controller._leave_campaign()
        await controller.wait_for_background()
        assert controller._maps_working == set()
        assert service.cached_map(campaign.id) is None

    asyncio.run(play())
    controller.close()
    store.close()


def test_deleting_a_campaign_cancels_its_map_and_leaves_no_file(
    tmp_path: Path,
) -> None:
    store = Store(tmp_path / "db.sqlite")
    controller = controller_for(store, ConfidentSegmenter())
    service = SlowService(tmp_path / "maps")
    controller._map_service = service

    async def play() -> None:
        controller.bind_loop(asyncio.get_running_loop())
        controller.set_setting("generated_map", True)
        ready_for_summon(controller)
        await asyncio.wait_for(service.started.wait(), 2)
        campaign = controller.snapshot().campaign
        assert campaign is not None
        controller._campaign = None
        controller.delete_campaign(campaign.id)
        service.release.set()
        await controller.wait_for_background()
        assert service.cached_map(campaign.id) is None
        assert list((tmp_path / "maps").glob("*")) == []

    asyncio.run(play())
    controller.close()
    store.close()


def test_map_service_refuses_to_write_after_the_campaign_is_deleted(
    tmp_path: Path,
) -> None:
    from tests.test_barrio_map import CAMPAIGN, baseline

    service = SlowService(tmp_path / "maps")

    async def play() -> Path | None:
        task = asyncio.create_task(
            service.ensure_map(CAMPAIGN, baseline(), None, demo_safe=False)
        )
        await service.started.wait()
        service.delete_map(CAMPAIGN)
        service.release.set()
        return await task

    assert asyncio.run(play()) is None
    assert service.cached_map(CAMPAIGN) is None


def test_delete_map_removes_temp_files_and_sweep_removes_orphans(
    tmp_path: Path,
) -> None:
    from tests.test_barrio_map import CAMPAIGN

    maps = tmp_path / "maps"
    maps.mkdir()
    service = ScriptedService(maps, [])
    (maps / f"{CAMPAIGN}.tmp").write_bytes(b"x")
    service.delete_map(CAMPAIGN)
    assert list(maps.iterdir()) == []
    keep = "keep-me"
    for name in (f"{keep}.png", "orphan.png", "orphan.tmp", "orphan.blocked"):
        (maps / name).write_bytes(b"x")
    (maps / "notes.txt").write_bytes(b"x")
    (maps / "bad name.png").write_bytes(b"x")
    assert service.sweep({keep}) == 3
    assert sorted(p.name for p in maps.iterdir()) == [
        "bad name.png",
        f"{keep}.png",
        "notes.txt",
    ]


def test_controller_start_sweeps_maps_of_unknown_campaigns(tmp_path: Path) -> None:
    store = Store(tmp_path / "db.sqlite")
    campaign = store.create_campaign("Barkada", Difficulty.NORMAL)
    maps = tmp_path / "maps"
    maps.mkdir()
    service = ScriptedService(maps, [])
    (maps / f"{campaign.id}.png").write_bytes(b"x")
    (maps / "00000000-orphan.png").write_bytes(b"x")
    controller = controller_for(store, ConfidentSegmenter())
    controller._map_service = service
    controller._sweep_maps()
    assert [p.name for p in maps.iterdir()] == [f"{campaign.id}.png"]
    controller.close()
    store.close()


def test_delete_campaign_survives_a_map_file_error(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    store = Store(tmp_path / "db.sqlite")
    controller = controller_for(store, ConfidentSegmenter())
    service = ScriptedService(tmp_path / "maps", [])

    def broken(_: str) -> None:
        raise PermissionError("locked")

    monkeypatch.setattr(service, "delete_map", broken)
    controller._map_service = service
    campaign = store.create_campaign("X", Difficulty.NORMAL)
    controller.delete_campaign(campaign.id)
    assert ("delete.done", {}) in controller.drain_notices()
    assert store.list_campaigns() == []
    controller.close()
    store.close()


def test_clear_recap_clears_the_row_even_without_a_loaded_recap(
    tmp_path: Path,
) -> None:
    store = Store(tmp_path / "db.sqlite")
    controller = controller_for(store, ConfidentSegmenter())
    controller.start_new_campaign("Barkada", Difficulty.NORMAL)
    campaign = controller.snapshot().campaign
    assert campaign is not None
    store.save_recap(campaign.id, "{}", "line_bank")
    assert controller._recap is None
    controller._clear_recap()
    assert store.get_recap(campaign.id) is None
    controller.close()
    store.close()


def test_clear_recap_cancels_a_recap_build_in_flight(tmp_path: Path) -> None:
    store = Store(tmp_path / "db.sqlite")
    controller = controller_for(store, ConfidentSegmenter())

    async def play() -> None:
        controller.start_new_campaign("Barkada", Difficulty.NORMAL)
        campaign = controller.snapshot().campaign
        assert campaign is not None

        async def build() -> None:
            await asyncio.sleep(30)

        assert controller._spawn(build(), campaign.id, "recap")
        await asyncio.sleep(0)
        task = next(iter(controller._bg_tasks))
        controller._clear_recap()
        await asyncio.sleep(0)
        assert task.cancelled()

    asyncio.run(play())
    controller.close()
    store.close()
