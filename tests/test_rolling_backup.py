import unittest
import os
import sys
import tempfile
import sqlite3
import time
import shutil

SERVER_DIR = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
if SERVER_DIR not in sys.path:
    sys.path.insert(0, SERVER_DIR)

from utils.db import (
    perform_rolling_backup,
    get_rolling_backups,
    start_backup_scheduler,
    _backup_sort_key
)

class TestRollingBackup(unittest.TestCase):
    def setUp(self):
        self.test_dir = tempfile.mkdtemp(prefix="test_backup_")
        self.db_path = os.path.join(self.test_dir, "players.db")
        self.backup_dir = os.path.join(self.test_dir, "backups")

        # Initialize a test database with schema and sample player
        conn = sqlite3.connect(self.db_path)
        conn.execute("CREATE TABLE players (uid TEXT PRIMARY KEY, name TEXT, PlayerLevel INTEGER)")
        conn.execute("INSERT INTO players (uid, name, PlayerLevel) VALUES (?, ?, ?)", ("12345", "Kevin", 10))
        conn.commit()
        conn.close()

    def tearDown(self):
        try:
            shutil.rmtree(self.test_dir)
        except OSError:
            pass

    def test_backup_creation_and_integrity(self):
        """Test that a backup file is created and contains correct data."""
        backup_file = perform_rolling_backup(
            force=True,
            backup_dir=self.backup_dir,
            db_path=self.db_path
        )
        self.assertIsNotNone(backup_file)
        self.assertTrue(os.path.exists(backup_file))
        self.assertTrue(os.path.basename(backup_file).startswith("players_backup_"))

        # Verify integrity of the backup database
        conn = sqlite3.connect(backup_file)
        row = conn.execute("SELECT name, PlayerLevel FROM players WHERE uid = ?", ("12345",)).fetchone()
        conn.close()
        self.assertIsNotNone(row)
        self.assertEqual(row[0], "Kevin")
        self.assertEqual(row[1], 10)

    def test_backup_interval_throttling(self):
        """Test that calling perform_rolling_backup within 24h interval is skipped."""
        # First backup (forced)
        first_backup = perform_rolling_backup(
            force=True,
            min_interval=86400,
            backup_dir=self.backup_dir,
            db_path=self.db_path
        )
        self.assertIsNotNone(first_backup)

        # Immediate second call without force should be skipped
        second_backup = perform_rolling_backup(
            force=False,
            min_interval=86400,
            backup_dir=self.backup_dir,
            db_path=self.db_path
        )
        self.assertIsNone(second_backup)

        # Backups directory should only contain the 1 backup
        backups = get_rolling_backups(self.backup_dir)
        self.assertEqual(len(backups), 1)

    def test_backup_creates_when_interval_elapsed(self):
        """Test that a backup is performed once the minimum interval has elapsed."""
        first_backup = perform_rolling_backup(
            force=True,
            backup_dir=self.backup_dir,
            db_path=self.db_path
        )
        self.assertIsNotNone(first_backup)

        # Calling with min_interval = 0 means interval has elapsed
        second_backup = perform_rolling_backup(
            force=False,
            min_interval=0,
            backup_dir=self.backup_dir,
            db_path=self.db_path
        )
        self.assertIsNotNone(second_backup)
        self.assertNotEqual(first_backup, second_backup)

        backups = get_rolling_backups(self.backup_dir)
        self.assertEqual(len(backups), 2)

    def test_retention_policy_keeps_only_four_most_recent(self):
        """Test that rolling retention prunes older backups, keeping only the 4 most recent."""
        created_backups = []
        # Create 6 backups in sequence
        for i in range(6):
            # Short sleep to ensure timestamps or counters increment
            time.sleep(0.05)
            bkp = perform_rolling_backup(
                force=True,
                max_backups=4,
                backup_dir=self.backup_dir,
                db_path=self.db_path
            )
            self.assertIsNotNone(bkp)
            created_backups.append(bkp)

        remaining_backups = get_rolling_backups(self.backup_dir)
        self.assertEqual(len(remaining_backups), 4, f"Expected 4 backups but found {len(remaining_backups)}")

        # The two oldest backups should have been deleted
        self.assertFalse(os.path.exists(created_backups[0]), "Oldest backup should have been pruned")
        self.assertFalse(os.path.exists(created_backups[1]), "Second oldest backup should have been pruned")

        # The four newest backups should still exist
        for bkp in created_backups[2:]:
            self.assertTrue(os.path.exists(bkp), f"Recent backup {bkp} should still exist")

    def test_backup_sort_key(self):
        """Test timestamp parsing in sort key."""
        f1 = os.path.join(self.backup_dir, "players_backup_20260920_120000.db")
        f2 = os.path.join(self.backup_dir, "players_backup_20260921_120000.db")
        f3 = os.path.join(self.backup_dir, "players_backup_20260921_120000_1.db")

        k1 = _backup_sort_key(f1)
        k2 = _backup_sort_key(f2)
        k3 = _backup_sort_key(f3)

        self.assertLess(k1, k2)
        self.assertLess(k2, k3)

if __name__ == '__main__':
    unittest.main()
