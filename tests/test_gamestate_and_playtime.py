import json
from tests.base_test import BaseServerTestCase
from utils.db import set_player_event_flag

class TestGamestateAndPlaytime(BaseServerTestCase):
    def test_playtime_guard_protects_progress(self):
        uid = "playtime_user_1"
        self.create_dummy_player(uid=uid, playtime=1000)

        # Incoming save with lower playtime (e.g. 500 seconds)
        stale_save = {
            "uid": uid,
            "totalAccumulatedGameplayDuration": 500,
            "lastPlayedTime": 500,
            "inventory": [{"ID": 0, "Definition": 0, "Quantity": 1}]
        }
        res = self.client.post(f"/rest/gamestate/{uid}", json=stale_save)
        self.assertEqual(res.status_code, 200)

        # Verify database kept the higher playtime (1000)
        row = self.get_db_row(uid)
        self.assertEqual(row["totalAccumulatedGameplayDuration"], 1000)

    def test_playtime_guard_manual_override_bypass(self):
        uid = "playtime_user_override"
        self.create_dummy_player(uid=uid, playtime=1000)

        # A dashboard manual save upload has lastPlayedTime >= 2000000000
        override_save = {
            "uid": uid,
            "totalAccumulatedGameplayDuration": 100,
            "lastPlayedTime": 2000000001,
            "inventory": [{"ID": 0, "Definition": 0, "Quantity": 99999}]
        }
        res = self.client.post(f"/rest/gamestate/{uid}", json=override_save)
        self.assertEqual(res.status_code, 200)

        # Verify update succeeded because of manual override timestamp
        row = self.get_db_row(uid)
        self.assertEqual(row["totalAccumulatedGameplayDuration"], 100)

    def test_special_event_item_110000_patching_active_vs_inactive(self):
        uid = "event_item_user"
        self.create_dummy_player(uid=uid)

        # 1. When christmas_event_active is 1 -> HasEnded: False
        set_player_event_flag(uid, "christmas_event_active", 1)
        res = self.client.get(f"/rest/gamestate/{uid}")
        self.assertEqual(res.status_code, 200)
        data = res.get_json()
        item_110000 = next((i for i in data.get("inventory", []) if i.get("Definition") == 110000), None)
        self.assertIsNotNone(item_110000)
        self.assertFalse(item_110000.get("HasEnded"))

        # 2. When christmas_event_active is 0 -> HasEnded: True
        set_player_event_flag(uid, "christmas_event_active", 0)
        res2 = self.client.get(f"/rest/gamestate/{uid}")
        self.assertEqual(res2.status_code, 200)
        data2 = res2.get_json()
        item_110000_inactive = next((i for i in data2.get("inventory", []) if i.get("Definition") == 110000), None)
        self.assertIsNotNone(item_110000_inactive)
        self.assertTrue(item_110000_inactive.get("HasEnded"))

    def test_save_and_retrieve_complex_structures(self):
        uid = "complex_save_user"
        initial_player = self.create_dummy_player(uid=uid)

        initial_player["villainQueue"] = [{"villainId": 501, "state": "active"}]
        initial_player["triggers"] = [{"id": 101, "completed": True}]
        initial_player["totalAccumulatedGameplayDuration"] = 2000
        initial_player["lastPlayedTime"] = 2000

        res = self.client.post(f"/rest/gamestate/{uid}", json=initial_player)
        self.assertEqual(res.status_code, 200)

        # Retrieve and verify structures parsed back
        res_get = self.client.get(f"/rest/gamestate/{uid}")
        self.assertEqual(res_get.status_code, 200)
        retrieved = res_get.get_json()
        self.assertEqual(retrieved["villainQueue"], [{"villainId": 501, "state": "active"}])
        self.assertEqual(retrieved["triggers"], [{"id": 101, "completed": True}])
