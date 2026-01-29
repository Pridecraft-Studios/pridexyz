from datetime import datetime

import typer

from pridexyz.builder import Builder
from pridexyz.color import convert_hex_to_rgb
from pridexyz.tooltip.build import TooltipBuilder
from pridexyz.system.config import settings, logger

app = typer.Typer()

@app.command(name="run")
def build_packs():
    start_time = datetime.now()
    logger.info("Starting build task")

    try:
        colors = settings.load_json(settings.COLORS_PATH)
        meta = settings.load_json(settings.META_PATH)
    except Exception:
        raise typer.Exit(code=1)

    builders = Builder.create_builders(
        logger,
        settings.SRC_DIR,
        settings.BUILD_DIR,
        settings.BUILD_USER,
        meta,
        [TooltipBuilder]
    )

    district_pack_count = 0
    for palette_name, palette in colors.items():
        clean_name = palette_name.split("/")[0]
        logger.info(f"Processing palette '{clean_name}'")
        palette_colors = [convert_hex_to_rgb(c) for c in palette['colors']]

        for builder in builders:
            district_pack_count += builder.build(palette, clean_name, palette_colors)

    elapsed = int((datetime.now() - start_time).total_seconds() * 1000)
    logger.info(f"Total packs built: {district_pack_count}")
    logger.info(f"Done: build task completed in {elapsed}ms.")