import base64
import logging
import os
import re
import threading
from collections.abc import Collection
from pathlib import Path
from typing import Final

import cv2
import numpy as np
import numpy.typing as npt

from config import CallKind, MetaModel
from meta_client import CallSpec, MetaClient, MetaError, MetaRequestError, Usage
from vision.sprites import (
    IMAGE_TOOL,
    SpriteError,
    decode_png,
    encode_png,
    image_payload,
)

logger = logging.getLogger("desktop.barrio_map")

Image = npt.NDArray[np.uint8]

MAP_SPEC: Final = CallSpec(
    model=MetaModel.IMAGE, kind=CallKind.IMAGE, is_idempotent=True
)
MAP_LONG_SIDE_PX: Final = 1024
MAP_REFERENCE_LONG_SIDE_PX: Final = 768
MAP_FILE_SUFFIX: Final = ".png"
MAP_BLOCKED_SUFFIX: Final = ".blocked"
MAP_TEMP_SUFFIX: Final = ".tmp"
MAP_SUFFIXES: Final = (MAP_FILE_SUFFIX, MAP_BLOCKED_SUFFIX, MAP_TEMP_SUFFIX)
CAMPAIGN_ID_PATTERN: Final = re.compile(r"^[A-Za-z0-9_-]{1,64}$")
MAP_PROMPT: Final = (
    "Redraw this top-down photo of an empty desk as a top-down 16-bit pixel art "
    "map of a small Filipino barrio at night, a game board background. Keep the "
    "same layout, proportions and edges so the map lines up with the photo. "
    "Keep the middle open and calm, with muted dark blue and green ground, "
    "simple paths, bahay kubo roofs, bamboo and banana plants near the borders. "
    "No characters, no creatures, no text, no border, no UI."
)
STYLE_ANCHOR_SENTENCE: Final = "Match the pixel art style of the second image."


def _data_url(png: bytes) -> str:
    return "data:image/png;base64," + base64.b64encode(png).decode("ascii")


def map_prompt(has_style_anchor: bool) -> str:
    if has_style_anchor:
        return f"{MAP_PROMPT} {STYLE_ANCHOR_SENTENCE}"
    return MAP_PROMPT


def baseline_reference_png(baseline_bgr: Image) -> bytes:
    if baseline_bgr.ndim != 3 or baseline_bgr.shape[2] != 3:
        raise SpriteError("baseline must be HxWx3")
    height, width = baseline_bgr.shape[:2]
    if height == 0 or width == 0:
        raise SpriteError("baseline is empty")
    scale = MAP_REFERENCE_LONG_SIDE_PX / max(height, width)
    size = (max(1, round(width * scale)), max(1, round(height * scale)))
    resized = cv2.resize(baseline_bgr, size, interpolation=cv2.INTER_AREA)
    return encode_png(
        np.ascontiguousarray(cv2.cvtColor(resized, cv2.COLOR_BGR2RGB), dtype=np.uint8)
    )


def fit_to_play_area(generated_rgba: Image, aspect: float) -> Image:
    if aspect <= 0:
        raise SpriteError("aspect must be positive")
    if aspect >= 1:
        size = (MAP_LONG_SIDE_PX, max(1, round(MAP_LONG_SIDE_PX / aspect)))
    else:
        size = (max(1, round(MAP_LONG_SIDE_PX * aspect)), MAP_LONG_SIDE_PX)
    rgb = np.ascontiguousarray(generated_rgba[:, :, :3])
    fitted = cv2.resize(rgb, size, interpolation=cv2.INTER_LINEAR)
    return np.ascontiguousarray(fitted, dtype=np.uint8)


class BarrioMapService:
    def __init__(self, client: MetaClient, maps_dir: Path) -> None:
        self._client = client
        self._maps_dir = maps_dir
        self._attempted: set[str] = set()
        self._generation: dict[str, int] = {}
        self._lock = threading.Lock()

    def map_path(self, campaign_id: str) -> Path:
        if CAMPAIGN_ID_PATTERN.fullmatch(campaign_id) is None:
            raise ValueError("campaign id is not a plain identifier")
        return self._maps_dir / f"{campaign_id}{MAP_FILE_SUFFIX}"

    def cached_map(self, campaign_id: str) -> Path | None:
        try:
            path = self.map_path(campaign_id)
        except ValueError:
            return None
        return path if path.is_file() else None

    def delete_map(self, campaign_id: str) -> None:
        try:
            path = self.map_path(campaign_id)
        except ValueError:
            return
        with self._lock:
            self._generation[campaign_id] = self._generation.get(campaign_id, 0) + 1
            self._attempted.discard(campaign_id)
            path.unlink(missing_ok=True)
            path.with_suffix(MAP_TEMP_SUFFIX).unlink(missing_ok=True)
            self._blocked_marker(campaign_id).unlink(missing_ok=True)

    def sweep(self, known_campaign_ids: Collection[str]) -> int:
        removed = 0
        try:
            entries = list(self._maps_dir.iterdir())
        except OSError:
            return 0
        for entry in entries:
            if entry.suffix not in MAP_SUFFIXES or not entry.is_file():
                continue
            if CAMPAIGN_ID_PATTERN.fullmatch(entry.stem) is None:
                continue
            if entry.stem in known_campaign_ids:
                continue
            try:
                entry.unlink()
            except OSError:
                continue
            removed += 1
        return removed

    def _blocked_marker(self, campaign_id: str) -> Path:
        return self._maps_dir / f"{campaign_id}{MAP_BLOCKED_SUFFIX}"

    async def ensure_map(
        self,
        campaign_id: str,
        baseline_bgr: Image,
        style_anchor_png: bytes | None,
        *,
        demo_safe: bool,
    ) -> Path | None:
        try:
            path = self.map_path(campaign_id)
        except ValueError:
            return None
        generation = self._generation.get(campaign_id, 0)
        if path.is_file():
            return path
        if demo_safe or campaign_id in self._attempted:
            return None
        if self._blocked_marker(campaign_id).exists():
            return None
        if not self._client.is_available(MetaModel.IMAGE):
            return None
        try:
            reference = baseline_reference_png(baseline_bgr)
        except SpriteError:
            logger.warning("barrio map skipped, the baseline frame is unusable")
            return None
        self._attempted.add(campaign_id)
        try:
            raw = await self._call(reference, style_anchor_png)
        except MetaRequestError as error:
            if error.is_content_policy:
                logger.warning("barrio map blocked by content policy")
                self._mark_blocked(campaign_id)
            return None
        except (MetaError, SpriteError):
            logger.warning("barrio map generation failed, keeping the night scene")
            return None
        try:
            height, width = baseline_bgr.shape[:2]
            fitted = fit_to_play_area(decode_png(raw), width / height)
            png = encode_png(fitted)
        except SpriteError:
            logger.warning("generated barrio map could not be processed")
            return None
        return self._write(path, png, campaign_id, generation)

    async def _call(
        self, reference_png: bytes, style_anchor_png: bytes | None
    ) -> bytes:
        content: list[dict[str, str]] = [
            {
                "type": "input_text",
                "text": map_prompt(style_anchor_png is not None),
            },
            {
                "type": "input_image",
                "image_url": _data_url(reference_png),
                "detail": "auto",
            },
        ]
        if style_anchor_png is not None:
            content.append(
                {
                    "type": "input_image",
                    "image_url": _data_url(style_anchor_png),
                    "detail": "auto",
                }
            )

        async def operation() -> object:
            return await self._client.sdk().responses.create(
                model=MetaModel.IMAGE.value,
                store=False,
                extra_body={
                    "input": [{"role": "user", "content": content}],
                    "tools": [IMAGE_TOOL],
                },
            )

        response = await self._client.execute(
            MAP_SPEC, operation, lambda _: Usage(images=1)
        )
        data, _ = image_payload(response)
        return data

    def _mark_blocked(self, campaign_id: str) -> None:
        try:
            self._maps_dir.mkdir(parents=True, exist_ok=True)
            self._blocked_marker(campaign_id).write_bytes(b"")
        except OSError:
            logger.warning("could not record the blocked barrio map")

    def _write(
        self, path: Path, png: bytes, campaign_id: str, generation: int
    ) -> Path | None:
        temp = path.with_suffix(MAP_TEMP_SUFFIX)
        with self._lock:
            if self._generation.get(campaign_id, 0) != generation:
                return None
            try:
                self._maps_dir.mkdir(parents=True, exist_ok=True)
                temp.write_bytes(png)
                os.replace(temp, path)
            except OSError:
                logger.warning("could not save the barrio map")
                temp.unlink(missing_ok=True)
                return None
        return path
