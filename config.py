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
    DEFINITIONS_PATH = os.getenv("DEFINITIONS_PATH", str(BASE_DIR / "data" / "definitions.json"))
    PLAYER_DATA_DIR = os.getenv("PLAYER_DATA_DIR", str(BASE_DIR / "player_data"))
    NOPROMOUSERS_PATH = os.getenv("NOPROMOUSERS_PATH", str(BASE_DIR / "data" / "nopromousers.txt"))
    MARKET_PRICES_PATH = os.getenv("MARKET_PRICES_PATH", str(BASE_DIR / "data" / "market_prices.json"))
    SCHEDULE_PATH = os.getenv("SCHEDULE_PATH", str(BASE_DIR / "data" / "ShopSchedule.json"))
    
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

    @classmethod
    def get_dynamic_server_config(cls):
        base_url = cls.get_base_url()
        timeout = cls.get_http_timeout()

        template_path = cls.BASE_DIR / "data" / "server_config_template.json"
        if not template_path.exists():
            template_path = cls.BASE_DIR / "data" / "config.json"

        data = {}
        if template_path.exists():
            try:
                with open(template_path, "r", encoding="utf-8") as f:
                    data = json.load(f)
            except Exception as e:
                print(f"[CONFIG] Error loading template: {e}", flush=True)

        cfg = data.setdefault("allConfigs", {}).setdefault("anyDeviceType", {})

        manifest_id = "d7c606f6-44bb-42ab-a655-96d03f1467e0"
        manifest_url = f"{base_url}/rest/dlc/manifests/{manifest_id}.json"
        dlc_manifests = cfg.setdefault("dlcManifests", {})
        for tier in ["low", "medium", "med", "high", "verylow", "LOW", "MEDIUM", "MED", "HIGH", "VERYLOW"]:
            dlc_manifests[tier] = manifest_url

        cfg["definitions"] = f"{base_url}/rest/definitions/0.json"
        cfg["videoUri"] = f"{base_url}/video.mp4"
        cfg["httpRequestTimeout"] = timeout
        cfg["httpRequestReadWriteTimeout"] = timeout

        return data

# Create directories if they don't exist
os.makedirs(Config.PLAYER_DATA_DIR, exist_ok=True)
os.makedirs(Config.BACKUP_DIR, exist_ok=True)
