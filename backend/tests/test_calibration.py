import cv2
import numpy as np
import numpy.typing as npt
import pytest

from capture.calibration import (
    CalibrationError,
    Corners,
    PlayArea,
    brightness_change,
    camera_shift_cm,
    compute_calibration,
    corners_from_mask,
    distance_cm,
    forest_edge_mask,
    is_camera_moved,
    is_lighting_changed,
    is_too_dark,
    order_corners,
    warp,
)

Image = npt.NDArray[np.uint8]
AREA = PlayArea()
CAMERA_SIZE = (1920, 1080)
CAMERA_SHEET: Corners = (
    (820.0, 300.0),
    (1140.0, 310.0),
    (1190.0, 760.0),
    (780.0, 750.0),
)


def textured_board(seed: int = 7) -> Image:
    width, height = AREA.warped_size
    rng = np.random.default_rng(seed)
    noise = rng.integers(0, 255, size=(height // 8, width // 8), dtype=np.uint8)
    board = cv2.resize(noise, (width, height), interpolation=cv2.INTER_NEAREST)
    return np.asarray(cv2.cvtColor(board, cv2.COLOR_GRAY2BGR), dtype=np.uint8)


def camera_view(board: Image) -> Image:
    calibration = compute_calibration(CAMERA_SHEET, AREA)
    inverse = np.linalg.inv(calibration.homography)
    view = cv2.warpPerspective(board, inverse, CAMERA_SIZE)
    return np.asarray(view, dtype=np.uint8)


def test_warped_size_is_20_px_per_cm() -> None:
    assert AREA.warped_size == (1200, 800)
    assert AREA.center_cm == (30.0, 20.0)


@pytest.mark.parametrize(
    ("width", "height"), [(20.0, 40.0), (60.0, 10.0), (200.0, 40.0)]
)
def test_play_area_bounds(width: float, height: float) -> None:
    with pytest.raises(CalibrationError):
        PlayArea(width_cm=width, height_cm=height)


def test_sheet_corners_map_to_a4_rectangle() -> None:
    calibration = compute_calibration(CAMERA_SHEET, AREA)
    top_left = calibration.to_cm(CAMERA_SHEET[0])
    bottom_right = calibration.to_cm(CAMERA_SHEET[2])
    assert top_left == pytest.approx((30 - 10.5, 20 - 14.85), abs=1e-6)
    assert bottom_right == pytest.approx((30 + 10.5, 20 + 14.85), abs=1e-6)


def test_ruler_check_within_half_a_centimeter() -> None:
    calibration = compute_calibration(CAMERA_SHEET, AREA)
    inverse = np.linalg.inv(calibration.homography)
    board_points = np.array(
        [[[25.0 * 20, 20.0 * 20], [35.0 * 20, 20.0 * 20]]], dtype=np.float64
    )
    camera_points = cv2.perspectiveTransform(board_points, inverse)[0]
    start = (float(camera_points[0][0]), float(camera_points[0][1]))
    end = (float(camera_points[1][0]), float(camera_points[1][1]))
    assert abs(distance_cm(calibration, start, end) - 10.0) < 0.5


def test_warp_recovers_the_top_down_board() -> None:
    board = textured_board()
    calibration = compute_calibration(CAMERA_SHEET, AREA)
    recovered = warp(camera_view(board), calibration)
    assert recovered.shape == board.shape
    center = (slice(300, 500), slice(450, 750))
    difference = np.abs(recovered[center].astype(int) - board[center].astype(int))
    assert float(np.median(difference)) < 5


@pytest.mark.parametrize(
    "corners",
    [
        ((820.0, 300.0), (780.0, 750.0), (1190.0, 760.0), (1140.0, 310.0)),
        ((820.0, 300.0), (1190.0, 760.0), (1140.0, 310.0), (780.0, 750.0)),
        ((100.0, 100.0), (110.0, 100.0), (110.0, 110.0), (100.0, 110.0)),
        ((0.0, 0.0), (0.0, 0.0), (0.0, 0.0), (0.0, 0.0)),
    ],
)
def test_bad_corners_are_rejected(corners: Corners) -> None:
    with pytest.raises(CalibrationError):
        compute_calibration(corners, AREA)


def test_non_finite_corners_are_rejected() -> None:
    corners: Corners = ((float("nan"), 0.0), (10.0, 0.0), (10.0, 10.0), (0.0, 10.0))
    with pytest.raises(CalibrationError):
        compute_calibration(corners, AREA)


def test_order_corners_sorts_any_input_order() -> None:
    shuffled = np.array(
        [CAMERA_SHEET[2], CAMERA_SHEET[0], CAMERA_SHEET[3], CAMERA_SHEET[1]]
    )
    assert order_corners(shuffled) == CAMERA_SHEET


def test_corners_from_sheet_mask() -> None:
    mask = np.zeros((CAMERA_SIZE[1], CAMERA_SIZE[0]), dtype=np.uint8)
    cv2.fillConvexPoly(mask, np.array(CAMERA_SHEET, dtype=np.int32), 255)
    found = corners_from_mask(mask)
    for got, expected in zip(found, CAMERA_SHEET, strict=True):
        assert got == pytest.approx(expected, abs=3)


def test_empty_or_tiny_mask_is_rejected() -> None:
    with pytest.raises(CalibrationError):
        corners_from_mask(np.zeros((100, 100), dtype=np.uint8))
    tiny = np.zeros((100, 100), dtype=np.uint8)
    tiny[10:20, 10:20] = 255
    with pytest.raises(CalibrationError):
        corners_from_mask(tiny)


def test_forest_edge_mask_is_a_5cm_ring() -> None:
    mask = forest_edge_mask(AREA)
    assert mask[0, 0] == 255
    assert mask[99, 600] == 255
    assert mask[100, 600] == 0
    assert mask[400, 600] == 0


def shifted(image: Image, dx: int, dy: int) -> Image:
    matrix = np.array([[1.0, 0.0, dx], [0.0, 1.0, dy]], dtype=np.float64)
    moved = cv2.warpAffine(
        image, matrix, (image.shape[1], image.shape[0]), borderMode=cv2.BORDER_REFLECT
    )
    return np.asarray(moved, dtype=np.uint8)


def test_camera_bump_over_2cm_is_detected() -> None:
    board = textured_board()
    assert camera_shift_cm(board, shifted(board, 50, 0), AREA) == pytest.approx(
        2.5, abs=0.3
    )
    assert is_camera_moved(board, shifted(board, 50, 0), AREA)


def test_small_jitter_is_not_a_camera_move() -> None:
    board = textured_board()
    assert not is_camera_moved(board, shifted(board, 10, 0), AREA)
    assert not is_camera_moved(board, board, AREA)


def test_camera_move_needs_matching_sizes() -> None:
    with pytest.raises(CalibrationError):
        camera_shift_cm(textured_board(), np.zeros((10, 10, 3), dtype=np.uint8), AREA)


def test_brightness_change_and_darkness() -> None:
    frame = np.full((10, 10, 3), 100, dtype=np.uint8)
    dark = np.full((10, 10, 3), 60, dtype=np.uint8)
    bright = np.full((10, 10, 3), 140, dtype=np.uint8)
    assert brightness_change(100.0, frame) == pytest.approx(0.0)
    assert is_too_dark(100.0, dark)
    assert not is_too_dark(100.0, bright)
    assert is_lighting_changed(100.0, bright)
    assert not is_lighting_changed(100.0, frame)
