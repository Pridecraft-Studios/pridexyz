from pathlib import Path

import numpy as np
from PIL import ImageFile, Image
from PIL.Image import Transpose

from pridexyz.color import (
    RGBColor,
    convert_hex_to_rgb,
    pil_rgb_to_float_rgb,
    float_rgb_to_pil_rgb,
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


def apply_template(
    template_config: dict,
    replacement_colors: list[RGBColor],
    src_dir: Path,
    transpose: Transpose = None,
) -> Image.Image:
    """
    Apply templating on an image with layers and color replacements.

    Parameters:
        src_dir (Path): The src directory
        template_config (dict): Configuration for templating.
        replacement_colors (list[RGBColor]): New colors for templating (float 0–1 RGB).
        transpose (Transpose): The transpose to apply. Default: None

    Returns:
        Image: The templated image.
    """
    size = (100, 100)
    base_template = None
    target_colors = None

    if "template" in template_config:
        # Convert hex to float RGB
        target_colors = [
            convert_hex_to_rgb(c) for c in template_config["templating_colors"]
        ]
        base_template = Image.open(src_dir / template_config["template"]).convert(
            "RGBA"
        )
        size = base_template.size

    composed_image = Image.new("RGBA", size).convert("RGBA")

    # Apply "before" layers
    if "before" in template_config:
        for before_layer in template_config["before"]:
            layer_image = Image.open(src_dir / before_layer).convert("RGBA")
            composed_image = Image.alpha_composite(composed_image, layer_image)

    # Apply template with color replacement
    if "template" in template_config:
        replaced_image = generate_image_from_template(
            base_template, target_colors, replacement_colors
        )
        composed_image = Image.alpha_composite(composed_image, replaced_image)

    # Apply "after" layers
    if "after" in template_config:
        for after_layer in template_config["after"]:
            layer_image = Image.open(src_dir / after_layer).convert("RGBA")
            composed_image = Image.alpha_composite(composed_image, layer_image)

    # transpose if needed
    if transpose is not None:
        composed_image = composed_image.transpose(transpose)

    return composed_image


def nine_slice_scale(
    image: Image.Image,
    left: int,
    top: int,
    right: int,
    bottom: int,
    width: int,
    height: int,
    tile=False,
    padding=(0, 0, 0, 0),
) -> Image.Image:
    """
    Scales an image using 9-slice scaling, accounting for padding.
    """
    pad_left, pad_top, pad_right, pad_bottom = padding
    src_width, src_height = image.size

    cropped_image = image.crop(
        (pad_left, pad_top, src_width - pad_right, src_height - pad_bottom)
    )
    cropped_width, cropped_height = cropped_image.size

    slices = slice_dict(bottom, cropped_height, cropped_width, left, right, top)
    target_slices = slice_dict(bottom, height, width, left, right, top)

    result = Image.new("RGBA", (width, height))

    for key, box in slices.items():
        region = cropped_image.crop(box)
        target_box = target_slices[key]
        target_width = target_box[2] - target_box[0]
        target_height = target_box[3] - target_box[1]

        if key in ["top", "center", "bottom"] and tile:
            tiled = Image.new("RGBA", (target_width, region.height))
            for x in range(0, target_width, region.width):
                tiled.paste(region, (x, 0))
            region = tiled
        elif key in ["left", "center", "right"] and tile:
            tiled = Image.new("RGBA", (region.width, target_height))
            for y in range(0, target_height, region.height):
                tiled.paste(region, (0, y))
            region = tiled

        if key == "center" and tile:
            tiled = Image.new("RGBA", (target_width, target_height))
            for x in range(0, target_width, region.width):
                for y in range(0, target_height, region.height):
                    tiled.paste(
                        region.crop(
                            (
                                0,
                                0,
                                min(region.width, target_width - x),
                                min(region.height, target_height - y),
                            )
                        ),
                        (x, y),
                    )
            region = tiled
        else:
            region = region.resize(
                (target_width, target_height), Image.Resampling.NEAREST
            )

        result.paste(region, target_box[:2])

    return result


def slice_dict(bottom, height, width, left, right, top):
    return {
        "top_left": (0, 0, left, top),
        "top": (left, 0, width - right, top),
        "top_right": (width - right, 0, width, top),
        "left": (0, top, left, height - bottom),
        "center": (left, top, width - right, height - bottom),
        "right": (width - right, top, width, height - bottom),
        "bottom_left": (0, height - bottom, left, height),
        "bottom": (left, height - bottom, width - right, height),
        "bottom_right": (width - right, height - bottom, width, height),
    }


def make_transparent(image: Image.Image, factor: float) -> Image.Image:
    """
    Returns a copy of the given image with adjusted transparency.
    """
    im = image.convert("RGBA")
    r, g, b, a = im.split()
    a = a.point(lambda i: int(i * factor))
    return Image.merge("RGBA", (r, g, b, a))
