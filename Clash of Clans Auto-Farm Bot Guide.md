# Clash of Clans Auto-Farm Bot — Panduan Lengkap (macOS)

# Clash of Clans Auto-Farm Bot — Panduan Lengkap (macOS)
> ⚠️ **Disclaimer:** Supercell secara resmi mem-_permaban_ akun yang ketahuan pakai bot / third-party software (kebijakan Fair Play). Panduan ini untuk tujuan belajar (computer vision, OCR, automation). **Pakai akun burner, JANGAN akun utama.**
* * *
## 0\. Ringkasan Arsitektur
Bot bekerja dalam loop 4 layer:

```plain
[ Environment ]  COC jalan di emulator Android (BlueStacks Air) di Mac
       │
[ Perception ]   Screenshot via ADB → OpenCV/YOLO deteksi objek + EasyOCR baca angka loot
       │
[ Decision ]     Logika: loot cukup? → attack. Kalau nggak → next base
       │
[ Action ]       Kirim tap/swipe balik ke emulator via ADB
       │
       └──────── ulang ────────┘
```

**Stack:** Python 3.11+, ADB (android-platform-tools), OpenCV, EasyOCR, NumPy, (opsional) Ultralytics YOLO.

**Prinsip anti-ban (paling penting):** manusia itu berantakan dan gak konsisten. Tugas kita bikin bot sengaja berantakan: timing acak, jadwal tidur, tap dengan jitter, sesekali salah.

* * *
## FASE 1 — Setup Environment
### 1.1 Install tools dasar

```bash
# Install Homebrew kalau belum ada
/bin/bash -c "$(curl -fsSL https://raw.githubusercontent.com/Homebrew/install/HEAD/install.sh)"

# Install ADB
brew install android-platform-tools

# Cek ADB kebaca
adb version
```

### 1.2 Install BlueStacks Air (native Apple Silicon)
1. Download dari situs resmi BlueStacks, install versi **Air** (native untuk Mac M-series).
2. Buka BlueStacks, login Google Play, install **Clash of Clans**.
3. Aktifkan ADB di BlueStacks: **Settings → Advanced → Android Debug Bridge (ADB) → Enable**. Catat port-nya (biasanya `5555`).
### 1.3 Konekin ADB ke emulator

```bash
adb connect localhost:5555
adb devices        # harus muncul 1 device "device" (bukan "offline")
```

### 1.4 Tes screenshot & tap

```bash
# Ambil screenshot ke Mac
adb exec-out screencap -p > test.png
open test.png

# Tes tap di koordinat tengah layar
adb shell input tap 540 960
```

Kalau screenshot muncul dan tap bereaksi di game, **Fase 1 selesai.** Jangan lanjut sebelum ini jalan.

* * *
## FASE 2 — Fondasi Kode & Modul Anti-Ban
Buat struktur project:

```plain
coc-bot/
├── requirements.txt
├── config.py
├── adb_controller.py      # wrapper ADB (screenshot, tap, swipe)
├── human.py               # timing manusiawi + jitter (PALING PENTING)
├── scheduler.py           # jadwal main manusiawi (jam acak + hari libur)
├── vision.py              # OpenCV template matching + YOLO
├── ocr.py                 # EasyOCR baca loot
├── bot.py                 # decision loop utama
└── templates/             # gambar tombol/objek buat matching
```

### 2.1 requirements.txt

```plain
opencv-python
numpy
easyocr
Pillow
python3 -m venv venv && source venv/bin/activate
pip install -r requirements.txt
```

### 2.2 [human.py](http://human.py) — INTI ANTI-BAN
Ini modul terpenting. Semua delay & tap harus lewat sini, jangan pernah pakai angka fix.

```python
import random, time

def human_delay(mean=1.5, sigma=0.4, floor=0.3):
    """Delay acak terdistribusi normal, bukan konstan."""
    d = max(floor, random.gauss(mean, sigma))
    time.sleep(d)
    return d

def think_pause():
    """Sesekali jeda 'mikir' kayak orang bengong milih base."""
    if random.random() < 0.15:      # 15% kemungkinan
        time.sleep(random.uniform(4, 14))

def jitter(x, y, radius=8):
    """Geser titik tap beberapa pixel biar gak selalu sama persis."""
    return (x + random.randint(-radius, radius),
            y + random.randint(-radius, radius))
```

### 2.3 adb\_controller.py — wrapper ADB

```python
import subprocess, numpy as np, cv2
from human import human_delay, jitter

DEVICE = "localhost:5555"

def _adb(*args):
    return subprocess.run(["adb", "-s", DEVICE, *args],
                          capture_output=True)

def screenshot():
    """Ambil screenshot sebagai array OpenCV (BGR)."""
    raw = _adb("exec-out", "screencap", "-p").stdout
    arr = np.frombuffer(raw, np.uint8)
    return cv2.imdecode(arr, cv2.IMREAD_COLOR)

def tap(x, y):
    """Tap dengan jitter + delay manusiawi."""
    jx, jy = jitter(x, y)
    _adb("shell", "input", "tap", str(jx), str(jy))
    human_delay(0.8, 0.3)

def swipe(x1, y1, x2, y2, dur=None):
    """Swipe dengan durasi acak (biar gak selalu sama)."""
    dur = dur or random.randint(250, 600)
    _adb("shell", "input", "swipe",
         str(x1), str(y1), str(x2), str(y2), str(dur))
    human_delay(0.6, 0.2)
```

### 2.4 [scheduler.py](http://scheduler.py) — jadwal tidur (anti-ban #2)

```python
import random, datetime, time

def should_be_active(now=None):
    """Bot cuma aktif di jendela jam yang beda-beda tiap hari,
       plus hari libur acak. Jangan pernah 24/7."""
    now = now or datetime.datetime.now()
    # Seed per hari → jendela konsisten dalam 1 hari, beda antar hari
    random.seed(now.date().toordinal())

    # 1 dari 7 hari = libur total
    if random.random() < 0.14:
        return False

    start_h = random.randint(8, 12)          # mulai antara jam 8-12
    play_hours = random.randint(6, 10)       # main 6-10 jam
    end_h = min(23, start_h + play_hours)
    return start_h <= now.hour < end_h
```

* * *
## FASE 3 — Perception (Mata Bot)
### 3.1 [vision.py](http://vision.py) — template matching
Ambil screenshot manual dulu, crop tombol-tombol penting (Attack, Find a Match, Next, End Battle, Return Home), simpan ke `templates/`.

```python
import cv2, numpy as np

def find(screen, template_path, threshold=0.8):
    """Cari lokasi template di screen. Return (x,y) tengah atau None."""
    tpl = cv2.imread(template_path)
    res = cv2.matchTemplate(screen, tpl, cv2.TM_CCOEFF_NORMED)
    _, maxval, _, maxloc = cv2.minMaxLoc(res)
    if maxval < threshold:
        return None
    h, w = tpl.shape[:2]
    return (maxloc[0] + w // 2, maxloc[1] + h // 2)
```

> Upgrade opsional: pakai **YOLO (Ultralytics)** untuk deteksi base/collector yang lebih robust terhadap variasi. Butuh dataset + training, tapi jauh lebih akurat dari template matching.
### 3.2 [ocr.py](http://ocr.py) — baca loot

```python
import easyocr, re
reader = easyocr.Reader(['en'], gpu=False)

def read_loot(screen, region):
    """region = (x1,y1,x2,y2) area angka loot di layar cari-base."""
    x1, y1, x2, y2 = region
    crop = screen[y1:y2, x1:x2]
    texts = reader.readtext(crop, detail=0)
    nums = [int(re.sub(r'[^0-9]', '', t)) for t in texts if re.search(r'\d', t)]
    return nums    # [gold, elixir, dark_elixir]
```

* * *
## FASE 4 — Decision Loop (Otak)
### 4.1 [config.py](http://config.py) — threshold

```python
GOLD_MIN   = 400_000
ELIXIR_MIN = 400_000
DARK_MIN   = 2_000
LOOT_REGION = (150, 300, 500, 600)   # sesuaikan resolusi lu
```

### 4.2 [bot.py](http://bot.py) — loop utama

```python
import time, random
import adb_controller as adb
import vision, ocr, config
from human import human_delay, think_pause
from scheduler import should_be_active

def find_and_attack():
    screen = adb.screenshot()

    # Buka menu attack
    btn = vision.find(screen, "templates/attack.png")
    if btn: adb.tap(*btn)
    human_delay(1.2, 0.4)

    btn = vision.find(adb.screenshot(), "templates/find_match.png")
    if btn: adb.tap(*btn)
    human_delay(2.5, 0.6)   # loading nyari lawan

    # Loop cari base yang lootnya cukup
    for _ in range(random.randint(8, 20)):   # batas skip acak
        screen = adb.screenshot()
        loot = ocr.read_loot(screen, config.LOOT_REGION)
        if len(loot) >= 2 and loot[0] >= config.GOLD_MIN and loot[1] >= config.ELIXIR_MIN:
            deploy_troops(screen)
            return
        # Loot kurang → next base
        nxt = vision.find(screen, "templates/next.png")
        if nxt: adb.tap(*nxt)
        think_pause()   # sesekali 'mikir'

def deploy_troops(screen):
    """Deploy pasukan di beberapa titik sekeliling base.
       Kasih variasi urutan & posisi biar gak robotik."""
    points = [(200, 500), (880, 500), (540, 300), (540, 800)]
    random.shuffle(points)
    for (x, y) in points:
        adb.tap(500, 1000)   # pilih pasukan (sesuaikan slot)
        adb.tap(x, y)
        human_delay(0.4, 0.2)
    human_delay(20, 5)       # tunggu battle jalan
    end = vision.find(adb.screenshot(), "templates/end_battle.png")
    if end: adb.tap(*end)

def main():
    while True:
        if not should_be_active():
            time.sleep(300)     # lagi 'tidur', cek tiap 5 menit
            continue
        try:
            find_and_attack()
        except Exception as e:
            print("error:", e)
        # Jeda antar serangan, acak
        human_delay(mean=8, sigma=3)

if __name__ == "__main__":
    main()
```

* * *
## FASE 5 — Kalibrasi & Testing
1. **Sesuaikan koordinat & region** ke resolusi emulator lu (resolusi contoh: 1080x1920). Ambil screenshot, buka di editor gambar, catat koordinat asli.
2. **Test per-modul dulu**, jangan langsung full loop: tes screenshot → tes template matching → tes OCR baca angka → baru gabung.
3. **Jalanin sesi pendek dulu** (15-30 menit) sambil diawasi, pastikan gak nyangkut di layar aneh.
4. **Tambah recovery**: kalau nyangkut (misal ada popup event), deteksi tombol X / back dan tap buat keluar.

* * *
## Checklist Anti-Ban (urut prioritas)
1. ✅ **Timing acak** — semua delay lewat `human_delay`, gak ada angka fix.
2. ✅ **Jadwal tidur** — `should_be_active`, main 6-10 jam/hari, jam beda tiap hari, ada hari libur.
3. ✅ **Tap jitter** — tiap tap digeser ±beberapa pixel.
4. ✅ **Swipe durasi acak** — jangan durasi konstan.
5. ✅ **Sengaja imperfect** — kadang skip base bagus / buka menu terus keluar.
6. ⬜ **Fingerprint emulator** — (advanced) edit build.prop biar gak keliatan emulator.

* * *
## Roadmap Pengerjaan (urutan disarankan)
1. Fase 1 — setup BlueStacks + ADB nyambung, tes screenshot & tap.
2. Fase 2 — `human.py` + `adb_controller.py` + `scheduler.py`.
3. Fase 3 — `vision.py` template matching + `ocr.py` baca loot.
4. Fase 4 — `bot.py` decision loop.
5. Fase 5 — kalibrasi koordinat, test bertahap, tambah recovery.
6. (Opsional) Upgrade vision ke YOLO, tambah multi-account, GUI kontrol.