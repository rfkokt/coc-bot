import time, random
import os
from datetime import datetime
import adb_controller as adb
import ocr, config
import subprocess
from human import human_delay, think_pause
from scheduler import should_be_active
import stats
import cv2, numpy as np
import re

# Mode dari env (konsisten sama COC_IGNORE_SCHEDULE). force_loot = serang base pertama,
# abaikan threshold loot. default = normal (nunggu loot >= GOLD_MIN/ELIXIR_MIN).
MODE = os.environ.get("COC_MODE", "normal").lower()

# Nama akun aktif — di-deteksi otomatis dari home village di awal sesi (OCR).
# Semua loot & waktu ke-tag ke nama ini. Default "unknown" sampai kebaca.
ACCOUNT = "unknown"

# reuse 1 instance EasyOCR dari ocr.py — jangan load model kedua (boros ~1GB RAM)

def log(msg):
    """Print bertimestamp + flush — biar dashboard tail keliatan real-time."""
    print(f"[{datetime.now():%H:%M:%S}] {msg}", flush=True)

def _back():
    subprocess.run([config.ADB_PATH, "-s", config.DEVICE, "shell", "input", "keyevent", "4"])

def screen_text(img):
    return ' '.join(ocr.reader.readtext(img, detail=0)).lower()

def detect_account(img):
    """OCR nama akun dari home village (region kecil, teks di-upscale 3x biar kebaca).
    Return nama string, atau None kalau ga kebaca."""
    x1, y1, x2, y2 = config.PLAYER_NAME_REGION
    crop = img[y1:y2, x1:x2]
    big = cv2.resize(crop, None, fx=3, fy=3, interpolation=cv2.INTER_CUBIC)
    tokens = ocr.reader.readtext(big, detail=0)
    name = ''.join(tokens).strip()
    return name or None

def in_battle_screen(img):
    """Cek akurat & cepat (<5ms, HSV mask tanpa OCR lambat):
    Layar battle musuh SELALU memiliki tombol merah 'End Battle' di kiri-bawah (y: 780..840, x: 80..200).
    Saat cari lawan (matchmaking), juga ada tombol oranye 'Next' di kanan-bawah.
    Jika tombol ini tidak ada, BUKAN layar battle (mencegah false positive di village/modal)."""
    if img is None:
        return False
    # Tombol merah End Battle di kiri-bawah
    crop_end = img[780:840, 80:200]
    hsv_end = cv2.cvtColor(crop_end, cv2.COLOR_BGR2HSV)
    red_end = (((hsv_end[:, :, 0] < 10) | (hsv_end[:, :, 0] > 170)) & (hsv_end[:, :, 1] > 140) & (hsv_end[:, :, 2] > 140)).sum()
    if red_end > 1500:
        return True

    # Tombol oranye Next di kanan-bawah saat matchmaking preview
    crop_next = img[730:820, 1650:1880]
    hsv_next = cv2.cvtColor(crop_next, cv2.COLOR_BGR2HSV)
    orange_next = ((hsv_next[:, :, 0] >= 10) & (hsv_next[:, :, 0] <= 25) & (hsv_next[:, :, 1] > 150) & (hsv_next[:, :, 2] > 150)).sum()
    if orange_next > 5000:
        return True

    return False

def in_army_confirm_screen(img):
    """Mendeteksi apakah modal konfirmasi 'My Army' muncul (karena spell/siege/cc belum penuh).
    Memiliki tombol hijau 'Attack!' berbentuk rounded rect di kanan-bawah modal (y: 920..1010, x: 1500..1900)."""
    if img is None or img.shape[0] < 1010 or img.shape[1] < 1900:
        return False
    crop_btn = img[920:1010, 1500:1900]
    hsv = cv2.cvtColor(crop_btn, cv2.COLOR_BGR2HSV)
    green_mask = ((hsv[:, :, 0] >= 35) & (hsv[:, :, 0] <= 85) & (hsv[:, :, 1] > 140) & (hsv[:, :, 2] > 140)).astype(np.uint8)
    kernel = cv2.getStructuringElement(cv2.MORPH_RECT, (15, 15))
    closed = cv2.morphologyEx(green_mask, cv2.MORPH_CLOSE, kernel)
    cnts, _ = cv2.findContours(closed, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)
    for c in cnts:
        x, y, w, h = cv2.boundingRect(c)
        if w >= 140 and h >= 45:
            return True
    return False

def in_builder_base(img):
    """Mendeteksi apakah saat ini layar berada di Desa Malam (Builder Base)."""
    if img is None or img.shape[0] < 990 or img.shape[1] < 1910:
        return False
    if get_center_confirm_btn(img) is not None or is_chest_screen(img):
        return False  # Result battle, chest, atau popup reward
    crop_build = img[880:990, 1800:1910]
    hsv = cv2.cvtColor(crop_build, cv2.COLOR_BGR2HSV)
    yellow = ((hsv[:, :, 0] >= 15) & (hsv[:, :, 0] <= 35) & (hsv[:, :, 1] > 120) & (hsv[:, :, 2] > 150)).sum()
    if yellow > 2000:
        return False  # Ada tombol Build kuning = Home Village!
    crop_btn = img[800:970, 20:115]
    return crop_btn.mean() > 70

def in_village(img):
    """Cek di village utama: teks 'Attack'/'Battle' muncul di tombol kiri-bawah,
    atau tombol Build kuning di kanan-bawah, BUKAN di Builder Base, dan TIDAK ADA popup / modal yg menutupi."""
    if img is None or img.shape[0] < 1040 or img.shape[1] < 1910:
        return False
    if in_builder_base(img):
        return False
    if has_popup(img) or in_army_confirm_screen(img):
        return False
    if get_center_confirm_btn(img) is not None:
        return False  # Masih ada tombol Return Home / Continue / Okay
    if is_chest_screen(img):
        return False

    # Deteksi cepat via tombol Build kuning khas Home Village (1800:1910, 880:990)
    crop_build = img[880:990, 1800:1910]
    hsv_b = cv2.cvtColor(crop_build, cv2.COLOR_BGR2HSV)
    yellow = ((hsv_b[:, :, 0] >= 15) & (hsv_b[:, :, 0] <= 35) & (hsv_b[:, :, 1] > 120) & (hsv_b[:, :, 2] > 150)).sum()
    if yellow > 5000:
        return True

    x1, y1, x2, y2 = getattr(config, "ATTACK_LABEL_REGION", (40, 990, 210, 1050))
    txt = ' '.join(ocr.reader.readtext(img[y1:y2, x1:x2], detail=0)).lower()
    return any(w in txt for w in ['attack', 'batt', 'bat', 'baf', 'bbaf', 'bbat'])

def read_result_loot(img):
    """Baca loot AKTUAL 'You got:' di result screen (Victory/Defeat).
    Ini loot beneran masuk ke storage — beda dari available-loot saat search
    (yg cuma potensi max, ga semua ke-ambil). Return (gold, elixir, dark)."""
    gold = ocr.read_region(img, config.RESULT_GOLD_REGION) or 0
    elixir = ocr.read_region(img, config.RESULT_ELIXIR_REGION) or 0
    dark = ocr.read_region(img, config.RESULT_DARK_REGION) or 0
    return gold, elixir, dark

def get_center_confirm_btn(img):
    """Mendeteksi tombol hijau konfirmasi/lanjut di bagian tengah bawah layar
    (Return Home pada result battle, CONTINUE pada hadiah peti, atau OKAY pada Star Bonus).
    Menggunakan deteksi kontur hijau rounded rectangle presisi tinggi tanpa delay OCR."""
    if img is None or img.shape[0] < 1040 or img.shape[1] < 1180:
        return None
    crop = img[780:1040, 750:1180]
    hsv = cv2.cvtColor(crop, cv2.COLOR_BGR2HSV)
    green = ((hsv[:, :, 0] >= 35) & (hsv[:, :, 0] <= 85) & (hsv[:, :, 1] > 140) & (hsv[:, :, 2] > 120)).astype(np.uint8)
    kernel = cv2.getStructuringElement(cv2.MORPH_RECT, (15, 15))
    closed = cv2.morphologyEx(green, cv2.MORPH_CLOSE, kernel)
    cnts, _ = cv2.findContours(closed, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)
    for c in sorted(cnts, key=cv2.contourArea, reverse=True):
        x, y, w, h = cv2.boundingRect(c)
        area = cv2.contourArea(c)
        solidity = area / (w * h) if w * h > 0 else 0
        if 180 <= w <= 400 and 50 <= h <= 160 and solidity >= 0.85 and area >= 12000:
            return (750 + x + w // 2, 780 + y + h // 2)
    return None

def is_chest_screen(img):
    """Mendeteksi layar hadiah peti (Treasure Chest / Star Bonus) saat peti menunggu diketuk.
    Ditandai dengan background fokus/gelap dan teks 'Tap!'/'Ketuk!' di atas peti (960, 520)."""
    if img is None or img.shape[0] < 350 or img.shape[1] < 1150:
        return False
    crop = img[200:320, 800:1120]
    hsv = cv2.cvtColor(crop, cv2.COLOR_BGR2HSV)
    bright_pixels = ((hsv[:, :, 2] > 220) & (hsv[:, :, 1] < 180)).sum()
    if bright_pixels > 3000:
        txt = ' '.join(ocr.reader.readtext(crop, detail=0)).lower()
        if any(w in txt for w in ['tap', 'ketuk', 'peti', 'chest', 'common', 'rare', 'epic', 'legendary']):
            return True
    return False

def handle_chest_and_rewards(img):
    """Mengecek dan menangani hadiah peti (Treasure Chest) atau tombol konfirmasi reward (Continue / Okay / Return Home).
    Return True jika ada aksi yang dilakukan, False jika layar bukan peti/reward."""
    if img is None:
        return False

    # 1. Cek tombol hijau tengah (Return Home / Continue / Okay)
    btn = get_center_confirm_btn(img)
    if btn is not None:
        log(f"  tombol konfirmasi/reward hijau terdeteksi di {btn}, tap...")
        adb.tap(*btn)
        human_delay(1.5, 0.3)
        return True

    # 2. Cek apakah peti menunggu di-tap (Tap! / Ketuk! peti di 960, 520)
    if is_chest_screen(img):
        log("  🎁 layar hadiah peti terdeteksi! Mengetuk peti...")
        for _ in range(5):
            adb.tap(960, 520)
            human_delay(0.35, 0.05)
        human_delay(1.5, 0.3)
        return True

    return False

def recover(img):
    """Popup/layar nyangkut → tutup popup atau back sampai balik ke layar dikenal."""
    for _ in range(3):
        if in_battle_screen(img):
            return True
        if handle_chest_and_rewards(img):
            pass
        elif has_popup(img):
            adb.tap(*config.POPUP_CLOSE_BTN)   # panel X merah
        else:
            adb.tap(*config.EMPTY_TAP)         # popup building -> tap rumput, JANGAN back (back = exit game)
        human_delay(1.2, 0.3)
        img = adb.screenshot()
    return False

def loot_enough(gold, elixir, dark):
    mode = getattr(config, "LOOT_MODE", "TOTAL").upper()
    if mode == "TOTAL":
        return (gold + elixir) >= getattr(config, "TOTAL_MIN", 1000000)
    elif mode == "EITHER":
        return gold >= config.GOLD_MIN or elixir >= config.ELIXIR_MIN
    elif mode == "BOTH":
        return gold >= config.GOLD_MIN and elixir >= config.ELIXIR_MIN
    elif mode == "DARK":
        return dark >= config.DARK_MIN
    return (gold + elixir) >= getattr(config, "TOTAL_MIN", 1000000)

def is_dead_base(img):
    """Deteksi dead base / akun pensiun berdasarkan badge liga unranked (abu-abu).
    Di COC battle search, player tanpa liga aktif memiliki badge perisai abu-abu
    dengan saturasi warna rendah (< 95), sementara pemain aktif di bronze/silver/gold/dll
    memiliki badge liga berwarna (sat > 110)."""
    if img is None:
        return False
    x1, y1, x2, y2 = getattr(config, "LEAGUE_BADGE_REGION", (12, 22, 55, 85))
    badge = img[y1:y2, x1:x2]
    if badge.size == 0:
        return False
    hsv = cv2.cvtColor(badge, cv2.COLOR_BGR2HSV)
    mean_sat = float(hsv[:, :, 1].mean())
    return mean_sat < 95

def read_damage(prev=None):
    """Baca destruction %. 2 sampel cepat langsung dari DAMAGE_REGION via regex."""
    vals = []
    x1, y1, x2, y2 = config.DAMAGE_REGION
    for _ in range(2):
        screen = adb.screenshot()
        if screen is None:
            continue
        crop = screen[y1:y2, x1:x2]
        if crop.size > 0:
            tokens = ocr.reader.readtext(crop, detail=0, allowlist='0123456789%')
            for t in tokens:
                m = re.search(r'(\d+)', t)
                if m:
                    val = int(m.group(1))
                    if 0 <= val <= 100:
                        vals.append(val)
        time.sleep(0.1)
    if not vals:
        return None
    top = max(vals)
    if prev is not None and top > prev + config.MAX_DAMAGE_JUMP:
        return None                        # lompatan ekstrem = misread sistematis
    return top

def reached_star1(prev=None):
    """Beneran bintang 1? read 2x, dua2nya >= STAR1_DAMAGE = konfirmasi.
    Cegah misread lolos -> end battle prematur padahal belum bintang.
    prev = damage terakhir dikenal → ikut guard lompatan."""
    d1 = read_damage(prev)
    if d1 is None or d1 < config.STAR1_DAMAGE:
        return False
    d2 = read_damage(d1)
    return d2 is not None and d2 >= config.STAR1_DAMAGE

def detect_active_slots(img):
    """Deteksi titik-tap semua slot troop/hero/spell/siege sepanjang bar.
    Opsi A (farming): deploy SAPU RATA — gak peduli jenis, semua di-deploy.
    Bar mulai kiri (~x138), pitch ~SLOT_PITCH; jumlah slot beda tiap TH
    (TH rendah ~4, TH13 ~10). Deteksi rentang bar via 'kolom berisi ikon'
    (terang & bukan hijau rumput), lalu bagi titik tap tiap SLOT_PITCH.
    Skip titik yg jatuh di rumput (hijau) — biar gak tap area kosong/dashed.
    Slot habis (abu2) tetap masuk; tap-nya diabaikan game (aman).
    sapu-rata robust ke N slot berapapun; presisi per-ikon gak perlu buat farming."""
    y1, y2 = config.SLOT_ICON_Y
    band = img[y1:y2, :1920]
    b, g, r = [band[:, :, i].astype(float) for i in range(3)]
    val = band.max(axis=2).astype(float)
    greenish = (g > r + 15) & (g > b + 15)           # rumput
    isslot = ((val > 90) & ~greenish).mean(axis=0)    # per-kolom: fraksi 'ikon'
    sm = np.convolve(isslot, np.ones(21) / 21, mode='same')
    xs = np.where(sm > 0.4)[0]
    if len(xs) < 10:                                  # ga ada bar = troop habis
        return []
    x0, x1 = int(xs[0]), int(xs[-1])
    active = []
    cx = x0 + config.SLOT_PITCH // 2
    while cx <= x1:
        # verifikasi titik ini beneran ikon (bukan rumput di gap dashed)
        px = band[:, max(0, cx - 30):cx + 30]
        pg = (px[:, :, 1].astype(float) > px[:, :, 2].astype(float) + 15) & \
             (px[:, :, 1].astype(float) > px[:, :, 0].astype(float) + 15)
        if pg.mean() < 0.5:                           # <50% hijau = slot valid
            active.append({'x': int(cx), 'y': config.TROOP_TAP_Y})
        cx += config.SLOT_PITCH
    return active


def detect_loot_center(img):
    """Cari pusat konsentrasi loot (gold+elixir) di layar base musuh via HSV mask.
    Return (cx, cy) center-of-mass pixel loot, atau None kalau ga cukup loot kebaca.
    Buang region UI (bar loot, available-loot, troop bar) biar warna emas/pink UI
    ga ke-hitung. Dipake buat arahin deploy ke storage — tujuan bot = farming."""
    if img is None:
        return None
    hsv = cv2.cvtColor(img, cv2.COLOR_BGR2HSV)
    (gl, gh), (pl, ph) = config.GOLD_HSV, config.PINK_HSV
    gold = cv2.inRange(hsv, np.array(gl), np.array(gh))
    # buang kuning-kehijauan (rumput kena sinar, pohon terang): emas storage r >> g,
    # rumput terang g ≈ r. Tanpa ini base berpohon bikin mask muncrat → center meleset.
    g, r = img[:, :, 1].astype(int), img[:, :, 2].astype(int)
    gold[g > r - 10] = 0
    pink = cv2.inRange(hsv, np.array(pl), np.array(ph))
    mask = gold | pink
    for x1, y1, x2, y2 in config.LOOT_UI_MASK:   # nol-in region UI
        mask[y1:y2, x1:x2] = 0
    # Filter blob: storage/mine = gumpalan PADAT >= LOOT_BLOB_MIN px. Noise rumput/pohon
    # yg lolos warna = bintik kecil tersebar → dibuang, biar center bener di storage.
    n, lbl, st, _ = cv2.connectedComponentsWithStats(mask, 8)
    keep = np.zeros_like(mask)
    for i in range(1, n):
        if st[i, cv2.CC_STAT_AREA] >= config.LOOT_BLOB_MIN:
            keep[lbl == i] = 255
    ys, xs = np.where(keep > 0)
    if len(xs) < config.LOOT_MIN_PX:             # base kosong / loot ga kebaca
        return None
    return int(xs.mean()), int(ys.mean())


def loot_deploy_points(center):
    """Titik deploy di perimeter luar arena (outer grass), di luar garis merah base musuh.
    PENTING: Arena CoC berbentuk diamond (belah ketupat isometrik). Titik harus mengikuti
    sabuk rumput terluar (outer perimeter) agar troop SELALU bisa deploy dan TIDAK ditolak
    karena mengenai bangunan/area merah, meskipun kamera tidak full zoom-out."""
    cx, cy = center
    pts = [
        # Sudut ekstrim
        (80, 480), (1840, 480), (960, 45),
        # Diagonal Kiri Atas (Top-Left)
        (200, 340), (380, 230), (580, 140), (780, 70),
        # Diagonal Kanan Atas (Top-Right)
        (1140, 70), (1340, 140), (1540, 230), (1720, 340),
        # Diagonal Kiri Bawah (Bottom-Left)
        (120, 530), (220, 630), (340, 720), (480, 800),
        # Diagonal Kanan Bawah (Bottom-Right)
        (1800, 530), (1700, 630), (1580, 720), (1440, 800),
    ]
    # Urutkan berdasarkan jarak terdekat ke konsentrasi loot (storage)
    pts.sort(key=lambda p: (p[0] - cx) ** 2 + (p[1] - cy) ** 2)
    return [(int(x), int(y)) for x, y in pts]


def in_preview(img):
    """PREVIEW screen (countdown 'Battle starts in') — troop BELUM bisa deploy.
    Tap troop/base saat ini diabaikan game → damage 0. Harus tunggu / skip dulu."""
    x1, y1, x2, y2 = config.COUNTDOWN_REGION
    txt = ' '.join(ocr.reader.readtext(img[y1:y2, x1:x2], detail=0)).lower()
    return 'starts in' in txt or 'battle start' in txt


def detect_speedup_btn(img):
    """Mendeteksi tombol Fast-Forward (1x / 2x / 4x) yang muncul di kanan layar saat battle.
    Return (x, y) koordinat tombol jika terdeteksi, atau None jika belum muncul."""
    if img is None or img.shape[:2] != (1080, 1920):
        return None
    # Region tombol di kanan atas panel Overall Damage: x: 1770..1920, y: 510..640
    crop = img[510:640, 1770:1920]
    hsv = cv2.cvtColor(crop, cv2.COLOR_BGR2HSV)
    # Warna hijau muda khas tombol speed-up CoC: H 35..55, S 70..220, V 170..255
    mask = (hsv[:, :, 0] >= 35) & (hsv[:, :, 0] <= 55) & (hsv[:, :, 1] >= 70) & (hsv[:, :, 2] >= 170)
    if mask.sum() > 2000:
        ys, xs = np.where(mask)
        return (1770 + int(xs.mean()), 510 + int(ys.mean()))
    return None


def check_and_apply_fast_forward(img):
    """Mengecek dan menaikkan kecepatan battle ke 4x jika tombol speed-up sudah muncul.
    Returns:
        True jika sudah terkonfirmasi di kecepatan 4x.
        False jika belum muncul, belum terbaca, atau masih dalam proses perpindahan."""
    btn_pt = detect_speedup_btn(img)
    if not btn_pt:
        return False
    bx, by = btn_pt
    crop = img[max(0, by - 50):min(1080, by + 50), max(0, bx - 60):min(1920, bx + 60)]
    tokens = ocr.reader.readtext(crop, detail=0, allowlist='124xX') if getattr(ocr, 'reader', None) else []
    txt = ''.join(tokens).lower()
    if '4x' in txt:
        return True  # sudah terkonfirmasi di 4x speed
    elif '2x' in txt:
        log("  ⏩ Tombol speed-up terdeteksi (2x) → tap 1x ke 4x...")
        adb.tap_fast(bx, by)
        return False
    elif '1x' in txt:
        log("  ⏩ Tombol speed-up muncul (1x) → aktifkan percepatan 4x...")
        adb.tap_fast(bx, by)
        time.sleep(0.12)
        adb.tap_fast(bx, by)
        return False
    return False


def wait_battle_ready():
    """Di Clash of Clans, menurunkan pasukan langsung memulai battle secara instan.
    Tidak perlu menunggu countdown 30s habis."""
    return True


def deploy_troops(loot=(0, 0, 0)):
    # loot = (gold, elixir, dark) base yg diserang → dicatat ke stats lifetime.
    # Deploy SEMUA troop: tiap slot di-tap banyak kali (1 tap = 1 troop keluar),
    # tersebar di beberapa titik biar gak numpuk (rawan splash).
    # Loop deploy diulang sampai BATTLE_SECS habis (3 menit) — biar troop yg
    # baru siap (CC drop, cooldown, animasi) tetep ke-deploy sampai stack kosong.
    # tap berlebih aman — kalau troop slot habis, tap kosong diabaikan game.
    from human import jitter
    log("  ⚔ MENYERANG, deploy troops...")
    wait_battle_ready()
    pts = None
    if config.LOOT_SEEK:
        shot = adb.screenshot()
        center = detect_loot_center(shot) if shot is not None else None
        if center:
            pts = loot_deploy_points(center)
            log(f"  🎯 loot-seek: pusat loot {center}, deploy ngepung storage")
    if pts is None:
        pts = list(config.DEPLOY_POINTS)
        log("  deploy statis (loot-seek off/ga kedeteksi)")
    # Sort by y → atas duluan (hindari boosted heroes di bawah base)
    pts = sorted(pts, key=lambda p: p[1])
    deadline = time.time() + config.BATTLE_SECS
    dmg = 0
    fast_forward_active = False
    # Baca komposisi troop SEKALI di awal (layar battle baru load = bar bersih,
    # belum ada efek ledakan yg bikin variance kacau). Simpan buat sepanjang deploy.
    roster = detect_active_slots(adb.screenshot())
    if roster:
        log(f"  bawa {len(roster)} slot troop aktif")
    while time.time() < deadline:
        shot = adb.screenshot()
        if not in_battle_screen(shot):  # game auto-end / result screen → stop nge-tap layar yg salah
            log("  battle udah berakhir (auto-end/result), stop deploy")
            break
        if not fast_forward_active and check_and_apply_fast_forward(shot):
            fast_forward_active = True
            log("  ⚡ Kecepatan battle 4x aktif!")
        active = detect_active_slots(shot)
        if not active:                  # semua slot abu2 → troop habis di-deploy
            log("  semua troop udah diturunkan, tunggu troop selesai bertarung...")
            if not fast_forward_active and check_and_apply_fast_forward(shot):
                fast_forward_active = True
                log("  ⚡ Kecepatan battle 4x aktif!")
            break
        log(f"  ⚔ MENYERANG ({len(active)} slot aktif), turunkan SEMUA cepat...")
        stop = False
        for slot in active:                 # SAPU semua slot tanpa jeda cek damage
            adb.tap(slot['x'], slot['y'])   # pilih 1 jenis pasukan
            # Sebar tiap slot ke SEMUA titik ring biar loot dari banyak sumber ke-hit.
            for pt in pts:                  # 1 tap per titik = pasukan tersebar rata
                x, y = jitter(*pt, radius=40)
                adb.tap_fast(x, y)
                adb.tap_fast(*jitter(*pt, radius=40))  # 2 troop/titik, minim delay
            # Deploy tersebar di perimeter aman (hindari tap tengah base agar tidak kena red area)
            # cek ringan tiap slot: battle kelar di tengah → stop
            if not in_battle_screen(adb.screenshot()):
                stop = True; break
        if stop:
            log("  battle berakhir saat deploy, stop")
            break
        human_delay(1.5, 0.5)           # jeda singkat lalu ulang buat troop yg baru siap (CC/cooldown)
        if not fast_forward_active:
            s_ff = adb.screenshot()
            if check_and_apply_fast_forward(s_ff):
                fast_forward_active = True
                log("  ⚡ Kecepatan battle 4x aktif!")
        d = read_damage(dmg or None)
        if d is not None and d > dmg:   # simpan MAX, jangan turun (result screen = 0)
            dmg = d
        log(f"  nyerang... damage={dmg}%")
        # LOOT_MAX: farming loot-maks → JANGAN end di bintang 1. 50% destruction ≠
        # 50% loot (storage bisa masih utuh). Biarin troop habis dulu (fase watch)
        # biar colek storage sebanyak mungkin. Kalau off, end cepet di bintang 1.
        if not config.LOOT_MAX and dmg >= config.STAR1_DAMAGE and reached_star1(dmg):
            log(f"  → bintang 1 ({dmg}%), end battle")
            break

    # Fase WATCH: troop udah semua di lapangan, damage masih naik selama troop nyerang.
    # Tungguin sampai damage berhenti naik (troop mati/kelar) atau bintang1/timer habis.
    # 3x stagnan berturut = battle beku → end. Naikin kalau end kecepetan.
    stagnan = 0
    hero_ability_triggered = False
    battle_time_start = time.time()

    # LOOT_MAX: tunggu sampai troop mati/kelar (stagnan) atau timer habis — abaikan
    # STAR1 biar loot maksimal. Non-LOOT_MAX: berhenti begitu nyampe bintang 1.
    while time.time() < deadline and (config.LOOT_MAX or dmg < config.STAR1_DAMAGE):
        shot = adb.screenshot()
        if not in_battle_screen(shot):   # battle auto-end di fase watch → stop nunggu
            log("  battle udah berakhir, stop watch")
            break

        # Fast-Forward 4x check
        if not fast_forward_active and check_and_apply_fast_forward(shot):
            fast_forward_active = True
            log("  ⚡ Kecepatan battle 4x aktif!")

        # Trigger hero abilities setelah ~15 detik bertarung (atau ~6 detik jika 4x speed aktif)
        hero_delay = 6 if fast_forward_active else 15
        if not hero_ability_triggered and (time.time() - battle_time_start >= hero_delay):
            log("  ⚡ trigger kemampuan khusus hero (Hero Abilities)...")
            for slot in (roster or []):
                adb.tap_fast(slot['x'], slot['y'])
                time.sleep(0.08)
            hero_ability_triggered = True

        human_delay(3, 1)               # kasih waktu troop nyerang
        d = read_damage(dmg or None)
        if d is None:                   # OCR ga konsisten / misread lompat -> skip, jangan stagnan
            continue
        if d > dmg:
            log(f"  troop masih nyerang... damage={d}%")
            dmg = d
            stagnan = 0
        else:
            stagnan += 1
            log(f"  damage stagnan {stagnan}/3 ({d}%)")
            if stagnan >= 3:            # 3x baca ga naik → troop kelar, battle selesai
                break
    if dmg >= config.STAR1_DAMAGE:
        log(f"  → bintang 1 ({dmg}%)")
    # Base full / troop cuma mencet2 pinggir → damage nyaris 0. Itu BUKAN nyerang.
    # Jangan hitung sebagai attack sukses (dulu bot nganggep udah nyerang @0%).
    real = dmg >= config.MIN_REAL_DAMAGE
    if not real:
        log(f"  ⚠ damage cuma {dmg}% (< {config.MIN_REAL_DAMAGE}%) — troop ga nembus, GAGAL nyerang")
    log(f"  battle selesai (damage akhir {dmg}%), end attack...")
    # loot dicatat dari RESULT SCREEN (loot aktual masuk storage), bukan available-loot
    # saat search (yg cuma potensi max). Dilakukan di end_battle_to_village pas result kebaca.
    end_battle_to_village(record=real, fallback_loot=loot)

def end_battle_to_village(record=False, fallback_loot=(0, 0, 0)):
    """Keluar dari battle balik ke village. Loop ADAPTIF: tiap iterasi cek layar,
    tap tombol yang sesuai. Path: masih di battle (Surrender → popup Okay),
    result screen (Return Home), peti hadiah/Star Bonus (Tap peti / Continue / Okay),
    atau udah village (selesai).
    Kalau record=True: baca loot AKTUAL 'You got:' di result screen SEBELUM Return Home,
    lalu catat ke stats. fallback_loot (available-loot saat search) dipakai kalau
    OCR result screen gagal baca (0 semua)."""
    recorded = False
    for i in range(15):
        img = adb.screenshot()
        if img is None:
            human_delay(1); continue
        if in_village(img):                 # ✓ udah pulang
            log("  → kembali ke village")
            collect_village_resources()
            if getattr(config, "AUTO_WALL_UPGRADE", False):
                auto_upgrade_walls()
            if getattr(config, "AUTO_LAB_UPGRADE", False):
                auto_upgrade_lab()
            return
        if in_battle_screen(img):           # masih di enemy base → Surrender + konfirmasi Okay
            log("  masih di battle, Surrender...")
            adb.tap(*config.END_ATTACK_BTN)     # buka popup "Surrender?"
            human_delay(1.2, 0.3)
            adb.tap(*config.SURRENDER_OKAY_BTN)  # tap Okay hijau di popup
            human_delay(1.5, 0.3)
            continue

        # Baca loot aktual di result screen SEBELUM menekan tombol pulang/reward
        if record and not recorded:
            g, e, d = read_result_loot(img)
            if g > 0 or e > 0 or d > 0:
                log(f"  loot aktual: gold={g:,} elixir={e:,} dark={d:,}")
                stats.bump(account=ACCOUNT, gold=g, elixir=e, dark=d, attack=1)
                recorded = True

        # Handle peti hadiah & tombol konfirmasi (Return Home / Continue / Okay / Chest tap)
        if handle_chest_and_rewards(img):
            continue

        # Handle popup panel atau modal nyangkut saat transisi balik ke desa
        if has_popup(img) or in_army_confirm_screen(img):
            log("  popup panel / modal terdeteksi di end battle, tutup X...")
            close_xy = get_popup_close_coord(img)
            adb.tap(*close_xy)
            human_delay(1.2, 0.3)
            continue

        # Fallback jika belum terdeteksi kontur (misal transisi layar result)
        if record and not recorded:
            g, e, d = fallback_loot
            log(f"  result OCR kosong, catat available-loot {g:,}/{e:,}/{d:,}")
            stats.bump(account=ACCOUNT, gold=g, elixir=e, dark=d, attack=1)
            recorded = True
        log("  result screen / transisi, Return Home...")
        adb.tap(*config.RETURN_HOME_BTN)
        human_delay(2, 0.5)
    log("  ⚠ STUCK end battle — gagal balik village")

def collect_village_resources():
    """Koleksi otomatis hasil gold mine, elixir collector, dan dark drill."""
    if not config.AUTO_COLLECT_RESOURCES:
        return
    log("  🧺 mengumpulkan resource desa (gold, elixir, dark)...")
    for btn in [config.GOLD_COLLECTOR_BTN, config.ELIXIR_COLLECTOR_BTN, config.DARK_COLLECTOR_BTN]:
        adb.tap(*btn)
        human_delay(0.3, 0.1)
    adb.tap(*config.EMPTY_TAP)

def read_storage_amount(screen, region):
    """Membaca angka gold/elixir dari storage bar desa."""
    if screen is None:
        return 0
    x1, y1, x2, y2 = region
    crop = screen[y1:y2, x1:x2]
    if crop.size == 0:
        return 0
    hsv = cv2.cvtColor(crop, cv2.COLOR_BGR2HSV)
    white_mask = ((hsv[:, :, 1] < 45) & (hsv[:, :, 2] > 190)).astype('uint8') * 255
    kernel = cv2.getStructuringElement(cv2.MORPH_RECT, (2, 2))
    mask = cv2.dilate(white_mask, kernel)
    big = cv2.resize(mask, None, fx=2, fy=2, interpolation=cv2.INTER_NEAREST)
    tokens = ocr.reader.readtext(big, detail=0, allowlist='0123456789 ')
    if not tokens:
        big_raw = cv2.resize(crop, None, fx=2, fy=2, interpolation=cv2.INTER_CUBIC)
        tokens = ocr.reader.readtext(big_raw, detail=0, allowlist='0123456789 ')
    digits = ''.join(re.sub(r'[^0-9]', '', t) for t in tokens)
    val = int(digits) if digits else 0
    # Sanity guard: storage CoC maksimal ~22jt. Jika >25jt, ada angka noise (misal 53jt padahal 3.5jt atau 5.3jt)
    if val > 25000000 and len(digits) >= 8:
        alt1 = int(digits[1:])
        alt2 = int(digits[:-1])
        if alt1 <= 25000000:
            val = alt1
        elif alt2 <= 25000000:
            val = alt2
    return val

def get_free_builders(screen):
    """Mengecek jumlah builder yang sedang bebas."""
    if screen is None:
        return 1
    x1, y1, x2, y2 = getattr(config, "BUILDER_COUNT_REGION", (1710, 800, 1785, 845))
    crop = screen[y1:y2, x1:x2]
    if crop.size == 0:
        return 1
    tokens = ocr.reader.readtext(crop, detail=0, allowlist='0123456789/')
    txt = ''.join(tokens).strip()
    if not txt:
        return 1
    if '/' in txt:
        try:
            return int(txt.split('/')[0])
        except ValueError:
            pass
    if txt[0].isdigit():
        return int(txt[0])
    return 1

CACHED_WALL_POINT = None
LAST_WALL_SCAN_TIME = 0

def generate_wall_scan_grid():
    """Menghasilkan titik pemindaian otomatis di sepanjang zona kompartemen desa (isometric grid)."""
    import math
    center_x, center_y = 960, 540
    # Jarak cincin dari pusat desa (radius cincin dalam ke luar)
    radii = [180, 260, 340, 420, 500]
    angles = [0, 45, 90, 135, 180, 225, 270, 315]
    points = []
    for r in radii:
        for a in angles:
            rad = math.radians(a)
            # Proyeksi isometrik (sumbu Y terkompresi ~0.58)
            px = int(center_x + r * math.cos(rad))
            py = int(center_y + r * math.sin(rad) * 0.58)
            if 380 <= px <= 1540 and 200 <= py <= 860:
                points.append((px, py))
    return points

def auto_upgrade_walls(max_upgrades=2):
    """Otomatis upgrade wall untuk membuang kelebihan gold/elixir agar tidak mubazir (anti-overflow).
    Mendukung Auto-Detect (Auto-Scan) cerdas tanpa perlu user mengisi koordinat manual."""
    global CACHED_WALL_POINT, LAST_WALL_SCAN_TIME
    if not getattr(config, "AUTO_WALL_UPGRADE", False):
        return False

    cooldown = getattr(config, "WALL_SCAN_COOLDOWN", 60)
    if CACHED_WALL_POINT is None and time.time() - LAST_WALL_SCAN_TIME < cooldown:
        return False

    total_upgraded = 0
    for cycle in range(max_upgrades):
        screen = adb.screenshot()
        if screen is None or not in_village(screen):
            break

        gold = read_storage_amount(screen, getattr(config, "VILLAGE_GOLD_REGION", (1600, 20, 1850, 75)))
        elixir = read_storage_amount(screen, getattr(config, "VILLAGE_ELIXIR_REGION", (1600, 90, 1850, 145)))

        min_gold = getattr(config, "WALL_MIN_GOLD", 5000000)
        min_elixir = getattr(config, "WALL_MIN_ELIXIR", 5000000)

        gold_overflow = gold >= min_gold
        elixir_overflow = elixir >= min_elixir

        if not gold_overflow and not elixir_overflow:
            if total_upgraded == 0:
                log(f"  🧱 Auto Wall check: Gold={gold:,} (min {min_gold:,}), Elixir={elixir:,} (min {min_elixir:,}) — belum melampaui batas")
            break

        free_builders = get_free_builders(screen)
        if free_builders <= 0:
            log("  🧱 Auto Wall Upgrade: storage penuh tapi builder 0 (sedang sibuk), tunda upgrade.")
            break

        resource_pref = getattr(config, "WALL_UPGRADE_RESOURCE", "ANY").upper()
        use_gold = False
        use_elixir = False

        if resource_pref == "GOLD":
            use_gold = gold_overflow
        elif resource_pref == "ELIXIR":
            use_elixir = elixir_overflow
        else:  # "ANY"
            if gold_overflow and elixir_overflow:
                use_elixir = elixir >= gold
                use_gold = not use_elixir
            elif gold_overflow:
                use_gold = True
            elif elixir_overflow:
                use_elixir = True

        if not use_gold and not use_elixir:
            break

        btn = config.WALL_UPGRADE_GOLD_BTN if use_gold else config.WALL_UPGRADE_ELIXIR_BTN
        res_name = "Gold" if use_gold else "Elixir"

        log(f"  🧱 Auto Wall Upgrade ({res_name})! Terbaca Gold={gold:,}, Elixir={elixir:,}")

        # Kumpulkan daftar titik yang akan diuji:
        # 1. Gunakan cached point jika ada
        # 2. Koordinat kustom user jika ada di config (opsional)
        # 3. Dynamic Auto-Scan Grid (AI mencari sendiri di seluruh zona desa)
        candidate_points = []
        if CACHED_WALL_POINT is not None:
            candidate_points.append(CACHED_WALL_POINT)

        configured_points = getattr(config, "WALL_TAP_POINTS", [])
        if configured_points:
            for p in configured_points:
                if p not in candidate_points:
                    candidate_points.append(p)

        # Tambahkan titik auto-scan grid
        for p in generate_wall_scan_grid():
            if p not in candidate_points:
                candidate_points.append(p)

        upgraded = False
        scanned_count = 0
        MAX_PROBES = 25  # batas maksimal pengecekan agar efisien dan cepat

        for pt in candidate_points:
            if scanned_count >= MAX_PROBES:
                break
            scanned_count += 1

            adb.tap(*pt)
            human_delay(0.7, 0.2)

            sel_img = adb.screenshot()
            if sel_img is None:
                continue

            # 1. Validasi ketat nama objek: HANYA jika mengandung kata "wall"
            crop_name = sel_img[650:770, 680:1280]
            sel_txt = ' '.join(ocr.reader.readtext(crop_name, detail=0)).lower()
            if "wall" not in sel_txt:
                adb.tap(*config.EMPTY_TAP)
                human_delay(0.3, 0.1)
                if pt == CACHED_WALL_POINT:
                    CACHED_WALL_POINT = None
                continue

            # 2. Periksa apakah tombol Upgrade benar-benar ada di bar bawah (jika max level, tombol upgrade tidak ada)
            crop_btn_bar = sel_img[850:950, 950:1400]
            btn_bar_txt = ' '.join(ocr.reader.readtext(crop_btn_bar, detail=0)).lower()
            if not any(w in btn_bar_txt for w in ["grade", "pgrade", "grad"]):
                adb.tap(*config.EMPTY_TAP)
                human_delay(0.3, 0.1)
                if pt == CACHED_WALL_POINT:
                    CACHED_WALL_POINT = None
                continue

            # 3. Tap tombol upgrade
            adb.tap(*btn)
            human_delay(0.9, 0.2)

            modal_img = adb.screenshot()
            if modal_img is None:
                adb.tap(*config.EMPTY_TAP)
                continue

            # 4. Pastikan modal upgrade benar-benar terbuka
            if not has_popup(modal_img):
                adb.tap(*config.EMPTY_TAP)
                human_delay(0.4, 0.1)
                continue

            # 5. Cek apakah modal terkunci Town Hall atau tombol confirm disabled (greyed out)
            note_crop = modal_img[740:860, 900:1500]
            hsv_note = cv2.cvtColor(note_crop, cv2.COLOR_BGR2HSV)
            red_warning_px = (((hsv_note[:, :, 0] < 10) | (hsv_note[:, :, 0] > 170)) & (hsv_note[:, :, 1] > 120) & (hsv_note[:, :, 2] > 120)).sum()
            is_th_locked = red_warning_px > 5000

            btn_crop = modal_img[880:940, 1270:1420]
            hsv_btn = cv2.cvtColor(btn_crop, cv2.COLOR_BGR2HSV)
            green_px = ((hsv_btn[:, :, 0] >= 35) & (hsv_btn[:, :, 0] <= 85) & (hsv_btn[:, :, 1] >= 80) & (hsv_btn[:, :, 2] >= 80)).sum()
            is_green = green_px > 500

            if is_green and not is_th_locked:
                adb.tap(*config.WALL_CONFIRM_BTN)
                human_delay(0.8, 0.2)
                adb.tap(*config.EMPTY_TAP)
                human_delay(0.5, 0.2)

                # Verifikasi apakah storage berkurang
                new_screen = adb.screenshot()
                if new_screen is not None:
                    new_g = read_storage_amount(new_screen, getattr(config, "VILLAGE_GOLD_REGION", (1600, 20, 1850, 75)))
                    new_e = read_storage_amount(new_screen, getattr(config, "VILLAGE_ELIXIR_REGION", (1600, 90, 1850, 145)))
                    if (use_gold and new_g < gold) or (use_elixir and new_e < elixir):
                        diff = (gold - new_g) if use_gold else (elixir - new_e)
                        log(f"  ✅ Auto Wall Upgrade BERHASIL di {pt}! Menggunakan {diff:,} {res_name}.")
                        CACHED_WALL_POINT = pt  # Simpan koordinat ini agar selanjutnya langsung dipakai tanpa scan!
                        upgraded = True
                        total_upgraded += 1
                        break
            else:
                reason = "terkunci level Town Hall" if is_th_locked else "tombol upgrade tidak aktif / greyed out"
                close_xy = get_popup_close_coord(modal_img)
                adb.tap(*close_xy)
                human_delay(0.6, 0.2)
                adb.tap(*config.EMPTY_TAP)
                human_delay(0.4, 0.1)
                if pt == CACHED_WALL_POINT:
                    CACHED_WALL_POINT = None

        if not upgraded:
            LAST_WALL_SCAN_TIME = time.time()
            log("  ℹ Auto Wall Upgrade selesai (tidak ada wall yang dapat diupgrade saat ini).")
            adb.tap(*config.EMPTY_TAP)
            break

    return total_upgraded > 0

def auto_upgrade_lab():
    """Mengecek apakah Laboratorium sedang idle. Jika idle, mulai riset pasukan/spell otomatis."""
    if not getattr(config, "AUTO_LAB_UPGRADE", False):
        return False

    # Buka progression menu
    adb.tap(*config.LAB_MENU_BTN)
    human_delay(1.0, 0.2)

    # Buka Tab 2: Army Upgrades (Lab)
    adb.tap(*config.LAB_TAB_BTN)
    human_delay(1.0, 0.2)

    img = adb.screenshot()
    if img is None:
        adb.tap(*config.LAB_CLOSE_PANEL_BTN)
        human_delay(0.5, 0.1)
        adb.tap(*config.EMPTY_TAP)
        return False

    # Cek apakah sedang ada riset berjalan
    # Di Tab 2, riset aktif memiliki progress bar hijau di baris atas
    top_crop = img[85:120, 1400:1880]
    hsv = cv2.cvtColor(top_crop, cv2.COLOR_BGR2HSV)
    green = (hsv[:, :, 0] > 35) & (hsv[:, :, 0] < 85) & (hsv[:, :, 1] > 100) & (hsv[:, :, 2] > 100)
    if green.sum() > 50:
        log("  🧪 Laboratorium sedang aktif melakukan riset. Lewati...")
        adb.tap(*config.LAB_CLOSE_PANEL_BTN)
        human_delay(0.5, 0.1)
        adb.tap(*config.EMPTY_TAP)
        return False

    log("  🧪 Laboratorium idle / menganggur! Mencari troop/spell untuk di-upgrade...")

    upgrade_rows = [(1600, 200), (1600, 275), (1600, 395)]
    upgraded = False
    for row_pt in upgrade_rows:
        adb.tap(*row_pt)
        human_delay(1.0, 0.2)

        modal_img = adb.screenshot()
        if modal_img is None:
            continue

        btn_crop = modal_img[850:920, 1250:1400]
        b_m, g_m, r_m = btn_crop.mean(axis=(0, 1))
        is_green = (g_m > b_m + 40) and (g_m > r_m + 15)

        if is_green:
            adb.tap(*config.LAB_CONFIRM_BTN)
            human_delay(1.0, 0.2)
            log("  ✅ Riset Laboratorium baru berhasil dimulai!")
            upgraded = True
            break
        else:
            adb.tap(1765, 75)
            human_delay(0.6, 0.2)

    adb.tap(*config.LAB_CLOSE_PANEL_BTN)
    human_delay(0.5, 0.1)
    adb.tap(*config.EMPTY_TAP)
    return upgraded

def quick_train():
    """Buka Saved Recipes (Quick Train) dan queue Army 1."""
    log("  🧑‍🍳 memasak pasukan via Quick Train (Army 1)...")
    adb.tap(*config.ATTACK_BTN)
    human_delay(1.2, 0.3)
    adb.tap(*config.FIND_MATCH_BTN)
    human_delay(1.5, 0.4)
    adb.tap(*config.SAVED_RECIPES_TAB_BTN)
    human_delay(1.2, 0.3)
    adb.tap(*config.QUICK_TRAIN_USE_BTN)
    human_delay(1.0, 0.2)
    adb.tap(*config.POPUP_CLOSE_BTN)
    human_delay(0.8, 0.2)
    adb.tap(*config.EMPTY_TAP)

def check_army_ready():
    """Cek apakah kapasitas army camp sudah penuh atau mencukupi (>=85%).
    Membuka layar Army Prep. Jika siap, layar tetap di Army Prep dan return True.
    Jika belum siap, queue quick train, tutup popup, dan return False."""
    log("  🔍 memeriksa kesiapan pasukan di camp...")
    adb.tap(*config.ATTACK_BTN)
    human_delay(1.2, 0.3)
    adb.tap(*config.FIND_MATCH_BTN)
    human_delay(1.5, 0.4)
    img = adb.screenshot()
    if img is None:
        adb.tap(*config.POPUP_CLOSE_BTN)
        return True

    # Baca kapasitas camp (misal 320/320)
    x1, y1, x2, y2 = config.CAMP_STATUS_REGION
    crop = img[y1:y2, x1:x2]
    tokens = ocr.reader.readtext(crop, detail=0, allowlist='0123456789/')
    text = ''.join(tokens).strip()
    log(f"  status camp: {text or 'tidak terbaca'}")

    ready = True
    if '/' in text:
        parts = text.split('/')
        try:
            cur, total = int(parts[0]), int(parts[1])
            if total > 0 and cur < int(total * 0.85):
                log(f"  ⚠ Pasukan belum siap: {cur}/{total} (< 85%)")
                ready = False
        except (ValueError, IndexError):
            pass

    if not ready:
        log("  queue masak pasukan di Saved Recipes...")
        adb.tap(*config.SAVED_RECIPES_TAB_BTN)
        human_delay(1.0, 0.2)
        adb.tap(*config.QUICK_TRAIN_USE_BTN)
        human_delay(0.8, 0.2)
        adb.tap(*config.POPUP_CLOSE_BTN)
        human_delay(0.8, 0.2)
        adb.tap(*config.EMPTY_TAP)
        return False

    return True

def has_popup(img):
    """Popup (Challenges/Rewards/Shop/Pass/Event/dll) kebuka -> tombol X merah di kanan-atas."""
    if img is None:
        return False
    crop = img[30:150, 1550:1910]
    hsv = cv2.cvtColor(crop, cv2.COLOR_BGR2HSV)
    red = (((hsv[:, :, 0] < 10) | (hsv[:, :, 0] > 170)) & (hsv[:, :, 1] > 140) & (hsv[:, :, 2] > 140)).sum()
    return red > 1200

def get_popup_close_coord(img):
    """Cari koordinat tepat (center) tombol X merah dari modal popup yg sedang aktif."""
    if img is not None:
        crop = img[30:150, 1550:1910]
        hsv = cv2.cvtColor(crop, cv2.COLOR_BGR2HSV)
        red = (((hsv[:, :, 0] < 10) | (hsv[:, :, 0] > 170)) & (hsv[:, :, 1] > 140) & (hsv[:, :, 2] > 140)).astype(np.uint8)
        cnts, _ = cv2.findContours(red, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)
        for c in sorted(cnts, key=cv2.contourArea, reverse=True):
            x, y, w, h = cv2.boundingRect(c)
            if w >= 25 and h >= 25:
                return (1550 + x + w // 2, 30 + y + h // 2)
    return config.POPUP_CLOSE_BTN

def ensure_village():
    """Balik ke village BERSIH sebelum attack. Handle:
    1. Result screen (Defeat/Victory) → tap Return Home
    2. Hadiah peti / Star Bonus (Chest tap / Continue / Okay)
    3. Popup panel (Challenges/Shop/Pass) → X merah
    4. Popup modal My Army nyangkut → tutup X
    5. Popup building (Tree/Storage) → tap rumput kosong aman
    Ulang sampai teks 'Attack' kebaca = bener2 di village."""
    for _ in range(8):
        img = adb.screenshot()
        if img is None:
            human_delay(1); continue
        if handle_chest_and_rewards(img):
            continue
        if in_village(img):             # udah di village bersih → selesai
            _maybe_detect_account(img)  # deteksi nama akun sekali di awal sesi
            return True
        if in_builder_base(img):        # jika di Desa Malam → kembali ke Desa Utama
            log("  terdeteksi di Desa Malam (Builder Base) — kembali ke Desa Utama...")
            adb.tap(65, 890)            # tombol Return Home di Desa Malam
            human_delay(2.5, 0.5)
            continue
        if in_army_confirm_screen(img): # modal My Army nyangkut di desa
            log("  modal My Army terbuka di village, tutup...")
            close_xy = get_popup_close_coord(img)
            adb.tap(*close_xy)
            human_delay(1, 0.3)
            continue
        if has_popup(img):              # panel Challenges/Rewards/Shop/Pass → X merah
            log("  popup panel terdeteksi, tutup X...")
            close_xy = get_popup_close_coord(img)
            adb.tap(*close_xy)
            human_delay(1, 0.3)
            continue

        # belum village & ga ada X merah / peti: kemungkinan result screen
        # atau popup building. Return Home aman di result screen.
        log("  belum di village, return home / deselect...")
        adb.tap(*config.RETURN_HOME_BTN)
        human_delay(1.0, 0.2)
        adb.tap(*config.EMPTY_TAP)
        human_delay(0.8, 0.2)
    log("  ⚠ gagal balik village bersih")
    return False

def _maybe_detect_account(village_img):
    """Baca nama akun sekali per sesi dari home village. Sesudah kebaca, ga OCR lagi."""
    global ACCOUNT
    if ACCOUNT != "unknown":
        return
    name = detect_account(village_img)
    if name:
        ACCOUNT = stats.normalize_account_name(name)
        log(f"  akun terdeteksi: {ACCOUNT}")

def wait_for_battle(timeout=35):
    """Tunggu transisi matchmaking/awan selesai sampai layar battle musuh bener2 muncul.
    Jika muncul konfirmasi 'My Army' (karena spell/siege/cc belum penuh), langsung tap Attack! hijau.
    Return screenshot battle, atau None kalau timeout."""
    start = time.time()
    while time.time() - start < timeout:
        img = adb.screenshot()
        if in_battle_screen(img):
            return img
        if in_army_confirm_screen(img):
            log("  konfirmasi pasukan (My Army), tap Attack! hijau...")
            adb.tap(*config.ARMY_CONFIRM_ATTACK_BTN)
            time.sleep(1.2)
            continue
        time.sleep(0.5)
    return None

def find_and_attack():
    log("cari base...")
    ensure_village()                  # pastikan di village bersih, jangan tap di atas popup
    if getattr(config, "AUTO_WALL_UPGRADE", False):
        auto_upgrade_walls()
    if getattr(config, "AUTO_LAB_UPGRADE", False):
        auto_upgrade_lab()

    adb.tap(*config.ATTACK_BTN)       # village: buka menu attack
    human_delay(1.2, 0.4)
    adb.tap(*config.FIND_MATCH_BTN)   # menu: Find a Match (1500 Gold) → langsung cari lawan
    human_delay(1.0, 0.3)

    # Cek apakah COC memunculkan konfirmasi 'My Army' (karena spell/siege/cc belum penuh)
    img_check = adb.screenshot()
    if in_army_confirm_screen(img_check):
        log("  konfirmasi pasukan (My Army), tap Attack! hijau...")
        adb.tap(*config.ARMY_CONFIRM_ATTACK_BTN)

    log("nyari enemy, tunggu lawan muncul...")
    screen = wait_for_battle(timeout=35)
    if screen is None:
        log("  → timeout nunggu lawan/awan, coba recover...")
        if not recover(adb.screenshot()):
            log("  → gagal masuk battle, ulang dari village")
            return False
        screen = wait_for_battle(timeout=10)
        if screen is None:
            log("  → masih belum battle, ulang dari village")
            return False

    log("lawan ditemukan, scan loot...")

    for i in range(random.randint(8, 20)):
        if screen is None:
            screen = wait_for_battle(timeout=30)
            if screen is None:
                log(f"[{i}] timeout nunggu base baru, coba recover...")
                if not recover(adb.screenshot()):
                    return False
                screen = wait_for_battle(timeout=10)
                if screen is None:
                    return False

        gold, elixir, dark = ocr.read_loot(
            screen, config.GOLD_REGION, config.ELIXIR_REGION, config.DARK_REGION)
        log(f"[{i}] gold={gold:,}  elixir={elixir:,}  dark={dark:,}")

        dead = False
        if getattr(config, "DEAD_BASE_DETECTION", True):
            dead = is_dead_base(screen)
            if dead:
                log("  💀 DEAD BASE / AKUN PENSIUN terdeteksi! (Unranked badge)")

        # Prioritas dead base jika loot memenuhi threshold DEAD_BASE_MIN_LOOT
        dead_base_attack = False
        if dead and getattr(config, "DEAD_BASE_PRIORITY", True):
            min_loot = getattr(config, "DEAD_BASE_MIN_LOOT", 500000)
            if (gold + elixir) >= (min_loot * 2) or gold >= min_loot or elixir >= min_loot:
                dead_base_attack = True

        if MODE == "force_loot" or dead_base_attack or loot_enough(gold, elixir, dark):
            reason = " [force_loot]" if MODE == "force_loot" else (" [💀 DEAD BASE]" if dead_base_attack else "")
            log(f"  → ATTACK! {gold:,}/{elixir:,}" + reason)
            deploy_troops((gold, elixir, dark))   # deploy langsung, JANGAN Next
            return True

        think_pause()
        adb.tap(*config.NEXT_BTN)       # loot kurang → skip base
        screen = None                   # invalidate screen biar loop depan nunggu base baru muncul

    log("  → limit skip, end battle")
    adb.tap(*config.END_ATTACK_BTN)
    return False

PID_FILE = os.path.join(os.path.dirname(__file__), "bot.pid")

def _acquire_singleton():
    """Cegah instance dobel (numpuk = mac lemot). Claim atomik via O_EXCL — bebas race."""
    import atexit, errno
    while True:
        try:
            fd = os.open(PID_FILE, os.O_CREAT | os.O_EXCL | os.O_WRONLY)
            break
        except FileExistsError:
            try:
                old = int(open(PID_FILE).read().strip())
                os.kill(old, 0)            # ga raise = proses masih jalan
                print(f"Bot sudah jalan (pid {old}), keluar.")
                raise SystemExit(1)
            except (ValueError, ProcessLookupError):
                os.remove(PID_FILE)      # pid file basi → hapus, ulang claim
    os.write(fd, str(os.getpid()).encode())
    os.close(fd)
    atexit.register(lambda: os.path.exists(PID_FILE) and os.remove(PID_FILE))

def main():
    _acquire_singleton()
    log(f"COC Bot started (mode={MODE})")
    ignore_sched = os.environ.get("COC_IGNORE_SCHEDULE") == "1"  # test mode
    STUCK_SECS = 360   # 1 siklus normal < ~4 menit; lebih dari ini = curiga nyangkut
    while True:
        # ADB health-check — cek device masih konek sebelum attack
        if not adb.healthy():
            log("⚠ ADB disconnect — tunggu 10s, coba konek ulang...")
            time.sleep(10)
            continue
        t0 = time.time()
        try:
            find_and_attack()
        except Exception as e:
            log(f"error: {e}")
        dur = time.time() - t0
        stats.add_time(account=ACCOUNT, seconds=dur)   # akumulasi waktu jalan per-akun
        if dur > STUCK_SECS:
            log(f"⚠ siklus lambat ({dur:.0f}s > {STUCK_SECS}s) — mungkin sempat nyangkut")
        human_delay(5, 2)

if __name__ == "__main__":
    main()
