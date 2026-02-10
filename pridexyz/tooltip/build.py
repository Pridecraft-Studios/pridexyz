import json
import shutil
from datetime import datetime
from pathlib import Path

from PIL import Image
from PIL.Image import Transpose, Resampling

from pridexyz.color import RGBColor
from pridexyz.markdown import appy_modrinth_markdown_template
from pridexyz.pack import (
    generate_random_word,
    create_pack_metadata,
    compress_and_remove_directory,
)
from pridexyz.builder import Builder
from pridexyz.tooltip.image_processing import (
    apply_template,
    nine_slice_scale,
    make_transparent,
)


class TooltipBuilder(Builder):
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
        return "tooltip"

    def load_styles(self):
        styles_path = self.src_dir / "styles.json"
        self.logger.info(f"Loading styles from {styles_path}")
        with open(styles_path, "r") as styles_file:
            return json.load(styles_file)

    def build(self, palette: dict, palette_name: str, palette_colors: list[RGBColor]):
        self.info(f"Building Tooltip Packs for '{palette_name}'", 0)

        district_pack_count = 0
        for style_name in palette["tooltip"]["styles"]:
            auto_sub_styles = {"regular": {}}
            style_config = self.styles[style_name]
            self.info(f"Generating for style '{style_name}'", 1)
            if style_config.get("generate_turned_variant", True):
                auto_sub_styles["turned"] = {
                    "transpose": Transpose.ROTATE_270,
                    "suffix": "-turned",
                    "description_name_suffix": " Turned",
                    "explanation_suffix": ", turned by 90 degrees",
                }
            for auto_sub_style in auto_sub_styles:
                auto_sub_style_config = auto_sub_styles[auto_sub_style]

                # Generate identifiers
                style_name = style_name + auto_sub_style_config.get("suffix", "")
                style_description_name = style_config[
                    "description_name"
                ] + auto_sub_style_config.get("description_name_suffix", "")
                style_explanation = style_config[
                    "explanation"
                ] + auto_sub_style_config.get("explanation_suffix", "")
                pack_slug = f"tooltip_{palette_name}+{style_name}"
                pack_version = f"v{palette['version']}+v{style_config['version']}+v{self.meta['tooltip']['global_version']}"
                pack_name = f"tooltip_{palette_name}.v{palette['version']}+{style_name}.v{style_config['version']}+v{self.meta['tooltip']['global_version']}"
                pack_friendly_name = (
                    f"{palette['description_name']} Tooltip ({style_description_name})"
                )
                color_palette_collection = palette.get("collection_id", "!remove_line!")
                build_pack_dir_name = f"{pack_name}.{generate_random_word(8)}"
                pack_friendly_name_description = pack_friendly_name.replace(
                    " Tooltip", ""
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
                    # Generate images
                    background_image = apply_template(
                        style_config["background"],
                        palette_colors,
                        self.src_dir,
                        auto_sub_style_config.get("transpose", None),
                    )
                    frame_image = apply_template(
                        style_config["frame"],
                        palette_colors,
                        self.src_dir,
                        auto_sub_style_config.get("transpose", None),
                    )
                    background_frame_image = Image.alpha_composite(
                        background_image, frame_image
                    )

                    # Save tooltip images
                    tooltip_path = (
                        build_zip_collect_path
                        / "assets"
                        / "minecraft"
                        / "textures"
                        / "gui"
                        / "sprites"
                        / "tooltip"
                    )
                    tooltip_path.mkdir(parents=True, exist_ok=True)

                    if style_config.get("merge_background_into_frame", False):
                        self.debug("Merging background into frame")
                        background_frame_image.save(tooltip_path / "frame.png")
                        shutil.copytree(
                            self.src_dir / "resources" / "tooltip_use_only_frame",
                            tooltip_path,
                            dirs_exist_ok=True,
                        )
                    else:
                        self.debug("Saving background and frame separately")
                        background_image.save(tooltip_path / "background.png")
                        frame_image.save(tooltip_path / "frame.png")

                    # Metadata + resources
                    create_pack_metadata(
                        build_zip_collect_path / "pack.mcmeta", pack_friendly_name
                    )
                    shutil.copytree(
                        self.src_dir / "resources" / "tooltip_common",
                        tooltip_path,
                        dirs_exist_ok=True,
                    )

                    self.debug("Generating pack.png & gallery image")

                    # Build base icon with transparency
                    base_icon_image = nine_slice_scale(
                        background_frame_image, 2, 2, 2, 2, 51, 36, False, (8, 8, 8, 8)
                    )
                    base_icon_image = make_transparent(base_icon_image, 0.92)

                    # Load overlay images
                    tooltip_text = Image.open(
                        self.src_dir / "resources" / "pack_png_tooltip_text.png"
                    )
                    tooltip_bg = Image.open(
                        self.src_dir / "resources" / "pack_png_tooltip_background.png"
                    )
                    pack_gallery = Image.open(
                        self.src_dir / "resources" / "pack_gallery_background.png"
                    )

                    # Compose unscaled icon
                    pack_png = Image.alpha_composite(tooltip_bg, base_icon_image)
                    pack_png = Image.alpha_composite(pack_png, tooltip_text)

                    # Compose unscaled gallery
                    icon_with_text = Image.alpha_composite(
                        base_icon_image, tooltip_text
                    )
                    pack_gallery.alpha_composite(icon_with_text, (50, 10))

                    # Scale up unscaled pack png
                    scaled_pack_png = pack_png.resize(
                        (pack_png.width * 6, pack_png.height * 6), Resampling.NEAREST
                    )

                    # Scale up unscaled gallery
                    pack_gallery = pack_gallery.resize(
                        (pack_gallery.width * 6, pack_gallery.height * 6),
                        Resampling.NEAREST,
                    )

                    # Final pack.png (256x256)
                    pack_png = Image.new("RGBA", (256, 256), (0, 0, 0, 0))
                    pack_png.paste(scaled_pack_png, (0, 18), mask=scaled_pack_png)

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
                            Path(self.src_dir / "resources" / "modrinth.md").read_text(
                                encoding="utf-8"
                            ),
                            context,
                        ),
                        encoding="utf-8",
                    )

                    self.info(f"Finished building {pack_name}")
                    district_pack_count += 1

                except Exception as e:
                    self.error(
                        f"Error while processing {pack_name}: {e}", exc_info=True
                    )

        return district_pack_count
