from collections.abc import Sequence
from dataclasses import dataclass
from typing import Final

import numpy as np
import numpy.typing as npt

from vision.signature import (
    AREA_WEIGHT,
    ASPECT_WEIGHT,
    HIST_BINS,
    HIST_WEIGHT,
    Signature,
    SignatureError,
    bhattacharyya,
)

MATCH_THRESHOLD: Final = 0.78
MIN_HISTOGRAM_SIMILARITY: Final = 0.70
AMBIGUITY_MARGIN: Final = 0.04
SMOOTH_KERNEL: Final = (0.25, 0.5, 0.25)


@dataclass(frozen=True)
class StoredSignature:
    unit_id: str
    signature: Signature


@dataclass(frozen=True)
class ReturningMatch:
    unit_id: str
    score: float
    runner_up: float


def _ratio(first: float, second: float) -> float:
    high = max(first, second)
    if high <= 0:
        return 0.0
    return min(first, second) / high


def smooth_histogram(histogram: tuple[float, ...]) -> tuple[float, ...]:
    if len(histogram) != int(np.prod(HIST_BINS)):
        raise SignatureError("histogram has the wrong size")
    grid: npt.NDArray[np.float64] = np.asarray(histogram, dtype=np.float64).reshape(
        HIST_BINS
    )
    for axis in range(grid.ndim):
        mode = "wrap" if axis == 0 else "nearest"
        blurred = np.zeros_like(grid)
        for offset, weight in zip((-1, 0, 1), SMOOTH_KERNEL, strict=True):
            blurred += weight * _shifted(grid, offset, axis, mode)
        grid = blurred
    total = float(grid.sum())
    if total <= 0:
        raise SignatureError("histogram is empty")
    return tuple(float(value) for value in (grid / total).ravel())


def _shifted(
    grid: npt.NDArray[np.float64], offset: int, axis: int, mode: str
) -> npt.NDArray[np.float64]:
    if offset == 0:
        return grid
    if mode == "wrap":
        shifted: npt.NDArray[np.float64] = np.roll(grid, offset, axis=axis)
        return shifted
    padded = np.concatenate(
        [
            np.take(grid, [0], axis=axis),
            grid,
            np.take(grid, [grid.shape[axis] - 1], axis=axis),
        ],
        axis=axis,
    )
    size = grid.shape[axis]
    start = 1 - offset
    result: npt.NDArray[np.float64] = np.take(
        padded, range(start, start + size), axis=axis
    )
    return result


def returning_score(first: Signature, second: Signature) -> tuple[float, float]:
    similarity = 1.0 - bhattacharyya(
        smooth_histogram(first.histogram), smooth_histogram(second.histogram)
    )
    score = (
        HIST_WEIGHT * similarity
        + AREA_WEIGHT * _ratio(first.area_cm2, second.area_cm2)
        + ASPECT_WEIGHT * _ratio(first.aspect, second.aspect)
    )
    return score, similarity


def _scored(
    stored: Sequence[StoredSignature], candidate: Signature
) -> list[tuple[float, str]]:
    scored: list[tuple[float, str]] = []
    for item in stored:
        try:
            score, similarity = returning_score(item.signature, candidate)
        except SignatureError:
            continue
        if similarity < MIN_HISTOGRAM_SIMILARITY:
            continue
        scored.append((score, item.unit_id))
    scored.sort(key=lambda entry: entry[0], reverse=True)
    return scored


def find_returning(
    stored: Sequence[StoredSignature], candidate: Signature
) -> ReturningMatch | None:
    scored = _scored(stored, candidate)
    if not scored:
        return None
    best_score, best_id = scored[0]
    if best_score < MATCH_THRESHOLD:
        return None
    runner_up = scored[1][0] if len(scored) > 1 else 0.0
    if best_score - runner_up < AMBIGUITY_MARGIN:
        return None
    return ReturningMatch(unit_id=best_id, score=best_score, runner_up=runner_up)


def match_returning(
    stored: Sequence[StoredSignature], candidate: Signature
) -> str | None:
    found = find_returning(stored, candidate)
    return None if found is None else found.unit_id
