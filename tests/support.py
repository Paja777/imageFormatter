"""Helpers for building images whose geometry is easy to check."""

from __future__ import annotations

from PIL import Image


RED = (255, 0, 0)
GREEN = (0, 255, 0)
BLUE = (0, 0, 255)
YELLOW = (255, 255, 0)
BLACK = (0, 0, 0)
WHITE = (255, 255, 255)


def channels(pixel: object) -> tuple[int, ...]:
    if isinstance(pixel, int):
        return (pixel,)
    return tuple(pixel)  # type: ignore[arg-type]


def almost(pixel: object, expected: tuple[int, ...], tolerance: int = 0) -> bool:
    actual = channels(pixel)
    if len(expected) > len(actual):
        return False
    return all(abs(left - right) <= tolerance for left, right in zip(actual, expected))


def color_bbox(
    image: Image.Image,
    expected: tuple[int, ...],
    tolerance: int = 0,
) -> tuple[int, int, int, int] | None:
    """Return ``(left, top, width, height)`` of pixels near ``expected``."""
    width, height = image.size
    min_x, min_y = width, height
    max_x = max_y = -1
    for y in range(height):
        for x in range(width):
            if not almost(image.getpixel((x, y)), expected, tolerance):
                continue
            min_x = min(min_x, x)
            min_y = min(min_y, y)
            max_x = max(max_x, x)
            max_y = max(max_y, y)
    if max_x < 0:
        return None
    return (min_x, min_y, max_x - min_x + 1, max_y - min_y + 1)


def pixel_values(image: Image.Image) -> tuple[object, ...]:
    """Return pixels without using the deprecated ``Image.getdata`` API."""
    reader = getattr(image, "get_flattened_data", None)
    if callable(reader):
        return tuple(reader())
    return tuple(image.getdata())


def same_pixels(left: Image.Image, right: Image.Image) -> bool:
    return left.mode == right.mode and left.size == right.size and pixel_values(left) == pixel_values(right)


def contains_color(
    image: Image.Image,
    expected: tuple[int, ...],
    tolerance: int = 0,
) -> bool:
    return any(almost(pixel, expected, tolerance) for pixel in pixel_values(image))


def columns(width: int, height: int, colors: tuple[tuple[int, int, int], ...]) -> Image.Image:
    image = Image.new("RGB", (width, height))
    column_width = width // len(colors)
    for index, color in enumerate(colors):
        left = index * column_width
        block_width = width - left if index == len(colors) - 1 else column_width
        image.paste(Image.new("RGB", (block_width, height), color), (left, 0))
    return image


def rows(width: int, height: int, colors: tuple[tuple[int, int, int], ...]) -> Image.Image:
    image = Image.new("RGB", (width, height))
    row_height = height // len(colors)
    for index, color in enumerate(colors):
        top = index * row_height
        block_height = height - top if index == len(colors) - 1 else row_height
        image.paste(Image.new("RGB", (width, block_height), color), (0, top))
    return image


def quadrants(width: int, height: int) -> Image.Image:
    image = Image.new("RGB", (width, height))
    mid_x, mid_y = width // 2, height // 2
    image.paste(Image.new("RGB", (mid_x, mid_y), RED), (0, 0))
    image.paste(Image.new("RGB", (width - mid_x, mid_y), GREEN), (mid_x, 0))
    image.paste(Image.new("RGB", (mid_x, height - mid_y), BLUE), (0, mid_y))
    image.paste(Image.new("RGB", (width - mid_x, height - mid_y), YELLOW), (mid_x, mid_y))
    return image
