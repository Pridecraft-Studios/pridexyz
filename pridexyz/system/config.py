import json
import os
from pathlib import Path
from dotenv import load_dotenv
from pridexyz.logger import get_logger

# Load environment variables once
load_dotenv()

logger = get_logger("pridexyz.system")


class Config:
    BASE_DIR = Path(__file__).parent.parent
    SRC_DIR = BASE_DIR / 'src'
    BUILD_DIR = BASE_DIR / 'build'

    # Files
    COLORS_PATH = SRC_DIR / 'colors.json'
    META_PATH = SRC_DIR / 'meta.json'
    ORGS_PATH = SRC_DIR / 'orgs.json'

    # Env Vars
    BUILD_USER = os.getenv('BUILD_USER', 'Unknown')
    MODRINTH_TOKEN = os.getenv("MODRINTH_TOKEN")
    MODRINTH_API_URL = os.getenv("MODRINTH_API_URL")
    DEBUG_LOGGING = os.getenv("MODRINTH_API_ENABLE_DEBUG_LOGGING", "false").lower() == "true"

    @classmethod
    def load_json(cls, path: Path):
        if not path.exists():
            logger.error(f"Configuration file not found: {path}")
            raise FileNotFoundError(f"{path} does not exist")
        with open(path, 'r') as f:
            return json.load(f)

    @classmethod
    def get_org_lookup(cls):
        """Resolves Org names to IDs based on orgs.json and .env"""
        try:
            orgs_env_lookup = cls.load_json(cls.ORGS_PATH)
            org_id_lookup = {}
            for org_key, org_env_key in orgs_env_lookup.items():
                org_id = os.getenv(org_env_key)
                if org_id:
                    org_id_lookup[org_key] = org_id
                else:
                    logger.warning(f"Missing environment variable {org_env_key} for org {org_key}")
            return org_id_lookup
        except Exception as e:
            logger.error(f"Failed to load organization lookup: {e}")
            return {}


settings = Config()