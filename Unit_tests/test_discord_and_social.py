import json
from tests.base_test import BaseServerTestCase
from utils.db import get_uid_by_discord_id, resolve_master_uid

class TestDiscordAndSocial(BaseServerTestCase):
    def test_discord_id_resolution(self):
        uid = "disc_user_123"
        discord_payload = {
            "id": "discord_id_99999",
            "username": "MinionMaster",
            "avatar": "https://cdn.discordapp.com/avatars/123/abc.png"
        }
        player_data = self.create_dummy_player(uid=uid)
        player_data["discord_info"] = json.dumps(discord_payload)

        from utils.db import update_player_in_db
        update_player_in_db(uid, player_data)

        # Lookup by Discord ID
        resolved_uid = get_uid_by_discord_id("discord_id_99999")
        self.assertEqual(resolved_uid, uid)

    def test_resolve_master_uid(self):
        uid = "master_user_test"
        self.create_dummy_player(uid=uid)
        master = resolve_master_uid(uid)
        self.assertEqual(master, uid)

    def test_unlink_socials(self):
        uid = "unlink_user"
        discord_payload = {"id": "disc_link_123", "username": "LinkedMinion"}
        player_data = self.create_dummy_player(uid=uid)
        player_data["discord_info"] = json.dumps(discord_payload)

        from utils.db import update_player_in_db
        update_player_in_db(uid, player_data)

        login_res = self.client.post("/api/dashboard/login", json={"uid": uid})
        token = login_res.get_json()["token"]

        res = self.client.post("/api/dashboard/unlink_socials", json={"uid": uid, "token": token})
        self.assertEqual(res.status_code, 200)

        # Verify socials unlinked
        row = self.get_db_row(uid)
        self.assertEqual(row["DISCORD"], "")
        self.assertEqual(row["FACEBOOK"], "")
        self.assertEqual(row["GOOGLE_PLAY"], "")
