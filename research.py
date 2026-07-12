#!/usr/bin/env python3
"""Deep Research engine for COC Bot — adaptasi dari Odysseus DeepResearcher pattern.

Iterative Think→Search→Extract→Synthesize loop, disederhanakan untuk konteks
COC upgrade strategy without requiring external LLM/search infra.

Pola Odysseus:
  1. PLAN: analisis question → sub-questions + key topics
  2. THINK: generate search queries (here: from static knowledge)
  3. SEARCH + EXTRACT: kumpulin findings dari knowledge base
  4. SYNTHESIZE: integrasikan findings ke evolving report
  5. DECIDE: cukup belum? (gap analysis)
  6. FINAL REPORT: polished comprehensive report

Untuk COC Bot: knowledge base-nya adalah static_data + strategi bawaan + gap analysis.
"""
import json
import os
from datetime import datetime
from typing import Optional

HERE = os.path.dirname(os.path.abspath(__file__))
STATIC_DATA_PATH = os.path.join(HERE, "web", "public", "assets", "static_data.json")

# ── Knowledge Base ───────────────────────────────────────────────────────

TH_STRATEGIES = {
    12: {
        "title": "Town Hall 12 — The Hybrid Transition",
        "overview": "TH12 introduces the Grand Warden (Gargoyle), Siege Machines, and Eagle Artillery. Priority #1 is unlocking the Warden's Eternal Tome and upgrading your core farming army (Hog+Miner Hybrid) to TH12 levels.",
        "farming": "Best farming: Crystal I to Master III. Use Baby Dragon + Lightning for dead bases, or mass Goblin + Jump for collector raids. Prioritize maxing Army Camps to 275 housing.",
        "war": "TH12 war meta: Queen Charge Hybrid (Hog+Miner) is most consistent. Lalo (LavaLoon) is the high-skill alt. Key: Eternal Tome negates Eagle Artillery volleys.",
        "upgrade_priority": [
            ("🔥 #1", "Laboratory", "Unlock TH12 troop levels ASAP."),
            ("🔥 #2", "Clan Castle", "Maxing CC unlocks +5 housing space."),
            ("🔥 #3", "Army Camp", "275 housing = bigger armies."),
            ("⚡ #4", "Grand Warden", "Biggest power spike at TH12."),
            ("⚡ #5", "Eagle Artillery", "Core anti-funnel defense."),
            ("💪 #6", "Workshop", "Unlock Siege Machines for wars."),
            ("💪 #7", "Spell Factory", "Extra spell capacity."),
            ("🔧 #8", "Dark Spell Factory", "Bat Spell unlocks BatLoon."),
            ("🔧 #9", "Inferno Towers", "Core defense."),
            ("🔧 #10", "X-Bows", "Sustained DPS."),
        ],
        "key_equipment": [
            ("Eternal Tome (Warden)", "Priority #1 — negates all damage for 8s."),
            ("Giant Gauntlet (King)", "Buffs DPS; great for funneling."),
            ("Rage Vial (Queen)", "Boosts Queen Walk clear speed."),
            ("Invisibility Vial (Queen)", "Pairs with Rage Vial for Queen Charge."),
        ],
        "hero_order": "Grand Warden → Archer Queen → Barbarian King. Warden's Tome is the strongest power spike.",
        "key_units": ["Hog Rider (lvl 8+)", "Miner (lvl 6+)", "Balloon (lvl 7+)", "Baby Dragon (lvl 6+)", "Wall Wrecker"],
        "key_spells": ["Heal (lvl 8)", "Rage (lvl 5)", "Freeze (lvl 6)", "Bat Spell (lvl 5)"],
    },
    13: {
        "title": "Town Hall 13 — The Scattershot Era",
        "overview": "TH13 brings the Royal Champion, Scattershots, and final Eagle Artillery. Focus on hero levels and core defenses first.",
        "farming": "Best farming: Master II to Champion III. Sneaky Goblin + Super Wall Breaker for dead bases.",
        "war": "TH13 meta: Yeti Smash (Yeti + P.E.K.K.A) is dominant. Super Archer Blimp for anti-3-star. Hybrid remains consistent.",
        "upgrade_priority": [
            ("🔥 #1", "Royal Champion", "Unlock and level to 25 ASAP."),
            ("🔥 #2", "Laboratory", "TH13 troop upgrades are huge."),
            ("🔥 #3", "Scattershot", "The defining TH13 defense."),
            ("⚡ #4", "Army Camp", "290 housing space."),
            ("⚡ #5", "Clan Castle", "+5 more housing."),
            ("⚡ #6", "Eagle Artillery", "Max level for max damage."),
            ("💪 #7", "Workshop", "Stone Slammer unlocks at TH13."),
            ("💪 #8", "Inferno Towers", "Both to max."),
            ("🔧 #9", "X-Bows", "Sustained DPS."),
            ("🔧 #10", "Hidden Tesla", "Surprise DPS."),
        ],
        "key_equipment": [
            ("Seeking Shield (Champion)", "Auto-targets key defenses."),
            ("Eternal Tome (Warden)", "Essential for protecting main push."),
            ("Giant Gauntlet (King)", "Top-tier King equipment."),
            ("Healer Puppet (Queen)", "Extends Queen Walk significantly."),
        ],
        "hero_order": "Royal Champion → Archer Queen → Grand Warden → Barbarian King.",
        "key_units": ["Yeti (lvl 4+)", "Super Archer", "P.E.K.K.A (lvl 8+)", "Root Rider"],
        "key_spells": ["Rage (lvl 6)", "Heal (lvl 9)", "Freeze (lvl 7)", "Invisibility"],
    },
    14: {
        "title": "Town Hall 14 — The Pet Power Spike",
        "overview": "TH14 unlocks Pets — the biggest power spike since the Grand Warden. Pet House should be #1 priority. Monolith defense arrives.",
        "farming": "Best farming: Champion I to Titan III. Super Goblin + Super Wall Breaker remains gold standard.",
        "war": "TH14 meta: Super Archer Blimp. Root Rider + Electro Titan smash. Unicorn for Queen, Phoenix for Warden, LASSI for King.",
        "upgrade_priority": [
            ("🔥 #1", "Pet House", "Unlock pets — biggest power spike."),
            ("🔥 #2", "Laboratory", "New troop levels."),
            ("🔥 #3", "Monolith", "Deletes any unit it targets."),
            ("⚡ #4", "Town Hall", "Giga Inferno weapon."),
            ("⚡ #5", "Army Camp", "300 housing space."),
            ("💪 #6", "Clan Castle", "+5 housing."),
            ("💪 #7", "Scattershot", "Extra Scattershot."),
            ("💪 #8", "Eagle Artillery", "Tank killers."),
            ("🔧 #9", "Inferno Towers", "Core defense."),
            ("🔧 #10", "X-Bows", "Sustained DPS."),
        ],
        "key_equipment": [
            ("Phoenix (Pet)", "Best Warden pet — second life."),
            ("Unicorn (Pet)", "Best Queen pet — constant healing."),
            ("Seeking Shield (Champion)", "Still top-tier."),
            ("Magic Mirror (Queen)", "Clone that heals."),
        ],
        "hero_order": "Royal Champion → Archer Queen → Grand Warden → Barbarian King → Minion Prince.",
        "key_units": ["Super Archer", "Root Rider (lvl 3+)", "Electro Titan (lvl 2+)", "Yeti (lvl 5+)"],
        "key_spells": ["Invisibility", "Rage (lvl 7)", "Recall", "Freeze (lvl 8+)"],
    },
    15: {
        "title": "Town Hall 15 — The Root Rider Meta",
        "overview": "TH15 introduces Dragon Duke hero, Spell Towers. Root Rider dominates. Spirit Fox unlocks as best Queen pet. Don't rush — max key offense first.",
        "farming": "Best farming: Titan III to Titan I. Super Goblin + Invisibility is fastest. Root Rider farming efficient for pushing while farming.",
        "war": "TH15 meta: Root Rider + Electro Titan is most powerful smash. Super Hog + RC charge for speed. Spirit Fox + Queen Walk for high-value picks.",
        "upgrade_priority": [
            ("🔥 #1", "Town Hall", "Unlock Spell Tower (Poison)."),
            ("🔥 #2", "Laboratory", "Root Rider, Electro Titan upgrades."),
            ("🔥 #3", "Pet House", "Unlock Spirit Fox."),
            ("⚡ #4", "Spell Tower", "Poison tower changes base meta."),
            ("⚡ #5", "Army Camp", "310 housing space."),
            ("💪 #6", "Clan Castle", "+5 housing + max donations."),
            ("💪 #7", "Monolith", "Max it — best single-target."),
            ("💪 #8", "Eagle Artillery", "Max level is devastating."),
            ("🔧 #9", "Scattershot", "Third Scattershot."),
            ("🔧 #10", "Inferno Towers", "Both to max."),
        ],
        "key_equipment": [
            ("Spiky Ball (King)", "Best King epic — huge damage + stun."),
            ("Magic Mirror (Queen)", "Clone + heal. Top-tier."),
            ("Spirit Fox (Pet)", "Best Queen pet — constant invisibility."),
            ("Phoenix (Pet)", "Best Warden pet — second life."),
            ("Electro Boots (Champion)", "AoE damage."),
        ],
        "hero_order": "Royal Champion → Archer Queen → Grand Warden → Dragon Duke → Barbarian King → Minion Prince.",
        "key_units": ["Root Rider (lvl 3+)", "Electro Titan (lvl 3+)", "Super Hog Rider", "Yeti (lvl 6)"],
        "key_spells": ["Rage (lvl 8)", "Invisibility", "Recall", "Overgrowth"],
    },
    16: {
        "title": "Town Hall 16 — The Firespitter Fortress",
        "overview": "TH16 upgrades with Firespitter, Multi-Archer Towers, Ricochet Cannons. Equipment levels matter more than ever at this stage.",
        "farming": "Best farming: Titan I to Legend League. Root Rider + Electro Titan most effective for both farming and pushing.",
        "war": "TH16 meta: Root Rider + Electro Titan + Dragon Duke. Fireball Warden with Rage Gem for anti-core. Super Artillery for tight bases.",
        "upgrade_priority": [
            ("🔥 #1", "Firespitter", "Burns through any ground unit."),
            ("🔥 #2", "Laboratory", "Max troop upgrades."),
            ("🔥 #3", "Multi-Archer Tower", "Extremely strong point defense."),
            ("⚡ #4", "Town Hall", "Upgraded TH weapon."),
            ("⚡ #5", "Army Camp", "320 housing space."),
            ("💪 #6", "Clan Castle", "Max CC."),
            ("💪 #7", "Monolith", "Max level."),
            ("💪 #8", "Spell Tower", "Both variants."),
            ("🔧 #9", "Ricochet Cannon", "Bouncing shots shred swarms."),
            ("🔧 #10", "Inferno Towers", "Core defense."),
        ],
        "key_equipment": [
            ("Fireball (Warden)", "Pair with Rage Gem for nuclear blast."),
            ("Rocket Spear (Champion)", "Range + damage."),
            ("Spiky Ball (King)", "Still #1 King epic."),
            ("Magic Mirror (Queen)", "Best Queen epic."),
            ("Electro Boots (Champion)", "AOE clear for RC charge."),
        ],
        "hero_order": "Royal Champion → Archer Queen → Grand Warden → Dragon Duke → Barbarian King → Minion Prince.",
        "key_units": ["Root Rider (lvl 5+)", "Electro Titan (lvl 5+)", "Dragon Rider (lvl 6+)"],
        "key_spells": ["Rage (lvl 9)", "Freeze (lvl 9)", "Invisibility", "Revive", "Recall"],
    },
    17: {
        "title": "Town Hall 17 — The Ultimate Grind",
        "overview": "TH17 pushes every system to max. Multi-Gear Towers, max hero levels, final pet upgrades. Prioritize efficiency over perfection.",
        "farming": "Best farming: Legend League. Root Rider + Electro Titan remains top. Use training potions for extended sessions.",
        "war": "TH17 war: Root Rider + Electro Titan + Yeti + Dragon Duke. Multi-Gear Tower changes target priority. Super Hog for fastest cleanup.",
        "upgrade_priority": [
            ("🔥 #1", "Multi-Gear Tower", "Targets both air+ground. Changes meta."),
            ("🔥 #2", "Laboratory", "Final troop levels."),
            ("🔥 #3", "Army Camp", "330 housing capacity."),
            ("⚡ #4", "Town Hall", "Maximum weapon level."),
            ("⚡ #5", "Monolith", "Maxed for endgame."),
            ("💪 #6", "Firespitter", "Still devastating."),
            ("💪 #7", "Eagle Artillery", "Maxed."),
            ("💪 #8", "Scattershot", "Final levels."),
            ("🔧 #9", "Inferno Towers", "Maxed defense."),
            ("🔧 #10", "Hero Hall", "Max hero levels."),
        ],
        "key_equipment": [
            ("Fireball + Rage Gem (Warden)", "Meta core destruction."),
            ("Rocket Spear (Champion)", "Range + damage."),
            ("Spiky Ball (King)", "Top King epic."),
            ("All epics to max", "Equipment > hero levels."),
        ],
        "hero_order": "Equipment first, then hero levels. Max Fireball before pushing Warden levels.",
        "key_units": ["Root Rider (lvl 6+)", "Electro Titan (lvl 5+)", "Dragon Duke"],
        "key_spells": ["All max level spells"],
    },
    18: {
        "title": "Town Hall 18 — The Age of Dragon Duke",
        "overview": "TH18 introduces Dragon Duke with Fire Heart ability, Meteor Golem, and final equipment cap. Dragon Duke spearheads air-based strategies.",
        "farming": "Best farming: Legend League. Dragon Duke + Lavaloon for push. Root Rider + Meteor Golem for safe 2-star.",
        "war": "TH18 meta: Dragon Duke + Fire Heart carries air attacks. Root Rider + Meteor Golem + Electro Titan for ground. Use Fireball Warden to open core, Dragon Duke cleans up.",
        "upgrade_priority": [
            ("🔥 #1", "Dragon Duke", "The defining TH18 hero."),
            ("🔥 #2", "Laboratory", "Meteor Golem and TH18 upgrades."),
            ("🔥 #3", "Army Camp", "Max capacity (340+ housing)."),
            ("⚡ #4", "Town Hall", "Max level weapon."),
            ("⚡ #5", "Firespitter", "Still meta defining."),
            ("💪 #6", "Multi-Gear Tower", "Critical point defense."),
            ("💪 #7", "Monolith", "Maxed."),
            ("💪 #8", "Spell Tower", "All variants."),
            ("🔧 #9", "Hero Hall", "Duke max unlock."),
            ("🔧 #10", "Eagle Artillery", "Final levels."),
        ],
        "key_equipment": [
            ("Lunar Launcher (Duke)", "Auto-targets defenses."),
            ("Gem Warden (Warden)", "Gem-based sustain."),
            ("Fireball + Rage Gem (Warden)", "Core destruction."),
            ("Spiky Ball (King)", "Still #1."),
            ("Rocket Spear (Champion)", "Range dominance."),
            ("Electro Boots (Champion)", "AOE clear."),
        ],
        "hero_order": "Dragon Duke → Equipment for all → Archer Queen → Royal Champion → Grand Warden → Barbarian King → Minion Prince.",
        "key_units": ["Dragon Duke", "Meteor Golem (lvl 3)", "Root Rider (lvl 7)", "Dragon Rider (lvl 6+)", "Electro Titan (lvl 6+)"],
        "key_spells": ["Rage (max)", "Invisibility", "Revive", "Recall", "Freeze (max)"],
    },
}

HERO_EQUIPMENT_GUIDE = {
    "Barbarian King": [
        ("Spiky Ball (Epic)", "Best epic — high damage + stun. Pairs with Rage Vial."),
        ("Giant Gauntlet (Epic)", "Buffs DPS + range. Great for funneling."),
        ("Rage Vial", "Reliable common. Pairs with any epic."),
        ("Vampstache", "Sustain for longer King walks."),
    ],
    "Archer Queen": [
        ("Magic Mirror (Epic)", "Best epic — clone deals massive damage and heals."),
        ("Frozen Arrow (Epic)", "Slows key defenses. Great for Queen Charge."),
        ("Invisibility Vial", "Essential for Queen Charge."),
        ("Healer Puppet", "Extra healers for extended Queen Walk."),
    ],
    "Grand Warden": [
        ("Fireball (Epic)", "Highest damage. One-shots key defenses."),
        ("Eternal Tome", "Essential invulnerability phase."),
        ("Rage Gem", "Puts Rage on army in attack mode."),
        ("Life Gem", "HP boost for main push."),
        ("Gem Warden (Epic)", "TH18 — sustain + damage."),
    ],
    "Royal Champion": [
        ("Seeking Shield", "Auto-targets key defenses. Best-in-slot."),
        ("Rocket Spear (Epic)", "Massive range + damage."),
        ("Electro Boots (Epic)", "AoE damage trail."),
        ("Haste Vial", "Speed boost for faster RC loops."),
    ],
    "Minion Prince": [
        ("Dark Orb (Epic)", "AoE damage. Best-in-slot."),
        ("Noble Iron (Epic)", "Defense targeting for funnel."),
    ],
    "Dragon Duke": [
        ("Lunar Launcher (Epic)", "Auto-targets defenses with high damage."),
        ("Heroic Torch (Epic)", "Buffs Fire Heart ability."),
        ("Dark Crown (Epic)", "AoE fear effect on defenses."),
    ],
}

FARMING_TIPS = [
    "Farm in Crystal I to Master III — dead bases plentiful with good loot bonus.",
    "Sneaky Goblin + Jump/Invisibility is the fastest farmer. Use training potions.",
    "Keep one farming army (Sneaky Goblins) and one war/push army.",
    "Save gems for 5th Builder first, then training potions and Book of Heroes.",
    "Target full collectors and mines. Skip bases where storages are deep.",
    "Best times: during Clan Games, CWL week, weekend mornings.",
]

GENERAL_TIPS = [
    "Offense > Defense. Always max army (camps, lab, barracks, CC) first.",
    "Heroes are the most impactful upgrades. Keep at least one hero down until maxed.",
    "Never let the lab sit idle. It's your most important building.",
    "Keep 1 builder free for walls. Dump excess resources into walls.",
    "Always participate in Clan Games & CWL. Rewards are invaluable.",
    "Use Books for long upgrades (14+ days), Hammers for expensive ones.",
    "Don't sit on full storages — upgrade traps and walls with overflow.",
    "A well-executed strategy beats a maxed army with a bad attack.",
]


def load_static_data() -> dict:
    try:
        with open(STATIC_DATA_PATH) as f:
            return json.load(f)
    except (FileNotFoundError, json.JSONDecodeError):
        return {}


def generate_deep_research(analysis: dict) -> dict:
    """Generate deep research report from village analysis.

    Mengadaptasi Odysseus DeepResearcher pattern:
      PLAN → THINK → SEARCH/EXTRACT → SYNTHESIZE → FINAL REPORT
    Untuk COC: knowledge base adalah static data + strategi bawaan.
    """
    th = analysis.get("th_level", 0)
    summary = analysis.get("summary", {})
    recs = analysis.get("recs", [])
    strats = analysis.get("strategies", [])

    if th not in TH_STRATEGIES:
        return {"th_level": th, "error": f"Tidak ada data strategi untuk TH {th}.", "sections": []}

    th_data = TH_STRATEGIES[th]
    static = load_static_data()

    upgrade_count = sum(1 for r in recs if r.get("gap", 0) > 0)
    hero_gap = summary.get("heroes_gap", 0)
    equip_gap = summary.get("equip_gap", 0)
    upgrading = summary.get("upgrading_count", 0)

    exec_summary = (
        f"**Town Hall {th}** — {upgrade_count} items need upgrades. "
        f"Hero gap: {hero_gap} levels. Equipment gap: {equip_gap} levels. "
        f"{upgrading} currently upgrading.\\n\\n{th_data['overview']}"
    )

    # Upgrade items dari analysis
    upgrade_items = []
    seen = set()
    for r in recs:
        if r.get("gap", 0) > 0 and r.get("name") not in seen:
            seen.add(r["name"])
            upgrade_items.append({
                "name": r["name"], "cat": r.get("cat", ""),
                "cur": r.get("cur", 0), "max": r.get("max", 0),
                "gap": r.get("gap", 0), "prio": r.get("prio", 0),
            })
    upgrade_items.sort(key=lambda x: -x["prio"])

    # Strategy items
    strategy_items = [{"name": s["name"], "desc": s["desc"], "status": s["status"], "ready": s["ready"]} for s in strats]

    # Equipment recommendations
    equip_recs = {}
    for hero, items in HERO_EQUIPMENT_GUIDE.items():
        has_hero = any(hero in r.get("name", "") for r in recs if r.get("cat") == "hero")
        if has_hero or hero in ("Grand Warden", "Archer Queen"):
            equip_recs[hero] = [{"name": e[0], "desc": e[1], "top": i == 0} for i, e in enumerate(items)]

    # Resource analysis
    resource_totals = {"Gold": 0, "Elixir": 0, "Dark Elixir": 0}
    total_time = 0
    static_buildings = {b["name"]: b for b in static.get("buildings", [])}

    for r in recs:
        if r.get("gap", 0) <= 0:
            continue
        name = r["name"]
        cur = r.get("cur", 0)
        mx = r.get("max", 0)
        item_data = static_buildings.get(name)
        if item_data and item_data.get("levels"):
            for ld in item_data["levels"]:
                lvl = ld.get("level", 0)
                if cur < lvl <= mx:
                    cost = ld.get("build_cost") or ld.get("upgrade_cost") or 0
                    ts = ld.get("build_time") or ld.get("upgrade_time") or 0
                    res = ld.get("upgrade_resource") or item_data.get("upgrade_resource", "Gold")
                    if res in ("DarkElixir", "Dark"):
                        res = "Dark Elixir"
                    if res in resource_totals:
                        resource_totals[res] += cost
                    total_time += ts

    # ── Build sections ──
    sections = [
        {"id": "executive-summary", "title": "Executive Summary", "icon": "📋", "content": exec_summary, "type": "markdown"},
        {"id": "upgrade-priority", "title": "Upgrade Priority Research", "icon": "📊",
         "content": "Optimal upgrade order berdasarkan analysis + meta strategy.",
         "type": "priority_table", "priorities": th_data["upgrade_priority"]},
        {"id": "attack-strategies", "title": "Attack Strategy Analysis", "icon": "⚔️",
         "content": f"**TH{th} Meta:** {th_data['war']}",
         "type": "strategies", "strategies": strategy_items,
         "key_units": th_data.get("key_units", []), "key_spells": th_data.get("key_spells", [])},
        {"id": "equipment-guide", "title": "Equipment Deep Research", "icon": "🛡️",
         "content": "Optimal hero equipment loadouts based on current meta.",
         "type": "equipment", "heroes": equip_recs},
        {"id": "hero-order", "title": "Hero Upgrade Order", "icon": "👑",
         "content": th_data["hero_order"], "type": "markdown"},
        {"id": "farming-strategy", "title": "Farming Research", "icon": "💰",
         "content": th_data["farming"], "type": "tips", "tips": FARMING_TIPS},
        {"id": "war-strategy", "title": "War Strategy Research", "icon": "🏴",
         "content": th_data["war"], "type": "markdown"},
        {"id": "resource-analysis", "title": "Resource & Time Analysis", "icon": "⏱️",
         "content": "Total resources and time to max.", "type": "resources",
         "resources": [{"r": k, "v": v} for k, v in resource_totals.items() if v > 0],
         "total_time": total_time},
        {"id": "general-tips", "title": "General Recommendations", "icon": "💡",
         "content": "Best practices for upgrade and resource management.",
         "type": "tips", "tips": GENERAL_TIPS},
    ]

    return {
        "th_level": th,
        "sections": sections,
        "executive_summary": exec_summary,
        "stats": {
            "upgrade_count": upgrade_count,
            "hero_gap": hero_gap,
            "equip_gap": equip_gap,
            "upgrading": upgrading,
            "strategies_available": len(strategy_items),
            "strategies_ready": sum(1 for s in strategy_items if s.get("ready")),
            "report_generated": datetime.now().strftime("%Y-%m-%d %H:%M"),
        },
        "query": f"Optimal upgrade strategy for Town Hall {th}",
        "category": "game_strategy",
    }
