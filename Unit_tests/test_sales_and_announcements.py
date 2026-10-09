import json
import os
from tests.base_test import BaseServerTestCase
from config import Config

class TestSalesAndAnnouncements(BaseServerTestCase):
    def test_market_prices(self):
        res = self.client.get("/rest/market_prices")
        self.assertEqual(res.status_code, 200)
        data = res.get_json()
        self.assertTrue(isinstance(data, dict))

    def test_sales_fetch_active_packs(self):
        uid = "sales_user_1"
        self.create_dummy_player(uid=uid)

        res = self.client.get(f"/rest/sales/{uid}/v2")
        self.assertEqual(res.status_code, 200)
        sales = res.get_json()
        self.assertTrue(isinstance(sales, list))
        self.assertGreater(len(sales), 0)

    def test_server_announcement_configuration(self):
        # Configure a test server announcement popup
        announcement_payload = {
            "enabled": True,
            "title": "Hello world",
            "message": "Welcome players!",
            "pack_id": "55000",
            "free_gift": True
        }
        post_res = self.client.post("/api/admin/announcement", json=announcement_payload)
        self.assertEqual(post_res.status_code, 200)

        # GET announcement
        get_res = self.client.get("/api/admin/announcement")
        self.assertEqual(get_res.status_code, 200)
        self.assertEqual(get_res.get_json()["title"], "Hello world")

        # Now fetch sales for a player: verify pack 55000 is injected with custom title
        uid = "ann_player"
        self.create_dummy_player(uid=uid)

        sales_res = self.client.get(f"/rest/sales/{uid}/v2")
        self.assertEqual(sales_res.status_code, 200)
        sales = sales_res.get_json()

        ann_pack = next((s for s in sales if str(s.get("SaleId")) == "55000"), None)
        self.assertIsNotNone(ann_pack)
        sale_def = json.loads(ann_pack["SaleDefinition"])
        self.assertEqual(sale_def.get("localizedKey"), "Hello world")
        self.assertTrue(sale_def.get("freeGift"))
        self.assertFalse(sale_def.get("DISABLED", False))

        # Disable announcement
        self.client.post("/api/admin/announcement", json={"enabled": False})

    def test_nopromo_restricted_user(self):
        uid = "restricted_user_99"
        self.create_dummy_player(uid=uid)

        # Write to nopromousers.txt
        with open(Config.NOPROMOUSERS_PATH, "a") as f:
            f.write(f"\n{uid}\n")

        try:
            res = self.client.get(f"/rest/sales/{uid}/v2")
            self.assertEqual(res.status_code, 200)
            sales = res.get_json()
            for s in sales:
                s_id = str(s.get("SaleId"))
                permanent_ids = {
                    "9098", "9099", "9100", "9101", "9102", "9103", "9104", "9105", "9106",
                    "9107", "9108", "9109", "9110", "9111", "9112",
                    "9129", "9130", "9131", "9132", "9133", "9134", "9135", "9136", "9137", "9138", "9139", "9140", "9141", "9142", "9143"
                }
                if s_id not in permanent_ids:
                    s_def = json.loads(s["SaleDefinition"])
                    self.assertTrue(s_def.get("DISABLED") or s_def.get("UNLOCKLEVEL", 0) >= 999)
        finally:
            # Clean up nopromousers.txt
            if os.path.exists(Config.NOPROMOUSERS_PATH):
                with open(Config.NOPROMOUSERS_PATH, "r") as f:
                    lines = [line for line in f if line.strip() != uid]
                with open(Config.NOPROMOUSERS_PATH, "w") as f:
                    f.writelines(lines)
