#!/usr/bin/env python3
"""
Tool to manage game definition versions (e.g., /rest/definitions/0.json, 1.json)
and link them to specific client version configurations.
"""

import os
import sys
import json
import shutil
import argparse
from pathlib import Path
from datetime import datetime

SERVER_DIR = Path(__file__).resolve().parent.parent
DATA_DIR = SERVER_DIR / "data"
DEFINITIONS_DIR = DATA_DIR / "definitions"
CONFIGS_DIR = DATA_DIR / "configs"
DEFAULT_DEF_PATH = DATA_DIR / "definitions.json"
TEMPLATE_CONFIG_PATH = DATA_DIR / "server_config_template.json"


def ensure_dirs():
    DEFINITIONS_DIR.mkdir(parents=True, exist_ok=True)
    CONFIGS_DIR.mkdir(parents=True, exist_ok=True)


def get_all_definitions():
    ensure_dirs()
    defs = {}
    
    # Check definitions dir
    for f in sorted(DEFINITIONS_DIR.glob("*.json")):
        def_id = f.stem
        defs[def_id] = f

    # Fallback/legacy definitions.json as '0' if 0.json does not exist
    if "0" not in defs and DEFAULT_DEF_PATH.exists():
        defs["0 (legacy)"] = DEFAULT_DEF_PATH

    return defs


def get_version_config_mappings():
    """Find which version configs point to which definition."""
    mappings = {}
    if not CONFIGS_DIR.exists():
        return mappings

    for cfg_file in sorted(CONFIGS_DIR.glob("*.json")):
        app_version = cfg_file.stem
        try:
            with open(cfg_file, "r", encoding="utf-8") as f:
                data = json.load(f)
            any_device = data.get("allConfigs", {}).get("anyDeviceType", {})
            def_id = str(any_device.get("definitionId", "0"))
            def_url = str(any_device.get("definitions", ""))
            allowed = any_device.get("isAllowed", True)
            mappings[app_version] = {
                "definitionId": def_id,
                "definitionsUrl": def_url,
                "isAllowed": allowed
            }
        except Exception:
            pass
    return mappings


def get_def_stats(file_path: Path):
    try:
        size_kb = file_path.stat().st_size / 1024
        mtime = datetime.fromtimestamp(file_path.stat().st_mtime).strftime("%Y-%m-%d %H:%M:%S")
        with open(file_path, "r", encoding="utf-8") as f:
            data = json.load(f)
        items = len(data.get("itemDefinitions", []))
        buildings = len(data.get("buildingDefinitions", []))
        quests = len(data.get("questDefinitions", []))
        return {
            "size_kb": f"{size_kb:.1f} KB",
            "mtime": mtime,
            "items": items,
            "buildings": buildings,
            "quests": quests,
            "valid": True
        }
    except Exception as e:
        return {"error": str(e), "valid": False}


def cmd_list(args=None):
    defs = get_all_definitions()
    mappings = get_version_config_mappings()

    print("\n" + "=" * 70)
    print("  GAME DEFINITIONS IN SERVER")
    print("=" * 70)
    if not defs:
        print("  No definition files found.")
    else:
        for def_id, path in defs.items():
            stats = get_def_stats(path)
            linked_versions = [v for v, info in mappings.items() if info.get("definitionId") == def_id]
            linked_str = f" [Linked to: {', '.join(linked_versions)}]" if linked_versions else " [Unlinked]"

            print(f"\n* ID: {def_id} -> {path.name}{linked_str}")
            print(f"  Path: {path}")
            if stats.get("valid"):
                print(f"  Size: {stats['size_kb']} | Modified: {stats['mtime']}")
                print(f"  Counts: {stats['items']} items, {stats['buildings']} buildings, {stats['quests']} quests")
            else:
                print(f"  Error: {stats.get('error')}")

    print("\n" + "-" * 70)
    print("  CLIENT VERSION CONFIGURATIONS")
    print("-" * 70)
    if not mappings:
        print("  No version configs found in data/configs/.")
    else:
        for app_ver, info in mappings.items():
            status = "ALLOWED" if info["isAllowed"] else "FORCED UPGRADE (not allowed)"
            print(f"* Version {app_ver}: defId={info['definitionId']} | status={status} | url={info['definitionsUrl']}")
    print("=" * 70 + "\n")


def cmd_create(args):
    ensure_dirs()
    new_id = str(args.version_id).strip()
    if new_id.endswith(".json"):
        new_id = new_id[:-5]

    target_path = DEFINITIONS_DIR / f"{new_id}.json"
    if target_path.exists() and not args.force:
        print(f"Error: Definition {target_path.name} already exists. Use --force to overwrite.")
        return 1

    source_id = args.source
    source_path = None

    if source_id:
        cand = DEFINITIONS_DIR / f"{source_id}.json"
        if cand.exists():
            source_path = cand
        elif source_id == "0" and DEFAULT_DEF_PATH.exists():
            source_path = DEFAULT_DEF_PATH
    else:
        # Default to 0.json or data/definitions.json
        if (DEFINITIONS_DIR / "0.json").exists():
            source_path = DEFINITIONS_DIR / "0.json"
        elif DEFAULT_DEF_PATH.exists():
            source_path = DEFAULT_DEF_PATH

    if not source_path or not source_path.exists():
        print(f"Error: Source definition could not be found.")
        return 1

    print(f"Cloning from {source_path} to {target_path}...")
    shutil.copyfile(source_path, target_path)

    # Validate JSON
    try:
        with open(target_path, "r", encoding="utf-8") as f:
            json.load(f)
    except Exception as e:
        print(f"Warning: Copied file is invalid JSON: {e}")
        return 1

    print(f"Successfully created definition: {target_path}")
    print(f"Served at URL: {{BASE_URL}}/rest/definitions/{new_id}.json")

    if args.link_version:
        cmd_link(argparse.Namespace(app_version=args.link_version, def_id=new_id, is_allowed=True))

    return 0


def normalize_version(version: str) -> str:
    if not version:
        return ""
    v = str(version).strip()
    if "." in v:
        parts = v.split(".")
        try:
            if len(parts) == 3:
                return str(int(parts[0]) * 10000 + int(parts[1]) * 100 + int(parts[2]))
        except ValueError:
            pass
    return v


def cmd_link(args):
    ensure_dirs()
    raw_version = str(args.app_version).strip()
    app_version = normalize_version(raw_version)
    def_id = str(args.def_id).strip()
    if def_id.endswith(".json"):
        def_id = def_id[:-5]

    cfg_path = CONFIGS_DIR / f"{app_version}.json"
    data = {}

    if cfg_path.exists():
        with open(cfg_path, "r", encoding="utf-8") as f:
            data = json.load(f)
    elif TEMPLATE_CONFIG_PATH.exists():
        with open(TEMPLATE_CONFIG_PATH, "r", encoding="utf-8") as f:
            data = json.load(f)
    else:
        data = {"allConfigs": {"anyDeviceType": {}}}

    any_dev = data.setdefault("allConfigs", {}).setdefault("anyDeviceType", {})
    any_dev["definitionId"] = def_id
    any_dev["definitions"] = f"{{BASE_URL}}/rest/definitions/{def_id}.json"
    if hasattr(args, "is_allowed") and args.is_allowed is not None:
        any_dev["isAllowed"] = bool(args.is_allowed)

    with open(cfg_path, "w", encoding="utf-8") as f:
        json.dump(data, f, indent=2)

    print(f"Updated {cfg_path.name}: definitionId='{def_id}', definitions='{{BASE_URL}}/rest/definitions/{def_id}.json'")
    return 0


def cmd_validate(args):
    def_id = str(args.def_id).strip()
    if def_id.endswith(".json"):
        p = DEFINITIONS_DIR / def_id
        if not p.exists():
            p = Path(def_id)
    else:
        p = DEFINITIONS_DIR / f"{def_id}.json"

    if not p.exists():
        print(f"Error: {p} not found.")
        return 1

    try:
        with open(p, "r", encoding="utf-8") as f:
            d = json.load(f)
        stats = get_def_stats(p)
        print(f"Valid JSON: {p.name}")
        print(f"Items: {stats.get('items')}, Buildings: {stats.get('buildings')}, Quests: {stats.get('quests')}")
        return 0
    except Exception as e:
        print(f"INVALID JSON in {p.name}: {e}")
        return 1


def interactive_menu():
    while True:
        print("\n=== Game Definitions Management ===")
        print("1. List definitions and linked configs")
        print("2. Create new definition version (e.g., 1.json)")
        print("3. Link a client version to a definition (e.g., 0.0.7 -> 1)")
        print("4. Validate a definition JSON")
        print("5. Exit")
        choice = input("\nEnter choice [1-5]: ").strip()

        if choice == "1":
            cmd_list()
        elif choice == "2":
            new_id = input("New definition ID (e.g. 1): ").strip()
            src_id = input("Clone from definition ID [default: 0]: ").strip() or "0"
            link_ver = input("Link to client version now? (e.g. 0.0.7 or leave empty): ").strip()
            args = argparse.Namespace(
                version_id=new_id,
                source=src_id,
                force=False,
                link_version=link_ver if link_ver else None
            )
            cmd_create(args)
        elif choice == "3":
            app_ver = input("Client version (e.g. 0.0.7): ").strip()
            def_id = input("Definition ID to use (e.g. 1): ").strip()
            allowed_in = input("Is this client version allowed? (y/n) [default: y]: ").strip().lower()
            allowed = False if allowed_in == "n" else True
            args = argparse.Namespace(app_version=app_ver, def_id=def_id, is_allowed=allowed)
            cmd_link(args)
        elif choice == "4":
            def_id = input("Definition ID to validate (e.g. 0 or 1): ").strip()
            cmd_validate(argparse.Namespace(def_id=def_id))
        elif choice == "5":
            break
        else:
            print("Invalid choice.")


def main():
    parser = argparse.ArgumentParser(description="Manage definitions and versioned game configs")
    subparsers = parser.add_subparsers(dest="command")

    # list
    subparsers.add_parser("list", help="List all definitions and linked versions")

    # create
    p_create = subparsers.add_parser("create", help="Create a new definition version")
    p_create.add_argument("version_id", help="New definition ID (e.g. 1)")
    p_create.add_argument("--source", "-s", default="0", help="Source definition ID to clone from (default: 0)")
    p_create.add_argument("--force", "-f", action="store_true", help="Overwrite if exists")
    p_create.add_argument("--link-version", "-l", help="Client version to automatically link (e.g. 0.0.7)")

    # link
    p_link = subparsers.add_parser("link", help="Link client version config to a definition")
    p_link.add_argument("app_version", help="Game client version (e.g. 0.0.7)")
    p_link.add_argument("def_id", help="Definition ID (e.g. 1)")
    p_link.add_argument("--disallow", action="store_false", dest="is_allowed", help="Set isAllowed: false (force upgrade)")

    # validate
    p_val = subparsers.add_parser("validate", help="Validate definition JSON")
    p_val.add_argument("def_id", help="Definition ID (e.g. 0 or 1)")

    if len(sys.argv) == 1:
        interactive_menu()
        return

    args = parser.parse_args()
    if args.command == "list":
        cmd_list(args)
    elif args.command == "create":
        cmd_create(args)
    elif args.command == "link":
        cmd_link(args)
    elif args.command == "validate":
        cmd_validate(args)
    else:
        parser.print_help()


if __name__ == "__main__":
    main()
