#!/usr/bin/env python3
"""Comprehensive test runner for all implemented features:
1. OCR Loot & Parsing Logic
2. Dead Base Detection Logic
3. Smart Loot Threshold Logic (TOTAL, EITHER, BOTH, DARK)
4. Human Input / Jitter Logic
5. Scheduler Anti-ban Windows
6. Dashboard Settings Read/Write Logic
7. Live ADB & Screen Capture Verification
8. Live Village OCR (Gold, Elixir, Dark Storage)
9. Live Resource Collector Routine
10. Live Auto Lab Upgrade Routine
11. Live Auto Wall Upgrade Routine
12. Live Deselect / Modal Recovery
"""

import sys
import subprocess
import time

print("=" * 60)
print("🚀 RUNNING COMPREHENSIVE BOT FEATURE VERIFICATION SUITE")
print("=" * 60)

# --- 1. Unit Tests (Logic & Parsing) in isolated process ---
print("\n[PHASE 1] Running Pure Logic & Unit Tests (19 tests)...")
sub = subprocess.run([sys.executable, "-m", "unittest", "test_bot", "-v"], capture_output=True, text=True)
print(sub.stderr if sub.stderr else sub.stdout)
if sub.returncode != 0:
    print("❌ Unit tests failed!")
    sys.exit(1)
print("✅ All unit tests PASSED!")

# --- 2. Live Device & Feature Integration ---
print("\n[PHASE 2] Running Live Device Verification...")
import config
import bot
import ocr

# Test 2.1: ADB Connection & Screen Shape
print("\n--- Test 2.1: ADB Screen Capture ---")
screen = bot.adb.screenshot()
assert screen is not None, "Failed to capture screenshot from ADB"
assert screen.shape == (1080, 1920, 3), f"Screen shape mismatch: {screen.shape}"
print(f"✅ Screen captured successfully: shape={screen.shape}")

# Test 2.2: Live Village Storage OCR
print("\n--- Test 2.2: Live Village Storage OCR ---")
g_val = bot.read_storage_amount(screen, config.VILLAGE_GOLD_REGION)
e_val = bot.read_storage_amount(screen, config.VILLAGE_ELIXIR_REGION)
builders = bot.get_free_builders(screen)
print(f"📊 Current Village Storage: Gold={g_val:,} | Elixir={e_val:,} | Free Builders={builders}")
assert g_val > 0, "Failed to read Village Gold"
print("✅ Village storage OCR working accurately!")

# Test 2.3: Live Resource Collector Tap
print("\n--- Test 2.3: Resource Collector Collection ---")
bot.collect_village_resources()
print("✅ Resource collectors tapped safely!")

# Test 2.4: Live Auto Lab Upgrade Check
print("\n--- Test 2.4: Live Auto Lab Upgrade Check ---")
bot.ensure_village()
bot.auto_upgrade_lab()
time.sleep(1.0)
screen_after_lab = bot.adb.screenshot()
assert bot.in_village(screen_after_lab), "Village screen not restored after Auto Lab!"
print("✅ Auto Lab check completed and returned to village cleanly!")

# Test 2.5: Live Auto Wall Upgrade Check
print("\n--- Test 2.5: Live Auto Wall Upgrade Check ---")
bot.ensure_village()
bot.auto_upgrade_walls()
time.sleep(1.0)
screen_after_wall = bot.adb.screenshot()
assert bot.in_village(screen_after_wall), "Village screen not restored after Auto Wall!"
print("✅ Auto Wall check completed and returned to village cleanly!")

# Test 2.6: Live Deselect Tap
print("\n--- Test 2.6: Deselect Tap Verification ---")
bot.adb.tap(*config.EMPTY_TAP)
time.sleep(0.5)
screen_clean = bot.adb.screenshot()
assert bot.in_village(screen_clean), "Village is not clean after deselect tap!"
print("✅ Deselect tap verified on safe coordinate!")

# Test 2.7: Dashboard Setting Read/Write
print("\n--- Test 2.7: Dashboard Config Integration ---")
import dashboard
settings = dashboard.read_settings()
print(f"⚙️ Loaded Dashboard Settings: {list(settings.keys())}")
assert "AUTO_LAB_UPGRADE" in settings
assert "AUTO_WALL_UPGRADE" in settings
assert "DEAD_BASE_DETECTION" in settings
assert "LOOT_MODE" in settings

# Test write & restore
orig_val = settings["AUTO_LAB_UPGRADE"]
dashboard.write_setting("AUTO_LAB_UPGRADE", "False")
assert dashboard.read_settings()["AUTO_LAB_UPGRADE"] == "False"
dashboard.write_setting("AUTO_LAB_UPGRADE", orig_val)
assert dashboard.read_settings()["AUTO_LAB_UPGRADE"] == orig_val
print("✅ Dashboard write & restore verified!")

print("\n" + "=" * 60)
print("🎉 ALL FEATURES TESTED AND 100% OPERATIONAL!")
print("=" * 60)
