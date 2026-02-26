import json
from datetime import datetime
from pathlib import Path

import numpy as np
from PIL import Image
from PIL.Image import Resampling

from pridexyz.builder import Builder
from pridexyz.color import RGBColor, convert_hex_to_rgb
from pridexyz.common.image_processing import (
    generate_image_from_template,
    apply_mask_lightness_mapping,
    with_binary_mask,
)
from pridexyz.markdown import appy_modrinth_markdown_template
from pridexyz.pack import (
    generate_random_word,
    create_pack_metadata,
    compress_and_remove_directory,
)


class HeartsBuilder(Builder):
    def __init__(
        self,
        logger,
        src: Path,
        build: Path,
        build_user: str,
        meta: dict,
        logger_base_indent: int = 1,
    ):
        super().__init__(logger, src, build, build_user, meta, logger_base_indent)
        self.styles = self.load_styles()

    @classmethod
    def get_name(cls):
        return "hearts"

    def load_styles(self):
        styles_path = self.src_dir / "styles.json"
        self.logger.info(f"Loading styles from {styles_path}")
        with open(styles_path, "r") as styles_file:
            return json.load(styles_file)

    def build(self, palette: dict, palette_name: str, palette_colors: list[RGBColor]):
        self.info(f"Building Hearts Packs for '{palette_name}'", 0)

        district_pack_count = 0
        if "hearts" not in palette:
            self.info("No styles for hearts in palette, skipping", 1)
            return district_pack_count
        for style_name in palette["hearts"]["styles"]:
            style_config = self.styles[style_name]
            self.info(f"Generating for style '{style_name}'", 1)

            # Generate identifiers
            style_name = style_name
            style_description_name = style_config["description_name"]
            style_explanation = style_config["explanation"]
            pack_slug = f"hearts_{palette_name}+{style_name}"
            pack_version = f"v{palette['version']}+v{style_config['version']}+v{self.meta['hearts']['global_version']}"
            pack_name = f"hearts_{palette_name}.v{palette['version']}+{style_name}.v{style_config['version']}+v{self.meta['hearts']['global_version']}"
            pack_friendly_name = (
                f"{palette['description_name']} Hearts ({style_description_name})"
            )
            color_palette_collection = palette.get("collection_id", "!remove_line!")
            build_pack_dir_name = f"{pack_name}.{generate_random_word(8)}"
            pack_friendly_name_description = pack_friendly_name.replace(" Hearts", "")
            if "Flag" in pack_friendly_name_description:
                pack_friendly_name_description = f"a {pack_friendly_name_description}"
            else:
                pack_friendly_name_description = f"be {pack_friendly_name_description}"

            build_out_path = self.build_dir / pack_slug
            build_zip_collect_path = build_out_path / build_pack_dir_name
            self.debug(f"Build output path: {build_zip_collect_path}")

            try:
                # Generate images
                target_colors = [
                    convert_hex_to_rgb(c)
                    for c in style_config["sprite"]["templating_colors"]
                ]

                base_template = Image.open(
                    self.src_dir / style_config["sprite"]["template"]
                ).convert("RGBA")

                base_sprite = generate_image_from_template(
                    base_template, target_colors, palette_colors
                )

                lightness_mask_default = Image.open(
                    self.src_dir / "resources" / "lightness_mask_default.png"
                ).convert("RGBA")

                lightness_mask_hardcore = Image.open(
                    self.src_dir / "resources" / "lightness_mask_hardcore.png"
                ).convert("RGBA")

                bright_spot_overlay = Image.open(
                    self.src_dir / "resources" / "bright_spot_overlay.png"
                ).convert("RGBA")

                blinking_overlay = Image.open(
                    self.src_dir / "resources" / "blinking_overlay.png"
                ).convert("RGBA")

                half_heart_binary_mask = Image.open(
                    self.src_dir / "resources" / "half_heart_binary_mask.png"
                ).convert("RGBA")

                def lm_shadow_darken_or_adjust(lightness):
                    lightness_new = np.clip(
                        lightness * 0.91 - ((0.01 / lightness) / 2.6), a_min=0, a_max=1
                    )
                    delta_lightness_new = lightness - lightness_new
                    # self.debug(f"lm shadow lightness delta_lightness_new: {delta_lightness_new}")
                    if delta_lightness_new < 0.05 and lightness < 0.07:
                        self.debug(
                            f"Adjusting lm shadow lightness to {lightness_new + 0.38}"
                        )
                        return lightness_new + 0.48
                    return lightness_new

                def lm_hardcore_darken_or_adjust(lightness):
                    lightness_new = np.clip(
                        lightness * 0.71 - ((0.01 / lightness) / 1.8), a_min=0, a_max=1
                    )
                    delta_lightness_new = lightness - lightness_new
                    # self.debug(f"lm hardcore lightness delta_lightness_new: {delta_lightness_new}")
                    if delta_lightness_new < 0.09 and lightness < 0.1:
                        self.debug(
                            f"Adjusting lm hardcore lightness to {lightness_new + 0.45}"
                        )
                        return lightness_new + 0.55
                    return lightness_new

                def lm_bright_spot_pre_brighten(lightness):
                    return 0.72 + (lightness * 0.5)

                mapping = {
                    (255, 0, 0): lm_bright_spot_pre_brighten,
                    (0, 255, 0): lm_shadow_darken_or_adjust,
                    (0, 0, 255): lm_hardcore_darken_or_adjust,
                }

                full_default_sprite = Image.alpha_composite(
                    apply_mask_lightness_mapping(
                        base_sprite, lightness_mask_default, mapping
                    ),
                    bright_spot_overlay,
                )

                full_hardcore_sprite = apply_mask_lightness_mapping(
                    base_sprite, lightness_mask_hardcore, mapping
                )

                full_default_blinking_sprite = Image.alpha_composite(
                    full_default_sprite, blinking_overlay
                )

                full_hardcore_blinking_sprite = Image.alpha_composite(
                    full_hardcore_sprite, blinking_overlay
                )

                half_default_sprite = with_binary_mask(
                    full_default_sprite, half_heart_binary_mask
                )

                half_hardcore_sprite = with_binary_mask(
                    full_hardcore_sprite, half_heart_binary_mask
                )

                half_default_blinking_sprite = with_binary_mask(
                    full_default_blinking_sprite, half_heart_binary_mask
                )

                half_hardcore_blinking_sprite = with_binary_mask(
                    full_default_blinking_sprite, half_heart_binary_mask
                )

                # Save hearts images
                sprites_hud_heart_path = (
                    build_zip_collect_path
                    / "assets"
                    / "minecraft"
                    / "textures"
                    / "gui"
                    / "sprites"
                    / "hud"
                    / "heart"
                )
                sprites_hud_heart_path.mkdir(parents=True, exist_ok=True)

                full_default_sprite.save(sprites_hud_heart_path / "full.png")
                full_hardcore_sprite.save(sprites_hud_heart_path / "hardcore_full.png")
                full_default_blinking_sprite.save(
                    sprites_hud_heart_path / "full_blinking.png"
                )
                full_hardcore_blinking_sprite.save(
                    sprites_hud_heart_path / "hardcore_full_blinking.png"
                )
                half_default_sprite.save(sprites_hud_heart_path / "half.png")
                half_hardcore_sprite.save(sprites_hud_heart_path / "hardcore_half.png")
                half_default_blinking_sprite.save(
                    sprites_hud_heart_path / "half_blinking.png"
                )
                half_hardcore_blinking_sprite.save(
                    sprites_hud_heart_path / "hardcore_half_blinking.png"
                )

                # Metadata + resources
                create_pack_metadata(
                    build_zip_collect_path / "pack.mcmeta", pack_friendly_name, 18
                )

                self.debug("Generating pack.png & gallery image")

                # Load overlay images
                pack_gallery = Image.open(
                    self.src_dir / "resources" / "pack_gallery_background.png"
                )
                pack_png_bg = Image.open(
                    self.src_dir / "resources" / "pack_png_bg.png"
                ).convert("RGBA")

                # unscaled icon
                pack_png = Image.alpha_composite(pack_png_bg, full_default_sprite)

                # add 1px padding on all sides
                pack_png_padded = Image.new("RGBA", (11, 11), (0, 0, 0, 0))
                pack_png_padded.paste(pack_png, (1, 1))
                pack_png = pack_png_padded

                # Compose unscaled gallery
                for i in range(0, 8):
                    pack_gallery.alpha_composite(
                        full_default_sprite, (35 + (8 * i), 10)
                    )

                pack_gallery.alpha_composite(half_default_sprite, (35 + (8 * 8), 10))

                for i in range(0, 9):
                    pack_gallery.alpha_composite(
                        full_hardcore_sprite, (35 + (8 * i), 21)
                    )

                pack_gallery.alpha_composite(half_hardcore_sprite, (35 + (8 * 9), 21))

                for i in range(0, 3):
                    pack_gallery.alpha_composite(
                        full_default_sprite, (35 + (8 * i), 32)
                    )

                pack_gallery.alpha_composite(
                    full_default_blinking_sprite, (35 + (8 * 3), 32)
                )
                pack_gallery.alpha_composite(
                    half_default_sprite, (35 + (8 * 3), 32)
                )

                for i in range(0, 5):
                    pack_gallery.alpha_composite(
                        full_default_blinking_sprite, (67 + (8 * i), 32)
                    )

                # Scale up unscaled pack png
                pack_png = pack_png.resize(
                    (pack_png.width * 28, pack_png.height * 28), Resampling.NEAREST
                )

                # Scale up unscaled gallery
                pack_gallery = pack_gallery.resize(
                    (pack_gallery.width * 6, pack_gallery.height * 6),
                    Resampling.NEAREST,
                )

                # Save outputs
                pack_png.save(build_zip_collect_path / "pack.png")
                pack_png.save(build_out_path / f"{pack_name}.png")
                pack_gallery.save(build_out_path / f"gallery_{pack_name}.png")

                # Compress
                self.debug(f"Compressing and finalizing {pack_name}")
                compress_and_remove_directory(build_zip_collect_path)

                # Markdown template
                context = {
                    "pack_slug": pack_slug,
                    "pack_friendly_name": pack_friendly_name,
                    "pack_name": pack_name,
                    "pack_friendly_name_description": pack_friendly_name_description,
                    "pack_version": pack_version,
                    "color_palette_name": palette["description_name"],
                    "color_palette_collection": color_palette_collection,
                    "color_palette_formated": "* " + "\n* ".join(palette["colors"]),
                    "style_explanation": f"{style_description_name} = {style_explanation}.",
                    "build_time": datetime.now()
                    .astimezone()
                    .isoformat(timespec="seconds"),
                    "build_user": self.build_user,
                }

                Path(build_out_path / "modrinth.md").write_text(
                    appy_modrinth_markdown_template(
                        Path(self.src_dir / "modrinth.md").read_text(encoding="utf-8"),
                        context,
                    ),
                    encoding="utf-8",
                )

                self.info(f"Finished building {pack_name}")
                district_pack_count += 1

            except Exception as e:
                self.error(f"Error while processing {pack_name}: {e}", exc_info=True)

        return district_pack_count
