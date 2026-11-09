"""Unit test logika-murni (tanpa emulator/ADB/OCR model).
Jalankan: ./venv/bin/python -m unittest test_bot -v

easyocr di-stub sebelum import ocr/bot supaya model berat (~1GB) gak ke-load.
"""
import sys, types, unittest, datetime

# --- stub easyocr sebelum import modul yang narik model ---
_fake = types.ModuleType("easyocr")
_fake.Reader = lambda *a, **k: None
sys.modules["easyocr"] = _fake

import ocr
import config
from human import jitter
from scheduler import should_be_active


class TestParseLoot(unittest.TestCase):
    def test_thousands_dot_separator(self):
        # OCR baca titik sebagai pemisah ribuan
        self.assertEqual(ocr.parse_loot("1.234.567"), 1234567)
        self.assertEqual(ocr.parse_loot("6.800"), 6800)

    def test_comma_stripped(self):
        self.assertEqual(ocr.parse_loot("1,234,567"), 1234567)

    def test_suffix_decimal(self):
        self.assertEqual(ocr.parse_loot("1.5M"), 1_500_000)
        self.assertEqual(ocr.parse_loot("250K"), 250_000)
        self.assertEqual(ocr.parse_loot("2M"), 2_000_000)

    def test_plain_number(self):
        self.assertEqual(ocr.parse_loot("5000"), 5000)

    def test_junk_returns_none(self):
        self.assertIsNone(ocr.parse_loot(""))
        self.assertIsNone(ocr.parse_loot("abc"))

    def test_lowercase_suffix(self):
        # read_region uppercase-kan dulu; parse_loot sendiri terima upper saja
        self.assertEqual(ocr.parse_loot("1.5M"), 1_500_000)


class TestLootEnough(unittest.TestCase):
    def setUp(self):
        # loot_enough ada di bot.py; import di sini (easyocr sudah di-stub)
        import bot
        self.loot_enough = bot.loot_enough

    def test_both_mode(self):
        config.LOOT_MODE = "BOTH"
        g, e = config.GOLD_MIN, config.ELIXIR_MIN
        self.assertTrue(self.loot_enough(g, e, 0))
        self.assertFalse(self.loot_enough(g - 1, e, 0))
        self.assertFalse(self.loot_enough(g, e - 1, 0))

    def test_total_mode(self):
        config.LOOT_MODE = "TOTAL"
        config.TOTAL_MIN = 1_000_000
        self.assertTrue(self.loot_enough(600_000, 500_000, 0))  # 1.1M >= 1M
        self.assertTrue(self.loot_enough(1_000_000, 0, 0))        # 1M >= 1M
        self.assertFalse(self.loot_enough(400_000, 500_000, 0))  # 900k < 1M

    def test_either_mode(self):
        config.LOOT_MODE = "EITHER"
        self.assertTrue(self.loot_enough(config.GOLD_MIN, 0, 0))
        self.assertTrue(self.loot_enough(0, config.ELIXIR_MIN, 0))
        self.assertFalse(self.loot_enough(config.GOLD_MIN - 1, config.ELIXIR_MIN - 1, 0))

    def test_dark_mode(self):
        config.LOOT_MODE = "DARK"
        self.assertTrue(self.loot_enough(0, 0, config.DARK_MIN))
        self.assertFalse(self.loot_enough(10_000_000, 10_000_000, config.DARK_MIN - 1))


class TestJitter(unittest.TestCase):
    def test_within_radius(self):
        for _ in range(200):
            jx, jy = jitter(100, 200, radius=8)
            self.assertLessEqual(abs(jx - 100), 8)
            self.assertLessEqual(abs(jy - 200), 8)


class TestScheduler(unittest.TestCase):
    def test_always_active(self):
        # Jadwal dinonaktifkan: harus selalu True di jam dan tanggal berapapun
        now1 = datetime.datetime(2026, 7, 10, 10, 0)
        now2 = datetime.datetime(2026, 7, 10, 3, 0)
        self.assertTrue(should_be_active(now1))
        self.assertTrue(should_be_active(now2))
        self.assertTrue(should_be_active())



class TestDeadBaseDetection(unittest.TestCase):
    def setUp(self):
        import bot
        self.is_dead_base = bot.is_dead_base

    def test_unranked_badge_detected(self):
        import numpy as np
        img = np.zeros((1080, 1920, 3), dtype=np.uint8)
        img[22:85, 12:55] = [130, 130, 130]  # grey unranked badge (sat=0)
        self.assertTrue(self.is_dead_base(img))

    def test_ranked_badge_rejected(self):
        import numpy as np
        img = np.zeros((1080, 1920, 3), dtype=np.uint8)
        img[22:85, 12:55] = [0, 215, 255]    # gold league badge (high sat)
        self.assertFalse(self.is_dead_base(img))

    def test_none_or_empty_image(self):
        self.assertFalse(self.is_dead_base(None))


class TestAutoLabConfig(unittest.TestCase):
    def test_auto_lab_config_attributes(self):
        self.assertIsInstance(config.AUTO_LAB_UPGRADE, bool)
        self.assertTrue(0 <= config.LAB_MENU_BTN[0] <= 1920)
        self.assertTrue(0 <= config.LAB_MENU_BTN[1] <= 1080)
        self.assertTrue(0 <= config.LAB_TAB_BTN[0] <= 1920)
        self.assertTrue(0 <= config.LAB_TAB_BTN[1] <= 1080)
        self.assertTrue(0 <= config.LAB_CONFIRM_BTN[0] <= 1920)
        self.assertTrue(0 <= config.LAB_CONFIRM_BTN[1] <= 1080)
        self.assertTrue(0 <= config.LAB_CLOSE_PANEL_BTN[0] <= 1920)
        self.assertTrue(0 <= config.LAB_CLOSE_PANEL_BTN[1] <= 1080)

    def test_dashboard_settings_read(self):
        from dashboard import read_settings
        settings = read_settings()
        self.assertIn("AUTO_LAB_UPGRADE", settings)
        self.assertIn(settings["AUTO_LAB_UPGRADE"], ("True", "False"))


class TestAutoCollectResources(unittest.TestCase):
    def test_toggle_persists_and_controls_collection(self):
        import tempfile
        from pathlib import Path
        from unittest.mock import patch
        import bot, dashboard

        with tempfile.TemporaryDirectory() as tmp:
            config_path = Path(tmp) / 'config.py'
            config_path.write_text('AUTO_COLLECT_RESOURCES = True\n')
            with patch.object(dashboard, 'CONFIG', str(config_path)):
                for enabled in (False, True):
                    dashboard.write_setting('AUTO_COLLECT_RESOURCES', str(enabled))
                    self.assertEqual(dashboard.read_settings()['AUTO_COLLECT_RESOURCES'], str(enabled))
                    with patch.object(config, 'AUTO_COLLECT_RESOURCES', enabled), \
                         patch.object(bot.adb, 'tap') as tap, \
                         patch.object(bot, 'human_delay'):
                        bot.collect_village_resources()
                        self.assertEqual(tap.call_count, 4 if enabled else 0)


class TestAutoWallUpgrade(unittest.TestCase):
    def test_wall_config_attributes(self):
        self.assertIsInstance(config.AUTO_WALL_UPGRADE, bool)
        self.assertGreater(config.WALL_MIN_GOLD, 0)
        self.assertGreater(config.WALL_MIN_ELIXIR, 0)
        self.assertTrue(0 <= config.WALL_UPGRADE_GOLD_BTN[0] <= 1920)
        self.assertTrue(0 <= config.WALL_UPGRADE_GOLD_BTN[1] <= 1080)
        self.assertTrue(0 <= config.WALL_UPGRADE_ELIXIR_BTN[0] <= 1920)
        self.assertTrue(0 <= config.WALL_UPGRADE_ELIXIR_BTN[1] <= 1080)
        self.assertTrue(0 <= config.WALL_CONFIRM_BTN[0] <= 1920)
        self.assertTrue(0 <= config.WALL_CONFIRM_BTN[1] <= 1080)
        self.assertIsInstance(config.WALL_TAP_POINTS, list)

    def test_wall_name_strict_validation(self):
        # Strict validation: Non-wall buildings (e.g. Cannon Level 15) must NOT pass as Wall
        self.assertFalse("wall" in "cannon level 15".lower())
        self.assertFalse("wall" in "archer tower level 18".lower())
        self.assertFalse("wall" in "army camp level 11".lower())
        self.assertTrue("wall" in "wall (level 17)".lower())
        self.assertTrue("wall" in "wall level 14".lower())

    def test_dashboard_wall_settings(self):
        from dashboard import read_settings
        settings = read_settings()
        self.assertIn("AUTO_WALL_UPGRADE", settings)
        self.assertIn("WALL_MIN_GOLD", settings)
        self.assertIn("WALL_MIN_ELIXIR", settings)

    def test_wall_toggle_persists_and_controls_upgrade(self):
        import tempfile
        from pathlib import Path
        from unittest.mock import patch
        import bot, dashboard

        with tempfile.TemporaryDirectory() as tmp:
            config_path = Path(tmp) / 'config.py'
            config_path.write_text('AUTO_WALL_UPGRADE = True  # keep comment\n')
            with patch.object(dashboard, 'CONFIG', str(config_path)):
                for enabled in (False, True):
                    dashboard.write_setting('AUTO_WALL_UPGRADE', str(enabled))
                    self.assertEqual(dashboard.read_settings()['AUTO_WALL_UPGRADE'], str(enabled))
                    self.assertIn('# keep comment', config_path.read_text())
                    with patch.object(config, 'AUTO_WALL_UPGRADE', enabled), \
                         patch.object(bot.adb, 'screenshot', return_value=None) as screenshot, \
                         patch.object(bot, 'LAST_WALL_SCAN_TIME', 0):
                        self.assertFalse(bot.auto_upgrade_walls())
                        self.assertEqual(screenshot.called, enabled)

    def test_generate_wall_scan_grid(self):
        import bot
        grid = bot.generate_wall_scan_grid()
        self.assertIsInstance(grid, list)
        self.assertGreater(len(grid), 10)
        for x, y in grid:
            self.assertTrue(0 <= x <= 1920)
            self.assertTrue(0 <= y <= 1080)


class TestScreenDetection(unittest.TestCase):
    def test_in_battle_screen_requires_actual_battle_ui(self):
        import numpy as np, bot
        # Layar kosong / desa tidak boleh terdeteksi battle
        blank = np.zeros((1080, 1920, 3), dtype=np.uint8)
        self.assertFalse(bot.in_battle_screen(blank))
        self.assertFalse(bot.in_battle_screen(None))

    def test_in_army_confirm_screen(self):
        import numpy as np, bot
        blank = np.zeros((1080, 1920, 3), dtype=np.uint8)
        self.assertFalse(bot.in_army_confirm_screen(blank))
        self.assertFalse(bot.in_army_confirm_screen(None))


class TestChestAndRewardDetection(unittest.TestCase):
    def setUp(self):
        import bot
        self.get_center_confirm_btn = bot.get_center_confirm_btn
        self.is_chest_screen = bot.is_chest_screen

    def test_get_center_confirm_btn_none_and_blank(self):
        import numpy as np
        self.assertIsNone(self.get_center_confirm_btn(None))
        blank = np.zeros((1080, 1920, 3), dtype=np.uint8)
        self.assertIsNone(self.get_center_confirm_btn(blank))

    def test_get_center_confirm_btn_detects_green_button(self):
        import numpy as np
        img = np.zeros((1080, 1920, 3), dtype=np.uint8)
        # BGR for COC button green (e.g. [50, 180, 50])
        # Position button at center: x=850..1100 (w=250), y=880..960 (h=80)
        img[880:960, 850:1100] = [50, 200, 50]
        btn = self.get_center_confirm_btn(img)
        self.assertIsNotNone(btn)
        self.assertEqual(btn, (850 + 125, 880 + 40))

    def test_is_chest_screen_none_and_blank(self):
        import numpy as np
        self.assertFalse(self.is_chest_screen(None))
        blank = np.zeros((1080, 1920, 3), dtype=np.uint8)
        self.assertFalse(self.is_chest_screen(blank))


class TestStatsNormalization(unittest.TestCase):
    def test_account_normalization(self):
        import stats
        self.assertEqual(stats.normalize_account_name("ziP"), "Zip")
        self.assertEqual(stats.normalize_account_name("zip"), "Zip")
        self.assertEqual(stats.normalize_account_name("ryu"), "Ryu")
        self.assertEqual(stats.normalize_account_name(""), "unknown")
class TestSpeedupDetection(unittest.TestCase):
    def test_detect_speedup_none_and_blank(self):
        import numpy as np, bot
        self.assertIsNone(bot.detect_speedup_btn(None))
        blank = np.zeros((1080, 1920, 3), dtype=np.uint8)
        self.assertIsNone(bot.detect_speedup_btn(blank))

    def test_detect_speedup_synthetic_button(self):
        import numpy as np, bot
        img = np.zeros((1080, 1920, 3), dtype=np.uint8)
        # BGR corresponding to lime green HSV (H~40..50, S~100..200, V~200..255)
        # e.g., B=50, G=220, R=160
        img[550:620, 1800:1880] = [50, 220, 160]
        pt = bot.detect_speedup_btn(img)
        self.assertIsNotNone(pt)
        bx, by = pt
        self.assertTrue(1770 <= bx <= 1920)
        self.assertTrue(510 <= by <= 640)

    def test_check_and_apply_fast_forward_blank(self):
        import numpy as np, bot
        blank = np.zeros((1080, 1920, 3), dtype=np.uint8)
        self.assertFalse(bot.check_and_apply_fast_forward(blank))


if __name__ == "__main__":
    unittest.main()

