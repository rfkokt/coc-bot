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

DEVICE = _detect_device()  # nilai awal; lihat __getattr__ utk live-resolve


def __getattr__(name):
    # ponytail: live-resolve DEVICE tiap akses biar kembali setelah BlueStacks
    # restart/ganti port tanpa reload. Field lain kembali ke ImportError default.
    if name == "DEVICE":
        return _detect_device()
    raise AttributeError(name)

# --- Resolusi ---
W, H = 1920, 1080

# --- Region OCR loot (x1, y1, x2, y2) - from OCR detection ---
GOLD_REGION   = (95, 150, 320, 192)   # x1 geser kanan biar gak kena icon koin (misread 5000->500); x2=320 muat 7 digit TH tinggi (1,234,567)
ELIXIR_REGION = (93, 208, 320, 248)   # x2=320: TH13 loot 7 digit lebih lebar, jangan kepotong
DARK_REGION   = (60, 270, 420, 335)   # kosong di base TH rendah, aman
DAMAGE_REGION = (1760, 760, 1910, 850)  # "Overall Damage" persen di kanan bawah saat battle
COUNTDOWN_REGION = (760, 20, 1160, 120)  # teks "Battle starts in" tengah-atas saat PREVIEW (troop belum bisa deploy)
PLAYER_NAME_REGION = (135, 25, 360, 60)  # nama akun di home village (di sblh XP-level), kiri-atas. OCR di-upscale 3x krn teks kecil
# --- Region OCR 'You got' di RESULT SCREEN (Victory/Defeat) ---
# Loot AKTUAL yg didapat (bukan available loot saat search). 3 baris angka putih
# di tengah layar hasil, kanan label 'You got:'. Dikalibrasi dari result @1920x1080.
# x lebar krn 7 digit; y jarak antar-baris ~88px.
RESULT_GOLD_REGION   = (745, 435, 1015, 500)
RESULT_ELIXIR_REGION = (745, 523, 1015, 588)
RESULT_DARK_REGION   = (745, 590, 1015, 660)   # digeser naik ~21px: region lama (611) angka kepotong -> OCR baca sampah. kosong kalau base ga ada dark storage kena

# --- Tombol ---
NEXT_BTN       = (1720, 745)   # Next (skip base) — center teks, jauh dari tepi/angka
END_ATTACK_BTN = (140, 805)    # End Battle / Surrender (kiri-bawah saat battle)
SURRENDER_OKAY_BTN = (1160, 695)  # tombol Okay hijau di popup konfirmasi "Surrender?"
ATTACK_BTN     = (127, 1019)    # Attack di village → buka menu
FIND_MATCH_BTN = (433, 771)    # Find a Match di menu
START_SEARCH_BTN = (1696, 964)  # tombol Attack hijau di army prep → cari enemy
RETURN_HOME_BTN= (960, 936)    # Return Home stlh battle
POPUP_CLOSE_BTN= (1855, 96)    # tombol X merah kanan-atas popup (Challenges/Recipes/Shop/dll) — center X asli terukur
POPUP_X_REGION = (1810, 55, 1905, 130)  # region tombol X — kalau merah → ada popup. bbox X asli x:[1822-1888] y:[67-119]
EMPTY_TAP      = (700, 180)              # rumput kosong — tap buat deselect building popup, aman di village bersih
ATTACK_LABEL_REGION = (40, 990, 210, 1050)  # teks "Attack!" kiri-bawah = tanda di village screen

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
    (320, 500), (320, 680),    # kiri atas, kiri bawah
    (1600, 500), (1600, 680),  # kanan atas, kanan bawah
    (600, 250), (1320, 250),   # atas kiri, atas kanan
    (600, 830), (1320, 830),   # bawah kiri, bawah kanan
    (560, 620), (1360, 620),   # tengah kiri, tengah kanan (TH rendah)
    (960, 350), (960, 750),    # tengah atas, tengah bawah (TH rendah)
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
# TH1 loot mentok ~6-8K. Naikin ke 300K+ saat TH tinggi.
GOLD_MIN   = 500000
ELIXIR_MIN = 500000
DARK_MIN   = 200
