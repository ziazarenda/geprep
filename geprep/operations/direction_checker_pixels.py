"""Pixels for the Direction Checker texture (pure numpy, no Blender needed).

The tile is 2 x 2 cells. Every cell shows a small axis frame in its
bottom-left corner: a cyan arrow along +U and an orange arrow along +V.
Pixel row 0 is the bottom of the image, the same as UV v = 0.
"""

import numpy as np

CELL_PIXELS = 128
TILE_CELLS = 2
TILE_PIXELS = CELL_PIXELS * TILE_CELLS

DARK_CELL = (0.10, 0.10, 0.10)
LIGHT_CELL = (0.78, 0.78, 0.78)
CYAN = (0.0, 0.80, 1.0)
ORANGE = (1.0, 0.45, 0.0)

_SUPERSAMPLE = 3
_ORIGIN = 0.17
_SHAFT_END = 0.60
_TIP = 0.88
_SHAFT_HALF_WIDTH = 0.030
_HEAD_HALF_WIDTH = 0.105
_OUTLINE = 0.020


def _arrow_mask(along, across):
    """Return a boolean mask of an arrow that points toward +along."""
    shaft = (
        (along >= _ORIGIN - _SHAFT_HALF_WIDTH)
        & (along <= _SHAFT_END)
        & (np.abs(across - _ORIGIN) <= _SHAFT_HALF_WIDTH)
    )
    head = (
        (along >= _SHAFT_END)
        & (along <= _TIP)
        & (
            np.abs(across - _ORIGIN)
            <= (_TIP - along) / (_TIP - _SHAFT_END) * _HEAD_HALF_WIDTH
        )
    )
    return shaft | head


def _dilate(mask, radius):
    """Grow a boolean mask by `radius` pixels."""
    grown = mask.copy()
    reach = int(np.ceil(radius))

    for dy in range(-reach, reach + 1):
        for dx in range(-reach, reach + 1):
            if dx * dx + dy * dy <= radius * radius:
                grown |= np.roll(np.roll(mask, dy, axis=0), dx, axis=1)

    return grown


def build_direction_checker_pixels():
    """Return float32 RGBA pixels shaped (TILE_PIXELS, TILE_PIXELS, 4)."""
    size = TILE_PIXELS * _SUPERSAMPLE
    cell = CELL_PIXELS * _SUPERSAMPLE

    rows, columns = np.mgrid[0:size, 0:size]
    cell_row, cell_column = rows // cell, columns // cell
    u = ((columns % cell) + 0.5) / cell
    v = ((rows % cell) + 0.5) / cell

    light = (cell_row + cell_column) % 2 == 1
    image = np.where(
        light[..., None],
        np.array(LIGHT_CELL),
        np.array(DARK_CELL),
    )

    arrow_u = _arrow_mask(u, v)
    arrow_v = _arrow_mask(v, u)
    arrows = arrow_u | arrow_v

    outline = _dilate(arrows, _OUTLINE * cell) & ~arrows
    outline_color = np.where(
        light[..., None],
        np.zeros(3),
        np.ones(3),
    )

    image = np.where(outline[..., None], outline_color, image)
    image = np.where(arrow_v[..., None], np.array(ORANGE), image)
    image = np.where(arrow_u[..., None], np.array(CYAN), image)

    image = image.reshape(
        TILE_PIXELS, _SUPERSAMPLE, TILE_PIXELS, _SUPERSAMPLE, 3,
    ).mean(axis=(1, 3))

    alpha = np.ones((TILE_PIXELS, TILE_PIXELS, 1))

    return np.concatenate((image, alpha), axis=2).astype(np.float32)
