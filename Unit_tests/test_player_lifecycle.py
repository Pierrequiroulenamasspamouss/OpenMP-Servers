import json
from tests.base_test import BaseServerTestCase
from utils.db import get_player_event_flags, player_has_christmas_minion, ALL_TARGET_UNLOCK_IDS
from routes.dashboard import gen_token

class TestPlayerLifecycle(BaseServerTestCase):
    """
    Simulates the exact end-to-end player lifecycle:
    1. Player connects and loads initial gamestate.
    2. Player accesses the dashboard, logs in, and toggles Special Event Buildings on.
    3. Player triggers the Christmas Minion offer.
    4. Client sends in-game periodic save (simulating gameplay/disconnect) WITHOUT target unlocks.
    5. Verify server protects and persists target unlocks without overwriting.
    6. Verify Christmas minion can be re-triggered if not yet claimed into inventory.
    7. Player acquires/claims Christmas minion into inventory (pack 8033 / 70009).
    8. Verify Christmas minion is recognized as OWNED and offer is locked.
    9. Player toggles Special Event Buildings off, sends save, verify cleanly relocked.
    """

    def test_full_player_lifecycle_and_desync_protection(self):
        uid = "lifecycle_user_1"
        self.create_dummy_player(uid=uid, playtime=120)

        # Step 1: Player connects to game server and retrieves gamestate
        res = self.client.get(f"/rest/gamestate/{uid}")
        self.assertEqual(res.status_code, 200)
        gamestate = res.get_json()
        self.assertEqual(gamestate["ID"], uid)

        # Initially, limited buildings are locked (deactivated by default)
        flags = get_player_event_flags(uid)
        self.assertEqual(flags["limited_buildings_unlocked"], 0)
        self.assertEqual(flags["holiday_offer_active"], 0)
        self.assertFalse(player_has_christmas_minion(uid))

        # Step 2: Player opens dashboard and logs in
        login_res = self.client.post("/api/dashboard/login", json={"uid": uid, "password": ""})
        self.assertEqual(login_res.status_code, 200)
        login_data = login_res.get_json()
        token = login_data["token"]
        self.assertTrue(token)

        # Step 3: Player activates Special Event Buildings on Dashboard
        toggle_res = self.client.post("/api/dashboard/set_limited_buildings", json={
            "uid": uid, "token": token, "enabled": 1
        })
        self.assertEqual(toggle_res.status_code, 200)
        flags = get_player_event_flags(uid)
        self.assertEqual(flags["limited_buildings_unlocked"], 1)

        # Verify DB unlocks table immediately updated
        row = self.get_db_row(uid)
        db_unlocks = json.loads(row["unlocks"])
        db_unlock_ids = {u.get("defID") for u in db_unlocks if isinstance(u, dict)}
        self.assertTrue(ALL_TARGET_UNLOCK_IDS.issubset(db_unlock_ids))

        # Step 4: Player triggers Christmas Minion Offer on Dashboard
        trigger_res = self.client.post("/api/dashboard/trigger_christmas_minion", json={
            "uid": uid, "token": token
        })
        self.assertEqual(trigger_res.status_code, 200)
        self.assertEqual(trigger_res.get_json()["status"], "success")

        flags = get_player_event_flags(uid)
        self.assertEqual(flags["holiday_offer_active"], 1)

        # Step 5: Player is playing in-game; client sends a periodic save with its OLD memory state
        # (Client does NOT know about target unlock IDs yet in its memory)
        client_save = gamestate.copy()
        client_save["totalAccumulatedGameplayDuration"] = 200
        client_save["lastPlayedTime"] = 2000
        # Client save has empty/basic unlocks (no ALL_TARGET_UNLOCK_IDS)
        client_save["unlocks"] = [{"defID": 3002, "quantity": 1}]

        save_res = self.client.post(f"/rest/gamestate/{uid}", json=client_save)
        self.assertEqual(save_res.status_code, 200)

        # CRITICAL DESYNC CHECK: Verify the incoming save did NOT wipe out ALL_TARGET_UNLOCK_IDS!
        row_after_save = self.get_db_row(uid)
        saved_unlocks = json.loads(row_after_save["unlocks"])
        saved_ids = {u.get("defID") for u in saved_unlocks if isinstance(u, dict)}
        self.assertTrue(ALL_TARGET_UNLOCK_IDS.issubset(saved_ids), "Server must protect and inject unlocks when flag is active!")

        # Step 6: Christmas Minion re-trigger check:
        # Since player hasn't claimed minion into inventory, check status on dashboard
        status_res = self.client.get(f"/api/dashboard/player_events_status?uid={uid}&token={token}")
        self.assertEqual(status_res.status_code, 200)
        status_data = status_res.get_json()
        self.assertFalse(status_data["christmas_minion_owned"])
        self.assertTrue(status_data["holiday_offer_active"])

        # Re-trigger is allowed so player never loses their minion opportunity
        retrigger_res = self.client.post("/api/dashboard/trigger_christmas_minion", json={
            "uid": uid, "token": token
        })
        self.assertEqual(retrigger_res.status_code, 200)
        self.assertEqual(retrigger_res.get_json()["status"], "success")

        # Step 7: Player claims minion in-game! (Pack 8033 purchased and minion 70009 added to inventory)
        client_save["purchasedSales"] = [{"defID": 8033, "numberPurchased": 1}]
        client_save["inventory"].append({"ID": 70009, "Definition": 70009, "Quantity": 1})
        client_save["totalAccumulatedGameplayDuration"] = 300
        client_save["lastPlayedTime"] = 3000

        save_res2 = self.client.post(f"/rest/gamestate/{uid}", json=client_save)
        self.assertEqual(save_res2.status_code, 200)

        # Step 8: Dashboard check: Minion is now marked as OWNED!
        self.assertTrue(player_has_christmas_minion(uid))
        status_res2 = self.client.get(f"/api/dashboard/player_events_status?uid={uid}&token={token}")
        self.assertTrue(status_res2.get_json()["christmas_minion_owned"])

        # Attempting to re-trigger now returns already_owned
        locked_trigger = self.client.post("/api/dashboard/trigger_christmas_minion", json={
            "uid": uid, "token": token
        })
        self.assertEqual(locked_trigger.get_json()["status"], "already_owned")

        # Step 9: Player deactivates Special Event Buildings on Dashboard (Opt-out)
        deact_res = self.client.post("/api/dashboard/set_limited_buildings", json={
            "uid": uid, "token": token, "enabled": 0
        })
        self.assertEqual(deact_res.status_code, 200)

        # Verify DB unlocks stripped
        row_deact = self.get_db_row(uid)
        deact_unlocks = json.loads(row_deact["unlocks"])
        deact_ids = {u.get("defID") for u in deact_unlocks if isinstance(u, dict)}
        self.assertFalse(any(tid in deact_ids for tid in ALL_TARGET_UNLOCK_IDS))

        # Client sends next save with leftover unlocks: server must strip them cleanly
        client_save["totalAccumulatedGameplayDuration"] = 400
        client_save["lastPlayedTime"] = 4000
        self.client.post(f"/rest/gamestate/{uid}", json=client_save)

        row_final = self.get_db_row(uid)
        final_unlocks = json.loads(row_final["unlocks"])
        final_ids = {u.get("defID") for u in final_unlocks if isinstance(u, dict)}
        self.assertFalse(any(tid in final_ids for tid in ALL_TARGET_UNLOCK_IDS))
