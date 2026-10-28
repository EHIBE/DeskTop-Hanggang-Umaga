from dataclasses import dataclass
from typing import Final

import cv2
import numpy as np
import numpy.typing as npt

from config import (
    A4_H_CM,
    A4_W_CM,
    BRIGHTNESS_CHANGE_ALERT,
    CAMERA_MOVED_CM,
    DEFAULT_PLAY_H_CM,
    DEFAULT_PLAY_W_CM,
    PX_PER_CM,
)
from rules.geometry import FOREST_EDGE_CM

Image = npt.NDArray[np.uint8]
Matrix = npt.NDArray[np.float64]
Point = tuple[float, float]
Corners = tuple[Point, Point, Point, Point]

MIN_PLAY_CM: Final = 30.0
MAX_PLAY_CM: Final = 120.0
MIN_SHEET_AREA_PX: Final = 2_500.0
MIN_BRIGHTNESS: Final = 1.0
CORNER_COUNT: Final = 4
POLY_EPSILON_RATIO: Final = 0.02


class CalibrationError(Exception):
    pass


@dataclass(frozen=True)
class PlayArea:
    width_cm: float = DEFAULT_PLAY_W_CM
    height_cm: float = DEFAULT_PLAY_H_CM
    px_per_cm: int = PX_PER_CM

    def __post_init__(self) -> None:
        for size in (self.width_cm, self.height_cm):
            if not MIN_PLAY_CM <= size <= MAX_PLAY_CM:
                raise CalibrationError("play area must be 30 to 120 cm per side")
        if self.width_cm < A4_W_CM or self.height_cm < A4_W_CM:
            raise CalibrationError("play area must fit the A4 sheet")

    @property
    def warped_size(self) -> tuple[int, int]:
        return round(self.width_cm * self.px_per_cm), round(
            self.height_cm * self.px_per_cm
        )

    @property
    def center_cm(self) -> Point:
        return self.width_cm / 2, self.height_cm / 2


@dataclass(frozen=True)
class Calibration:
    homography: Matrix
    area: PlayArea

    def to_cm(self, camera_point: Point) -> Point:
        source = np.array([[camera_point]], dtype=np.float64)
        warped = cv2.perspectiveTransform(source, self.homography)[0][0]
        return float(warped[0]) / self.area.px_per_cm, float(
            warped[1]
        ) / self.area.px_per_cm

    def homography_list(self) -> list[float]:
        return [float(value) for value in self.homography.flatten()]


def _signed_area(points: npt.NDArray[np.float64]) -> float:
    x = points[:, 0]
    y = points[:, 1]
    return 0.5 * float(np.dot(x, np.roll(y, -1)) - np.dot(y, np.roll(x, -1)))


def _validate_corners(points: npt.NDArray[np.float64]) -> None:
    if points.shape != (CORNER_COUNT, 2) or not np.all(np.isfinite(points)):
        raise CalibrationError("need exactly 4 finite corner points")
    if not cv2.isContourConvex(points.astype(np.float32).reshape(-1, 1, 2)):
        raise CalibrationError("corners must form a convex shape")
    area = _signed_area(points)
    if area <= 0:
        raise CalibrationError(
            "corners must go top-left, top-right, bottom-right, bottom-left"
        )
    if area < MIN_SHEET_AREA_PX:
        raise CalibrationError("the sheet is too small in the camera view")


def compute_calibration(corners_px: Corners, area: PlayArea) -> Calibration:
    source = np.array(corners_px, dtype=np.float64)
    _validate_corners(source)
    cx, cy = area.center_cm
    half_w, half_h = A4_W_CM / 2, A4_H_CM / 2
    sheet_cm = np.array(
        [
            [cx - half_w, cy - half_h],
            [cx + half_w, cy - half_h],
            [cx + half_w, cy + half_h],
            [cx - half_w, cy + half_h],
        ],
        dtype=np.float64,
    )
    target = (sheet_cm * area.px_per_cm).astype(np.float32)
    matrix = cv2.getPerspectiveTransform(source.astype(np.float32), target)
    return Calibration(homography=matrix.astype(np.float64), area=area)


def warp(frame: Image, calibration: Calibration) -> Image:
    warped = cv2.warpPerspective(
        frame, calibration.homography, calibration.area.warped_size
    )
    return np.asarray(warped, dtype=np.uint8)


def distance_cm(calibration: Calibration, start_px: Point, end_px: Point) -> float:
    start = calibration.to_cm(start_px)
    end = calibration.to_cm(end_px)
    return float(np.hypot(end[0] - start[0], end[1] - start[1]))


def _point(values: npt.NDArray[np.float64]) -> Point:
    return float(values[0]), float(values[1])


def order_corners(points: npt.NDArray[np.float64]) -> Corners:
    sums = points.sum(axis=1)
    diffs = points[:, 1] - points[:, 0]
    top_left = points[int(np.argmin(sums))]
    bottom_right = points[int(np.argmax(sums))]
    top_right = points[int(np.argmin(diffs))]
    bottom_left = points[int(np.argmax(diffs))]
    return (
        _point(top_left),
        _point(top_right),
        _point(bottom_right),
        _point(bottom_left),
    )


def corners_from_mask(mask: Image) -> Corners:
    binary = (mask > 0).astype(np.uint8)
    contours, _ = cv2.findContours(binary, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)
    if not contours:
        raise CalibrationError("no sheet in the mask")
    contour = max(contours, key=cv2.contourArea)
    if cv2.contourArea(contour) < MIN_SHEET_AREA_PX:
        raise CalibrationError("the sheet mask is too small")
    perimeter = cv2.arcLength(contour, True)
    approx = cv2.approxPolyDP(contour, POLY_EPSILON_RATIO * perimeter, True)
    points = (
        approx.reshape(-1, 2)
        if len(approx) == CORNER_COUNT
        else cv2.boxPoints(cv2.minAreaRect(contour))
    )
    return order_corners(np.asarray(points, dtype=np.float64))


def forest_edge_mask(area: PlayArea) -> Image:
    width, height = area.warped_size
    edge = round(FOREST_EDGE_CM * area.px_per_cm)
    mask = np.full((height, width), 255, dtype=np.uint8)
    mask[edge : height - edge, edge : width - edge] = 0
    return mask


def _gray(frame: Image) -> npt.NDArray[np.float32]:
    if frame.ndim == 2:
        return frame.astype(np.float32)
    gray: npt.NDArray[np.float32] = cv2.cvtColor(frame, cv2.COLOR_BGR2GRAY).astype(
        np.float32
    )
    return gray


def camera_shift_cm(baseline: Image, current: Image, area: PlayArea) -> float:
    if baseline.shape != current.shape:
        raise CalibrationError("baseline and current frame sizes differ")
    weights = forest_edge_mask(area).astype(np.float32) / 255.0
    base = _gray(baseline) * weights
    now = _gray(current) * weights
    window = cv2.createHanningWindow((base.shape[1], base.shape[0]), cv2.CV_32F)
    (dx, dy), _ = cv2.phaseCorrelate(base, now, window)
    return float(np.hypot(dx, dy)) / area.px_per_cm


def is_camera_moved(baseline: Image, current: Image, area: PlayArea) -> bool:
    return camera_shift_cm(baseline, current, area) > CAMERA_MOVED_CM


def brightness(frame: Image) -> float:
    return float(_gray(frame).mean())


def brightness_change(baseline_brightness: float, frame: Image) -> float:
    base = max(baseline_brightness, MIN_BRIGHTNESS)
    return (brightness(frame) - base) / base


def is_lighting_changed(baseline_brightness: float, frame: Image) -> bool:
    return abs(brightness_change(baseline_brightness, frame)) > BRIGHTNESS_CHANGE_ALERT


def is_too_dark(baseline_brightness: float, frame: Image) -> bool:
    return brightness_change(baseline_brightness, frame) < -BRIGHTNESS_CHANGE_ALERT
