import asyncio
import threading
from dataclasses import dataclass, field
from enum import StrEnum


class FrameView(StrEnum):
    RAW = "raw"
    WARPED = "warped"


@dataclass(frozen=True)
class Pose:
    id: str
    x_cm: float
    y_cm: float
    uncertain: bool


@dataclass(frozen=True)
class EncodedFrame:
    sequence: int
    view: FrameView
    width: int
    height: int
    jpg_base64: str
    poses: tuple[Pose, ...] = ()


@dataclass
class LiveState:
    _lock: threading.Lock = field(default_factory=threading.Lock, init=False)
    _frame: EncodedFrame | None = field(default=None, init=False)

    def publish(self, frame: EncodedFrame) -> None:
        with self._lock:
            self._frame = frame

    def latest(self) -> EncodedFrame | None:
        with self._lock:
            return self._frame

    def clear(self) -> None:
        with self._lock:
            self._frame = None


BROADCAST_QUEUE_SIZE = 64


class Broadcast:
    def __init__(self) -> None:
        self._queues: set[asyncio.Queue[dict[str, object]]] = set()

    def subscribe(self) -> asyncio.Queue[dict[str, object]]:
        queue: asyncio.Queue[dict[str, object]] = asyncio.Queue(
            maxsize=BROADCAST_QUEUE_SIZE
        )
        self._queues.add(queue)
        return queue

    def unsubscribe(self, queue: asyncio.Queue[dict[str, object]]) -> None:
        self._queues.discard(queue)

    def publish(self, message: dict[str, object]) -> None:
        for queue in list(self._queues):
            if queue.full():
                continue
            queue.put_nowait(message)
