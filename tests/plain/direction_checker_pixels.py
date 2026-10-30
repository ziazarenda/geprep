"""Run with plain Python: python tests/direction_checker_pixels.py"""

import importlib.util
from pathlib import Path

import numpy as np

ROOT = Path(__file__).resolve().parents[2]
spec = importlib.util.spec_from_file_location(
    "pixels",
    ROOT / "geprep" / "operations" / "direction_checker_pixels.py",
)
pixels = importlib.util.module_from_spec(spec)
spec.loader.exec_module(pixels)


def check(condition, message):
    if not condition:
        raise AssertionError(message)

    print("PASS:", message)


image = pixels.build_direction_checker_pixels()
size = pixels.TILE_PIXELS
cell = pixels.CELL_PIXELS

check(
    image.shape == (size, size, 4) and image.dtype == np.float32,
    "tile is float32 RGBA of the expected size",
)
check(
    image.min() >= 0.0 and image.max() <= 1.0 and np.all(image[..., 3] == 1),
    "values are in 0-1 and fully opaque",
)


def near(pixel, color, tolerance=0.08):
    return np.all(np.abs(pixel[:3] - np.array(color)) < tolerance)


# Row 0 is the bottom. The arrows sit in the bottom-left of every cell.
for cell_x in range(pixels.TILE_CELLS):
    for cell_y in range(pixels.TILE_CELLS):
        left, bottom = cell_x * cell, cell_y * cell
        along_u = image[bottom + int(cell * 0.17), left + int(cell * 0.45)]
        along_v = image[bottom + int(cell * 0.45), left + int(cell * 0.17)]
        tip_u = image[bottom + int(cell * 0.17), left + int(cell * 0.80)]
        tip_v = image[bottom + int(cell * 0.80), left + int(cell * 0.17)]

        check(near(along_u, pixels.CYAN), f"cell {cell_x},{cell_y}: +U shaft is cyan")
        check(near(tip_u, pixels.CYAN), f"cell {cell_x},{cell_y}: +U head is cyan")
        check(near(along_v, pixels.ORANGE), f"cell {cell_x},{cell_y}: +V shaft is orange")
        check(near(tip_v, pixels.ORANGE), f"cell {cell_x},{cell_y}: +V head is orange")

dark = image[cell // 2 + 40, cell // 2 + 40, :3]
light = image[cell // 2 + 40, cell + cell // 2 + 40, :3]
check(
    near(np.append(dark, 1), pixels.DARK_CELL)
    != near(np.append(light, 1), pixels.DARK_CELL),
    "neighbouring cells alternate dark and light",
)

print("ALL DIRECTION CHECKER PIXEL TESTS PASSED")
