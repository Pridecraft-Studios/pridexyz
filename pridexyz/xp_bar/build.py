import json
from datetime import datetime
from pathlib import Path

from PIL import Image
from PIL.Image import Resampling

from pridexyz.builder import Builder
from pridexyz.color import RGBColor
from pridexyz.markdown import appy_modrinth_markdown_template
from pridexyz.pack import (
    generate_random_word,
    create_pack_metadata,
    compress_and_remove_directory,
)
from pridexyz.xp_bar.image_processing import recolor_banded, recolor_gradient


class XPBarBuilder(Builder):
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
        return "xp_bar"

    def load_styles(self):
        styles_path = self.src_dir / "styles.json"
        self.logger.info(f"Loading styles from {styles_path}")
        with open(styles_path, "r") as styles_file:
            return json.load(styles_file)

    def _build_bar_images(
        self,
        mode: str,
        palette_colors: list[RGBColor],
    ) -> tuple[Image.Image, Image.Image]:
        template_progress = Image.open(
            self.src_dir / "templates" / "progress.png"
        ).convert("RGBA")
        template_background = Image.open(
            self.src_dir / "templates" / "background.png"
        ).convert("RGBA")

        if not palette_colors:
            raise ValueError("At least one palette color is required")

        if mode == "banded":
            progress = recolor_banded(template_progress, palette_colors)
        elif mode == "gradient":
            progress = recolor_gradient(template_progress, palette_colors)
        else:
            raise ValueError(f"Unknown XP bar mode: {mode!r}")

        return progress, template_background

    @staticmethod
    def _make_icon_layer(progress: Image.Image) -> Image.Image:
        bar_w, bar_h = progress.size
        center = bar_w // 2
        left = max(0, center - 5)
        right = min(bar_w, left + 11)
        slice_img = progress.crop((left, 0, right, bar_h))

        canvas = Image.new("RGBA", (11, 11), (0, 0, 0, 0))
        y_offset = (11 - slice_img.height) // 2
        x_offset = (11 - slice_img.width) // 2
        canvas.alpha_composite(slice_img, (x_offset, y_offset))
        return canvas

    def _make_gallery(
        self,
        progress: Image.Image,
        background: Image.Image,
    ) -> Image.Image:
        gallery_bg = Image.open(
            self.src_dir / "resources" / "pack_gallery_background.png"
        ).convert("RGBA")

        partials = [1.0, 0.5, 0.25]

        bar_scale = 2.35
        pad_x = 12
        spacing = 10

        scaled_bar_w = int(progress.width * bar_scale) # 546
        scaled_bar_h = int(progress.height * bar_scale) # 15
        bars_total_h = (
            len(partials) * scaled_bar_h + (len(partials) - 1) * spacing
        )  # 53

        target_w = scaled_bar_w + 2 * pad_x  # 566
        target_h = round(target_w * gallery_bg.height / gallery_bg.width)

        if (target_w, target_h) != (gallery_bg.width, gallery_bg.height):
            gallery_bg = gallery_bg.resize(
                (gallery_bg.width*3, gallery_bg.height *3),
                Resampling.NEAREST,
            )

        # Centre the bar stack vertically inside the gallery.
        y_cursor = max(0, (gallery_bg.height - bars_total_h) // 2) - 4
        for frac in partials:
            scaled_bg = background.resize(
                (scaled_bar_w, scaled_bar_h),
                Resampling.NEAREST,
            )
            gallery_bg.alpha_composite(scaled_bg, (pad_x, y_cursor))

            crop_w = max(1, int(progress.width * frac))
            filled_progress = progress.crop((0, 0, crop_w, progress.height))
            scaled_progress = filled_progress.resize(
                (int(crop_w * bar_scale), scaled_bar_h),
                Resampling.NEAREST,
            )
            gallery_bg.alpha_composite(scaled_progress, (pad_x, y_cursor))

            y_cursor += scaled_bar_h + spacing

        return gallery_bg

    def build(self, palette: dict, palette_name: str, palette_colors: list[RGBColor]):
        self.info(f"Building XP Bar Packs for '{palette_name}'", 0)

        district_pack_count = 0
        if "xp_bars" not in palette:
            self.info("No styles for xp_bars in palette, skipping", 1)
            return district_pack_count
        for style_name in palette["xp_bars"]["styles"]:
            style_config = self.styles[style_name]
            self.info(f"Generating for style '{style_name}'", 1)

            no_lable = style_config.get("no_lable")
            anti_override_tag = palette["xp_bars"].get("anti_override_tag") or ""
            if anti_override_tag != "": 
                self.info(f"anti_override_tag {anti_override_tag}")
                style_name = f"{style_name}-{anti_override_tag}"
                
            mode = style_config.get("mode")
            if mode not in ("banded", "gradient"):
                self.error(
                    f"Unsupported mode '{mode}' for style '{style_name}', skipping"
                )
                continue

            # Generate identifiers
            style_description_name = style_config["description_name"]
            style_explanation = style_config["explanation"]
            pack_slug_sufix = ""
            if not no_lable:
                pack_slug_sufix = f".{style_name}"
            pack_slug = f"xp_bar_{palette_name}{pack_slug_sufix}"
            pack_version = f"v{palette['version']}+v{style_config['version']}+v{self.meta['xp_bar']['global_version']}"
            pack_name = f"xp_bar_{palette_name}.v{palette['version']}+{style_name}.v{style_config['version']}+v{self.meta['xp_bar']['global_version']}"
            pack_friendly_name_sufix = ""
            if not no_lable:
                pack_friendly_name_sufix = f" ({style_description_name})"
            pack_friendly_name = (
                f"{palette['description_name']} XP Bar{pack_friendly_name_sufix}"
            )
            color_palette_collection = palette.get("collection_id", "!remove_line!")
            build_pack_dir_name = f"{pack_name}.{generate_random_word(8)}"
            pack_friendly_name_description = pack_friendly_name.replace(
                " XP Bar", ""
            )
            if "Flag" in pack_friendly_name_description:
                pack_friendly_name_description = (
                    f"a {pack_friendly_name_description}"
                )
            else:
                pack_friendly_name_description = (
                    f"be {pack_friendly_name_description}"
                )

            build_out_path = self.build_dir / pack_slug
            build_zip_collect_path = build_out_path / build_pack_dir_name
            self.debug(f"Build output path: {build_zip_collect_path}")

            try:
                progress_image, background_image = self._build_bar_images(
                    mode, palette_colors
                )

                # Save bar textures
                hud_sprites_path = (
                    build_zip_collect_path
                    / "assets"
                    / "minecraft"
                    / "textures"
                    / "gui"
                    / "sprites"
                    / "hud"
                )
                hud_sprites_path.mkdir(parents=True, exist_ok=True)

                background_image.save(
                    hud_sprites_path / "experience_bar_background.png"
                )
                progress_image.save(
                    hud_sprites_path / "experience_bar_progress.png"
                )

                # Metadata
                create_pack_metadata(
                    build_zip_collect_path / "pack.mcmeta", pack_friendly_name
                )

                self.debug("Generating pack.png & gallery image")

                # Build the unscaled pack icon
                pack_png_bg = Image.open(
                    self.src_dir / "resources" / "pack_png_bg.png"
                ).convert("RGBA")
                icon_layer = self._make_icon_layer(progress_image)
                unscaled_icon = Image.alpha_composite(pack_png_bg, icon_layer)

                # Build the unscaled gallery
                unscaled_gallery = self._make_gallery(progress_image, background_image)

                # Scale up unscaled pack png
                scaled_icon = unscaled_icon.resize(
                    (
                        unscaled_icon.width * 28,
                        unscaled_icon.height * 28,
                    ),
                    Resampling.NEAREST,
                )

                # Scale up unscaled gallery
                scaled_gallery = unscaled_gallery.resize(
                    (
                        unscaled_gallery.width * 6,
                        unscaled_gallery.height * 6,
                    ),
                    Resampling.NEAREST,
                )

                # Final pack.png (256x256)
                pack_png = Image.new("RGBA", (256, 256), (0, 0, 0, 0))
                pack_png.paste(scaled_icon, (0, 0), mask=scaled_icon)

                # Save outputs
                pack_png.save(build_zip_collect_path / "pack.png")
                pack_png.save(build_out_path / f"{pack_name}.png")
                scaled_gallery.save(
                    build_out_path / f"gallery_{pack_name}.webp",
                    format="webp",
                    optimize=True,
                    quality=100,
                    method=5,
                )

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
                        Path(self.src_dir / "modrinth.md").read_text(
                            encoding="utf-8"
                        ),
                        context,
                    ),
                    encoding="utf-8",
                )

                self.info(f"Finished building {pack_name}")
                district_pack_count += 1

            except Exception as e:
                self.error(f"Error while processing {pack_name}: {e}", exc_info=True)

        return district_pack_count