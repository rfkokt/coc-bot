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
    """Cek CEPAT: crop region loot kecil (bukan full-screen OCR yg makan ~15s).
    Kalau ada angka loot ke-baca → di layar enemy base."""
    g = ocr.read_region(img, config.GOLD_REGION)
    e = ocr.read_region(img, config.ELIXIR_REGION)
    return (g or 0) > 0 or (e or 0) > 0

def in_village(img):
    """Cek di village: teks 'Attack' muncul di tombol kiri-bawah.
    Beda dari result screen (yg juga bukan battle) → biar Return Home di-tap sampai bener2 pulang."""
    x1, y1, x2, y2 = config.ATTACK_LABEL_REGION
    txt = ' '.join(ocr.reader.readtext(img[y1:y2, x1:x2], detail=0)).lower()
    return 'attack' in txt

def read_result_loot(img):
    """Baca loot AKTUAL 'You got:' di result screen (Victory/Defeat).
    Ini loot beneran masuk ke storage — beda dari available-loot saat search
    (yg cuma potensi max, ga semua ke-ambil). Return (gold, elixir, dark)."""
    gold = ocr.read_region(img, config.RESULT_GOLD_REGION) or 0
    elixir = ocr.read_region(img, config.RESULT_ELIXIR_REGION) or 0
    dark = ocr.read_region(img, config.RESULT_DARK_REGION) or 0
    return gold, elixir, dark

def recover(img):
    """Popup/layar nyangkut → tutup popup atau back sampai balik ke layar dikenal."""
    # pakai has_popup (cek region kecil) — buang screen_text() full-frame OCR (~15s, biang lag)
    for _ in range(3):
        if in_battle_screen(img):
            return True
        if has_popup(img):
            adb.tap(*config.POPUP_CLOSE_BTN)   # panel X merah
        else:
            adb.tap(*config.EMPTY_TAP)         # popup building -> tap rumput, JANGAN back (back = exit game)
        human_delay(1.2, 0.3)
        img = adb.screenshot()
    return False

def loot_enough(gold, elixir, dark):
    return gold >= config.GOLD_MIN and elixir >= config.ELIXIR_MIN

def read_damage(prev=None):
    """Baca destruction %. OCR sering salah: tanda % dibaca angka -> '13%' jadi
    '1380'. Dulu %100 bikin 1380->80 = fake bintang, lalu filter >=prev nge-lock
    80 selamanya. Fix: 5 sampel, buang >100 (invalid), ambil MODE (bukan median:
    median [13,80,80]=80 tetep salah). Butuh >=2 sampel sama = konsisten.

    GUARD LOMPATAN (prev): misread SISTEMATIK ('9%'->'89%') lolos semua filter
    di atas karena OCR salah konsisten -> mode=89 n>=2, konfirmasi 2x juga 89.
    Yang nangkep: damage COC naik MONOTON & bertahap, gak mungkin 4->89 dalam
    1 cycle (apalagi post-deploy). Lompatan > MAX_DAMAGE_JUMP dari prev = misread.
    Self-correcting: read ditolak, cycle depan baca real (udah deket dmg baru)."""
    from collections import Counter
    vals = []
    for _ in range(5):
        v = ocr.read_region(adb.screenshot(), config.DAMAGE_REGION)
        if v is not None and v <= 100:     # destruction 0-100, di atasnya = misread
            vals.append(v)
        human_delay(0.2, 0.05)
    if not vals:
        return None
    top, n = Counter(vals).most_common(1)[0]
    if n < 2:
        return None                        # semua sampel beda = ngawur
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
    """Titik deploy di TEPI arena (perimeter), ngepung base dari semua sisi.
    PENTING: troop cuma bisa turun di rumput PINGGIR arena, BUKAN di dalam base
    (di atas building/wall = deploy ditolak, troop ga keluar -> keliatan 'muter2').
    Jadi titik SELALU nempel di 4 tepi arena, disebar merata. Sisi terdekat ke
    pusat loot dikasih titik lebih rapat (troop nembus ke storage lebih cepet)."""
    cx, cy = center
    L, R, T, B = 300, 1620, 220, 840           # tepi arena aman (rumput deploy-able)
    midx, midy = (L + R) // 2, (T + B) // 2
    # Titik di sepanjang KEEMPAT tepi (perimeter), merata. Semua di rumput -> deploy-able.
    pts = [
        (L, midy), (L, (T + midy) // 2), (L, (midy + B) // 2),      # tepi kiri (3)
        (R, midy), (R, (T + midy) // 2), (R, (midy + B) // 2),      # tepi kanan (3)
        (midx, T), ((L + midx) // 2, T), ((midx + R) // 2, T),      # tepi atas (3)
        (midx, B), ((L + midx) // 2, B), ((midx + R) // 2, B),      # tepi bawah (3)
    ]
    # Prioritaskan tepi PALING DEKET ke loot (troop dari sisi itu nembus duluan):
    # sort by jarak titik->pusat loot, titik terdekat dipakai lebih sering.
    pts.sort(key=lambda p: (p[0] - cx) ** 2 + (p[1] - cy) ** 2)
    return [(int(x), int(y)) for x, y in pts]


def in_preview(img):
    """PREVIEW screen (countdown 'Battle starts in') — troop BELUM bisa deploy.
    Tap troop/base saat ini diabaikan game → damage 0. Harus tunggu / skip dulu."""
    x1, y1, x2, y2 = config.COUNTDOWN_REGION
    txt = ' '.join(ocr.reader.readtext(img[y1:y2, x1:x2], detail=0)).lower()
    return 'starts in' in txt or 'battle start' in txt


def wait_battle_ready():
    """Sebelum deploy: pastikan battle BENER2 mulai (bukan preview countdown).
    Tap base buat skip countdown (COC langsung mulai kalau di-tap), poll sampai
    teks countdown ilang. Re-tap tiap ~1.5s kalau tap pertama meleset.
    Return False kalau timeout (nyangkut)."""
    log("  preview countdown, tap base buat mulai battle...")
    # EMPTY_TAP = rumput/base area; re-tap berkala kalau tap pertama meleset.
    for i in range(30):                     # 30*0.3 = ~9s timeout
        if not in_preview(adb.screenshot()):
            return True                     # udah battle aktif → boleh deploy
        if i % 5 == 0:                      # re-tap tiap ~1.5s, jaga2 tap pertama meleset
            adb.tap(*config.EMPTY_TAP)
        time.sleep(0.3)
    log("  ⚠ stuck di preview, gagal mulai battle")
    return False


def deploy_troops(loot=(0, 0, 0)):
    # loot = (gold, elixir, dark) base yg diserang → dicatat ke stats lifetime.
    # Deploy SEMUA troop: tiap slot di-tap banyak kali (1 tap = 1 troop keluar),
    # tersebar di beberapa titik biar gak numpuk (rawan splash).
    # Loop deploy diulang sampai BATTLE_SECS habis (3 menit) — biar troop yg
    # baru siap (CC drop, cooldown, animasi) tetep ke-deploy sampai stack kosong.
    # tap berlebih aman — kalau troop slot habis, tap kosong diabaikan game.
    from human import jitter
    log("  ⚔ MENYERANG, deploy troops...")
    # preview countdown: coba skip, tapi JANGAN nyerah kalau timeout.
    # Loop deploy di bawah udah tangguh (cek in_battle_screen + active slots):
    # kalau ternyata udah battle (preview cepet ilang, mis. preview dipersingkat)
    # troop keluar normal; kalau beneran masih preview, loop break sendiri → end di akhir.
    wait_battle_ready()
    # Titik deploy: kalau LOOT_SEEK aktif, arahin ke pusat konsentrasi loot
    # (storage gold/elixir) biar troop nyerang duit, bukan asal ngepung.
    # Fallback ke DEPLOY_POINTS statis kalau loot ga kedeteksi (base kosong/misread).
    pts = None
    if config.LOOT_SEEK:
        center = detect_loot_center(adb.screenshot())
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
        active = detect_active_slots(shot)
        if not active:                  # semua slot abu2 → troop habis di-deploy
            log("  semua troop udah diturunkan, tunggu troop selesai bertarung...")
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
            # cek ringan tiap slot: battle kelar di tengah → stop
            if not in_battle_screen(adb.screenshot()):
                stop = True; break
        if stop:
            log("  battle berakhir saat deploy, stop")
            break
        human_delay(1.5, 0.5)           # jeda singkat lalu ulang buat troop yg baru siap (CC/cooldown)
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
    # LOOT_MAX: tunggu sampai troop mati/kelar (stagnan) atau timer habis — abaikan
    # STAR1 biar loot maksimal. Non-LOOT_MAX: berhenti begitu nyampe bintang 1.
    while time.time() < deadline and (config.LOOT_MAX or dmg < config.STAR1_DAMAGE):
        if not in_battle_screen(adb.screenshot()):   # battle auto-end di fase watch → stop nunggu
            log("  battle udah berakhir, stop watch")
            break
        human_delay(5, 1)               # kasih waktu troop nyerang
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
    result screen (Return Home), atau udah village (selesai).
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
            return
        if in_battle_screen(img):           # masih di enemy base → Surrender + konfirmasi Okay
            log("  masih di battle, Surrender...")
            adb.tap(*config.END_ATTACK_BTN)     # buka popup "Surrender?"
            human_delay(1.2, 0.3)
            adb.tap(*config.SURRENDER_OKAY_BTN)  # tap Okay hijau di popup
        else:                               # bukan battle & bukan village = result screen
            if record and not recorded:     # baca loot aktual DULU sebelum Return Home
                g, e, d = read_result_loot(img)
                if g == 0 and e == 0 and d == 0:   # OCR result gagal → pakai available-loot
                    g, e, d = fallback_loot
                    log(f"  result OCR kosong, catat available-loot {g:,}/{e:,}/{d:,}")
                else:
                    log(f"  loot aktual: gold={g:,} elixir={e:,} dark={d:,}")
                stats.bump(account=ACCOUNT, gold=g, elixir=e, dark=d, attack=1)
                recorded = True
            log("  result screen, Return Home...")
            adb.tap(*config.RETURN_HOME_BTN)
        human_delay(2, 0.5)
    log("  ⚠ STUCK end battle — gagal balik village")

def has_popup(img):
    """Popup (Challenges/Rewards/Shop/dll) kebuka -> tombol X merah muncul di kanan-atas."""
    x1, y1, x2, y2 = config.POPUP_X_REGION
    hsv = cv2.cvtColor(img[y1:y2, x1:x2], cv2.COLOR_BGR2HSV)
    red = ((hsv[:, :, 0] < 10) | (hsv[:, :, 0] > 170)) & (hsv[:, :, 1] > 120) & (hsv[:, :, 2] > 120)
    return red.mean() > 0.15

def ensure_village():
    """Balik ke village BERSIH sebelum attack. Handle 3 kasus:
    1. Result screen (Defeat/Victory) → tap Return Home
    2. Popup panel (Challenges/Shop) → X merah
    3. Popup building (Tree/Mine) → tap rumput kosong
    Ulang sampai teks 'Attack' kebaca = bener2 di village."""
    for _ in range(8):
        img = adb.screenshot()
        if img is None:
            human_delay(1); continue
        if in_village(img):             # udah di village bersih → selesai
            _maybe_detect_account(img)  # deteksi nama akun sekali di awal sesi
            return True
        if has_popup(img):              # panel Challenges/Rewards/Shop → X merah
            log("  popup panel, tutup X...")
            adb.tap(*config.POPUP_CLOSE_BTN)
            human_delay(1, 0.3)
            continue
        # belum village & ga ada X merah: kemungkinan result screen (Defeat/Victory)
        # atau popup building. Return Home aman di result screen; di village ga ke-tap
        # (udah ketangkap in_village di atas). Lalu tap rumput buat deselect building.
        log("  belum di village, return home / tutup...")
        adb.tap(*config.RETURN_HOME_BTN)
        human_delay(1.2, 0.3)
        adb.tap(*config.EMPTY_TAP)
        human_delay(0.8, 0.2)
    log("  ⚠ gagal balik village bersih")
    return True

def _maybe_detect_account(village_img):
    """Baca nama akun sekali per sesi dari home village. Sesudah kebaca, ga OCR lagi."""
    global ACCOUNT
    if ACCOUNT != "unknown":
        return
    name = detect_account(village_img)
    if name:
        ACCOUNT = name
        log(f"  akun terdeteksi: {ACCOUNT}")

def find_and_attack():
    log("cari base...")
    ensure_village()                  # pastikan di village bersih, jangan tap di atas popup
    adb.tap(*config.ATTACK_BTN)       # village: buka menu attack
    human_delay(1.2, 0.4)
    adb.tap(*config.FIND_MATCH_BTN)  # menu: Find a Match → army prep
    human_delay(1.5, 0.4)
    adb.tap(*config.START_SEARCH_BTN)  # army prep: mulai cari enemy
    human_delay(2.8, 0.6)
    log("nyari enemy, scan loot...")

    for i in range(random.randint(8, 20)):
        screen = adb.screenshot()
        if screen is None:
            human_delay(2); continue

        # Popup nyangkut → recover dulu
        if not in_battle_screen(screen):
            log(f"[{i}] bukan layar battle (mungkin masih village/army prep), recover...")
            if not recover(screen):
                log("  → gagal masuk battle, ulang dari village")
                return False
            screen = adb.screenshot()
            if not in_battle_screen(screen):
                log("  → masih belum battle, ulang dari village")
                return False

        gold, elixir, dark = ocr.read_loot(
            screen, config.GOLD_REGION, config.ELIXIR_REGION, config.DARK_REGION)
        log(f"[{i}] gold={gold:,}  elixir={elixir:,}  dark={dark:,}")

        if MODE == "force_loot" or loot_enough(gold, elixir, dark):
            log(f"  → ATTACK! {gold:,}/{elixir:,}" + (" [force_loot]" if MODE == "force_loot" else ""))
            deploy_troops((gold, elixir, dark))   # deploy langsung, JANGAN Next
            return True

        think_pause()
        adb.tap(*config.NEXT_BTN)       # loot kurang → skip base
        human_delay(2.5, 0.5)

    log("  → limit skip, end battle")
    adb.tap(*config.END_ATTACK_BTN)
    return False

PID_FILE = os.path.join(os.path.dirname(__file__), "bot.pid")

def _acquire_singleton():
    """Cegah instance dobel (numpuk = mac lemot). Cek pid lama masih hidup?"""
    if os.path.exists(PID_FILE):
        try:
            old = int(open(PID_FILE).read().strip())
            os.kill(old, 0)            # ga raise = proses masih jalan
            print(f"Bot sudah jalan (pid {old}), keluar.")
            raise SystemExit(1)
        except (ValueError, ProcessLookupError):
            pass                       # pid file basi / proses mati → lanjut
    open(PID_FILE, "w").write(str(os.getpid()))
    import atexit
    atexit.register(lambda: os.path.exists(PID_FILE) and os.remove(PID_FILE))

def main():
    _acquire_singleton()
    log(f"COC Bot started (mode={MODE})")
    ignore_sched = os.environ.get("COC_IGNORE_SCHEDULE") == "1"  # test mode
    STUCK_SECS = 360   # 1 siklus normal < ~4 menit; lebih dari ini = curiga nyangkut
    while True:
        if not ignore_sched and not should_be_active():
            log("Di luar jam aktif, tidur...")
            time.sleep(300)
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
