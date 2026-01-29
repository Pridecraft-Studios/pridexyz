import typer
from pridexyz.system.tasks import build, clean, modrinth

app = typer.Typer(
    help="PrideXYZ Build & Distribution",
    no_args_is_help=True
)

# Register sub-commands
app.add_typer(build.app, name="build", help="Build resource packs")
app.add_typer(clean.app, name="clean", help="Clean build artifacts")
app.add_typer(modrinth.app, name="modrinth", help="Manage Modrinth projects")

if __name__ == "__main__":
    app()