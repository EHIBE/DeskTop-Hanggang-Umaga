import asyncio
from pathlib import Path

from db.store import Store
from game.night import AppPhase, GameController
from gm.narrator import (
    LineBank,
    Narration,
    NarrationRequest,
    NarrationService,
    NarrationSource,
)
from gm.schemas import Mood
from meta_client import MetaError
from rules.resolve import Action
from state import Broadcast
from tests.test_night import CONTENT
from tests.test_tracking_flow import ConfidentSegmenter, controller_for, summon_three


def drain(queue: asyncio.Queue[dict[str, object]]) -> list[dict[str, object]]:
    messages: list[dict[str, object]] = []
    while not queue.empty():
        messages.append(queue.get_nowait())
    return messages


def narrations(queue: asyncio.Queue[dict[str, object]]) -> list[dict[str, object]]:
    return [m for m in drain(queue) if m["type"] == "narration"]


def claimed(controller: GameController) -> None:
    summon_three(controller)
    controller.begin_night()
    controller.claim("Migs", ["u_kubo", "u_2"], CONTENT.clean_player_name)
    controller.claim("Bea", ["u_3"], CONTENT.clean_player_name)
    controller.finish_claims()


class FixedNarrator:
    def __init__(self, delay_s: float = 0.0, error: Exception | None = None) -> None:
        self.requests: list[NarrationRequest] = []
        self.nights = 0
        self._delay_s = delay_s
        self._error = error

    async def narrate(self, request: NarrationRequest) -> Narration:
        self.requests.append(request)
        if self._delay_s:
            await asyncio.sleep(self._delay_s)
        if self._error is not None:
            raise self._error
        return Narration("Live tl", "Live en", Mood.KABA, (), "", NarrationSource.SPARK)

    def new_night(self) -> None:
        self.nights += 1


def test_line_bank_narrates_every_moment_of_a_night(tmp_path: Path) -> None:
    store = Store(tmp_path / "db.sqlite")
    broadcast = Broadcast()
    queue = broadcast.subscribe()
    controller = controller_for(
        store, ConfidentSegmenter(), narration=NarrationService(LineBank()), broadcast=broadcast
    )
    claimed(controller)
    first = narrations(queue)
    assert [m["phase"] for m in first] == ["night_start"]
    assert first[0]["source"] == "line_bank"
    assert first[0]["turn"] == 1
    assert first[0]["night"] == 1
    phases: list[object] = []
    for _ in range(8):
        if controller.snapshot().phase is not AppPhase.PLAYER_PHASE:
            break
        night = controller.snapshot().night
        assert night is not None
        if night.enemies:
            controller.add_intent("u_2", Action.ATTACK, night.enemies[0].id)
        asyncio.run(controller.end_turn())
        phases.extend(m["phase"] for m in narrations(queue))
    final = controller.snapshot().phase
    expected_end = "sunrise" if final is AppPhase.SUNRISE else "defeat"
    assert phases[-1] == expected_end
    assert all(p == "resolution_then_telegraph" for p in phases[:-1])
    controller.close()
    store.close()


def test_blocked_end_turn_does_not_narrate(tmp_path: Path) -> None:
    store = Store(tmp_path / "db.sqlite")
    broadcast = Broadcast()
    queue = broadcast.subscribe()
    segmenter = ConfidentSegmenter()
    controller = controller_for(
        store, segmenter, narration=NarrationService(LineBank()), broadcast=broadcast
    )
    claimed(controller)
    drain(queue)
    segmenter._shift = 400
    asyncio.run(controller.end_turn())
    assert narrations(queue) == []
    controller.close()
    store.close()


def test_demo_safe_uses_the_line_bank_even_with_a_live_narrator(tmp_path: Path) -> None:
    store = Store(tmp_path / "db.sqlite")
    broadcast = Broadcast()
    queue = broadcast.subscribe()
    live = FixedNarrator()
    controller = controller_for(
        store,
        ConfidentSegmenter(),
        narration=NarrationService(LineBank(), lambda: live),
        broadcast=broadcast,
    )
    controller.set_demo_safe(True)
    claimed(controller)
    assert [m["source"] for m in narrations(queue)] == ["line_bank"]
    assert live.requests == []
    controller.close()
    store.close()


def test_live_narration_runs_in_the_background(tmp_path: Path) -> None:
    store = Store(tmp_path / "db.sqlite")
    broadcast = Broadcast()
    queue = broadcast.subscribe()
    live = FixedNarrator()
    controller = controller_for(
        store,
        ConfidentSegmenter(),
        narration=NarrationService(LineBank(), lambda: live),
        broadcast=broadcast,
    )

    summon_three(controller)

    async def play() -> None:
        controller.begin_night()
        controller.claim("Migs", ["u_kubo", "u_2"], CONTENT.clean_player_name)
        controller.finish_claims()
        await controller.wait_for_narration()
        await controller.end_turn()
        await controller.wait_for_narration()

    asyncio.run(play())
    sent = narrations(queue)
    assert [m["source"] for m in sent] == ["spark", "spark"]
    assert sent[0]["narration_tl"] == "Live tl"
    assert live.nights == 0
    assert live.requests[0].phase == "night_start"
    request = live.requests[1]
    assert request.phase == "resolution_then_telegraph"
    assert {u.id for u in request.units} == {"u_2", "u_3"}
    assert {u.owner for u in request.units} == {"Migs", None}
    assert request.kubo_hp_max > 0
    assert request.events
    controller.close()
    store.close()


def test_slow_or_failing_narration_falls_back_to_the_line_bank() -> None:
    line_bank = LineBank()
    request = NarrationRequest(1, 1, "night_start", "normal", 10, 10)
    published: list[Narration] = []

    async def run(narrator: FixedNarrator) -> None:
        service = NarrationService(line_bank, lambda: narrator, timeout_s=0.01)
        service.submit(request, False, lambda _, n: published.append(n))
        await service.wait()

    asyncio.run(run(FixedNarrator(delay_s=1.0)))
    asyncio.run(run(FixedNarrator(error=MetaError("down"))))
    assert [n.source for n in published] == [NarrationSource.LINE_BANK] * 2
    assert published[0] == line_bank.pick(request)


def test_stale_narration_is_dropped() -> None:
    line_bank = LineBank()
    first = NarrationRequest(1, 1, "night_start", "normal", 10, 10)
    second = NarrationRequest(1, 2, "resolution_then_telegraph", "normal", 10, 10)
    published: list[int] = []

    async def run() -> None:
        service = NarrationService(line_bank, lambda: FixedNarrator(delay_s=0.05))
        service.submit(first, False, lambda r, _: published.append(r.turn))
        service.submit(second, True, lambda r, _: published.append(r.turn))
        await service.wait()

    asyncio.run(run())
    assert published == [2]


def test_cancel_stops_pending_narration() -> None:
    published: list[int] = []

    async def run() -> None:
        service = NarrationService(LineBank(), lambda: FixedNarrator(delay_s=0.05))
        service.submit(
            NarrationRequest(1, 1, "night_start", "normal", 10, 10),
            False,
            lambda r, _: published.append(r.turn),
        )
        service.cancel()
        await service.wait()

    asyncio.run(run())
    assert published == []


def test_new_night_resets_the_live_chain() -> None:
    live = FixedNarrator()

    async def run() -> None:
        service = NarrationService(LineBank(), lambda: live)
        service.submit(
            NarrationRequest(1, 1, "night_start", "normal", 10, 10), False, lambda r, n: None
        )
        await service.wait()
        service.new_night()

    asyncio.run(run())
    assert live.nights == 1


def test_gm_invalid_is_logged_at_the_current_turn(tmp_path: Path) -> None:
    store = Store(tmp_path / "db.sqlite")
    controller = controller_for(store, ConfidentSegmenter())
    claimed(controller)
    controller.log_invalid("gm_invalid:SchemaError")
    campaign = controller.snapshot().campaign
    assert campaign is not None
    night = store.start_or_resume_night(campaign.id)
    with store.transaction() as conn:
        row = conn.execute(
            "SELECT turn, phase FROM turn_log WHERE night_id = ? AND event_type = 'gm_invalid'",
            (night.id,),
        ).fetchone()
    assert (row[0], row[1]) == (1, "PLAYER_PHASE")
    controller.close()
    store.close()
