import json
from tests.base_test import BaseServerTestCase

class TestDashboardFeatures(BaseServerTestCase):
    def test_login_and_token_generation(self):
        uid = "dash_user_1"
        self.create_dummy_player(uid=uid)

        res = self.client.post("/api/dashboard/login", json={"uid": uid})
        self.assertEqual(res.status_code, 200)
        data = res.get_json()
        self.assertTrue(data.get("token"))
        self.assertFalse(data.get("secured"))

    def test_password_protection_flow(self):
        uid = "dash_pwd_user"
        self.create_dummy_player(uid=uid)

        # Login without password initially
        res = self.client.post("/api/dashboard/login", json={"uid": uid})
        token = res.get_json()["token"]

        # Set password
        set_pwd_res = self.client.post("/api/dashboard/set_password", json={
            "uid": uid, "token": token, "password": "SecretPassword123"
        })
        self.assertEqual(set_pwd_res.status_code, 200)

        # Try to login without password -> should fail
        fail_login = self.client.post("/api/dashboard/login", json={"uid": uid, "password": ""})
        self.assertEqual(fail_login.status_code, 401)

        # Try to login with wrong password -> should fail
        wrong_pwd = self.client.post("/api/dashboard/login", json={"uid": uid, "password": "WrongPassword"})
        self.assertEqual(wrong_pwd.status_code, 401)

        # Login with correct password -> should succeed
        ok_login = self.client.post("/api/dashboard/login", json={"uid": uid, "password": "SecretPassword123"})
        self.assertEqual(ok_login.status_code, 200)
        self.assertTrue(ok_login.get_json().get("secured"))

    def test_inventory_api_crud(self):
        uid = "dash_inv_user"
        self.create_dummy_player(uid=uid)

        login_res = self.client.post("/api/dashboard/login", json={"uid": uid})
        token = login_res.get_json()["token"]

        # 1. View inventory
        inv_res = self.client.get(f"/api/dashboard/inventory?uid={uid}&token={token}")
        self.assertEqual(inv_res.status_code, 200)
        inv_list = inv_res.get_json()["inventory"]
        self.assertGreater(len(inv_list), 0)

        # 2. Add / Update item (item ID 205 = Sand Dollar, amount 77)
        update_res = self.client.post("/api/dashboard/update_inventory_item", json={
            "uid": uid, "token": token, "item_id": 205, "amount": 77, "action": "update"
        })
        self.assertEqual(update_res.status_code, 200)

        # Verify item added/updated
        row = self.get_db_row(uid)
        inventory = json.loads(row["inventory"])
        item = next((i for i in inventory if i.get("Definition") == 205 or i.get("ID") == 205), None)
        self.assertIsNotNone(item)
        self.assertEqual(item.get("Quantity"), 77)

        # 3. Delete item
        del_res = self.client.post("/api/dashboard/update_inventory_item", json={
            "uid": uid, "token": token, "item_id": 205, "action": "delete"
        })
        self.assertEqual(del_res.status_code, 200)

        row_after_del = self.get_db_row(uid)
        inventory_after = json.loads(row_after_del["inventory"])
        item_del = next((i for i in inventory_after if i.get("Definition") == 205 or i.get("ID") == 205), None)
        self.assertIsNone(item_del)

    def test_update_profile(self):
        uid = "profile_user"
        self.create_dummy_player(uid=uid)

        login_res = self.client.post("/api/dashboard/login", json={"uid": uid})
        token = login_res.get_json()["token"]

        res = self.client.post("/api/dashboard/update_profile", json={
            "uid": uid, "token": token, "custom_name": "MegaMinion", "custom_avatar": "https://avatar.com/test.png"
        })
        self.assertEqual(res.status_code, 200)

        row = self.get_db_row(uid)
        self.assertEqual(row["name"], "MegaMinion")
        self.assertEqual(row["custom_name"], "MegaMinion")
        self.assertEqual(row["custom_avatar"], "https://avatar.com/test.png")

    def test_save_migration(self):
        source_uid = "source_user_1"
        target_uid = "target_user_2"
        self.create_dummy_player(uid=source_uid, playtime=500)
        self.create_dummy_player(uid=target_uid, playtime=10)

        login_res = self.client.post("/api/dashboard/login", json={"uid": source_uid})
        token = login_res.get_json()["token"]

        # Migrate TO target_uid
        mig_res = self.client.post("/api/dashboard/migrate_save", json={
            "uid": source_uid, "token": token, "direction": "to", "target_uid": target_uid
        })
        self.assertEqual(mig_res.status_code, 200)

        target_row = self.get_db_row(target_uid)
        self.assertEqual(target_row["totalAccumulatedGameplayDuration"], 500)

    def test_backup_save_download(self):
        uid = "backup_user"
        self.create_dummy_player(uid=uid)

        login_res = self.client.post("/api/dashboard/login", json={"uid": uid})
        token = login_res.get_json()["token"]

        res = self.client.get(f"/api/dashboard/backup_save?uid={uid}&token={token}")
        self.assertEqual(res.status_code, 200)
        self.assertIn("application/json", res.headers.get("Content-Type", ""))
        data = res.get_json()
        self.assertEqual(data.get("uid"), uid)
