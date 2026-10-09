import time
import json
import os
from config import Config

def generate_new_player_profile(user_id_str):
    server_dir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    candidate_paths = [
        getattr(Config, 'EMPTY_PLAYER_PATH', ''),
        os.path.join(server_dir, "data", "empty_player.json"),
        os.path.join(server_dir, "empty_player.json")
    ]
    
    empty_player_path = next((p for p in candidate_paths if p and os.path.exists(p)), None)
    
    if empty_player_path:
        try:
            with open(empty_player_path, 'r', encoding='utf-8') as f:
                profile = json.load(f)
            
            # Update the ID to the one requested
            profile["ID"] = str(user_id_str)
            print(f"[PROFILE] Generated new profile for {user_id_str} using {empty_player_path}")
            return profile
        except Exception as e:
            print(f"[PROFILE] Error loading empty_player.json from {empty_player_path}: {e}")

    # Fallback if empty_player.json is missing or corrupt
    numeric_id = 1001
    try:
        numeric_id = int(str(user_id_str))
    except ValueError:
        numeric_id = 1001

    profile = {
        "version": "3",
        "ID": str(numeric_id),
        "nextId": 1000,
        
        "inventory": [],
        
        "villainQueue": [],
        "pendingTransactions": [],
        "unlocks": [],
        "socialRewards": [],
        "PlatformStoreTransactionIDs": [],
        
        "highestFtueLevel": 999,
        "lastLevelUpTime": 0,
        "lastGameStartTime": 0,
        "totalGameplayDurationSinceLastLevelUp": 0,
        "targetExpansionID": 0,
        "freezeTime": 0
    }
    
    return profile
