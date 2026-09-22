import os
from pathlib import Path

# Simple .env loader if python-dotenv is not installed
def load_env(env_path=".env"):
    if os.path.exists(env_path):
        with open(env_path, "r") as f:
            for line in f:
                if line.strip() and not line.startswith("#"):
                    key, value = line.strip().split("=", 1)
                    os.environ[key] = value

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
    
    # URL configurations
    BASE_URL = os.getenv("BASE_URL", f"http://localhost:{PORT_MAIN}")
    SECONDARY_URL = os.getenv("SECONDARY_URL", f"http://localhost:{PORT_SECONDARY}")
    
    # Admin settings
    ADMIN_PASSWORD = os.getenv("ADMIN_PASSWORD", "admin")

    # Database backup settings
    BACKUP_DIR = os.getenv("BACKUP_DIR", str(BASE_DIR / "player_data" / "backups"))
    BACKUP_INTERVAL_SECONDS = int(os.getenv("BACKUP_INTERVAL_SECONDS", 86400))  # 24 hours
    MAX_ROLLING_BACKUPS = int(os.getenv("MAX_ROLLING_BACKUPS", 4))

# Create directories if they don't exist
os.makedirs(Config.PLAYER_DATA_DIR, exist_ok=True)
os.makedirs(Config.BACKUP_DIR, exist_ok=True)
