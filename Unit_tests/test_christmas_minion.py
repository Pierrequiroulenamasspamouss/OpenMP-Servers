import json
from tests.base_test import BaseServerTestCase
from utils.db import player_has_christmas_minion, set_player_event_flag, get_player_event_flags

class TestChristmasMinion(BaseServerTestCase):
    def test_minion_ownership_detection_empty(self):
        uid = "minion_user_none"
        self.create_dummy_player(uid=uid)
        self.assertFalse(player_has_christmas_minion(uid))

    def test_minion_ownership_detection_purchased_sales(self):
        uid = "minion_user_pack"
        self.create_dummy_player(uid=uid, purchased_sales=[{"defID": 8033, "numberPurchased": 1}])
        self.assertTrue(player_has_christmas_minion(uid))

    def test_minion_ownership_detection_store_pack_id(self):
        uid = "minion_user_store_pack"
        self.create_dummy_player(uid=uid, purchased_sales=[{"ID": 18033, "numberPurchased": 1}])
        self.assertTrue(player_has_christmas_minion(uid))

    def test_minion_ownership_detection_unlocks(self):
        uid = "minion_user_unlock"
        self.create_dummy_player(uid=uid, unlocks=[{"defID": 70009, "quantity": 1}])
        self.assertTrue(player_has_christmas_minion(uid))

    def test_minion_ownership_detection_inventory(self):
        uid = "minion_user_inv"
        self.create_dummy_player(uid=uid, inventory=[{"ID": 70009, "Definition": 70009, "Quantity": 1}])
        self.assertTrue(player_has_christmas_minion(uid))

    def test_dashboard_trigger_allows_retrigger_when_not_owned(self):
        uid = "minion_trigger_user"
        self.create_dummy_player(uid=uid)

        login_res = self.client.post("/api/dashboard/login", json={"uid": uid})
        token = login_res.get_json()["token"]

        # First trigger
        res1 = self.client.post("/api/dashboard/trigger_christmas_minion", json={"uid": uid, "token": token})
        self.assertEqual(res1.status_code, 200)
        self.assertEqual(res1.get_json()["status"], "success")
        self.assertTrue(get_player_event_flags(uid)["holiday_offer_active"])

        # Second trigger (player still hasn't received minion into inventory)
        res2 = self.client.post("/api/dashboard/trigger_christmas_minion", json={"uid": uid, "token": token})
        self.assertEqual(res2.status_code, 200)
        self.assertEqual(res2.get_json()["status"], "success")

    def test_dashboard_trigger_locks_when_owned(self):
        uid = "minion_owned_user"
        self.create_dummy_player(uid=uid, purchased_sales=[{"defID": 8033}])

        login_res = self.client.post("/api/dashboard/login", json={"uid": uid})
        token = login_res.get_json()["token"]

        res = self.client.post("/api/dashboard/trigger_christmas_minion", json={"uid": uid, "token": token})
        self.assertEqual(res.status_code, 200)
        data = res.get_json()
        self.assertEqual(data["status"], "already_owned")
        self.assertTrue(data["christmas_minion_owned"])

    def test_sales_endpoint_pack_8033_active_when_triggered(self):
        uid = "minion_sales_user"
        self.create_dummy_player(uid=uid)
        set_player_event_flag(uid, "holiday_offer_active", 1)

        res = self.client.get(f"/rest/sales/{uid}/v2")
        self.assertEqual(res.status_code, 200)
        sales = res.get_json()
        pack_8033 = next((s for s in sales if s.get("SaleId") == 8033), None)
        self.assertIsNotNone(pack_8033)
        sale_def = json.loads(pack_8033["SaleDefinition"])
        self.assertTrue(sale_def.get("freeGift"))
        self.assertFalse(sale_def.get("DISABLED", False))

    def test_sales_endpoint_pack_8033_disabled_if_already_owned(self):
        uid = "minion_sales_owned"
        self.create_dummy_player(uid=uid, purchased_sales=[{"defID": 8033}])
        set_player_event_flag(uid, "holiday_offer_active", 1)

        res = self.client.get(f"/rest/sales/{uid}/v2")
        self.assertEqual(res.status_code, 200)
        sales = res.get_json()
        pack_8033 = next((s for s in sales if s.get("SaleId") == 8033), None)
        if pack_8033:
            sale_def = json.loads(pack_8033["SaleDefinition"])
            # Should be disabled or expired since minion is already owned
            self.assertTrue(sale_def.get("DISABLED") or sale_def.get("UTCENDDATE") <= 1)
