import unittest
import os
import sys
import tempfile
import sqlite3
import json

# Ensure SERVER directory is in Python path
SERVER_DIR = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
if SERVER_DIR not in sys.path:
    sys.path.insert(0, SERVER_DIR)

from config import Config
import utils.db as db_utils
from kampai_server import create_app

class BaseServerTestCase(unittest.TestCase):
    def setUp(self):
        # Create a unique temporary SQLite database for each test
        self.temp_db_file = tempfile.NamedTemporaryFile(suffix=".db", delete=False)
        self.temp_db_path = self.temp_db_file.name
        self.temp_db_file.close()

        # Point Config and db_utils to the temporary database
        self.orig_db_path = Config.DB_PATH
        Config.DB_PATH = self.temp_db_path
        db_utils.Config.DB_PATH = self.temp_db_path
        db_utils.DB_PATH = self.temp_db_path

        # Create isolated test app and client
        self.app = create_app(8080)
        self.app.config['TESTING'] = True
        self.client = self.app.test_client()

    def tearDown(self):
        # Restore original DB path
        Config.DB_PATH = self.orig_db_path
        db_utils.Config.DB_PATH = self.orig_db_path
        db_utils.DB_PATH = self.orig_db_path

        # Clean up temporary database file
        try:
            if os.path.exists(self.temp_db_path):
                os.remove(self.temp_db_path)
        except Exception:
            pass

    def create_dummy_player(self, uid="10001", name="Kevin", level=1, xp=0, playtime=100, inventory=None, unlocks=None, purchased_sales=None):
        """Helper to create a fully formed dummy player in the test DB."""
        if inventory is None:
            inventory = [
                {"ID": 0, "Definition": 0, "Quantity": 1000}, # Soft currency
                {"ID": 1, "Definition": 1, "Quantity": 50},   # Hard currency
                {"ID": 2, "Definition": 2, "Quantity": xp}    # XP item
            ]
        if unlocks is None:
            unlocks = [
                {"defID": 3002, "quantity": 1}
            ]
        if purchased_sales is None:
            purchased_sales = []

        player_data = {
            "uid": str(uid),
            "ID": str(uid),
            "version": 1,
            "nextId": 200,
            "villainQueue": [],
            "inventory": inventory,
            "pendingTransactions": [],
            "unlocks": unlocks,
            "purchasedSales": purchased_sales,
            "triggers": [],
            "lastLevelUpTime": 0,
            "lastGameStartTime": 1000,
            "firstGameStartTime": 1000,
            "lastPlayedTime": 1000,
            "totalGameplayDurationSinceLastLevelUp": playtime,
            "totalAccumulatedGameplayDuration": playtime,
            "targetExpansionID": 0,
            "timezoneOffset": 0,
            "country": "US",
            "completedOrders": 0,
            "highestFtueLevel": 1,
            "socialRewards": [],
            "mtxPurchaseTracking": [],
            "completedQuestsTotal": 0,
            "currentItemCount": len(inventory),
            "PlatformStoreTransactionIDs": [],
            "helpTipsTrackingData": [],
            "PlayerLevel": level,
            "xp": xp,
            "Time_played": playtime
        }
        db_utils.update_player_in_db(str(uid), player_data)
        return player_data

    def get_db_row(self, uid):
        """Directly query the database for a player's row."""
        conn = db_utils.get_db_connection()
        row = conn.execute("SELECT * FROM players WHERE uid = ?", (str(uid),)).fetchone()
        conn.close()
        return dict(row) if row else None
