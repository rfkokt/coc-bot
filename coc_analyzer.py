"""COC Village Analyzer — rekomendasi upgrade & strategi dari JSON village export."""
import json

# Mapping mengikuti skema clash.ninja / pghant export (cocMapping.json)
BLDG = {
    1000001: "Town Hall", 1000008: "Cannon", 1000009: "Archer Tower",
    1000013: "Mortar", 1000012: "Air Defense", 1000011: "Wizard Tower",
    1000028: "Air Sweeper", 1000019: "Hidden Tesla", 1000032: "Bomb Tower",
    1000021: "X-Bow", 1000027: "Inferno Tower", 1000031: "Eagle Artillery",
    1000067: "Scattershot", 1000015: "Builder's Hut", 1000072: "Spell Tower",
    1000077: "Monolith", 1000089: "Firespitter", 1000010: "Wall",
    1000084: "Multi-Archer Tower", 1000085: "Ricochet Cannon",
    1000079: "Multi-Gear Tower", 1000097: "Crafted Defense",
    1000004: "Gold Mine", 1000002: "Elixir Collector", 1000005: "Gold Storage",
    1000003: "Elixir Storage", 1000023: "Dark Elixir Drill", 1000024: "Dark Elixir Storage",
    1000014: "Clan Castle", 1000000: "Army Camp", 1000006: "Barracks",
    1000026: "Dark Barracks", 1000007: "Laboratory", 1000020: "Spell Factory",
    1000071: "Hero Hall", 1000029: "Dark Spell Factory", 1000070: "Blacksmith",
    1000059: "Workshop", 1000068: "Pet House", 1000093: "Helper Hut",
}
BLDG2 = {
    1000033: "Wall (BB2)", 1000034: "Cannon (BB2)", 1000035: "Double Cannon",
    1000036: "Archer Tower (BB2)", 1000037: "Multi Mortar",
    1000038: "Air Bombs", 1000039: "Roaster", 1000040: "Builder Hall",
    1000041: "Lava Launcher", 1000042: "Firecrackers",
    1000043: "Mega Tesla", 1000044: "Battle Machine Altar",
    1000045: "Battle Copter Altar", 1000046: "Clan Capital Hall",
    1000047: "Guard Post", 1000048: "Giant Cannon",
    1000050: "Clock Tower", 1000051: "Builder Barracks (BB2)",
    1000052: "Army Camp (BB2)", 1000053: "Star Laboratory",
    1000054: "Elixir Storage (BB2)", 1000055: "Gold Storage (BB2)",
    1000056: "Elixir Collector (BB2)", 1000057: "Gold Mine (BB2)",
    1000058: "Gem Mine", 1000078: "Reinforcement Camp",
}
TROOP = {
    4000000: "Barbarian", 4000001: "Archer", 4000002: "Goblin",
    4000003: "Giant", 4000004: "Wall Breaker", 4000005: "Balloon",
    4000006: "Wizard", 4000007: "Healer", 4000008: "Dragon",
    4000009: "P.E.K.K.A", 4000010: "Minion", 4000011: "Hog Rider",
    4000012: "Valkyrie", 4000013: "Golem", 4000015: "Witch",
    4000017: "Lava Hound", 4000022: "Baby Dragon", 4000023: "Miner",
    4000024: "Electro Dragon", 4000053: "Yeti", 4000058: "Ice Golem",
    4000059: "Electro Titan", 4000065: "Dragon Rider",
    4000082: "Headhunter", 4000095: "Root Rider", 4000097: "Apprentice Warden",
    4000110: "Root Rider", 4000123: "Druid", 4000132: "Thrower", 4000150: "Furnace",
    4000095: "Electro Titan", 4000177: "Meteor Golem",  # TH18 (dataId verified)
    4000051: "Wall Wrecker", 4000052: "Battle Blimp", 4000062: "Stone Slammer",
    4000075: "Siege Barracks", 4000087: "Log Launcher", 4000091: "Flame Flinger",
    4000092: "Battle Drill", 4000135: "Troop Launcher",
}
HERO = {
    28000000: "Barbarian King", 28000001: "Archer Queen",
    28000002: "Grand Warden", 28000004: "Royal Champion",
    28000006: "Minion Prince",
    28000007: "Dragon Duke",  # TH18 (dataId verified), unlocked Hero Hall 9
}
SPELL = {
    26000000: "Lightning", 26000001: "Heal", 26000002: "Rage",
    26000003: "Jump", 26000005: "Freeze", 26000009: "Poison",
    26000010: "Earthquake", 26000011: "Haste", 26000016: "Clone",
    26000017: "Skeleton", 26000028: "Bat", 26000035: "Invisibility",
    26000053: "Recall", 26000070: "Overgrowth", 26000098: "Revive",
    26000109: "Ice Block", 26000098: "Revive",
    26000120: "Totem",  # TH16+ (dataId verified)
}
PET = {
    73000000: "L.A.S.S.I", 73000001: "Electro Owl", 73000002: "Mighty Yak",
    73000003: "Unicorn", 73000004: "Phoenix", 73000007: "Poison Lizard",
    73000008: "Diggy", 73000009: "Frosty", 73000010: "Spirit Fox",
    73000011: "Angry Jelly", 73000016: "Sneezy",
    73000017: "Greedy Raven",  # TH18 (dataId verified)
}
PET_MAX = {
    73000000: 15, 73000001: 15, 73000002: 15,
    73000003: 10, 73000004: 10, 73000007: 10,
    73000008: 10, 73000009: 10, 73000010: 10,
    73000011: 10, 73000016: 10, 73000017: 10,
}
TRAP = {
    12000000: "Bomb", 12000001: "Spring Trap", 12000002: "Giant Bomb",
    12000005: "Air Bomb", 12000006: "Seeking Air Mine",
    12000008: "Skeleton Trap", 12000016: "Tornado Trap", 12000020: "Giga Bomb",
}
EQUIP_NAME = {
    90000000: "Barbarian Puppet", 90000001: "Archer Puppet",
    90000002: "Giant Gauntlet", 90000003: "Earthquake Boots",
    90000004: "Vampstache", 90000005: "Rage Vial",
    90000006: "Royal Gem", 90000007: "Seeking Shield",
    90000008: "Hog Rider Puppet", 90000009: "Haste Vial",
    90000010: "Healer Puppet", 90000011: "Invisibility Vial",
    90000012: "Giant Arrow", 90000013: "Frozen Arrow",
    90000014: "Fireball", 90000015: "Rage Gem",
    90000016: "Eternal Tome", 90000017: "Life Gem",
    90000019: "Dark Orb", 90000020: "Metal Pants",
    90000022: "Noble Iron", 90000024: "Dark Crown",
    90000032: "Magic Mirror", 90000034: "Rocket Spear",
    90000035: "Electro Boots", 90000039: "Snake Bracelet",
    90000040: "Spiky Ball", 90000041: "Lavaloon Puppet",
    90000042: "Action Figure", 90000043: "Heroic Torch",
    90000047: "Lunar Launcher", 90000048: "Gem Warden",
    90000052: "Spiky Ball (Epic)", 90000057: "Action Figure (Epic)",
}

EPIC_EQUIPMENT = {90000002, 90000013, 90000014, 90000032, 90000034, 90000040, 90000041, 90000043, 90000052, 90000057}

# Hero max per TH
HERO_MAX = {
    12: {28000000: 65, 28000001: 65, 28000002: 40, 28000006: 40},
    13: {28000000: 75, 28000001: 75, 28000002: 50, 28000004: 25, 28000006: 50},
    14: {28000000: 85, 28000001: 85, 28000002: 60, 28000004: 30, 28000006: 60},
    15: {28000000: 90, 28000001: 90, 28000002: 65, 28000004: 40, 28000006: 70, 28000007: 10},
    16: {28000000: 95, 28000001: 95, 28000002: 70, 28000004: 45, 28000006: 80, 28000007: 15},
    17: {28000000: 100, 28000001: 100, 28000002: 75, 28000004: 50, 28000006: 90, 28000007: 20},
    18: {28000000: 110, 28000001: 110, 28000002: 85, 28000004: 55, 28000006: 95, 28000007: 25},
}

# Key building max per TH (army buildings only)
# IDs: Lab=1000007 ArmyCamp=1000000 Barracks=1000006 DarkBarracks=1000026
#      SpellFactory=1000020 DarkSpellFactory=1000029 ClanCastle=1000014
#      PetHouse=1000068 Workshop=1000059
BLDG_MAX = {
    12: {1000007: 10, 1000000: 9, 1000006: 14, 1000026: 9, 1000020: 7, 1000029: 5, 1000014: 8, 1000068: 8, 1000059: 6},
    13: {1000007: 10, 1000000: 10, 1000006: 15, 1000026: 10, 1000020: 7, 1000029: 5, 1000014: 9, 1000068: 8, 1000059: 7},
    14: {1000007: 10, 1000000: 11, 1000006: 16, 1000026: 10, 1000020: 7, 1000029: 5, 1000014: 10, 1000068: 9, 1000059: 7},
    15: {1000007: 10, 1000000: 12, 1000006: 17, 1000026: 10, 1000020: 7, 1000029: 5, 1000014: 11, 1000068: 10, 1000059: 8},
    16: {1000007: 14, 1000000: 12, 1000006: 18, 1000026: 13, 1000020: 9, 1000029: 8, 1000014: 12, 1000068: 10, 1000059: 8},
    17: {1000007: 15, 1000000: 13, 1000006: 19, 1000026: 13, 1000020: 9, 1000029: 8, 1000014: 13, 1000068: 11, 1000059: 9},
    18: {1000007: 16, 1000000: 14, 1000006: 19, 1000026: 13, 1000020: 9, 1000029: 8, 1000014: 14, 1000068: 12, 1000059: 9},
}

# Equipment max (epic = 27, common = 18)
EQUIP_MAX = {}
for eid in EQUIP_NAME:
    EQUIP_MAX[eid] = 27 if eid in (90000002,90000013,90000014,90000022,90000024,90000032,90000034,90000040,90000042,90000043,90000052,90000057) else 18

# Max ~ TH18-era (Feb/Mar 2026), dipakai untuk hitung gap upgrade (heuristik, kalibrasi bila perlu)
# nilai max hardcoded, update saat balance patch besar. Sumber: clash.ninja max-levels table.
TROOP_MAX = {4000000: 13, 4000001: 14, 4000002: 10, 4000003: 14, 4000004: 14, 4000005: 13, 4000006: 14, 4000007: 11, 4000008: 13, 4000009: 13, 4000010: 14, 4000011: 15, 4000012: 12, 4000013: 15, 4000015: 8, 4000017: 8, 4000022: 12, 4000023: 12, 4000024: 9, 4000053: 8, 4000058: 9, 4000059: 5, 4000065: 6, 4000082: 4, 4000095: 4, 4000097: 4, 4000110: 6, 4000123: 4, 4000132: 4, 4000150: 4, 4000177: 3,
             4000051: 6, 4000052: 6, 4000062: 6, 4000075: 6, 4000087: 6, 4000091: 5, 4000092: 6, 4000135: 4}
SPELL_MAX = {26000000: 13, 26000001: 12, 26000002: 7, 26000003: 5, 26000005: 8, 26000009: 12, 26000010: 8, 26000011: 7, 26000016: 9, 26000017: 8, 26000028: 8, 26000035: 4, 26000053: 7, 26000070: 5, 26000098: 2, 26000109: 6, 26000120: 4}
TRAP_MAX = {12000000: 14, 12000001: 13, 12000002: 12, 12000005: 13, 12000006: 8, 12000008: 5, 12000016: 3, 12000020: 4}

# Attack strategies per TH
STRATEGIES = {
    12: [
        ("Hybrid (Hog+Miner)", "Queen Walk → Hog+Miner core. Heal+Rage sustain. Paling konsisten.", ["Hog Rider", "Miner", "Heal", "Rage"]),
        ("DragBat", "Electro Dragon funnel → Bat Spell sweep. Freeze protect bat.", ["Electro Dragon", "Bat Spell", "Freeze"]),
        ("Witch Slap", "Golem tank + Witch spam. Simpel, efektif.", ["Witch", "Golem", "Rage", "Heal"]),
    ],
    13: [
        ("LavaLoon", "Lava Hound tank → Balloon surg. High skill ceiling.", ["Lava Hound", "Balloon", "Haste"]),
        ("Yeti Smash", "Yeti + P.E.K.K.A core smash. Rage+Heal.", ["Yeti", "P.E.K.K.A", "Rage"]),
        ("Hybrid", "Updated Hybrid TH13. Masih meta kuat.", ["Miner", "Hog Rider", "Heal"]),
    ],
    14: [
        ("Super Arch Blimp", "Blimp Super Archer → core destroy. Edrag cleanup.", ["Electro Dragon", "Invisibility"]),
        ("Hybrid", "Hybrid + poison pet. Konsisten.", ["Miner", "Hog Rider", "Heal"]),
    ],
    15: [
        ("Root Rider Smash", "Root Rider + Yeti. Overpower core.", ["Root Rider", "Yeti", "Rage"]),
        ("Super Hog", "Hybrid v2. Heal sustain + warden.", ["Hog Rider", "Miner", "Heal"]),
        ("Fireball Warden", "Fireball equip + core smash.", ["Root Rider", "Rage"]),
    ],
    16: [
        ("Electro Titan", "Electro Titan AoE + Root Rider. Meta.", ["Electro Titan", "Root Rider", "Rage"]),
        ("Super Bowler", "Bowler bounce + Root Rider pathing.", ["Bowler", "Root Rider", "Jump"]),
    ],
    17: [
        ("Root Rider Meta", "Root Rider + Electro Titan. Dominant.", ["Root Rider", "Electro Titan", "Rage"]),
        ("Hybrid Endgame", "Masih viable TH17.", ["Miner", "Hog Rider", "Heal"]),
    ],
    18: [
        ("Dragon Duke Air", "Dragon Duke spearhead (Fire Heart) + Lavaloon/Edrag. Meta baru TH18.", ["Dragon", "Balloon", "Haste"]),
        ("Root Rider Smash", "Root Rider + Meteor Golem tank. Overpower core.", ["Root Rider", "Rage", "Freeze"]),
        ("Hybrid Endgame", "Masih viable TH18.", ["Miner", "Hog Rider", "Heal"]),
    ],
}


def _detect_th(village):
    """Infer real TH level dari hero levels & building presence.
    Hero levels lebih reliable daripada TH field (sering stale).
    Prioritas: RC > GW > building hints > MP/BK/AQ (bisa di-boost)."""
    th_raw = next((b["lvl"] for b in village.get("buildings", []) if b["data"] == 1000001), 0)
    bldg_ids = {b["data"] for b in village.get("buildings", [])}
    hero_ids = {h["data"] for h in village.get("heroes", [])}
    hero_lvls = {h["data"]: h["lvl"] for h in village.get("heroes", [])}

    # Primary: TH field (kalau benar)
    th = th_raw

    # Primary: Royal Champion (paling reliable, TH13+)
    # Max levels: TH13=25, TH14=30, TH15=40, TH16=45, TH17=50, TH18=55
    if 28000004 in hero_ids: th = max(th, 13)
    rc = hero_lvls.get(28000004, 0)
    if rc > 25: th = max(th, 14)
    if rc > 30: th = max(th, 15)
    if rc > 40: th = max(th, 16)
    if rc > 45: th = max(th, 17)
    if rc > 50: th = max(th, 18)

    # Primary: Grand Warden (TH11+)
    # Max levels: TH11=20, TH12=40, TH13=50, TH14=60, TH15=65, TH16=70, TH17=75, TH18=85
    gw = hero_lvls.get(28000002, 0)
    if gw > 0:   th = max(th, 11)
    if gw > 20:  th = max(th, 12)
    if gw > 40:  th = max(th, 13)
    if gw > 50:  th = max(th, 14)
    if gw > 60:  th = max(th, 15)
    if gw > 65:  th = max(th, 16)
    if gw > 70:  th = max(th, 17)
    if gw > 75:  th = max(th, 18)

    # Dragon Duke exists only TH15+ (Hero Hall 9); its presence rules out low TH
    if 28000007 in hero_ids: th = max(th, 15)

    # Secondary: building presence (only bump if heroes give no signal)
    # Skip building detection — building IDs unreliable across export versions

    return th

def analyze(village):
    """Analyze village JSON → recommendations dict."""
    th = _detect_th(village)
    heroes = {h["data"]: h["lvl"] for h in village.get("heroes", [])}
    troops = {t["data"]: t["lvl"] for t in village.get("units", [])}
    spells = {s["data"]: s["lvl"] for s in village.get("spells", [])}
    equips = {e["data"]: e["lvl"] for e in village.get("equipment", [])}
    pets = {p["data"]: p["lvl"] for p in village.get("pets", [])}

    # Aggregate buildings
    bldgs = {}
    for b in village.get("buildings", []):
        did = b["data"]
        if did not in bldgs:
            bldgs[did] = {"total": 0, "levels": {}}
        lvl, cnt = b["lvl"], b.get("cnt", 1)
        bldgs[did]["total"] += cnt
        bldgs[did]["levels"][lvl] = bldgs[did]["levels"].get(lvl, 0) + cnt

    recs = []

    # Heroes
    hero_max = HERO_MAX.get(th, {})
    for hid, hname in HERO.items():
        cur = heroes.get(hid, 0)
        mx = hero_max.get(hid, 0)
        if mx and cur < mx:
            gap = mx - cur
            recs.append({"prio": 50 + gap, "cat": "hero", "name": hname, "id": hid,
                         "cur": cur, "max": mx, "gap": gap,
                         "note": f"⚠️ {gap} level dari max!" if gap > 10 else f"{gap} level lagi"})

    # Process all buildings dynamically
    for bid, info in bldgs.items():
        name = BLDG.get(bid, BLDG2.get(bid, f"Building {bid}"))
        if "(BB2)" in name or "Builder Hall" in name: continue # Skip builder base

        cat = "defense"
        if name == "Town Hall": cat = "townhall"
        elif "Mine" in name or "Collector" in name or "Drill" in name or "Storage" in name: cat = "resource"
        elif "Barracks" in name or "Camp" in name or "Factory" in name or "Laboratory" in name or "Clan Castle" in name: cat = "army_bldg"
        elif "Wall" in name: cat = "wall"

        # Find max level. If not in BLDG_MAX, guess from the highest level the player has
        mx = BLDG_MAX.get(th, {}).get(bid, max(info["levels"].keys()))
        
        low = {l: c for l, c in info["levels"].items() if l < mx}
        highest = max(info["levels"].keys())
        total = info["total"]
        
        if not low:
            recs.append({"prio": 0, "cat": cat, "name": name, "id": bid, "cur": highest, "max": highest, "gap": 0, "levels": info["levels"], "note": f"{total}x maxed" if total > 1 else ""})
        else:
            total_low = sum(low.values())
            lowest = min(low.keys())
            recs.append({"prio": 30, "cat": cat, "name": name, "id": bid,
                         "cur": lowest, "max": mx, "gap": mx - lowest, "levels": info["levels"],
                         "note": f"{total_low}x belum max (terendah lvl {lowest})" if total_low > 1 else ""})

    # Equipment recommendations
    equip_recs = []
    for eid, ename in EQUIP_NAME.items():
        cur = equips.get(eid, 0)
        if cur > 0:
            mx = 27 if eid in EPIC_EQUIPMENT else 18
            if cur < mx:
                equip_recs.append({"prio": 40 + (mx-cur), "cat": "equipment", "name": ename, "id": eid, "cur": cur, "max": mx, "gap": mx - cur})
    recs.extend(equip_recs)

    # Pets
    pet_recs = []
    for pid, pname in PET.items():
        cur = pets.get(pid, 0)
        if cur > 0:
            mx = PET_MAX.get(pid, cur)
            if cur < mx:
                pet_recs.append({"prio": 20 + (mx-cur), "cat": "pet", "name": pname, "id": pid, "cur": cur, "max": mx, "gap": mx - cur})
    recs.extend(pet_recs)

    # Troops & Spells & Traps
    for t in village.get("units", []):
        tid, cur = t["data"], t["lvl"]
        name = TROOP.get(tid, f"Troop {tid}")
        cat = "dark_troop" if tid in (4000010, 4000011, 4000012, 4000013, 4000015, 4000017, 4000058, 4000082, 4000097) else "troop"
        if "Siege" in name or tid in (4000051, 4000052, 4000062, 4000075, 4000087, 4000091, 4000092, 4000135): cat = "siege"
        mx = TROOP_MAX.get(tid, cur)
        if cur < mx:
            recs.append({"prio": 10 + (mx-cur), "cat": cat, "name": name, "id": tid, "cur": cur, "max": mx, "gap": mx - cur})
            
    for s in village.get("spells", []):
        sid, cur = s["data"], s["lvl"]
        name = SPELL.get(sid, f"Spell {sid}")
        mx = SPELL_MAX.get(sid, cur)
        if cur < mx:
            recs.append({"prio": 15 + (mx-cur), "cat": "spell", "name": name, "id": sid, "cur": cur, "max": mx, "gap": mx - cur})
        
    for sm in village.get("siege_machines", []):
        sid, cur = sm["data"], sm["lvl"]
        name = TROOP.get(sid, f"Siege {sid}")
        mx = TROOP_MAX.get(sid, cur)
        if cur < mx:
            recs.append({"prio": 10 + (mx-cur), "cat": "siege", "name": name, "id": sid, "cur": cur, "max": mx, "gap": mx - cur})

    traps = {}
    for t in village.get("traps", []):
        did = t["data"]
        if did not in traps: traps[did] = {"levels": {}}
        lvl, cnt = t["lvl"], t.get("cnt", 1)
        traps[did]["levels"][lvl] = traps[did]["levels"].get(lvl, 0) + cnt

    for tid, mx in TRAP_MAX.items():
        info = traps.get(tid)
        if not info: continue
        low = {l: c for l, c in info["levels"].items() if l < mx}
        if not low:
            highest = max(info["levels"].keys())
            recs.append({"prio": 0, "cat": "trap", "name": TRAP.get(tid, f"Trap {tid}"), "id": tid, "cur": highest, "max": highest, "gap": 0, "levels": info["levels"]})
        else:
            lowest = min(low.keys())
            total = sum(low.values())
            recs.append({"prio": 5, "cat": "trap", "name": TRAP.get(tid, f"Trap {tid}"), "id": tid, "cur": lowest, "max": mx, "gap": mx - lowest, "levels": info["levels"], "note": f"{total}x belum max"})

    # Upgrading items
    upgrading = []
    for b in village.get("buildings", []) + village.get("buildings2", []):
        if "timer" in b: upgrading.append({"name": BLDG.get(b["data"], BLDG2.get(b["data"], f"Bldg {b['data']}")), "lvl": b["lvl"], "timer": b["timer"]})
    for t in village.get("units", []) + village.get("units2", []) + village.get("siege_machines", []):
        if "timer" in t: upgrading.append({"name": TROOP.get(t["data"], f"Unit {t['data']}"), "lvl": t["lvl"], "timer": t["timer"]})
    for h in village.get("heroes", []) + village.get("heroes2", []):
        if "timer" in h: upgrading.append({"name": HERO.get(h["data"], f"Hero {h['data']}"), "lvl": h["lvl"], "timer": h["timer"]})

    # Strategy
    strats = []
    for name, desc, key_units in STRATEGIES.get(th, []):
        ready = True
        missing = []
        for uname in key_units:
            # Find troop/spell by name
            found = False
            for tid, tname in TROOP.items():
                if tname == uname and troops.get(tid, 0) > 0:
                    found = True
                    break
            for sid, sname in SPELL.items():
                if sname == uname and spells.get(sid, 0) > 0:
                    found = True
                    break
            if not found:
                ready = False
                missing.append(uname)
        status = "✅ Siap" if ready else f"⚠️ Perlu: {', '.join(missing)}"
        strats.append({"name": name, "desc": desc, "status": status, "ready": ready})

    # Sort recs by priority
    recs.sort(key=lambda x: -x["prio"])

    return {
        "th_level": th,
        "recs": recs,
        "upgrading": upgrading,
        "equip_recs": equip_recs[:15],  # top 15
        "pet_recs": pet_recs,
        "strategies": strats,
        "summary": {
            "heroes_gap": sum(max(0, hero_max.get(h, 0) - heroes.get(h, 0)) for h in hero_max),
            "equip_gap": sum(max(0, EQUIP_MAX.get(e, 0) - equips.get(e, 0)) for e in EQUIP_NAME),
            "upgrading_count": len(upgrading),
        },
    }
