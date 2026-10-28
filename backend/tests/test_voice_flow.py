import asyncio
from collections.abc import Callable, Sequence
from pathlib import Path

import pytest

from db.store import Store
from game.night import AppPhase, GameController, GameError
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


def test_voice_down_notifies_and_orders_wait_for_player_phase(tmp_path: Path) -> None:
    store, controller, voices, _ = setup(tmp_path)

    async def play() -> None:
        start(controller)
        voice = voices.made[0]
        controller.pause_night()
        voice.say("Stapler, atake ang aswang!")
        assert controller.snapshot().night.chips == ()  # type: ignore[union-attr]
        voice.on_status(VoiceStatus.DOWN)
        assert controller.snapshot().voice.status == "down"
        assert "net.down" in notices(controller)
        controller.close()
        await controller.wait_for_voice()

    asyncio.run(play())
    assert controller.snapshot().phase is AppPhase.PAUSED
    store.close()
