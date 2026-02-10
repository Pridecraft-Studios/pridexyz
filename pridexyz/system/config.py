import json
import os
from dataclasses import dataclass, asdict
from pathlib import Path

import typer
from dotenv import load_dotenv

from pridexyz.logger import get_logger

logger = get_logger("pridexyz.system")


@dataclass
class Config:
    base_dir: Path
    src_dir: Path
    build_dir: Path

    colors_path: Path
    meta_path: Path
    orgs_path: Path

    build_user: str
    modrinth_token: str | None
    modrinth_api_url: str | None
    mr_api_debug_logging: bool
    mr_api_extended_debug_logging: bool

    @classmethod
    def load(
        cls,
        *,
        env_file: Path | None = None,
        base_dir: Path | None = None,
        mr_api_debug_logging: bool | None = None,
        mr_api_extended_debug_logging: bool,
    ) -> Config:

        if env_file:
            logger.info(f"Loading env file: {env_file}")
            load_dotenv(env_file, override=True)
        else:
            load_dotenv()

        base_dir = base_dir or Path(__file__).parent.parent.parent
        src_dir = base_dir / "src"
        build_dir = base_dir / "build"

        return cls(
            base_dir=base_dir,
            src_dir=src_dir,
            build_dir=build_dir,
            colors_path=src_dir / "colors.json",
            meta_path=src_dir / "meta.json",
            orgs_path=src_dir / "orgs.json",
            build_user=os.getenv("BUILD_USER", "Unknown"),
            modrinth_token=os.getenv("MODRINTH_TOKEN"),
            modrinth_api_url=os.getenv("MODRINTH_API_URL"),
            mr_api_debug_logging=(
                mr_api_debug_logging
                if mr_api_debug_logging is not None
                else os.getenv("MODRINTH_API_ENABLE_DEBUG_LOGGING", "false").lower()
                == "true"
            ),
            mr_api_extended_debug_logging=mr_api_extended_debug_logging,
        )

    def get_org_lookup(self) -> dict[str, str]:
        orgs_env_lookup = self.load_json(self.orgs_path)
        org_id_lookup = {}

        for org_key, org_env_key in orgs_env_lookup.items():
            org_id = os.getenv(org_env_key)
            if org_id:
                org_id_lookup[org_key] = org_id
            else:
                logger.warning(
                    f"Missing environment variable {org_env_key} for org {org_key}"
                )

        return org_id_lookup

    @staticmethod
    def load_json(path: Path):
        if not path.exists():
            logger.error(f"Configuration file not found: {path}")
            raise FileNotFoundError(path)
        return json.loads(path.read_text())

    def as_debug_dict(self) -> dict:
        data = asdict(self)

        for key, value in data.items():
            if isinstance(value, Path):
                data[key] = str(value.resolve())

        return data


def get_config(ctx: typer.Context) -> Config:
    return ctx.obj["config"]
