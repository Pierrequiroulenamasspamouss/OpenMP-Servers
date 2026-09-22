import sqlite3
import os
import json

from config import Config

DB_PATH = Config.DB_PATH
DEFINITIONS_PATH = Config.DEFINITIONS_PATH
PLAYER_DATA_DIR = Config.PLAYER_DATA_DIR
LEADERBOARD_JSON_PATH = os.path.join(PLAYER_DATA_DIR, 'leaderboard.json')

MINION_NAMES = ["Kevin", "Stuart", "Bob", "Dave", "Jerry", "Carl", "Mel", "Otto", "Tim", "Mark", "Phil", "Paul", "Donny", "Ken", "Mike"]
NOPROMOUSERS_PATH = Config.NOPROMOUSERS_PATH

def is_nopromo_user(user_id):
    """
    Checks if a user_id (or any ID in a comma-separated list) is in nopromousers.txt.
    Returns True if restricted, False otherwise.
    """
    if not user_id:
        return False
        
    if not os.path.exists(NOPROMOUSERS_PATH):
        return False
        
    try:
        with open(NOPROMOUSERS_PATH, 'r') as f:
            restricted_ids = [line.strip() for line in f if line.strip()]
            
        user_id_str = str(user_id)
        # Handle comma-separated list (from resolve_master_uid logic)
        for uid_part in user_id_str.split(','):
            if uid_part.strip() in restricted_ids:
                return True
                
        return False
    except Exception as e:
        print(f"[DB] Error reading nopromousers.txt: {e}")
        return False


def get_db_connection():
    conn = sqlite3.connect(Config.DB_PATH)
    conn.row_factory = sqlite3.Row
    return conn

def init_db():
    conn = get_db_connection()
    conn.execute('''
        CREATE TABLE IF NOT EXISTS players (
            uid TEXT PRIMARY KEY,
            ID TEXT,
            version INTEGER,
            nextId INTEGER,
            villainQueue TEXT,
            inventory TEXT,
            pendingTransactions TEXT,
            unlocks TEXT,
            purchasedSales TEXT,
            triggers TEXT,
            lastLevelUpTime INTEGER,
            lastGameStartTime INTEGER,
            firstGameStartTime INTEGER,
            lastPlayedTime INTEGER,
            totalGameplayDurationSinceLastLevelUp INTEGER,
            totalAccumulatedGameplayDuration INTEGER,
            targetExpansionID INTEGER,
            timezoneOffset INTEGER,
            country TEXT,
            completedOrders INTEGER,
            highestFtueLevel INTEGER,
            socialRewards TEXT,
            mtxPurchaseTracking TEXT,
            completedQuestsTotal INTEGER,
            currentItemCount INTEGER,
            PlatformStoreTransactionIDs TEXT,
            helpTipsTrackingData TEXT,
            
            name TEXT,
            PlayerLevel INTEGER,
            xp INTEGER,
            Time_played INTEGER,
            DISCORD TEXT,
            discord_username TEXT,
            discord_avatar TEXT,
            FACEBOOK TEXT,
            GOOGLE_PLAY TEXT,
            
            password TEXT,
            custom_avatar TEXT,
            custom_name TEXT,
            
            last_updated TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )
    ''')
    conn.execute('''
        CREATE TABLE IF NOT EXISTS tse_teams (
            team_id INTEGER PRIMARY KEY AUTOINCREMENT,
            event_id INTEGER NOT NULL,
            order_progress TEXT DEFAULT '[]',
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )
    ''')
    conn.execute('''
        CREATE TABLE IF NOT EXISTS tse_members (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            team_id INTEGER NOT NULL,
            user_id TEXT NOT NULL,
            reward_claimed INTEGER DEFAULT 0,
            FOREIGN KEY (team_id) REFERENCES tse_teams(team_id),
            UNIQUE(team_id, user_id)
        )
    ''')
    conn.execute('''
        CREATE TABLE IF NOT EXISTS tse_invitations (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            event_id INTEGER NOT NULL,
            team_id INTEGER NOT NULL,
            inviter_uid TEXT NOT NULL,
            invitee_uid TEXT NOT NULL,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            FOREIGN KEY (team_id) REFERENCES tse_teams(team_id)
        )
    ''')
    conn.execute('''
        CREATE TABLE IF NOT EXISTS global_chat (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            user_id TEXT NOT NULL,
            message TEXT NOT NULL,
            timestamp TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )
    ''')
    conn.commit()
    
    # Try to add columns for existing databases
    try:
        conn.execute("ALTER TABLE players ADD COLUMN password TEXT")
    except sqlite3.OperationalError:
        pass
    try:
        conn.execute("ALTER TABLE players ADD COLUMN custom_avatar TEXT")
    except sqlite3.OperationalError:
        pass
    try:
        conn.execute("ALTER TABLE players ADD COLUMN custom_name TEXT")
    except sqlite3.OperationalError:
        pass
    try:
        conn.execute("ALTER TABLE players ADD COLUMN christmas_event_active INTEGER DEFAULT 0")
    except sqlite3.OperationalError:
        pass
    try:
        conn.execute("ALTER TABLE players ADD COLUMN limited_buildings_unlocked INTEGER DEFAULT 0")
    except sqlite3.OperationalError:
        pass
    try:
        conn.execute("ALTER TABLE players ADD COLUMN holiday_offer_active INTEGER DEFAULT 0")
    except sqlite3.OperationalError:
        pass
        
    conn.commit()
    conn.close()

def resolve_master_uid(user_id, conn=None):
    """
    Finds the exact 'uid' string (might be a comma-separated list) 
    in the database that contains the given user_id.
    """
    if not user_id:
        return None
        
    local_conn = False
    if conn is None:
        conn = get_db_connection()
        local_conn = True
        
    user_id_str = str(user_id)
    
    # 1. Exact match
    row = conn.execute("SELECT uid FROM players WHERE uid = ?", (user_id_str,)).fetchone()
    if row:
        if local_conn: conn.close()
        return row['uid']
        
    # 3. Check social identity columns for uids list (consolidated accounts)
    for col in ['DISCORD', 'FACEBOOK', 'GOOGLE_PLAY']:
        query = f"SELECT uid FROM players WHERE {col} LIKE ?"
        search_cursor = conn.execute(query, (f'%"uids":%"{user_id_str}"%',))
        search_row = search_cursor.fetchone()
        if search_row:
            res = search_row['uid']
            if local_conn: conn.close()
            return res

    # 4. Check for id as fallback in social identity
    for col in ['DISCORD', 'FACEBOOK', 'GOOGLE_PLAY']:
        query = f"SELECT uid FROM players WHERE {col} LIKE ?"
        search_cursor = conn.execute(query, (f'%"id": "{user_id_str}"%',))
        search_row = search_cursor.fetchone()
        if search_row:
            res = search_row['uid']
            if local_conn: conn.close()
            return res

    if local_conn: conn.close()
    return None

ALL_TARGET_UNLOCK_IDS = set(range(4101, 4106)) | set(range(4201, 4217)) | {
    3113, 1000009345, 1000010729, 1000010970, 1000011021, 1000011117,
    1000011349, 1000011652, 1000011700, 1000011706, 1000012546,
    1000012942, 1000012966, 1000012972, 1000012978, 1000012984,
    1000021206, 1000021207, 1000021208, 1000021209, 1000021210,
    1000021211, 1000021212, 1000021213, 1000021214, 1000021215,
    1000021216, 1000021217, 1000021218, 1000021219, 1000021220, 1000021221
}

def extract_id(val):
    """Safely extracts integer ID from int, str, or dict."""
    if val is None or isinstance(val, bool):
        return None
    if isinstance(val, (int, float)):
        return int(val)
    if isinstance(val, str) and val.isdigit():
        return int(val)
    if isinstance(val, dict):
        for k in ("ID", "id", "defID", "Definition", "ReferencedDefinitionID"):
            nested = val.get(k)
            if nested is not None and not isinstance(nested, bool):
                if isinstance(nested, (int, float)):
                    return int(nested)
                if isinstance(nested, str) and nested.isdigit():
                    return int(nested)
    return None

def player_has_christmas_minion(uid):
    """
    Check if the player has received/unlocked the Christmas / Holiday minion (pack 8033/18033 or character 70009).
    Handles integers, strings, and full dictionary objects safely.
    """
    data = get_player_data(uid)
    if not data:
        return False
    
    target_ids = {8033, 18033, 70009}

    def matches_target(item):
        if item is None:
            return False
        # Direct check
        eid = extract_id(item)
        if eid in target_ids:
            return True
        if isinstance(item, dict):
            for k in ("ID", "id", "defID", "Definition", "ReferencedDefinitionID"):
                nested = item.get(k)
                if extract_id(nested) in target_ids:
                    return True
        return False
    
    # 1. Check purchased sales
    for s in data.get("purchasedSales", []):
        if matches_target(s):
            return True

    # 2. Check unlocks
    for u in data.get("unlocks", []):
        if matches_target(u):
            return True

    # 3. Check inventory
    for item in data.get("inventory", []):
        if matches_target(item):
            return True

    # 4. Check instances / items / villainQueue
    for key in ("instances", "items", "villainQueue"):
        for inst in data.get(key, []):
            if matches_target(inst):
                return True

    return False

def get_player_event_flags(uid):
    master_uid = resolve_master_uid(uid) or str(uid)
    conn = get_db_connection()
    row = conn.execute("SELECT christmas_event_active, limited_buildings_unlocked, holiday_offer_active FROM players WHERE uid = ?", (master_uid,)).fetchone()
    conn.close()
    if not row:
        return {"christmas_event_active": 0, "limited_buildings_unlocked": 0, "holiday_offer_active": 0}
    c_active = row["christmas_event_active"] if row["christmas_event_active"] is not None else 0
    h_active = row["holiday_offer_active"] if row["holiday_offer_active"] is not None else 0
    l_active = row["limited_buildings_unlocked"] if row["limited_buildings_unlocked"] is not None else 0
    return {
        "christmas_event_active": c_active,
        "limited_buildings_unlocked": l_active,
        "holiday_offer_active": h_active
    }

def set_player_event_flag(uid, flag_name, value):
    valid_flags = {"christmas_event_active", "limited_buildings_unlocked", "holiday_offer_active"}
    if flag_name not in valid_flags:
        return False
    master_uid = resolve_master_uid(uid) or str(uid)
    val_int = 1 if value else 0
    conn = get_db_connection()
    row = conn.execute("SELECT uid, unlocks FROM players WHERE uid = ?", (master_uid,)).fetchone()
    import time
    current_ts = int(time.time())
    
    if not row:
        conn.execute(f"INSERT INTO players (uid, {flag_name}, lastPlayedTime) VALUES (?, ?, ?)", (master_uid, val_int, current_ts))
    else:
        conn.execute(f"UPDATE players SET {flag_name} = ?, lastPlayedTime = ?, last_updated = CURRENT_TIMESTAMP WHERE uid = ?", (val_int, current_ts, master_uid))
        
        # When toggling limited_buildings_unlocked, immediately synchronize the unlocks column in DB
        if flag_name == "limited_buildings_unlocked":
            raw_unlocks = row["unlocks"]
            try:
                unlocks_list = json.loads(raw_unlocks) if raw_unlocks else []
            except Exception:
                unlocks_list = []
            if not isinstance(unlocks_list, list):
                unlocks_list = []

            if val_int == 1:
                existing_ids = set()
                for u in unlocks_list:
                    if isinstance(u, dict):
                        for k in ("defID", "ReferencedDefinitionID", "ID", "id"):
                            eid = extract_id(u.get(k))
                            if eid is not None:
                                existing_ids.add(eid)
                    else:
                        eid = extract_id(u)
                        if eid is not None:
                            existing_ids.add(eid)
                for u_id in ALL_TARGET_UNLOCK_IDS:
                    if u_id not in existing_ids:
                        unlocks_list.append({
                            "defID": u_id,
                            "quantity": 1,
                            "ReferencedDefinitionID": u_id,
                            "Quantity": 1,
                            "ID": u_id
                        })
            else:
                def is_target_unlock(u):
                    if isinstance(u, dict):
                        for k in ("defID", "ReferencedDefinitionID", "ID", "id"):
                            if extract_id(u.get(k)) in ALL_TARGET_UNLOCK_IDS:
                                return True
                        return False
                    return extract_id(u) in ALL_TARGET_UNLOCK_IDS
                unlocks_list = [u for u in unlocks_list if not is_target_unlock(u)]
            conn.execute("UPDATE players SET unlocks = ? WHERE uid = ?", (json.dumps(unlocks_list), master_uid))

    conn.commit()
    conn.close()
    return True


def get_tse_team_for_user(event_id, user_id):
    """Get a user's team for an event from DB. Returns (team_dict, reward_claimed) or (None, False)."""
    conn = get_db_connection()
    row = conn.execute('''
        SELECT t.team_id, t.event_id, t.order_progress, m.reward_claimed
        FROM tse_teams t
        JOIN tse_members m ON t.team_id = m.team_id
        WHERE t.event_id = ? AND m.user_id = ?
    ''', (event_id, str(user_id))).fetchone()
    
    if not row:
        conn.close()
        return None, False
    
    team_id = row['team_id']
    order_progress = json.loads(row['order_progress'] or '[]')
    reward_claimed = bool(row['reward_claimed'])
    
    # Get all members
    members = conn.execute('SELECT user_id FROM tse_members WHERE team_id = ?', (team_id,)).fetchall()
    conn.close()
    
    member_list = []
    for m in members:
        mid = m['user_id']
        member_list.append({
            "id": mid, "externalId": mid, "userId": mid,
            "type": 1,
            "secret": "mock", "sessionKey": "mock",
            "iconUrl": f"{Config.SECONDARY_URL}/api/{mid}/icon.png"
        })
    
    team = {
        "id": team_id,
        "socialEventId": event_id,
        "members": member_list,
        "orderProgress": order_progress
    }
    return team, reward_claimed

def create_tse_team_for_user(event_id, user_id):
    """Create a new team for a user. Returns (team_dict, False)."""
    conn = get_db_connection()
    cursor = conn.execute(
        'INSERT INTO tse_teams (event_id, order_progress) VALUES (?, ?)',
        (event_id, '[]')
    )
    team_id = cursor.lastrowid
    conn.execute(
        'INSERT INTO tse_members (team_id, user_id) VALUES (?, ?)',
        (team_id, str(user_id))
    )
    conn.commit()
    conn.close()
    
    team = {
        "id": team_id,
        "socialEventId": event_id,
        "members": [
            {"id": str(user_id), "externalId": str(user_id), "userId": str(user_id),
             "type": 1,
             "secret": "mock", "sessionKey": "mock",
             "iconUrl": f"{Config.SECONDARY_URL}/api/{user_id}/icon.png"}
        ],
        "orderProgress": []
    }
    return team, False

def save_tse_order_progress(team_id, order_progress):
    """Save order progress to DB."""
    conn = get_db_connection()
    conn.execute('UPDATE tse_teams SET order_progress = ? WHERE team_id = ?',
                 (json.dumps(order_progress), team_id))
    conn.commit()
    conn.close()

def claim_tse_reward(team_id, user_id):
    """Mark reward as claimed for a user on a team. Returns True if newly claimed, False if already claimed."""
    conn = get_db_connection()
    row = conn.execute('SELECT reward_claimed FROM tse_members WHERE team_id = ? AND user_id = ?',
                       (team_id, str(user_id))).fetchone()
    if not row:
        conn.close()
        return False
    if row['reward_claimed']:
        conn.close()
        return False  # Already claimed
    conn.execute('UPDATE tse_members SET reward_claimed = 1 WHERE team_id = ? AND user_id = ?',
                 (team_id, str(user_id)))
    conn.commit()
    conn.close()
    return True

def get_tse_team_by_id(team_id):
    """Get team info by ID."""
    conn = get_db_connection()
    row = conn.execute('SELECT * FROM tse_teams WHERE team_id = ?', (team_id,)).fetchone()
    if not row:
        conn.close()
        return None
    
    event_id = row['event_id']
    order_progress = json.loads(row['order_progress'] or '[]')
    
    members = conn.execute('SELECT user_id FROM tse_members WHERE team_id = ?', (team_id,)).fetchall()
    conn.close()
    
    member_list = []
    for m in members:
        mid = m['user_id']
        member_list.append({
            "id": mid, "externalId": mid, "userId": mid,
            "type": 1,
            "secret": "mock", "sessionKey": "mock",
            "iconUrl": f"{Config.SECONDARY_URL}/api/{mid}/icon.png"
        })
    
    return {
        "id": team_id,
        "socialEventId": event_id,
        "members": member_list,
        "orderProgress": order_progress
    }

def join_tse_team(team_id, user_id):
    """Add a user to a team."""
    conn = get_db_connection()
    # Check if team is full (max 4 members usually)
    count = conn.execute('SELECT COUNT(*) FROM tse_members WHERE team_id = ?', (team_id,)).fetchone()[0]
    if count >= 4:
        conn.close()
        return False, "TEAM_FULL"
    
    try:
        conn.execute('INSERT INTO tse_members (team_id, user_id) VALUES (?, ?)', (team_id, str(user_id)))
        # Also remove any invitations for this user to this team
        conn.execute('DELETE FROM tse_invitations WHERE team_id = ? AND invitee_uid = ?', (team_id, str(user_id)))
        conn.commit()
    except sqlite3.IntegrityError:
        pass # Already a member
    
    conn.close()
    return True, None

def leave_tse_team(team_id, user_id):
    """Remove a user from a team."""
    conn = get_db_connection()
    conn.execute('DELETE FROM tse_members WHERE team_id = ? AND user_id = ?', (team_id, str(user_id)))
    # If no members left, maybe delete team? (Optional, skipping for now)
    conn.commit()
    conn.close()
    return True

def create_tse_invitation(event_id, team_id, inviter_uid, invitee_uid):
    """Create an invitation."""
    conn = get_db_connection()
    conn.execute(
        'INSERT INTO tse_invitations (event_id, team_id, inviter_uid, invitee_uid) VALUES (?, ?, ?, ?)',
        (event_id, team_id, str(inviter_uid), str(invitee_uid))
    )
    conn.commit()
    conn.close()

def get_tse_invitations(user_id):
    """Get all invitations for a user."""
    conn = get_db_connection()
    rows = conn.execute('''
        SELECT i.event_id, i.team_id, i.inviter_uid
        FROM tse_invitations i
        WHERE i.invitee_uid = ?
    ''', (str(user_id),)).fetchall()
    
    invites = []
    for r in rows:
        team_id = r['team_id']
        # Get team view info
        team_row = conn.execute('SELECT order_progress FROM tse_teams WHERE team_id = ?', (team_id,)).fetchone()
        if not team_row: continue
        
        orders = json.loads(team_row['order_progress'] or '[]')
        member_count = conn.execute('SELECT COUNT(*) FROM tse_members WHERE team_id = ?', (team_id,)).fetchone()[0]
        
        invites.append({
            "eventId": r['event_id'],
            "team": {
                "id": team_id,
                "socialEventId": r['event_id'],
                "membersCount": member_count,
                "completedOrdersCount": len(orders)
            },
            "inviter": {
                "id": r['inviter_uid'], "externalId": r['inviter_uid'], "userId": r['inviter_uid'],
                "type": 0
            }
        })
    conn.close()
    return invites

def reject_tse_invitation(event_id, team_id, user_id):
    """Remove an invitation."""
    conn = get_db_connection()
    conn.execute('DELETE FROM tse_invitations WHERE event_id = ? AND team_id = ? AND invitee_uid = ?',
                 (event_id, team_id, str(user_id)))
    conn.commit()
    conn.close()
    return True

def get_level_from_xp(xp, xp_needed_list):
    level = 0
    for threshold in xp_needed_list:
        if xp >= threshold:
            level += 1
        else:
            break
    return level



def fix_consolidated_uids():
    """
    Migration: Converts comma-separated 'uid' values into a single primary UID
    and moves the other UIDs to the 'uids' list in the DISCORD/social identity JSON.
    This prevents 'DeserializingPlayerData returned false' errors in the game client.
    """
    conn = get_db_connection()
    rows = conn.execute("SELECT uid, DISCORD, FACEBOOK, GOOGLE_PLAY FROM players WHERE uid LIKE '%,%'").fetchall()
    
    for row in rows:
        old_uid_str = row['uid']
        uids = [u.strip() for u in old_uid_str.split(',')]
        primary_uid = uids[0]
        
        print(f"[MIGRATION] Fixing consolidated UID: {old_uid_str} -> {primary_uid}")
        
        # Update DISCORD info
        discord_info = row['DISCORD']
        if discord_info:
            try:
                d = json.loads(discord_info)
                existing_uids = set(d.get('uids', []))
                for u in uids: existing_uids.add(u)
                d['uids'] = sorted(list(existing_uids))
                discord_info = json.dumps(d)
            except: pass
            
        try:
            # Check if primary_uid already exists
            existing = conn.execute("SELECT uid FROM players WHERE uid = ?", (primary_uid,)).fetchone()
            if existing and existing['uid'] != old_uid_str:
                print(f"[MIGRATION] Primary UID {primary_uid} already exists. Deleting it to prioritize consolidated data.")
                conn.execute("DELETE FROM players WHERE uid = ?", (primary_uid,))
            
            conn.execute(
                "UPDATE players SET uid = ?, ID = ?, DISCORD = ? WHERE uid = ?",
                (primary_uid, primary_uid, discord_info, old_uid_str)
            )
        except Exception as e:
            print(f"[MIGRATION] ERROR fixing {old_uid_str}: {e}")
    
    conn.commit()
    conn.close()

def update_player_in_db(user_id, player_data):
    # Find the record that "owns" this user_id
    record_uid = resolve_master_uid(user_id) or str(user_id)
    
    # 1. Re-calculate Level and XP
    inventory = player_data.get('inventory', [])
    xp = 0
    if isinstance(inventory, list):
        for item in inventory:
            if item.get('Definition') == 2:
                xp = item.get('Quantity', 0)
                break
    
    level = 0
    try:
        if os.path.exists(DEFINITIONS_PATH):
            with open(DEFINITIONS_PATH, 'r') as f:
                defs = json.load(f)
                xp_needed_list = defs.get('levelXPTable', {}).get('xpNeededList', [])
                level = get_level_from_xp(xp, xp_needed_list)
    except:
        pass

    conn = get_db_connection()
    row_data = conn.execute('SELECT * FROM players WHERE uid = ?', (record_uid,)).fetchone()
    row = dict(row_data) if row_data else None

    # 2. High Playtime Guard: If existing record has more playtime, don't overwrite critical fields
    incoming_playtime = player_data.get('totalAccumulatedGameplayDuration', 0)
    existing_playtime = row['totalAccumulatedGameplayDuration'] if row and row.get('totalAccumulatedGameplayDuration') else 0
    existing_last_played = row['lastPlayedTime'] if row and row.get('lastPlayedTime') else 0
    incoming_last_played = player_data.get('lastPlayedTime', 0)
    final_last_played = max(incoming_last_played, existing_last_played)
    
    # 5s margin for safety (client might have slightly different drift)
    # If lastPlayedTime >= 2000000000, it's a manual dashboard upload override so don't block update
    is_manual_override = incoming_last_played >= 2000000000 or existing_last_played >= 2000000000
    is_stale_update = not is_manual_override and row and incoming_playtime < (existing_playtime - 5) 
    if is_stale_update:
        print(f"[DB] PROTECTING {record_uid}: Incoming playtime {incoming_playtime} is less than existing {existing_playtime}. Skipping progress update.")
        # We only update last_updated and lastPlayedTime to keep the session alive
        conn.execute("UPDATE players SET last_updated = CURRENT_TIMESTAMP, lastPlayedTime = ? WHERE uid = ?", 
                     (final_last_played, record_uid))
        conn.commit()
        conn.close()
        return

    # Ensure unlocks respects limited_buildings_unlocked flag in DB
    l_unlocked = row.get('limited_buildings_unlocked') if row else 0
    incoming_unlocks = player_data.get('unlocks', [])
    if isinstance(incoming_unlocks, str):
        try: incoming_unlocks = json.loads(incoming_unlocks)
        except: incoming_unlocks = []
    if not isinstance(incoming_unlocks, list):
        incoming_unlocks = []

    if l_unlocked:
        existing_ids = set()
        for u in incoming_unlocks:
            if isinstance(u, dict):
                for k in ("defID", "ReferencedDefinitionID", "ID", "id"):
                    eid = extract_id(u.get(k))
                    if eid is not None:
                        existing_ids.add(eid)
            else:
                eid = extract_id(u)
                if eid is not None:
                    existing_ids.add(eid)
        for u_id in ALL_TARGET_UNLOCK_IDS:
            if u_id not in existing_ids:
                incoming_unlocks.append({
                    "defID": u_id,
                    "quantity": 1,
                    "ReferencedDefinitionID": u_id,
                    "Quantity": 1,
                    "ID": u_id
                })
    else:
        def is_target_unlock(u):
            if isinstance(u, dict):
                for k in ("defID", "ReferencedDefinitionID", "ID", "id"):
                    if extract_id(u.get(k)) in ALL_TARGET_UNLOCK_IDS:
                        return True
                return False
            return extract_id(u) in ALL_TARGET_UNLOCK_IDS
        incoming_unlocks = [u for u in incoming_unlocks if not is_target_unlock(u)]

    # 3. Build fields
    fields = {
        'uid': record_uid,
        'ID': record_uid, # Store the list in Both ID and uid as requested
        'version': player_data.get('version', 0),
        'nextId': player_data.get('nextId', 0),
        'villainQueue': json.dumps(player_data.get('villainQueue', [])),
        'inventory': json.dumps(player_data.get('inventory', [])),
        'pendingTransactions': json.dumps(player_data.get('pendingTransactions', [])),
        'unlocks': json.dumps(incoming_unlocks),
        'purchasedSales': json.dumps(player_data.get('purchasedSales', [])),
        'triggers': json.dumps(player_data.get('triggers', [])),
        'lastLevelUpTime': player_data.get('lastLevelUpTime', 0),
        'lastGameStartTime': player_data.get('lastGameStartTime', 0),
        'firstGameStartTime': player_data.get('firstGameStartTime', 0),
        'lastPlayedTime': final_last_played,
        'totalGameplayDurationSinceLastLevelUp': player_data.get('totalGameplayDurationSinceLastLevelUp', 0),
        'totalAccumulatedGameplayDuration': player_data.get('totalAccumulatedGameplayDuration', 0),
        'targetExpansionID': player_data.get('targetExpansionID', 0),
        'timezoneOffset': player_data.get('timezoneOffset', 0),
        'country': player_data.get('country', ''),
        'completedOrders': player_data.get('completedOrders', 0),
        'highestFtueLevel': player_data.get('highestFtueLevel', 0),
        'socialRewards': json.dumps(player_data.get('socialRewards', [])),
        'mtxPurchaseTracking': json.dumps(player_data.get('mtxPurchaseTracking', [])),
        'completedQuestsTotal': player_data.get('completedQuestsTotal', 0),
        'currentItemCount': player_data.get('currentItemCount', 0),
        'PlatformStoreTransactionIDs': json.dumps(player_data.get('PlatformStoreTransactionIDs', [])),
        'helpTipsTrackingData': json.dumps(player_data.get('helpTipsTrackingData', [])),
        'PlayerLevel': level,
        'xp': xp,
        'Time_played': player_data.get('totalAccumulatedGameplayDuration', 0),
'DISCORD': player_data.get('discord_info', row.get('DISCORD', '') if row else ''),
        'FACEBOOK': player_data.get('facebook_id', row.get('FACEBOOK', '') if row else ''),
        'GOOGLE_PLAY': player_data.get('google_id', row.get('GOOGLE_PLAY', '') if row else '')
    }

    if row:
        # Prioritize discord_username if name is currently a default minion name or missing
        discord_name = fields.get('discord_username') or row.get('discord_username')
        current_name = row.get('name', '')
        
        if discord_name and (current_name in MINION_NAMES or not current_name):
            fields['name'] = discord_name
        else:
            fields['name'] = current_name
        
        placeholders = ", ".join([f"{k} = ?" for k in fields.keys()])

        query = f"UPDATE players SET {placeholders}, last_updated = CURRENT_TIMESTAMP WHERE uid = ?"
        params = list(fields.values()) + [record_uid]
        conn.execute(query, params)
    else:
        fields['name'] = random_minion_name()
        cols = ", ".join(fields.keys())
        placeholders = ", ".join(["?"] * len(fields))
        query = f"INSERT INTO players ({cols}) VALUES ({placeholders})"
        conn.execute(query, list(fields.values()))
    
    conn.commit()
    conn.close()

def get_player_data(user_id):
    record_uid = resolve_master_uid(user_id)
    if not record_uid:
        return None
        
    conn = get_db_connection()
    row = conn.execute('SELECT * FROM players WHERE uid = ?', (record_uid,)).fetchone()
    conn.close()
    
    if not row: return None
        
    data = {}
    for key in row.keys():
        val = row[key]
        if key in ['villainQueue', 'inventory', 'pendingTransactions', 'unlocks', 'purchasedSales', 
                  'triggers', 'socialRewards', 'mtxPurchaseTracking', 'PlatformStoreTransactionIDs', 'helpTipsTrackingData']:
            data[key] = json.loads(val or '[]')
        else:
            data[key] = val
            
    # CRITICAL: Return the specific ID the client expects
    data['ID'] = str(user_id)
    return data

def player_exists(user_id):
    return resolve_master_uid(user_id) is not None

def get_uid_by_discord_id(discord_id):
    conn = get_db_connection()
    # Check all social columns since they all might store Discord IDs in this mock server
    for col in ['DISCORD', 'FACEBOOK', 'GOOGLE_PLAY']:
        row = conn.execute(f"SELECT uid FROM players WHERE {col} LIKE ?", (f'%"id": "{discord_id}"%',)).fetchone()
        if row:
            uid = row['uid']
            conn.close()
            return uid
    conn.close()
    return None

def link_discord_to_player(uid, discord_profile):
    """
    Consolidates multiple accounts into ONE row where 'uid' and 'ID' columns 
    contain all linked game IDs as a comma-separated string.
    """
    discord_id = str(discord_profile.get('id'))
    conn = get_db_connection()
    
    # 1. Find all rows linked to this Discord ID
    cursor = conn.execute(
        "SELECT uid, totalAccumulatedGameplayDuration, DISCORD FROM players WHERE uid = ? OR DISCORD LIKE ?", 
        (str(uid), f'%"id": "{discord_id}"%')
    )
    rows = cursor.fetchall()
    
    all_uids = set([str(uid)])
    candidates = []
    
    for row_obj in rows:
        row = dict(row_obj)
        r_uid = str(row['uid'])
        # Split by comma in case it's already a list
        for part in r_uid.split(', '):
            all_uids.add(part.strip())
        try:
            d_data = json.loads(row['DISCORD'] or '{}')
            for part in d_data.get('uids', []):
                all_uids.add(str(part))
        except:
            pass
        candidates.append({
            'uid': r_uid,
            'playtime': row['totalAccumulatedGameplayDuration'] or 0
        })
    
    if not candidates:
        conn.close()
        return

    # 2. Pick the row with longest playtime to survive
    survivor = max(candidates, key=lambda x: x['playtime'])
    survivor_record_uid = survivor['uid']
    
    # 3. Create the consolidated UID list string
    consolidated_uid_str = ", ".join(sorted(list(all_uids)))
    
    # 4. Update the survivor row
    discord_profile['uids'] = list(all_uids)
    
    # Extract useful info for columns
    discord_username = discord_profile.get('username', '')
    discord_avatar = discord_profile.get('avatar', '')
    
    # max() already picked the survivor by playtime, we just update it with the new consolidated UID list.
    conn.execute(
        "UPDATE players SET uid = ?, ID = ?, name = ?, DISCORD = ?, discord_username = ?, discord_avatar = ?, last_updated = CURRENT_TIMESTAMP WHERE uid = ?", 
        (consolidated_uid_str, consolidated_uid_str, discord_username, json.dumps(discord_profile), discord_username, discord_avatar, survivor_record_uid)
    )

    
    # 5. Delete other redundant rows
    for cand in candidates:
        if cand['uid'] != survivor_record_uid:
            print(f"[DB] Consolidating row {cand['uid']} and DELETING it.")
            conn.execute("DELETE FROM players WHERE uid = ?", (cand['uid'],))
            
    conn.commit()
    conn.close()
    print(f"[DB] Linked Discord {discord_id}. Consolidated UIDs: {consolidated_uid_str} | Survivor: {survivor_record_uid}")

def check_and_generate_social_events():
    import datetime
    import time
    
    filepath = DEFINITIONS_PATH
    if not filepath or not os.path.exists(filepath):
        return
        
    try:
        with open(filepath, "r", encoding="utf-8") as f:
            data = json.load(f)
    except Exception as e:
        print(f"[TSE] Error loading definitions for checking: {e}")
        return

    events = data.get("timedSocialEventDefinitions", [])
    now = int(time.time())
    
    need_regen = False
    if not events:
        need_regen = True
    else:
        last_event = events[-1]
        last_finish = last_event.get("finishTime", 0)
        if last_finish < now + 4 * 7 * 24 * 3600:
            need_regen = True
            
    if need_regen:
        print("[TSE] Social events are expired or expiring soon. Regenerating weekly events...")
        today = datetime.datetime.now(datetime.timezone.utc)
        monday = today - datetime.timedelta(days=today.weekday())
        monday = monday.replace(hour=0, minute=0, second=0, microsecond=0)
        
        new_events = []
        order_templates = [
            {"orderId": 1, "transaction": 16008},
            {"orderId": 2, "transaction": 16071},
            {"orderId": 3, "transaction": 16009},
            {"orderId": 4, "transaction": 16056},
            {"orderId": 5, "transaction": 16037},
            {"orderId": 6, "transaction": 16061},
            {"orderId": 7, "transaction": 16074},
            {"orderId": 8, "transaction": 16039},
            {"orderId": 9, "transaction": 16020}
        ]
        
        base_id = 45000
        for week in range(52):
            event_start = monday + datetime.timedelta(weeks=week)
            event_end = event_start + datetime.timedelta(days=6)
            
            start_ts = int(event_start.timestamp())
            finish_ts = int(event_end.timestamp())
            
            ev = {
                "finishTime": finish_ts,
                "id": base_id + week,
                "localizedKey": "TempTimedSocialEvent",
                "maxTeamSize": 4,
                "orders": order_templates,
                "rewardTransaction": 22,
                "startTime": start_ts
            }
            new_events.append(ev)
            
        data["timedSocialEventDefinitions"] = new_events
        try:
            with open(filepath, "w", encoding="utf-8") as f:
                json.dump(data, f, indent=2, ensure_ascii=False)
            print(f"[TSE] Successfully regenerated {len(new_events)} weekly social events.")
        except Exception as e:
            print(f"[TSE] Error writing regenerated definitions: {e}")

def migrate_files_to_db():
    check_and_generate_social_events()
    if not os.path.exists(PLAYER_DATA_DIR): return
    for f in os.listdir(PLAYER_DATA_DIR):
        if f.endswith('.json') and f != 'leaderboard.json':
            user_id = f.replace('.json', '')
            try:
                with open(os.path.join(PLAYER_DATA_DIR, f), 'r') as jf:
                    update_player_in_db(user_id, json.load(jf))
                os.remove(os.path.join(PLAYER_DATA_DIR, f))
            except: pass

def random_minion_name():
    import random
    return random.choice(MINION_NAMES)

def add_chat_message(user_id, message):
    """Adds a message to the global chat."""
    conn = get_db_connection()
    conn.execute(
        'INSERT INTO global_chat (user_id, message) VALUES (?, ?)',
        (str(user_id), message)
    )
    conn.commit()
    conn.close()

def get_chat_messages(limit=50, since=None):
    """Returns the latest messages from the global chat."""
    conn = get_db_connection()
    if since:
        query = '''
            SELECT c.user_id, c.message, c.timestamp, p.name as username, p.discord_avatar
            FROM global_chat c
            LEFT JOIN players p ON c.user_id = p.uid
            WHERE c.timestamp > ?
            ORDER BY c.timestamp DESC
            LIMIT ?
        '''
        params = (since, limit)
    else:
        query = '''
            SELECT c.user_id, c.message, c.timestamp, p.name as username, p.discord_avatar
            FROM global_chat c
            LEFT JOIN players p ON c.user_id = p.uid
            ORDER BY c.timestamp DESC
            LIMIT ?
        '''
        params = (limit,)
    
    rows = conn.execute(query, params).fetchall()
    conn.close()
    
    messages = []
    for r in rows:
        messages.append({
            "userId": r['user_id'],
            "username": r['username'] or f"Minion {r['user_id'][-4:]}",
            "message": r['message'],
            "timestamp": r['timestamp'],
            "avatar": r['discord_avatar']
        })
    return messages

if __name__ == "__main__":
    init_db()
