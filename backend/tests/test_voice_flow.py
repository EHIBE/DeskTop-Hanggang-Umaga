import asyncio
from collections.abc import Callable, Sequence
from pathlib import Path

import pytest

from db.store import Store
from game.night import GameController, GameError
from state import Broadcast
from tests.test_night import CONTENT
from tests.test_tracking_flow import ConfidentSegmenter, controller_for, summon_three
from voice.session import Caption, VoiceMode, VoiceStatus


class FakeVoice:
    def __init__(
        self,
        keywords: Sequence[str],
        on_caption: Callable[[Caption], None],
        on_final: Callable[[Caption], None],
        on_overlap: Callable[[], None],
        on_status: Callable[[VoiceStatus], None],
    ) -> None:
        self.keywords = tuple(keywords)
        self.on_caption = on_caption
        self.on_final = on_final
        self.on_overlap = on_overlap
        self.on_status = on_status
        self.mode = VoiceMode.OPEN
        self.ptt: list[bool] = []
        self.is_stopped = False
        self._stop = asyncio.Event()

    async def run(self) -> None:
        self.on_status(VoiceStatus.LISTENING)
        await self._stop.wait()

    def stop(self) -> None:
        self.is_stopped = True
        self._stop.set()

    def set_mode(self, mode: VoiceMode) -> None:
        self.mode = mode

    def set_ptt(self, is_down: bool) -> None:
        self.ptt.append(is_down)

    def say(self, text: str, speaker: str | None = "spk_0") -> None:
        caption = Caption("t1", text, True, speaker)
        self.on_caption(caption)
        self.on_final(caption)


class Voices:
    def __init__(self) -> None:
        self.made: list[FakeVoice] = []

    def __call__(self, *args: object) -> FakeVoice:
        voice = FakeVoice(*args)  # type: ignore[arg-type]
        self.made.append(voice)
        return voice


def setup(tmp_path: Path) -> tuple[Store, GameController, Voices, asyncio.Queue[dict[str, object]]]:
    store = Store(tmp_path / "db.sqlite")
    broadcast = Broadcast()
    queue = broadcast.subscribe()
    voices = Voices()
    controller = controller_for(store, ConfidentSegmenter(), broadcast=broadcast)
    controller._voice_factory = voices  # type: ignore[assignment]
    summon_three(controller)
    return store, controller, voices, queue


def start(controller: GameController) -> None:
    controller.begin_night()
    controller.claim("Migs", ["u_kubo", "u_2", "u_3"], CONTENT.clean_player_name)
    controller.finish_claims()


def notices(controller: GameController) -> list[str]:
    return [key for key, _ in controller.drain_notices()]


def test_voice_orders_make_chips_and_cancel(tmp_path: Path) -> None:
    store, controller, voices, queue = setup(tmp_path)

    async def play() -> None:
        start(controller)
        await asyncio.sleep(0)
        voice = voices.made[0]
        assert "Stapler" in voice.keywords and "aswang" in voice.keywords
        assert controller.snapshot().voice.status == "listening"
        voice.say("Stapler, atake ang aswang!")
        night = controller.snapshot().night
        assert night is not None
        assert [(c.unit_id, c.action, c.source, c.speaker) for c in night.chips] == [
            ("u_2", "attack", "voice", "spk_0")
        ]
        voice.say("Hindi, mali")
        assert controller.snapshot().night.chips == ()  # type: ignore[union-attr]
        assert "cmd.cancel" in notices(controller)
        voice.say("kumain ka na ba")
        assert "cmd.unknown" in notices(controller)
        voice.say("Tapos!")
        await controller.wait_for_voice_end_turns()
        assert controller.snapshot().night.turn == 2  # type: ignore[union-attr]
        voice.on_overlap()
        assert "cmd.overlap" in notices(controller)
        controller.close()
        await controller.wait_for_voice()

    asyncio.run(play())
    messages = []
    while not queue.empty():
        messages.append(queue.get_nowait())
    captions = [m for m in messages if m["type"] == "caption"]
    assert captions[0] == {
        "type": "caption",
        "turn_id": "t1",
        "text": "Stapler, atake ang aswang!",
        "is_final": True,
        "speaker": "spk_0",
    }
    assert any(m["type"] == "state.changed" for m in messages)
    assert voices.made[0].is_stopped
    store.close()


def test_demo_safe_keeps_voice_off(tmp_path: Path) -> None:
    store, controller, voices, _ = setup(tmp_path)
    controller.set_demo_safe(True)

    async def play() -> None:
        start(controller)

    asyncio.run(play())
    assert voices.made == []
    assert controller.snapshot().voice.status == "off"
    controller.close()
    store.close()


def test_ptt_mode_and_retry(tmp_path: Path) -> None:
    store, controller, voices, _ = setup(tmp_path)
    with pytest.raises(GameError):
        controller.set_ptt(True)

    async def play() -> None:
        start(controller)
        controller.set_voice_mode(VoiceMode.PTT)
        controller.set_ptt(True)
        voice = voices.made[0]
        assert voice.mode is VoiceMode.PTT
        assert controller.snapshot().voice.is_ptt_down
        controller.retry_voice()
        await asyncio.sleep(0)
        assert voice.is_stopped
        assert len(voices.made) == 2
        assert voices.made[1].mode is VoiceMode.PTT
        assert not controller.snapshot().voice.is_ptt_down
        controller.close()
        await controller.wait_for_voice()

    asyncio.run(play())
    store.close()


def test_pause_stops_voice_and_stale_callbacks_are_ignored(tmp_path: Path) -> None:
    store, controller, voices, _ = setup(tmp_path)

    async def play() -> None:
        start(controller)
        first = voices.made[0]
        controller.pause_night()
        assert first.is_stopped
        assert controller.snapshot().voice.status == "off"
        first.say("Stapler, atake ang aswang!")
        first.on_status(VoiceStatus.LISTENING)
        assert controller.snapshot().voice.status == "off"
        controller.resume_night(is_forced=False)
        await asyncio.sleep(0)
        second = voices.made[1]
        assert controller.snapshot().voice.status == "listening"
        first.say("Stapler, atake ang aswang!")
        assert controller.snapshot().night.chips == ()  # type: ignore[union-attr]
        second.on_status(VoiceStatus.OFF)
        assert controller.snapshot().voice.status == "down"
        assert "net.down" in notices(controller)
        controller.close()
        await controller.wait_for_voice()

    asyncio.run(play())
    store.close()


def test_demo_safe_off_restarts_voice(tmp_path: Path) -> None:
    store, controller, voices, _ = setup(tmp_path)

    async def play() -> None:
        start(controller)
        controller.set_demo_safe(True)
        assert voices.made[0].is_stopped
        controller.set_demo_safe(False)
        assert len(voices.made) == 2
        controller.set_ptt(False)
        controller.close()
        await controller.wait_for_voice()

    asyncio.run(play())
    store.close()


def test_spoken_claims_map_speakers_to_players(tmp_path: Path) -> None:
    store, controller, voices, queue = setup(tmp_path)
    controller._clean_name = CONTENT.clean_player_name

    async def play() -> None:
        controller.begin_night()
        voice = voices.made[0]
        voice.say("ako si Migs, hawak ko ang Stapler at Phone", "spk_0")
        night = controller.snapshot().night
        assert night is not None
        assert night.players == ("Migs",)
        voice.say("hawak ko ang Mug", "spk_1")
        assert "claim.who" in notices(controller)
        voice.say("ako si Bea", "spk_1")
        voice.say("akin ang Mug", "spk_1")
        controller.finish_claims()
        owners = {u.game_id: u.owner for u in controller.snapshot().night.units}  # type: ignore[union-attr]
        assert owners == {"u_kubo": "Bea", "u_2": "Migs", "u_3": "Migs"}
        voice.say("Stapler, atake ang aswang!", "spk_0")
        chips = controller.snapshot().night.chips  # type: ignore[union-attr]
        assert [c.speaker for c in chips] == ["Migs"]
        controller.retry_voice()
        assert "voice.reclaim" in notices(controller)
        second = voices.made[1]
        second.say("Phone, atake ang aswang!", "spk_0")
        chips = controller.snapshot().night.chips  # type: ignore[union-attr]
        assert chips[-1].speaker == "spk_0"
        second.say("ako si Migs", "spk_0")
        assert [c.speaker for c in controller.snapshot().night.chips] == ["Migs", "Migs"]  # type: ignore[union-attr]
        second.say("Hindi", "spk_0")
        remaining = controller.snapshot().night.chips  # type: ignore[union-attr]
        assert [(c.unit_id, c.speaker) for c in remaining] == [("u_2", "Migs")]
        controller.close()
        await controller.wait_for_voice()

    asyncio.run(play())
    captions = []
    while not queue.empty():
        message = queue.get_nowait()
        if message["type"] == "caption":
            captions.append(message["speaker"])
    assert "Migs" in captions
    store.close()
