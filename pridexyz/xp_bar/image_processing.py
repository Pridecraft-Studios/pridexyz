import numpy as np
from PIL import Image

from pridexyz.color import (
    RGBColor,
    oklab_to_rgb,
    rgb_to_oklab,
)

MIN_BRIGHTNESS = 0.25


def _ensure_rgba(image: Image.Image) -> Image.Image:
    return image.convert("RGBA")


def _to_float_array(image: Image.Image) -> np.ndarray:
    return np.asarray(_ensure_rgba(image), dtype=np.float64) / 255.0


def _relative_brightness(template_rgba: np.ndarray) -> np.ndarray:
    rgb = template_rgba[..., :3]
    alpha = template_rgba[..., 3]

    flat_rgb = rgb.reshape(-1, 3)
    flat_L = np.array(
        [rgb_to_oklab(c)[0] for c in flat_rgb],
        dtype=np.float64,
    ).reshape(rgb.shape[:2])

    visible = alpha > 0
    if not visible.any():
        return np.ones_like(flat_L)

    visible_L = flat_L[visible]
    bright_L = float(visible_L.max())
    if bright_L <= 0:
        return np.ones_like(flat_L)

    rel = np.zeros_like(flat_L)
    rel[visible] = flat_L[visible] / bright_L
    return rel


def _recolor_with_target_lab(
    template_rgba: np.ndarray,
    target_lab_per_pixel: np.ndarray,
) -> np.ndarray:
    rgb = template_rgba[..., :3]
    alpha = template_rgba[..., 3:4]

    rel = _relative_brightness(template_rgba)

    factor = MIN_BRIGHTNESS + (1.0 - MIN_BRIGHTNESS) * rel
    factor3 = factor[..., None]

    target_L = target_lab_per_pixel[..., 0:1]
    target_a = target_lab_per_pixel[..., 1:2]
    target_b = target_lab_per_pixel[..., 2:3]

    scaled_L = np.clip(target_L * factor3, 0.0, 1.0)
    scaled_a = target_a * factor3
    scaled_b = target_b * factor3

    new_lab = np.concatenate([scaled_L, scaled_a, scaled_b], axis=-1).reshape(-1, 3)
    new_rgb = np.array(
        [oklab_to_rgb(c) for c in new_lab],
        dtype=np.float64,
    ).reshape(rgb.shape)

    new_rgb = np.clip(new_rgb, 0.0, 1.0)
    return np.concatenate([new_rgb, alpha], axis=-1)


def _banded_target_map(
    width: int,
    height: int,
    palette_colors: list[RGBColor],
) -> np.ndarray:
    if not palette_colors:
        raise ValueError("At least one palette color is required")
    palette_lab = np.array(
        [rgb_to_oklab(c) for c in palette_colors],
        dtype=np.float64,
    )
    num_colors = palette_lab.shape[0]
    segment_width = max(1, width / num_colors)
    rows = np.empty((height, width, 3), dtype=np.float64)
    for x in range(width):
        idx = int(np.clip(x // segment_width, 0, num_colors - 1))
        rows[:, x, :] = palette_lab[idx]
    return rows


def _gradient_target_map(
    width: int,
    height: int,
    palette_colors: list[RGBColor],
) -> np.ndarray:
    from pridexyz.color import make_oklab_gradient

    if not palette_colors:
        raise ValueError("At least one palette color is required")
    if len(palette_colors) < 2:
        return _banded_target_map(width, height, palette_colors)

    gradient = make_oklab_gradient(palette_colors, width)
    grad_rgba = _to_float_array(gradient)
    grad_lab = np.array(
        [rgb_to_oklab(c) for c in grad_rgba[..., :3].reshape(-1, 3)],
        dtype=np.float64,
    ).reshape(grad_rgba.shape[0], grad_rgba.shape[1], 3)
    if grad_lab.shape[0] != 1:
        grad_lab = grad_lab.mean(axis=0, keepdims=True)
    return np.broadcast_to(grad_lab, (height, width, 3)).copy()


def recolor_banded(
    template: Image.Image,
    palette_colors: list[RGBColor],
) -> Image.Image:
    template_rgba = _to_float_array(template)
    h, w = template_rgba.shape[:2]
    target_lab = _banded_target_map(w, h, palette_colors)
    out = _recolor_with_target_lab(template_rgba, target_lab)
    out_u8 = (out * 255.0).round().clip(0, 255).astype(np.uint8)
    return Image.fromarray(out_u8, mode="RGBA")


def recolor_gradient(
    template: Image.Image,
    palette_colors: list[RGBColor],
) -> Image.Image:
    template_rgba = _to_float_array(template)
    h, w = template_rgba.shape[:2]
    target_lab = _gradient_target_map(w, h, palette_colors)
    out = _recolor_with_target_lab(template_rgba, target_lab)
    out_u8 = (out * 255.0).round().clip(0, 255).astype(np.uint8)
    return Image.fromarray(out_u8, mode="RGBA")