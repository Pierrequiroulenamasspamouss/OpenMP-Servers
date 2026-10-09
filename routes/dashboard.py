from flask import Blueprint, jsonify, request, render_template, redirect
import json
import os
import sqlite3
from utils.db import get_db_connection, DB_PATH, PLAYER_DATA_DIR, DEFINITIONS_PATH, resolve_master_uid
from config import Config

dashboard_bp = Blueprint('dashboard', __name__)

EMPTY_PLAYER_JSON = getattr(Config, 'EMPTY_PLAYER_PATH', os.path.join(os.path.dirname(__file__), '..', 'data', 'empty_player.json'))
if not os.path.exists(EMPTY_PLAYER_JSON):
    EMPTY_PLAYER_JSON = os.path.join(os.path.dirname(__file__), '..', 'empty_player.json')

# Very simple unauthenticated token implementation for the session (real apps should use JWT or proper sessions)
# Since UID + password check is lightweight, we use a basic static "token" generation.
def gen_token(uid):
    return f"tok_{uid}"

def verify_session(data):
    uid = data.get('uid')
    if not uid:
        return False
    token = data.get('token')
    # Allow in-game client requests (which only send uid) or valid token authenticated dashboard requests
    if token is not None and token != gen_token(uid):
        return False
    return True

@dashboard_bp.route('/dashboard', methods=['GET'])
def render_dashboard():
    return render_template('dashboard.html')

@dashboard_bp.route('/api/dashboard/login', methods=['POST'])
def dashboard_login():
    data = request.json
    uid_input = data.get('uid')
    pwd = data.get('password', '')
    
    # Resolve the actual UID in the database (handles consolidated/Discord linked accounts)
    master_uid = resolve_master_uid(uid_input)
    
    if not master_uid:
        return jsonify({"error": "Player not found. Login to the game first to create the account."}), 404
    
    conn = get_db_connection()
    row = conn.execute("SELECT password, custom_name, discord_username FROM players WHERE uid = ?", (master_uid,)).fetchone()
    
    if not row:
        conn.close()
        return jsonify({"error": "Player not found. Login to the game first to create the account."}), 404
    
    db_pwd = row['password']
    
    if db_pwd and db_pwd != pwd:
        conn.close()
        return jsonify({"error": "Incorrect password."}), 401
        
    conn.close()
    
    name = row['custom_name'] or row['discord_username'] or "Player"
    secured = bool(db_pwd)
    
    return jsonify({
        "msg": "Login successful",
        "token": gen_token(master_uid), # Use the actual master_uid for the session
        "name": name,
        "secured": secured,
        "resolved_uid": master_uid # Inform the UI about the resolved UID if needed
    })

@dashboard_bp.route('/api/dashboard/set_password', methods=['POST'])
def set_password():
    data = request.json
    if not verify_session(data): return jsonify({"error": "Unauthorized"})
    
    uid = data.get('uid')
    pwd = data.get('password')
    
    conn = get_db_connection()
    # Check if a password already exists
    row = conn.execute("SELECT password FROM players WHERE uid = ?", (uid,)).fetchone()
    if row and row['password']:
        conn.close()
        return jsonify({"error": "Profile is already secured."})
        
    conn.execute("UPDATE players SET password = ? WHERE uid = ?", (pwd, uid))
    conn.commit()
    conn.close()
    return jsonify({"msg": "Password updated successfully!"})

@dashboard_bp.route('/api/dashboard/reset_save', methods=['POST'])
def reset_save():
    import time
    data = request.json
    if not verify_session(data): return jsonify({"error": "Unauthorized"})
    uid = data.get('uid')
    
    try:
        with open(EMPTY_PLAYER_JSON, 'r') as f:
            empty_data = json.load(f)
            inventory_str = json.dumps(empty_data.get('inventory', {}))
    except Exception as e:
        return jsonify({"error": f"Failed to read empty_player.json: {e}"})
        
    conn = get_db_connection()
    conn.execute('''
        UPDATE players 
        SET inventory = ?, DISCORD = '', discord_username = '', discord_avatar = '',
            FACEBOOK = '', GOOGLE_PLAY = '', custom_name = '', custom_avatar = '',
            totalAccumulatedGameplayDuration = 0, Time_played = 0,
            lastPlayedTime = 2000000000, last_updated = CURRENT_TIMESTAMP
        WHERE uid = ?
    ''', (inventory_str, uid))
    conn.commit()
    conn.close()
    
    return jsonify({"msg": "Save data has been successfully reset."})


@dashboard_bp.route('/api/dashboard/unlink_socials', methods=['POST'])
def unlink_socials():
    data = request.json
    if not verify_session(data): return jsonify({"error": "Unauthorized"})
    uid = data.get('uid')
    
    conn = get_db_connection()
    conn.execute("UPDATE players SET DISCORD = '', discord_username = '', discord_avatar = '', FACEBOOK = '', GOOGLE_PLAY = '' WHERE uid = ?", (uid,))
    conn.commit()
    conn.close()
    
    return jsonify({"msg": "Socials unlinked successfully."})

@dashboard_bp.route('/api/dashboard/update_profile', methods=['POST'])
def update_profile():
    data = request.json
    if not verify_session(data): return jsonify({"error": "Unauthorized"})
    uid = data.get('uid')
    
    c_name = data.get('custom_name')
    conn = get_db_connection()
    if c_name:
        conn.execute("UPDATE players SET name = ?, custom_name = ?, custom_avatar = ? WHERE uid = ?", 
                     (c_name, c_name, data.get('custom_avatar'), uid))
    else:
        conn.execute("UPDATE players SET custom_avatar = ? WHERE uid = ?", 
                     (data.get('custom_avatar'), uid))
    conn.commit()
    conn.close()
    return jsonify({"msg": "Profile updated successfully."})

@dashboard_bp.route('/api/dashboard/backup_save', methods=['GET'])
def backup_save():
    uid = request.args.get('uid')
    token = request.args.get('token')
    if token != gen_token(uid): return "Unauthorized", 401
    
    conn = get_db_connection()
    row = conn.execute("SELECT * FROM players WHERE uid = ?", (uid,)).fetchone()
    conn.close()
    
    if not row: return "Not Found", 404
    
    # Dump entire row as JSON
    d = dict(row)
    # Parse internally nested JSON for a cleaner export
    for k in ['inventory', 'purchasedSales', 'unlocks', 'DISCORD']:
        if d.get(k):
            try: d[k] = json.loads(d[k])
            except: pass
            
    from flask import Response
    return Response(json.dumps(d, indent=2), mimetype='application/json', headers={'Content-Disposition': f'attachment;filename=player_{uid}.json'})

@dashboard_bp.route('/api/dashboard/upload_save', methods=['POST'])
def upload_save():
    import time
    data = request.json
    if not verify_session(data): return jsonify({"error": "Unauthorized"})
    uid = data.get('uid')
    payload = data.get('payload', {})
    
    if not isinstance(payload, dict): return jsonify({"error": "Invalid payload"})
    
    # Map payload fields to DB columns
    json_fields = {
        'inventory': ['inventory'],
        'purchasedSales': ['purchasedSales', 'PurchasedSales', 'purchasedsales'],
        'unlocks': ['unlocks', 'Unlocks'],
        'triggers': ['triggers', 'Triggers'],
        'villainQueue': ['villainQueue', 'VillainQueue'],
        'pendingTransactions': ['pendingTransactions', 'PendingTransactions'],
        'socialRewards': ['socialRewards', 'SocialRewards'],
        'mtxPurchaseTracking': ['mtxPurchaseTracking', 'MtxPurchaseTracking'],
        'PlatformStoreTransactionIDs': ['PlatformStoreTransactionIDs'],
        'helpTipsTrackingData': ['helpTipsTrackingData']
    }
    
    primitive_fields = {
        'version': ['version'],
        'nextId': ['nextId'],
        'PlayerLevel': ['PlayerLevel', 'playerLevel', 'level'],
        'xp': ['xp', 'XP'],
        'totalAccumulatedGameplayDuration': ['totalAccumulatedGameplayDuration', 'total_gameplay_duration', 'Time_played'],
        'completedOrders': ['completedOrders'],
        'completedQuestsTotal': ['completedQuestsTotal'],
        'highestFtueLevel': ['highestFtueLevel'],
        'targetExpansionID': ['targetExpansionID']
    }
    
    fields_to_update = {}
    for db_col, keys in json_fields.items():
        for k in keys:
            if k in payload:
                val = payload[k]
                fields_to_update[db_col] = json.dumps(val) if not isinstance(val, str) else val
                break

    for db_col, keys in primitive_fields.items():
        for k in keys:
            if k in payload:
                fields_to_update[db_col] = payload[k]
                break

    if 'totalAccumulatedGameplayDuration' in fields_to_update:
        fields_to_update['Time_played'] = fields_to_update['totalAccumulatedGameplayDuration']

    # Always ensure lastPlayedTime is set to a future timestamp (2000000000) so server save overrides local device save
    fields_to_update['lastPlayedTime'] = 2000000000

    conn = get_db_connection()
    set_clauses = [f"{k} = ?" for k in fields_to_update.keys()]
    set_clauses.append("last_updated = CURRENT_TIMESTAMP")
    values = list(fields_to_update.values()) + [uid]
    
    query = f"UPDATE players SET {', '.join(set_clauses)} WHERE uid = ?"
    conn.execute(query, values)
    conn.commit()
    conn.close()
    
    return jsonify({"msg": "Save uploaded successfully! Timestamp updated to override local save."})


@dashboard_bp.route('/api/dashboard/migrate_save', methods=['POST'])
def migrate_save():
    data = request.json
    if not verify_session(data): return jsonify({"error": "Unauthorized"})
    
    uid = data.get('uid')
    target = data.get('target_uid')
    direction = data.get('direction')
    target_pwd = data.get('target_password', '')
    
    conn = get_db_connection()
    # Check target
    target_row = conn.execute("SELECT password, inventory FROM players WHERE uid = ?", (target,)).fetchone()
    if not target_row:
        conn.close()
        return jsonify({"error": "Target UID not found."})
        
    if target_row['password'] and target_row['password'] != target_pwd:
        conn.close()
        return jsonify({"error": "Incorrect password for target UID."})
        
    progress_cols = [
        'inventory', 'unlocks', 'purchasedSales', 'villainQueue', 'triggers',
        'totalAccumulatedGameplayDuration', 'Time_played', 'PlayerLevel', 'xp',
        'completedOrders', 'highestFtueLevel'
    ]
    cols_str = ", ".join(progress_cols)
    current_row = conn.execute(f"SELECT {cols_str} FROM players WHERE uid = ?", (uid,)).fetchone()
    target_row_full = conn.execute(f"SELECT {cols_str} FROM players WHERE uid = ?", (target,)).fetchone()
    
    set_clause = ", ".join([f"{col} = ?" for col in progress_cols]) + ", lastPlayedTime = 2000000000, last_updated = CURRENT_TIMESTAMP"
    if direction == 'to':
        # current -> target
        values = [current_row[col] for col in progress_cols] + [target]
        conn.execute(f"UPDATE players SET {set_clause} WHERE uid = ?", values)
    elif direction == 'from':
        # target -> current
        values = [target_row_full[col] for col in progress_cols] + [uid]
        conn.execute(f"UPDATE players SET {set_clause} WHERE uid = ?", values)
    else:
        conn.close()
        return jsonify({"error": "Invalid direction."})
        
    conn.commit()
    conn.close()
    return jsonify({"msg": f"Save migrated successfully {direction} {target}."})

def get_loc_text(key):
    # Quick simple search through EN.json to map LocKeys
    loc_path = os.path.join(os.path.dirname(__file__), '..', 'loc_text', 'EN.json')
    try:
        with open(loc_path, 'r', encoding='utf-8') as f:
            translations = json.load(f)
            return translations.get(key, key)
    except:
        return key

@dashboard_bp.route('/api/dashboard/inventory', methods=['GET'])
def inventory():
    uid = request.args.get('uid')
    token = request.args.get('token')
    if token != gen_token(uid): return jsonify({"error": "Unauthorized"})
    
    conn = get_db_connection()
    row = conn.execute("SELECT inventory FROM players WHERE uid = ?", (uid,)).fetchone()
    conn.close()
    
    if not row or not row['inventory']: return jsonify({"inventory": []})
    
    # Load definitions for nice names
    defs = {}
    try:
        with open(DEFINITIONS_PATH, 'r', encoding='utf-8') as f:
            d = json.load(f)
            for item in d.get('itemDefinitions', []):
                defs[item.get('id')] = item.get('localizedKey', f"Item {item.get('id')}")
            for item in d.get('currencyItemDefinitions', []):
                defs[item.get('id')] = item.get('localizedKey', f"Currency {item.get('id')}")
    except:
        pass

    inv_json = json.loads(row['inventory'])
    res = []
    
    if isinstance(inv_json, list):
        for item in inv_json:
            item_def = item.get('Definition')
            amount = item.get('Quantity')
            if item_def is not None and amount is not None:
                loc_key = defs.get(item_def, f"Item {item_def}")
                name = get_loc_text(loc_key)
                res.append({"id": item_def, "name": name, "amount": amount})
    elif isinstance(inv_json, dict):
        for item_id, amount in inv_json.items():
            if not str(item_id).isdigit():
                continue
            item_id = int(item_id)
            loc_key = defs.get(item_id, f"Item {item_id}")
            name = get_loc_text(loc_key)
            res.append({"id": item_id, "name": name, "amount": amount})
        
    return jsonify({"inventory": res})

@dashboard_bp.route('/api/dashboard/update_inventory_item', methods=['POST'])
def update_inventory_item():
    data = request.json
    if not verify_session(data): return jsonify({"error": "Unauthorized"})
    
    uid = data.get('uid')
    item_id = int(data.get('item_id'))
    amount = int(data.get('amount') or 0)
    action = data.get('action') # 'update' or 'delete'
    
    conn = get_db_connection()
    row = conn.execute("SELECT inventory FROM players WHERE uid = ?", (uid,)).fetchone()
    
    if not row:
        conn.close()
        return jsonify({"error": "Player not found."})
        
    inv_json = json.loads(row['inventory'])
    
    if isinstance(inv_json, list):
        found = False
        for i in range(len(inv_json)-1, -1, -1):
            if inv_json[i].get('Definition') == item_id:
                if action == 'delete':
                    del inv_json[i]
                else:
                    inv_json[i]['Quantity'] = amount
                found = True
        
        if not found and action != 'delete':
            # Need a fake ID, maybe max + 1
            max_id = max([x.get('ID', 0) for x in inv_json]) if len(inv_json) > 0 else 0
            inv_json.append({"ID": max_id + 1, "Definition": item_id, "Quantity": amount})
    elif isinstance(inv_json, dict):
        if action == 'delete':
            inv_json.pop(str(item_id), None)
        else:
            inv_json[str(item_id)] = amount
            
    conn.execute("UPDATE players SET inventory = ? WHERE uid = ?", (json.dumps(inv_json), uid))
    conn.commit()
    conn.close()
    
    return jsonify({"msg": "Inventory updated display refreshed!"})

# --- ADMIN DASHBOARD ---
from config import Config

def verify_admin_token(token):
    return token == f"tok_admin_{Config.ADMIN_PASSWORD}"

def require_admin():
    # Helper to check token from either headers, JSON body, or query params
    token = request.headers.get("Authorization")
    if not token and request.is_json:
        try:
            token = request.json.get("token")
        except:
            pass
    if not token:
        token = request.args.get("token")
    
    if token and token.startswith("Bearer "):
        token = token[7:]
        
    if not verify_admin_token(token):
        return False
    return True

@dashboard_bp.route('/admin', methods=['GET'])
def render_admin_dashboard():
    return render_template('admin.html')

@dashboard_bp.route('/api/admin/login', methods=['POST'])
def admin_login():
    data = request.json or {}
    password = data.get("password", "")
    if password == Config.ADMIN_PASSWORD:
        return jsonify({
            "status": "success",
            "token": f"tok_admin_{Config.ADMIN_PASSWORD}"
        })
    return jsonify({"error": "Invalid admin password."}), 401

@dashboard_bp.route('/api/admin/players', methods=['GET'])
def admin_players():
    if not require_admin():
        return jsonify({"error": "Unauthorized"}), 401
        
    conn = get_db_connection()
    rows = conn.execute('''
        SELECT uid, name, PlayerLevel, xp, Time_played, discord_username, discord_avatar, last_updated 
        FROM players
        ORDER BY last_updated DESC
    ''').fetchall()
    conn.close()
    
    players = []
    for r in rows:
        players.append({
            "uid": r["uid"],
            "name": r["name"] or "Player",
            "level": r["PlayerLevel"] or 0,
            "xp": r["xp"] or 0,
            "playtime": r["Time_played"] or 0,
            "discord_username": r["discord_username"] or "",
            "discord_avatar": r["discord_avatar"] or "",
            "last_updated": r["last_updated"]
        })
    return jsonify(players)

@dashboard_bp.route('/api/admin/shop_schedule', methods=['GET'])
def admin_get_shop_schedule():
    if not require_admin():
        return jsonify({"error": "Unauthorized"}), 401
        
    schedule = {"active_packs": {}, "default_min_level": 0, "default_max_purchases": 1, "global_end_utc": 2000000000}
    if os.path.exists(Config.SCHEDULE_PATH):
        try:
            with open(Config.SCHEDULE_PATH, 'r') as f:
                schedule = json.load(f)
        except Exception as e:
            print(f"[ADMIN] Error reading schedule: {e}")
            
    # Also fetch all available sale pack definitions from definitions.json to allow selecting them
    pack_options = []
    if os.path.exists(DEFINITIONS_PATH):
        try:
            with open(DEFINITIONS_PATH, 'r') as f:
                defs = json.load(f)
                # Parse all packs
                for pack in defs.get('salePackDefinitions', []):
                    pack_options.append({
                        "id": str(pack.get("id")),
                        "name": pack.get("localizedKey", f"Pack {pack.get('id')}")
                    })
                for pack in defs.get('storeItemDefinitions', []):
                    pack_options.append({
                        "id": str(pack.get("id")),
                        "name": pack.get("localizedKey", f"Store Item {pack.get('id')}")
                    })
        except Exception as e:
            print(f"[ADMIN] Error reading pack definitions: {e}")
            
    return jsonify({
        "schedule": schedule,
        "available_packs": pack_options
    })

@dashboard_bp.route('/api/admin/shop_schedule', methods=['POST'])
def admin_save_shop_schedule():
    if not require_admin():
        return jsonify({"error": "Unauthorized"}), 401
        
    data = request.json or {}
    schedule_data = data.get("schedule")
    if not schedule_data:
        return jsonify({"error": "Missing schedule data"}), 400
        
    try:
        os.makedirs(os.path.dirname(Config.SCHEDULE_PATH), exist_ok=True)
        with open(Config.SCHEDULE_PATH, 'w') as f:
            json.dump(schedule_data, f, indent=2)
        return jsonify({"msg": "Shop schedule saved successfully!"})
    except Exception as e:
        return jsonify({"error": f"Failed to save schedule: {e}"}), 500

@dashboard_bp.route('/api/admin/social_events', methods=['GET'])
def admin_get_social_events():
    if not require_admin():
        return jsonify({"error": "Unauthorized"}), 401
        
    events = []
    if os.path.exists(DEFINITIONS_PATH):
        try:
            with open(DEFINITIONS_PATH, 'r') as f:
                defs = json.load(f)
                events = defs.get('timedSocialEventDefinitions', [])
        except Exception as e:
            print(f"[ADMIN] Error reading social events: {e}")
            
    import time
    now = int(time.time())
    
    return jsonify({
        "events": events,
        "now": now
    })

@dashboard_bp.route('/api/admin/social_events/regenerate', methods=['POST'])
def admin_regenerate_social_events():
    if not require_admin():
        return jsonify({"error": "Unauthorized"}), 401
        
    try:
        # Force check_and_generate_social_events by mocking expired check or deleting existing
        # But wait! We can just modify definitions.json and write it
        from utils.db import check_and_generate_social_events
        # Let's call the function, but since it has a 4-week logic, let's force write by updating definitions.json to have empty events first, then running it!
        if os.path.exists(DEFINITIONS_PATH):
            with open(DEFINITIONS_PATH, 'r') as f:
                d = json.load(f)
            d["timedSocialEventDefinitions"] = []
            with open(DEFINITIONS_PATH, 'w') as f:
                json.dump(d, f, indent=2)
                
        check_and_generate_social_events()
        return jsonify({"msg": "Social events successfully regenerated!"})
    except Exception as e:
        return jsonify({"error": f"Failed to regenerate: {e}"}), 500

@dashboard_bp.route('/api/dashboard/player_events_status', methods=['GET'])
def player_events_status():
    uid = request.args.get('uid')
    token = request.args.get('token')
    if token != gen_token(uid): return jsonify({"error": "Unauthorized"}), 401
    from utils.db import get_player_event_flags, player_has_christmas_minion
    flags = get_player_event_flags(uid)
    has_minion = player_has_christmas_minion(uid)
    res = jsonify({
        "christmas_event_active": bool(flags.get("christmas_event_active")),
        "limited_buildings_unlocked": bool(flags.get("limited_buildings_unlocked")),
        "holiday_offer_active": bool(flags.get("holiday_offer_active")),
        "christmas_minion_owned": bool(has_minion)
    })
    res.headers['Cache-Control'] = 'no-cache, no-store, must-revalidate'
    return res

@dashboard_bp.route('/api/dashboard/trigger_christmas_minion', methods=['POST'])
def trigger_christmas_minion():
    data = request.json or {}
    if not verify_session(data): return jsonify({"error": "Unauthorized"}), 401
    uid = data.get('uid')
    from utils.db import player_has_christmas_minion, set_player_event_flag
    
    if player_has_christmas_minion(uid):
        return jsonify({
            "status": "already_owned",
            "christmas_minion_owned": True,
            "holiday_offer_active": False,
            "msg": "Christmas Minion is already in your inventory or on your island!"
        })
    
    set_player_event_flag(uid, "holiday_offer_active", 1)
    return jsonify({
        "status": "success",
        "christmas_minion_owned": False,
        "holiday_offer_active": True,
        "msg": "Christmas Minion Offer activated! Check the in-game store / popups to claim your minion."
    })

@dashboard_bp.route('/api/dashboard/set_christmas_event', methods=['POST'])
def set_christmas_event():
    data = request.json or {}
    if not verify_session(data): return jsonify({"error": "Unauthorized"}), 401
    uid = data.get('uid')
    enabled = 1 if data.get('enabled') or data.get('active') else 0
    from utils.db import set_player_event_flag
    set_player_event_flag(uid, "christmas_event_active", enabled)
    status_str = "enabled" if enabled else "disabled"
    return jsonify({
        "status": "success",
        "christmas_event_active": bool(enabled),
        "msg": f"Christmas Event is now {status_str} for user {uid}!"
    })

@dashboard_bp.route('/api/dashboard/set_limited_buildings', methods=['POST'])
def set_limited_buildings():
    data = request.json or {}
    if not verify_session(data): return jsonify({"error": "Unauthorized"}), 401
    uid = data.get('uid')
    enabled = 1 if data.get('enabled') or data.get('active') else 0
    from utils.db import set_player_event_flag
    set_player_event_flag(uid, "limited_buildings_unlocked", enabled)
    status_str = "unlocked" if enabled else "relocked"
    return jsonify({
        "status": "success",
        "limited_buildings_unlocked": bool(enabled),
        "msg": f"Special Event Buildings are now {status_str} for user {uid}!"
    })

@dashboard_bp.route('/api/dashboard/set_holiday_offer', methods=['POST'])
def set_holiday_offer():
    data = request.json or {}
    if not verify_session(data): return jsonify({"error": "Unauthorized"}), 401
    uid = data.get('uid')
    enabled = 1 if data.get('enabled') or data.get('active') else 0
    from utils.db import set_player_event_flag
    set_player_event_flag(uid, "holiday_offer_active", enabled)
    status_str = "active" if enabled else "hidden"
    return jsonify({
        "status": "success",
        "holiday_offer_active": bool(enabled),
        "msg": f"Holiday Offer is now {status_str} for user {uid}!"
    })

@dashboard_bp.route('/api/dashboard/toggle_christmas_event', methods=['POST'])
def toggle_christmas_event():
    data = request.json or {}
    if not verify_session(data): return jsonify({"error": "Unauthorized"}), 401
    uid = data.get('uid')
    from utils.db import get_player_event_flags, set_player_event_flag
    flags = get_player_event_flags(uid)
    new_val = 0 if flags.get("christmas_event_active") else 1
    set_player_event_flag(uid, "christmas_event_active", new_val)
    status_str = "enabled" if new_val else "disabled"
    return jsonify({
        "status": "success",
        "christmas_event_active": bool(new_val),
        "msg": f"Christmas Event is now {status_str} for user {uid}!"
    })

@dashboard_bp.route('/api/dashboard/toggle_limited_buildings', methods=['POST'])
def toggle_limited_buildings():
    data = request.json or {}
    if not verify_session(data): return jsonify({"error": "Unauthorized"}), 401
    uid = data.get('uid')
    from utils.db import get_player_event_flags, set_player_event_flag
    flags = get_player_event_flags(uid)
    new_val = 0 if flags.get("limited_buildings_unlocked") else 1
    set_player_event_flag(uid, "limited_buildings_unlocked", new_val)
    status_str = "unlocked" if new_val else "relocked"
    return jsonify({
        "status": "success",
        "limited_buildings_unlocked": bool(new_val),
        "msg": f"Special Event Buildings are now {status_str} for user {uid}!"
    })

@dashboard_bp.route('/api/dashboard/toggle_holiday_offer', methods=['POST'])
def toggle_holiday_offer():
    data = request.json or {}
    if not verify_session(data): return jsonify({"error": "Unauthorized"}), 401
    uid = data.get('uid')
    from utils.db import get_player_event_flags, set_player_event_flag
    flags = get_player_event_flags(uid)
    new_val = 0 if flags.get("holiday_offer_active") else 1
    set_player_event_flag(uid, "holiday_offer_active", new_val)
    status_str = "active" if new_val else "hidden"
    return jsonify({
        "status": "success",
        "holiday_offer_active": bool(new_val),
        "msg": f"Holiday Offer is now {status_str} for user {uid}!"
    })




