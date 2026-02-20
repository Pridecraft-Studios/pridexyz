import numpy as np
from PIL import ImageFile, Image
from typing import Callable, Mapping

from pridexyz.color import (
    RGBColor,
    pil_rgb_to_float_rgb,
    float_rgb_to_pil_rgb,
    PilRGBColor,
    rgb_to_oklab,
    oklab_to_rgb,
)


def generate_image_from_template(
    template_image: ImageFile.ImageFile,
    old_colors: list[RGBColor],
    new_colors: list[RGBColor],
) -> Image.Image:
    """
    Create a new PNG image based on an input image, replacing specified colors with new colors.

    Parameters:
        template_image (ImageFile): The input image.
        old_colors (list[RGBColor]): RGB color tuples to replace (0–1 floats).
        new_colors (list[RGBColor]): RGB color tuples to replace with (same length as 'old_colors').

    Returns:
        Image: The new templated image.
    """
    if len(old_colors) != len(new_colors):
        raise ValueError(
            "The length of old_colors and new_colors lists must be the same."
        )

    pixels = template_image.load()
    new_image = Image.new("RGBA", template_image.size)
    new_pixels = new_image.load()

    for y in range(template_image.height):
        for x in range(template_image.width):
            r, g, b, a = pixels[x, y]

            current_color_float = pil_rgb_to_float_rgb((r, g, b))

            replacement_color_float = current_color_float

            for target_color, replacement_color in zip(old_colors, new_colors):
                if np.allclose(current_color_float, target_color):
                    replacement_color_float = replacement_color
                    break

            new_pixels[x, y] = (*float_rgb_to_pil_rgb(replacement_color_float), a)

    return new_image


def with_binary_mask(image: Image.Image, mask: Image.Image) -> Image.Image:
    image = image.convert("RGBA")

    mask = mask.convert("L")

    empty_canvas = Image.new("RGBA", image.size, (0, 0, 0, 0))

    return Image.composite(image, empty_canvas, mask)


def apply_mask_lightness_mapping(
    image: Image.Image,
    mask: Image.Image,
    mapping: Mapping[PilRGBColor, Callable[[float], float] | None],
) -> Image.Image:
    """
    Modify image lightness in OKLab space based on mask color mapping,
    preserving transparency.
    """

    if image.size != mask.size:
        raise ValueError("Image and mask must have the same dimensions.")

    image = image.convert("RGBA")
    mask = mask.convert("RGB")

    img_pixels = image.load()
    mask_pixels = mask.load()

    width, height = image.size

    for y in range(height):
        for x in range(width):
            mask_color = mask_pixels[x, y]

            func = mapping.get(mask_color)
            if not callable(func):
                continue

            # Unpack RGBA: we only modify R, G, and B
            r, g, b, alpha = img_pixels[x, y]

            # Convert RGB part to float for processing
            float_rgb = pil_rgb_to_float_rgb((r, g, b))

            # Convert to OKLab
            lab = rgb_to_oklab(float_rgb)
            L, a_val, b_val = lab

            # Modify lightness and clamp
            new_L = np.clip(func(L), 0.0, 1.0)

            # Convert back to RGB
            new_lab = np.array([new_L, a_val, b_val])
            new_rgb = oklab_to_rgb(new_lab)
            new_rgb = np.clip(new_rgb, 0.0, 1.0)

            # Convert back to PIL format (0-255)
            new_r, new_g, new_b = float_rgb_to_pil_rgb(new_rgb)

            # Re-apply the original alpha channel
            img_pixels[x, y] = (new_r, new_g, new_b, alpha)

    return image
