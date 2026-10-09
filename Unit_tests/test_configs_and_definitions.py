import json
import os
from tests.base_test import BaseServerTestCase
from config import Config
from routes.sales import get_defs, clear_cached_defs

class TestConfigsAndDefinitions(BaseServerTestCase):
    def test_config_json_validity(self):
        config_path = os.path.join(Config.BASE_DIR, "config.json")
        self.assertTrue(os.path.exists(config_path))
        with open(config_path, "r") as f:
            cfg = json.load(f)
        self.assertIn("allConfigs", cfg)

    def test_shop_schedule_validity(self):
        self.assertTrue(os.path.exists(Config.SCHEDULE_PATH))
        with open(Config.SCHEDULE_PATH, "r") as f:
            sched = json.load(f)
        self.assertIn("active_packs", sched)
        self.assertTrue(isinstance(sched["active_packs"], dict))

    def test_definitions_caching_and_indexing(self):
        clear_cached_defs()
        defs, indexed = get_defs()
        self.assertIsNotNone(defs)
        self.assertIsNotNone(indexed)
        self.assertTrue(isinstance(indexed, dict))
        # Ensure key definitions exist
        self.assertIn("buildingDefinitions", defs)
        self.assertIn("itemDefinitions", defs)

    def test_dlc_manifest_validity(self):
        manifest_path = os.path.join(Config.BASE_DIR, "data", "DLC_Manifest.json")
        if os.path.exists(manifest_path):
            with open(manifest_path, "r") as f:
                manifest = json.load(f)
            self.assertTrue(isinstance(manifest, (dict, list)))
