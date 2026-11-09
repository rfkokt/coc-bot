"""
Desa Malam (Builder Base) mode — reuse HV helpers dari bot.py, JANGAN modif bot.py.

Temuan kalibrasi dari battle BB live (bukan asumsi):
- BB 2.0 BUKAN dark theme (corner brightness ~87, sama terang kaya HV).
- Battle UI BB ≈ HV: 'Overall Damage %' di kanan-bawah (config.DAMAGE_REGION),
  Surrender kiri-bawah (~config.END_ATTACK_BTN), troop bar bawah.
- HV detect_active_slots / detect_loot_center / read_damage JALAN di BB (udah dites).
- BEDA #1: BB gak ada loot readout di kiri-atas saat battle → in_battle_screen (HV)
  yg baca GOLD_REGION selalu False di BB. Ganti pakai battle-active check sendiri.
- BEDA #2: entry flow beda tombol (Find Now, bukan Find a Match + army prep).
- BEDA #3: gak ada threshold loot — BB serang base pertama yg ketemu (loot dari
  menang + star bonus, bukan pilih2 base kaya HV).
- BEDA #4: result screen 'Return Home' di tengah (~960,910), teks 'Total damage'.
"""
import time
import cv2
import adb_controller as adb
import ocr, config
from human import human_delay, jitter
import bot   # reuse HV helpers — import != modif, bot.py utuh

log = lambda m: bot.log(f"[BB] {m}")


def bb_active_slots(img):
    """Slot troop BB yg MASIH ADA isi. BB pakai 1 army buat 2 base: habis base-1,
    sebagian slot kehabisan = abu (saturasi rendah). Tap slot abu di BB = banner
    'select a different unit' + nol deploy = STUCK (beda HV, di HV aman).

    PENTING: geometri slot BB BEDA dari HV (HV auto-detect meleset ~45px di BB →
    tap & sample sat jatuh di antara ikon = garbage). Pakai BB_SLOT_X fixed
    (dikalibrasi dari probe live), sample sat di center tiap ikon, buang yg abu."""
    hsv = cv2.cvtColor(img, cv2.COLOR_BGR2HSV)
    y1, y2 = config.BB_SLOT_ICON_Y
    keep, sats = [], []
    for x in config.BB_SLOT_X:
        sat = hsv[y1:y2, max(0, x - 40):x + 40, 1].mean()
        sats.append(f"{x}:{sat:.0f}")
        if sat >= config.BB_SLOT_MIN_SAT:
            keep.append({'x': x, 'y': config.BB_TROOP_TAP_Y})
    log(f"slots keep={len(keep)}/{len(config.BB_SLOT_X)} sat=[{' '.join(sats)}]")
    return keep


def bb_battle_active(img):
    """BB battle SCREEN aktif (scout countdown ATAU battle jalan) → boleh deploy.
    Beda dari HV: BB gak ada loot kiri-atas, jadi in_battle_screen HV gagal.
    Temuan live: 'Battle starts in' = scout ~60s, troop BISA di-deploy selama ini
    (deploy pertama = start battle). Jadi countdown 'battle' = layar deploy aktif,
    BUKAN blokir (beda HV in_preview). Result screen gak punya 'battle'/'surrender'
    → otomatis False, loop berhenti."""
    if img is None:
        return False
    x1, y1, x2, y2 = config.COUNTDOWN_REGION
    cd = ' '.join(ocr.reader.readtext(img[y1:y2, x1:x2], detail=0)).lower()
    if 'battle' in cd:                 # scout countdown / 'battle ends in' = layar battle
        return True
    x1, y1, x2, y2 = config.BB_BATTLE_TAG_REGION
    txt = ' '.join(ocr.reader.readtext(img[y1:y2, x1:x2], detail=0)).lower()
    return 'surrender' in txt or 'damage' in txt


def bb_result_screen(img):
    """Layar HASIL BB (battle beneran kelar) = tombol 'Return Home' bawah-tengah.
    Crop KECIL (region tombol, dari probe live cx959 cy894-926) biar cepat + presisi:
    OCR area gede tiap loop = 2-3s/ronde (biang lambat) & 'Return Home' malah kelewat
    di luar crop tengah. Transisi base1->base2 GAK ada tombol ini -> gak salah-stop."""
    if img is None:
        return False
    x1, y1, x2, y2 = config.BB_RESULT_REGION
    txt = ' '.join(ocr.reader.readtext(img[y1:y2, x1:x2], detail=0)).lower()
    return 'return' in txt or 'home' in txt


def bb_deploy(deadline_secs=None):
    """Deploy troop di BB. BB = 2 base berurutan (destruction bisa sampai 200%).
    Farming = tumpahin SEMUA troop, biarin auto-end + auto-pindah base ke-2.
    GAK ada damage-gating (BB tembus 100%, read_damage HV buang >100 = useless).
     End natur: slot troop habis (detect_active_slots kosong) beberapa ronde
    berturut, atau timer. Troop bar persist saat transisi base1->base2, jadi
    re-detect tiap ronde otomatis handle base ke-2."""
    secs = deadline_secs or config.BATTLE_SECS
    # JANGAN wait_battle_ready (HV): di BB countdown 'Battle starts in' = scout phase
    # yg emang buat deploy. Nunggu ilang = stuck 40s + auto-start kosong. Deploy langsung.
    shot = adb.screenshot()
    center = bot.detect_loot_center(shot) if config.LOOT_SEEK and shot is not None else None
    pts = bot.loot_deploy_points(center) if center else list(config.DEPLOY_POINTS)
    if center:
        log(f"loot-seek: pusat {center}")
    pts = sorted(pts, key=lambda p: p[1])

    deadline = time.time() + secs
    # STOP hanya saat layar RESULT muncul (Victory/Defeat). JANGAN pakai
    # bb_battle_active 3x: transisi base1->base2 bikin tag battle ilang sekejap
    # -> salah stop -> base 2 ga keserang. Result screen ga muncul di transisi.
    while time.time() < deadline:
        shot = adb.screenshot()
        if bb_result_screen(shot):
            log("result screen muncul, battle kelar")
            break
        # sapu SEMUA slot BB (fixed geometry), tanpa gating saturasi
        for x in config.BB_SLOT_X:
            adb.tap(x, config.BB_TROOP_TAP_Y)
            for pt in pts:
                adb.tap_fast(*jitter(*pt, radius=40))
                adb.tap_fast(*jitter(*pt, radius=40))
        human_delay(1.2, 0.4)
        log(f"deploy sapu {len(config.BB_SLOT_X)} slot...")

    log("battle selesai")
    bb_return_home()
    return True


def bb_return_home():
    """Keluar battle BB balik ke village. Surrender kalau masih di battle,
    Return Home kalau result screen. Ulang sampai di village."""
    for _ in range(15):
        img = adb.screenshot()
        if img is None:
            human_delay(1); continue
        if bot.in_village(img):
            log("kembali ke desa malam")
            return
        if bb_battle_active(img):
            log("masih battle, Surrender...")
            adb.tap(*config.END_ATTACK_BTN)
            human_delay(1.2, 0.3)
            adb.tap(*config.SURRENDER_OKAY_BTN)
        else:
            log("result screen, Return Home...")
            adb.tap(*config.BB_RETURN_HOME_BTN)
        human_delay(2, 0.5)
    log("⚠ STUCK end battle BB")


def bb_find_and_attack():
    """1 siklus BB: Attack → Find Now → tunggu battle → deploy → return home.
    BB gak pilih base (serang yg pertama ketemu)."""
    log("cari base malam...")
    bot.ensure_village()
    adb.tap(*config.ATTACK_BTN)          # buka menu attack BB
    human_delay(1.5, 0.4)
    adb.tap(*config.BB_FIND_NOW_BTN)     # Find Now → langsung matchmaking
    human_delay(3, 0.6)
    # tunggu battle/preview muncul. BB matchmaking bisa lama (10-40s) — poll ~45s.
    for _ in range(45):
        img = adb.screenshot()
        if bot.in_preview(img) or bb_battle_active(img):
            log("dapat lawan, deploy...")
            bb_deploy()
            return True
        human_delay(1, 0.3)
    log("⚠ ga dapat lawan, ulang")
    return False


def main():
    bot._acquire_singleton()   # reuse lock+PID bot.py → tombol Stop dashboard tetap jalan
    log("=== DESA MALAM (Builder Base) MODE ===")
    while True:
        try:
            bb_find_and_attack()
        except Exception as e:
            log(f"error: {e}")
            human_delay(3)
        human_delay(4, 1)


if __name__ == "__main__":
    main()
