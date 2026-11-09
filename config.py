# --- ADB ---
import subprocess
ADB_PATH = "/Applications/BlueStacks.app/Contents/MacOS/hd-adb"
# ponytail: probe port BlueStacks umum di import-time. Cukup untuk 1-2 instance;
# kalau port custom banyak, daftar di _BS_PORTS. Device ditarik pertama yg online.
_BS_PORTS = [5555, 5556, 5557, 5565, 5575]

def _detect_device(default="emulator-5554"):
    """Cari device online. Kalau kosong, coba adb connect port BlueStacks dulu."""
    def online():
        out = subprocess.run([ADB_PATH, "devices"], capture_output=True, text=True, timeout=5)
        return [ln.split("\t")[0] for ln in out.stdout.splitlines()
                if ln.strip().endswith("\tdevice")]
    devs = online()
    if not devs:
        for p in _BS_PORTS:
            subprocess.run([ADB_PATH, "connect", f"localhost:{p}"],
                           capture_output=True, timeout=5)
        devs = online()
    return devs[0] if devs else default

try:
    DEVICE = _detect_device()  # nilai awal; lihat __getattr__ utk live-resolve
except Exception:
    DEVICE = "emulator-5554"  # fallback; __getattr__ akan retry saat akses


def __getattr__(name):
    # ponytail: live-resolve DEVICE tiap akses biar kembali setelah BlueStacks
    # restart/ganti port tanpa reload. Field lain kembali ke ImportError default.
    if name == "DEVICE":
        return _detect_device()
    raise AttributeError(name)

# --- Resolusi ---
W, H = 1920, 1080

# --- Region OCR loot (x1, y1, x2, y2) - from OCR detection ---
GOLD_REGION   = (75, 125, 380, 180)   # Available Loot: Gold @1920x1080 (dikalibrasi live)
ELIXIR_REGION = (75, 185, 380, 240)   # Available Loot: Elixir @1920x1080
DARK_REGION   = (75, 245, 380, 298)   # Available Loot: Dark Elixir @1920x1080
DAMAGE_REGION = (1780, 780, 1900, 840)  # "Overall Damage" persen di kanan bawah saat battle
COUNTDOWN_REGION = (760, 20, 1160, 120)  # teks "Battle starts in" tengah-atas saat PREVIEW (troop belum bisa deploy)
PLAYER_NAME_REGION = (135, 25, 360, 60)  # nama akun di home village (di sblh XP-level), kiri-atas. OCR di-upscale 3x krn teks kecil
# --- Region OCR 'You got' di RESULT SCREEN (Victory/Defeat) ---
RESULT_GOLD_REGION   = (780, 460, 1050, 520)
RESULT_ELIXIR_REGION = (780, 530, 1050, 590)
RESULT_DARK_REGION   = (745, 590, 1015, 660)

# --- Tombol ---
NEXT_BTN       = (1750, 770)   # Next (skip base) — center tombol oranye
END_ATTACK_BTN = (136, 807)    # End Battle / Surrender (kiri-bawah saat battle, center merah)
SURRENDER_OKAY_BTN = (1142, 685)  # tombol Okay hijau di popup konfirmasi "Surrender?"
ATTACK_BTN     = (114, 962)     # Attack / Battle di village → buka menu (center terkalibrasi)
FIND_MATCH_BTN = (231, 768)     # Find a Match di menu (tombol oranye di panel Battle kiri)
START_SEARCH_BTN = (1696, 964)  # tombol Attack hijau di army prep / My Army modal → cari enemy
ARMY_CONFIRM_ATTACK_BTN = (1696, 964)  # tombol Attack! hijau di modal konfirmasi 'My Army' (saat spell/siege/cc belum penuh)
RETURN_HOME_BTN= (964, 915)    # Return Home hijau stlh battle
POPUP_CLOSE_BTN= (1844, 80)     # tombol X merah kanan-atas popup — center asli terukur
POPUP_X_REGION = (1800, 30, 1910, 120)  # region tombol X — kalau merah → ada popup
EMPTY_TAP      = (250, 50)               # rumput kosong aman di atas kiri — deselect building tanpa kena tombol
BATTLE_SKIP_TAP= (960, 200)              # rumput atas base saat battle preview — tap buat skip countdown 'Battle starts in'
ATTACK_LABEL_REGION = (40, 990, 210, 1050)  # teks "Attack!" atau "Battle" kiri-bawah = tanda di village screen

# --- Quick Train & Army Prep ---
ARMY_TAB_BTN          = (388, 110)
SAVED_RECIPES_TAB_BTN = (960, 110)
COOKBOOK_TAB_BTN      = (1500, 110)
QUICK_TRAIN_USE_BTN   = (1766, 278)   # [Use] Army 1 di Saved Recipes
CAMP_STATUS_REGION    = (850, 230, 1020, 280)  # teks "320/320" di My Army

# --- Village Resource Collectors ---
# Tap 1 kolektor per tipe mengumpulkan semua sumber daya bertipe sama di desa
AUTO_COLLECT_RESOURCES = True
GOLD_COLLECTOR_BTN    = (640, 210)
ELIXIR_COLLECTOR_BTN  = (740, 370)
DARK_COLLECTOR_BTN    = (750, 550)

# --- Desa Malam / Builder Base (dikalibrasi dari battle BB live @1920x1080) ---
# BB pakai layar & tombol beda dari HV. Attack(127,1019) & Surrender(140,805) SAMA.
BB_FIND_NOW_BTN     = (1425, 708)   # "Find Now" di menu attack BB (kanan-tengah panel)
BB_RETURN_HOME_BTN  = (960, 910)    # "Return Home" tengah-bawah di result screen BB
# region OCR teks 'Return Home' di layar result BB (dari probe live: cx959 cy894-926)
# dipakai bb_result_screen buat stop deploy tepat waktu (bukan nunggu timeout 180s)
BB_RESULT_REGION = (820, 860, 1100, 960)
# region deteksi battle-aktif BB: kanan-bawah (Surrender + Overall Damage kebaca).
# BB gak ada loot readout kiri-atas -> in_battle_screen HV gagal, pakai ini.
BB_BATTLE_TAG_REGION = (60, 730, 260, 860)   # area tombol Surrender kiri-bawah saat battle
# BB pakai 1 army buat 2 base. Habis base-1, slot troop kehabisan = ABU (sat rendah).
# Tap slot abu di BB = banner 'select a different unit' + nol deploy -> keliatan stuck.
# Beda HV (tap slot abu diabaikan, aman). Filter: sat < ini = slot habis, skip.
# Kalibrasi live: slot-1 (kiri) troop-nya less-saturated (~99) drpd slot lain (110-165);
# habis = 66-97. Ambang 98 = split slot-1-aktif(99) vs habis(<=97). Gap sempit tapi
# aman: per-frame re-detect bikin 1 mistap borderline gak fatal (dulu stuck krn SEMUA
# slot abu ke-keep loop selamanya; sekarang cuma skip/tap 1 slot borderline).
BB_SLOT_MIN_SAT = 98
# Geometri slot BB FIXED (dari probe battle live) — BEDA dari HV auto-detect yg
# meleset ~45px di BB (start 199 vs 154, pitch 145 vs 152) bikin tap+sampling off.
BB_SLOT_X       = [193, 364, 500, 652, 804, 937, 1089]  # pusat-x ikon troop BB (diukur live dari _battle.png, bukan tebakan)
BB_TROOP_TAP_Y  = 985         # y tap slot troop BB (tengah ikon, sama band kaya HV)
BB_SLOT_ICON_Y  = (950, 1005)  # y-band wajah ikon BB utk cek saturasi (kalibrasi live: aktif 124-148, habis 68-94)

# --- Deploy pasukan ---
BATTLE_SECS   = 180            # timer cadangan: end paksa kalau gak nyampe bintang 1 dalam 3 menit
STAR1_DAMAGE  = 50             # bintang 1 = destruction >= 50% → end battle
MIN_REAL_DAMAGE = 8            # damage < ini di akhir battle = troop cuma mencet2 pinggir /
                              # base full ga ketembus → BUKAN attack sukses, ga di-bump ke stats.
                              # naikin kalau mau lebih ketat (mis. 15 = minimal 1 building hancur).
MAX_DAMAGE_JUMP = 70          # ponytail: cap lompatan damage per read-cycle.
                              # cegah misread sistematis OCR ('9%'->'89%') nge-fake bintang 1.
                              # ceiling 45: army berat clear cepat bisa >45/tick -> 1 read
                              # ditolak, self-correct cycle depan. naikin kalau army tank-heavy.
TROOP_TAP_Y  = 985          # y utk tap slot troop (pilih pasukan)
# Slot troop di battle: posisi FIXED (COC layout konstan @1920x1080), pitch ~145px.
# Kalibrasi dari screenshot battle kalau UI/resolusi beda: ukur pusat tiap ikon.
SLOT_CENTERS    = [231, 376, 521, 667]  # pusat-x 4 slot (giant, barb, archer, goblin)
SLOT_ICON_Y     = (950, 1005)           # y range wajah ikon buat cek saturasi
SLOT_ACTIVE_SAT = 50                    # (legacy)
SLOT_PITCH   = 145          # jarak antar-slot (px). deploy sapu tiap PITCH sepanjang bar                    # sat ikon > ini = masih ada troop; <=0 = habis (abu2)
# Titik deploy: campuran TENGAH (TH rendah, base kecil) + PINGGIR/CORNER
# (TH tinggi, wall+defence numpuk di tengah → harus serang dari pinggir).
# 12 titik, 4 sisi: kiri, kanan, atas, bawah — troops ngepung dari segala arah.
# Jitter ±40px di deploy_troops() bikin natural, gak numpuk di 1 titik.
DEPLOY_POINTS = [
    # Titik aman perimeter terluar (outer grass) di luar garis merah base manapun
    (80, 480), (1840, 480), (960, 45),                     # Sudut kiri, kanan, atas
    (200, 340), (380, 230), (580, 140), (780, 70),         # Diagonal Kiri Atas
    (1140, 70), (1340, 140), (1540, 230), (1720, 340),     # Diagonal Kanan Atas
    (120, 530), (220, 630), (340, 720), (480, 800),       # Diagonal Kiri Bawah
    (1800, 530), (1700, 630), (1580, 720), (1440, 800),   # Diagonal Kanan Bawah
]

# --- Loot-seek deploy (deploy troop ngepung storage, bukan asal 12 titik) ---
# Tujuan bot = farming, jadi arahin troop ke konsentrasi gold/elixir.
# Deteksi: mask warna emas + pink (HSV) di layar base, buang region UI,
# ambil center-of-mass loot → generate titik deploy melingkar di sekitarnya.
# Fallback ke DEPLOY_POINTS statis kalau loot ga kedeteksi.
LOOT_SEEK = True
# HSV range (OpenCV: H 0-179). Dikalibrasi dari screenshot battle TH12-14.
# Sat/Val tinggi biar cuma storage/mine (warna pekat) yg kena, bukan rumput pucat.
GOLD_HSV = ((18, 150, 150), (32, 255, 255))    # emas storage/mine
PINK_HSV = ((145, 90, 120), (172, 255, 255))   # elixir storage pink/magenta
# Region UI yg di-mask (bukan base): (x1,y1,x2,y2). Warna emas/pink UI jangan kehitung.
LOOT_UI_MASK = [
    (0, 0, 360, 340),        # "Available Loot" kiri-atas
    (1560, 0, 1920, 230),    # bar loot kanan-atas
    (0, 880, 1920, 1080),    # troop bar bawah
    (1720, 720, 1920, 1080), # Overall Damage kanan-bawah
    (0, 770, 260, 860),      # tombol Surrender
]
LOOT_BLOB_MIN = 200   # blob warna < ini px = noise rumput/pohon, dibuang (bukan storage)
LOOT_MIN_PX = 2000    # total px loot (stlh filter blob) < ini = base kosong → fallback statis
# LOOT_MAX: farming loot-maksimal. Kalau True, JANGAN end battle di bintang 1 (50%).
# 50% destruction ≠ 50% loot: storage bisa masih utuh. Biarin troop habis dulu biar
# colek storage+collector sebanyak mungkin. Set False kalau mau cepet (end di 50%,
# lebih banyak base/jam tapi loot/base lebih dikit).
LOOT_MAX = True

# --- Threshold loot minimum ---
# Mode filter: "TOTAL" (gold + elixir >= TOTAL_MIN), "EITHER", "BOTH", "DARK"
LOOT_MODE  = "TOTAL"
TOTAL_MIN  = 1000000
GOLD_MIN   = 1000000
ELIXIR_MIN = 1000000
DARK_MIN   = 10000

# --- Dead Base Detection ---
DEAD_BASE_DETECTION = True       # deteksi akun pensiun/unranked
DEAD_BASE_PRIORITY  = True       # serang langsung jika dead base dan loot >= DEAD_BASE_MIN_LOOT
DEAD_BASE_MIN_LOOT  = 500000     # batas minimal loot dead base (mudah di-farm di luar pagar)
LEAGUE_BADGE_REGION = (12, 22, 55, 85)  # region badge liga lawan di battle preview

# --- Auto Wall Upgrade (Anti-Overflow Storage) ---
AUTO_WALL_UPGRADE      = False
WALL_MIN_GOLD          = 5000000    # upgrade wall jika gold di desa >= ini (5M)
WALL_MIN_ELIXIR        = 5000000    # upgrade wall jika elixir di desa >= ini (5M)
WALL_UPGRADE_RESOURCE  = "ANY"     # "GOLD", "ELIXIR", atau "ANY" (preferensi persediaan terbanyak)
WALL_TAP_POINTS        = [(960, 644), (832, 613)]  # Titik wall valid terverifikasi di desa
WALL_SCAN_COOLDOWN     = 60        # Cooldown jika scan tidak menemukan wall (60 detik, bukan 10 menit)
WALL_UPGRADE_GOLD_BTN  = (1065, 895)
WALL_UPGRADE_ELIXIR_BTN= (1275, 895)
WALL_CONFIRM_BTN       = (1342, 905)
VILLAGE_GOLD_REGION    = (1600, 20, 1850, 75)
VILLAGE_ELIXIR_REGION  = (1600, 90, 1850, 145)
BUILDER_COUNT_REGION   = (1710, 800, 1785, 845)

# --- Auto Laboratory Upgrade ---
AUTO_LAB_UPGRADE       = False
LAB_MENU_BTN           = (1820, 930) # tombol progression menu di samping Build
LAB_TAB_BTN            = (1595, 995) # Tab 2 (Army Upgrades / Lab)
LAB_CONFIRM_BTN        = (1342, 885) # tombol hijau Confirm upgrade di modal
LAB_CLOSE_PANEL_BTN    = (1885, 30)  # tombol X merah panel progression
