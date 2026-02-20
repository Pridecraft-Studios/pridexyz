import shutil
import typer
from datetime import datetime

from pridexyz.system.config import logger, get_config


def clean_build(ctx: typer.Context):
    settings = get_config(ctx)

    start_time = datetime.now()
    logger.info("Starting clean task")

    if settings.build_dir.is_dir():
        try:
            shutil.rmtree(settings.build_dir)
            logger.info(f"Removed existing build directory at {settings.build_dir}")
        except Exception as e:
            logger.error(f"Failed to remove build directory: {e}", exc_info=True)
            raise typer.Exit(code=1)
    else:
        logger.info(f"No existing build directory found at {settings.build_dir}.")

    elapsed = int((datetime.now() - start_time).total_seconds() * 1000)
    logger.info(f"Done: clean task completed in {elapsed}ms.")
