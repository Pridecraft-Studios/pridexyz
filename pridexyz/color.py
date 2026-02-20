import colour
import numpy as np
from PIL import Image
from colour.models import RGB_COLOURSPACE_sRGB
from numpy.typing import NDArray

OkLabColor = NDArray[np.float64]
RGBColor = NDArray[np.float64]
PilRGBColor = tuple[int, int, int]


def convert_hex_to_rgb(hex_color: str) -> np.ndarray:
    """
    Convert a hex color string to sRGB (0–1 float).
    """
    hex_color = hex_color.lstrip("#")
    if len(hex_color) != 6:
        raise ValueError("Input should be a 6-character hex color code.")

    rgb_255 = np.array(
        [
            int(hex_color[0:2], 16),
            int(hex_color[2:4], 16),
            int(hex_color[4:6], 16),
        ],
        dtype=float,
    )

    return rgb_255 / 255.0


def rgb_to_oklab(rgb: RGBColor) -> OkLabColor:
    """
    Convert sRGB float (0–1) to OKLab.
    """
    return colour.convert(rgb, "RGB", "OKLAB", source_colourspace=RGB_COLOURSPACE_sRGB)


def oklab_to_rgb(lab: OkLabColor) -> RGBColor:
    """
    Convert OKLab back to sRGB float (0–1).
    """
    return colour.convert(lab, "OKLAB", "RGB", target_colourspace=RGB_COLOURSPACE_sRGB)


def make_oklab_gradient(colors: list[RGBColor], width: int) -> Image.Image:
    """
    Create a 1px-high gradient image interpolated in OKLab space.

    Parameters:
        colors (list[RGBColor]): Input colors in sRGB (0–1)
        width (int):Output image width.

    Returns:
        PIL.Image.Image: A horizontal OKLab-interpolated gradient.
    """
    if len(colors) < 2:
        raise ValueError("At least two colors are required to make a gradient.")

    oklab_colors = np.array([rgb_to_oklab(c) for c in colors], dtype=float)

    # Segment boundaries across the width
    n = len(colors) - 1
    segment_positions = np.linspace(0, 1, n + 1)

    # Output pixel x positions normalized to 0–1
    x = np.linspace(0, 1, width)

    # Find segment index for each pixel
    idx = np.clip(np.searchsorted(segment_positions, x, side="right") - 1, 0, n - 1)

    # Local interpolation parameter t within segment
    t = (x - segment_positions[idx]) / (
        segment_positions[idx + 1] - segment_positions[idx]
    )

    # Interpolate in OKLab
    lab1 = oklab_colors[idx]
    lab2 = oklab_colors[idx + 1]
    lab_interp = lab1 * (1 - t)[:, None] + lab2 * t[:, None]

    rgb = np.clip(oklab_to_rgb(lab_interp), 0, 1)
    rgb_255 = (rgb * 255).astype(np.uint8)
    img = Image.fromarray(rgb_255.reshape(1, width, 3), mode="RGB")
    return img


def pil_rgb_to_float_rgb(rgb: PilRGBColor) -> RGBColor:
    """Convert PIL RGB (0–255 ints) to colour-science RGB floats."""
    return np.array(rgb, dtype=float) / 255.0


def float_rgb_to_pil_rgb(rgb: RGBColor) -> PilRGBColor:
    """Convert colour-science RGB floats to PIL RGB ints (0–255)."""
    # noinspection PyTypeChecker
    return tuple(int(max(0, min(1, c)) * 255) for c in rgb)
