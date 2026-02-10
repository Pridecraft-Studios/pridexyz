from pathlib import Path

import typer
from rich import json

from pridexyz.system.config import Config, get_config
from pridexyz.system.tasks import build, clean, modrinth

app = typer.Typer(help="PrideXYZ Build & Distribution", no_args_is_help=True)

app.add_typer(build.app, name="build", help="Build resource packs")
app.add_typer(clean.app, name="clean", help="Clean build artifacts")
app.add_typer(modrinth.app, name="modrinth", help="Manage Modrinth projects")


@app.callback()
def main(
    ctx: typer.Context,
    env_file: Path = typer.Option(None, "--env-file", "-e"),
    base_dir: Path = typer.Option(None),
    mr_debug_logging: bool = typer.Option(None),
):
    ctx.ensure_object(dict)
    ctx.obj["config"] = Config.load(
        env_file=env_file,
        base_dir=base_dir,
        mr_debug_logging=mr_debug_logging,
    )


@app.command()
def debug(ctx: typer.Context):
    typer.echo(json.dumps(get_config(ctx).as_debug_dict(), indent=2))
