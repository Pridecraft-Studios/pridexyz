import shutil
import typer
from datetime import datetime
from pridexyz.system.config import settings, logger

app = typer.Typer()

@app.command(name="run")
def clean_build():
    start_time = datetime.now()
    logger.info("Starting clean task")

    if settings.BUILD_DIR.is_dir():
        try:
            shutil.rmtree(settings.BUILD_DIR)
            logger.info(f"Removed existing build directory at {settings.BUILD_DIR}")
        except Exception as e:
            logger.error(f"Failed to remove build directory: {e}", exc_info=True)
            raise typer.Exit(code=1)
    else:
        logger.info(f"No existing build directory found at {settings.BUILD_DIR}.")

    elapsed = int((datetime.now() - start_time).total_seconds() * 1000)
    logger.info(f"Done: clean task completed in {elapsed}ms.")