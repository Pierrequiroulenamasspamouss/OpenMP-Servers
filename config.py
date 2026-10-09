import os
import json
from pathlib import Path

# Simple .env loader if python-dotenv is not installed
def load_env(env_path=".env"):
    if os.path.exists(env_path):
        with open(env_path, "r", encoding="utf-8") as f:
            for line in f:
                line = line.strip()
                if line and not line.startswith("#") and "=" in line:
                    key, value = line.split("=", 1)
                    os.environ.setdefault(key.strip(), value.strip())

# Load from .env if present
env_file = os.path.join(os.path.dirname(__file__), ".env")
load_env(env_file)

class Config:
    PORT_MAIN = int(os.getenv("PORT_MAIN", 44733))
    PORT_SECONDARY = int(os.getenv("PORT_SECONDARY", 44732))
    HOST = os.getenv("HOST", "0.0.0.0")
    DEBUG = os.getenv("DEBUG", "False").lower() == "true"
    
    # Paths (relative to SERVER directory)
    BASE_DIR = Path(__file__).parent
    DB_PATH = os.getenv("DB_PATH", str(BASE_DIR / "player_data" / "players.db"))
    CONFIGS_DIR = BASE_DIR / "data" / "configs"
    DEFINITIONS_DIR = BASE_DIR / "data" / "definitions"
    DEFINITIONS_PATH = os.getenv("DEFINITIONS_PATH", str(BASE_DIR / "data" / "definitions.json"))
    PLAYER_DATA_DIR = os.getenv("PLAYER_DATA_DIR", str(BASE_DIR / "player_data"))
    NOPROMOUSERS_PATH = os.getenv("NOPROMOUSERS_PATH", str(BASE_DIR / "data" / "nopromousers.txt"))
    MARKET_PRICES_PATH = os.getenv("MARKET_PRICES_PATH", str(BASE_DIR / "data" / "market_prices.json"))
    SCHEDULE_PATH = os.getenv("SCHEDULE_PATH", str(BASE_DIR / "data" / "ShopSchedule.json"))
    EMPTY_PLAYER_PATH = os.getenv("EMPTY_PLAYER_PATH", str(BASE_DIR / "data" / "empty_player.json"))
    
    # Mode
    IS_PUBLIC = os.getenv("IS_PUBLIC", "false").lower() in ("true", "1", "yes")

    # URL endpoints
    LOCAL_BASE_URL = os.getenv("LOCAL_BASE_URL", f"http://localhost:{PORT_MAIN}")
    LOCAL_SECONDARY_URL = os.getenv("LOCAL_SECONDARY_URL", f"http://localhost:{PORT_SECONDARY}")
    PUBLIC_BASE_URL = os.getenv("PUBLIC_BASE_URL", f"http://bluebridge.homeonthewater.com:{PORT_MAIN}")
    PUBLIC_SECONDARY_URL = os.getenv("PUBLIC_SECONDARY_URL", f"http://bluebridge.homeonthewater.com:{PORT_SECONDARY}")

    # Dynamic URLs initialized to current mode
    BASE_URL = PUBLIC_BASE_URL if IS_PUBLIC else LOCAL_BASE_URL
    SECONDARY_URL = PUBLIC_SECONDARY_URL if IS_PUBLIC else LOCAL_SECONDARY_URL

    # Admin settings
    ADMIN_PASSWORD = os.getenv("ADMIN_PASSWORD", "admin")

    # Database backup settings
    BACKUP_DIR = os.getenv("BACKUP_DIR", str(BASE_DIR / "player_data" / "backups"))
    BACKUP_INTERVAL_SECONDS = int(os.getenv("BACKUP_INTERVAL_SECONDS", 86400))  # 24 hours
    MAX_ROLLING_BACKUPS = int(os.getenv("MAX_ROLLING_BACKUPS", 4))

    @classmethod
    def set_public(cls, is_public: bool):
        cls.IS_PUBLIC = is_public
        os.environ["IS_PUBLIC"] = "true" if is_public else "false"
        cls.BASE_URL = cls.PUBLIC_BASE_URL if is_public else cls.LOCAL_BASE_URL
        cls.SECONDARY_URL = cls.PUBLIC_SECONDARY_URL if is_public else cls.LOCAL_SECONDARY_URL

    @classmethod
    def get_base_url(cls):
        return cls.PUBLIC_BASE_URL if cls.IS_PUBLIC else cls.LOCAL_BASE_URL

    @classmethod
    def get_secondary_url(cls):
        return cls.PUBLIC_SECONDARY_URL if cls.IS_PUBLIC else cls.LOCAL_SECONDARY_URL

    @classmethod
    def get_http_timeout(cls):
        return 30000 if cls.IS_PUBLIC else 10000

    @staticmethod
    def normalize_version(version: str) -> str:
        """
        Converts semver 'X.Y.Z' to integer version code 'X*10000 + Y*100 + Z'
        (e.g., 0.0.1 -> 1, 0.0.6 -> 6, 0.0.7 -> 7, 1.15.2 -> 11502).
        """
        if not version:
            return ""
        v = str(version).strip()
        if "." in v:
            parts = v.split(".")
            try:
                if len(parts) == 3:
                    return str(int(parts[0]) * 10000 + int(parts[1]) * 100 + int(parts[2]))
            except ValueError:
                pass
        return v

    @classmethod
    def get_dynamic_server_config(cls, version: str = None):
        base_url = cls.get_base_url()
        timeout = cls.get_http_timeout()

        template_path = None
        # 1. Check version-specific config: SERVER/data/configs/<version_code>.json
        if version:
            v_code = cls.normalize_version(version)
            candidates = [
                cls.CONFIGS_DIR / f"{v_code}.json",
                cls.CONFIGS_DIR / f"{version}.json",
            ]
            for cand in candidates:
                if cand.exists():
                    template_path = cand
                    break

        # 2. Fallback to default template
        if not template_path:
            template_path = cls.BASE_DIR / "data" / "server_config_template.json"
            if not template_path.exists():
                template_path = cls.BASE_DIR / "data" / "config.json"

        data = {}
        if template_path and template_path.exists():
            try:
                with open(template_path, "r", encoding="utf-8") as f:
                    content = f.read().replace("{BASE_URL}", base_url)
                    data = json.loads(content)
            except Exception as e:
                print(f"[CONFIG] Error loading config from {template_path}: {e}", flush=True)

        cfg = data.setdefault("allConfigs", {}).setdefault("anyDeviceType", {})

        manifest_id = "d7c606f6-44bb-42ab-a655-96d03f1467e0"
        manifest_url = f"{base_url}/rest/dlc/manifests/{manifest_id}.json"
        dlc_manifests = cfg.setdefault("dlcManifests", {})
        for tier in ["low", "medium", "med", "high", "verylow", "LOW", "MEDIUM", "MED", "HIGH", "VERYLOW"]:
            dlc_manifests.setdefault(tier, manifest_url)

        if "definitions" in cfg:
            cfg["definitions"] = cfg["definitions"].replace("{BASE_URL}", base_url)
        else:
            cfg["definitions"] = f"{base_url}/rest/definitions/0.json"

        if "videoUri" in cfg:
            cfg["videoUri"] = cfg["videoUri"].replace("{BASE_URL}", base_url)
        else:
            cfg["videoUri"] = f"{base_url}/video.mp4"

        cfg["httpRequestTimeout"] = timeout
        cfg["httpRequestReadWriteTimeout"] = timeout

        return data

    @classmethod
    def get_definition_path(cls, filename: str):
        # 1. Check data/definitions/<filename>
        target = cls.DEFINITIONS_DIR / filename
        if target.exists():
            return target
        if not filename.endswith(".json"):
            target_json = cls.DEFINITIONS_DIR / f"{filename}.json"
            if target_json.exists():
                return target_json
        # 2. Fallback to data/definitions.json (especially for 0.json or legacy requests)
        legacy = Path(cls.DEFINITIONS_PATH)
        if legacy.exists():
            return legacy
        return None

# Create directories if they don't exist
os.makedirs(Config.PLAYER_DATA_DIR, exist_ok=True)
os.makedirs(Config.BACKUP_DIR, exist_ok=True)
os.makedirs(Config.CONFIGS_DIR, exist_ok=True)
os.makedirs(Config.DEFINITIONS_DIR, exist_ok=True)

