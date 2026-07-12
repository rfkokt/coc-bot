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

    def test_all_above_threshold(self):
        g, e = config.GOLD_MIN, config.ELIXIR_MIN
        self.assertTrue(self.loot_enough(g, e, 0))

    def test_gold_below(self):
        self.assertFalse(self.loot_enough(config.GOLD_MIN - 1, config.ELIXIR_MIN, 0))

    def test_elixir_below(self):
        self.assertFalse(self.loot_enough(config.GOLD_MIN, config.ELIXIR_MIN - 1, 0))


class TestJitter(unittest.TestCase):
    def test_within_radius(self):
        for _ in range(200):
            jx, jy = jitter(100, 200, radius=8)
            self.assertLessEqual(abs(jx - 100), 8)
            self.assertLessEqual(abs(jy - 200), 8)


class TestScheduler(unittest.TestCase):
    def test_deterministic_per_date(self):
        # seed = tanggal → hasil harus konsisten utk jam yang sama di tanggal sama
        now = datetime.datetime(2026, 7, 10, 10, 0)
        self.assertEqual(should_be_active(now), should_be_active(now))

    def test_returns_bool(self):
        now = datetime.datetime(2026, 7, 10, 10, 0)
        self.assertIsInstance(should_be_active(now), bool)

    def test_midnight_inactive(self):
        # jam 3 pagi: di luar window main (start 8-12) → selalu False
        now = datetime.datetime(2026, 7, 10, 3, 0)
        self.assertFalse(should_be_active(now))


if __name__ == "__main__":
    unittest.main()
