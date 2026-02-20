from datetime import datetime

import typer

from pridexyz.builder import Builder
from pridexyz.color import convert_hex_to_rgb
from pridexyz.hearts.build import HeartsBuilder
from pridexyz.system.config import get_config, logger
from pridexyz.tooltip.build import TooltipBuilder

AVAILABLE_BUILDERS = {
    "hearts": HeartsBuilder,
    "tooltip": TooltipBuilder,
}


def build_packs(
    ctx: typer.Context,
    use_builders: str = typer.Option(
        "hearts,tooltip", help="Comma-separated list of builders to run"
    ),
):
    settings = get_config(ctx)

    start_time = datetime.now()
    logger.info("Starting build task")

    try:
        colors = settings.load_json(settings.colors_path)
        meta = settings.load_json(settings.meta_path)
    except Exception:
        raise typer.Exit(code=1)

    builders = Builder.create_builders(
        logger,
        settings.src_dir,
        settings.build_dir,
        settings.build_user,
        meta,
        [
            AVAILABLE_BUILDERS[builder_name]
            for builder_name in (
                builder_names.strip() for builder_names in use_builders.split(",")
            )
            if builder_name in AVAILABLE_BUILDERS
        ],
    )

    district_pack_count = 0
    for palette_name, palette in colors.items():
        if palette_name.startswith("$"):
            continue
        clean_name = palette_name.split("/")[0]
        logger.info(f"Processing palette '{clean_name}'")
        palette_colors = [convert_hex_to_rgb(c) for c in palette["colors"]]

        for builder in builders:
            district_pack_count += builder.build(palette, clean_name, palette_colors)

    elapsed = int((datetime.now() - start_time).total_seconds() * 1000)
    logger.info(f"Total packs built: {district_pack_count}")
    logger.info(f"Done: build task completed in {elapsed}ms.")
