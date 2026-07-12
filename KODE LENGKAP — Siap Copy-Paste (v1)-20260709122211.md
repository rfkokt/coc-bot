# KODE LENGKAP — Siap Copy-Paste (v1)

# KODE LENGKAP — Siap Copy-Paste (v1)
Semua file buat `~/coc-bot/`. Koordinat udah disesuaikan ke **1920x1080** + ADB BlueStacks. Ini versi pertama yang bisa jalan; finetune koordinat/threshold pas testing.
> Struktur:  
> `coc-bot/`  
> `├── config.py`  
> `├── human.py`  
> `├── adb_controller.py`  
> `├── scheduler.py`  
> `├── ocr.py`  
> `├── vision.py`  
> `├── bot.py`  
> `└── templates/ (isi nanti pas testing)`
* * *
## [config.py](http://config.py)

```python
# --- ADB ---
ADB_PATH = "/Applications/BlueStacks.app/Contents/MacOS/hd-adb"
DEVICE   = "emulator-5554"

# --- Resolusi ---
W, H = 1920, 1080

# --- Region OCR loot (x1, y1, x2, y2) ---
GOLD_REGION   = (60, 120, 420, 185)
ELIXIR_REGION = (60, 195, 420, 260)
DARK_REGION   = (60, 270, 420, 335)   # kosong di base TH rendah, aman

# --- Tombol ---
NEXT_BTN       = (1739, 776)
END_ATTACK_BTN = (154, 888)
ATTACK_BTN     = (140, 980)    # tombol Attack di home village (finetune)
FIND_MATCH_BTN = (960, 700)    # tombol Find a Match (finetune)
RETURN_HOME_BTN= (960, 950)    # tombol Return Home stlh battle (finetune)

# --- Deploy pasukan ---
TROOP_SLOT_1  = (233, 994)     # slot pasukan pertama
DEPLOY_POINTS = [(288, 486), (1632, 486), (960, 302), (960, 756)]

# --- Threshold loot minimum ---
GOLD_MIN   = 300_000
ELIXIR_MIN = 300_000
DARK_MIN   = 1_500
```

* * *
## [human.py](http://human.py)

```python
import random, time

def human_delay(mean=1.5, sigma=0.4, floor=0.3):
    d = max(floor, random.gauss(mean, sigma))
    time.sleep(d)
    return d

def think_pause():
    if random.random() < 0.15:
        time.sleep(random.uniform(4, 14))

def jitter(x, y, radius=8):
    return (x + random.randint(-radius, radius),
            y + random.randint(-radius, radius))
```

* * *
## adb\_controller.py

```python
import subprocess, random, numpy as np, cv2
from config import ADB_PATH, DEVICE
from human import human_delay, jitter

def _adb(*args):
    return subprocess.run([ADB_PATH, "-s", DEVICE, *args], capture_output=True)

def screenshot():
    raw = _adb("exec-out", "screencap", "-p").stdout
    if not raw:
        return None
    arr = np.frombuffer(raw, np.uint8)
    return cv2.imdecode(arr, cv2.IMREAD_COLOR)

def tap(x, y):
    jx, jy = jitter(x, y)
    _adb("shell", "input", "tap", str(jx), str(jy))
    human_delay(0.8, 0.3)

def swipe(x1, y1, x2, y2, dur=None):
    dur = dur or random.randint(250, 600)
    _adb("shell", "input", "swipe", str(x1), str(y1), str(x2), str(y2), str(dur))
    human_delay(0.6, 0.2)
```

* * *
## [scheduler.py](http://scheduler.py)

```python
import random, datetime

def should_be_active(now=None):
    now = now or datetime.datetime.now()
    random.seed(now.date().toordinal())
    if random.random() < 0.14:          # ~1 hari/minggu libur
        return False
    start_h = random.randint(8, 12)
    play_hours = random.randint(6, 10)
    end_h = min(23, start_h + play_hours)
    random.seed()                       # balikin randomness normal
    return start_h <= now.hour < end_h
```

* * *
## [ocr.py](http://ocr.py)

```python
import easyocr, re
reader = easyocr.Reader(['en'], gpu=False)

def parse_loot(text):
    text = text.upper().replace(',', '').replace(' ', '')
    m = re.search(r'([\d.]+)\s*([KM]?)', text)
    if not m:
        return None
    try:
        num = float(m.group(1))
    except ValueError:
        return None
    mult = {'K': 1_000, 'M': 1_000_000, '': 1}[m.group(2)]
    return int(num * mult)

def read_region(screen, region):
    x1, y1, x2, y2 = region
    crop = screen[y1:y2, x1:x2]
    tokens = reader.readtext(crop, detail=0)
    joined = ''.join(re.sub(r'[^0-9.KMkm]', '', t) for t in tokens)
    return parse_loot(joined)

def read_loot(screen, gold_r, elixir_r, dark_r=None):
    gold   = read_region(screen, gold_r)   or 0
    elixir = read_region(screen, elixir_r) or 0
    dark   = read_region(screen, dark_r)   or 0 if dark_r else 0
    return gold, elixir, dark
```

* * *
## [vision.py](http://vision.py)

```python
import cv2

def find(screen, template_path, threshold=0.8):
    tpl = cv2.imread(template_path)
    if tpl is None:
        return None
    for scale in [0.9, 1.0, 1.1]:
        resized = cv2.resize(tpl, None, fx=scale, fy=scale)
        if resized.shape[0] > screen.shape[0] or resized.shape[1] > screen.shape[1]:
            continue
        res = cv2.matchTemplate(screen, resized, cv2.TM_CCOEFF_NORMED)
        _, maxval, _, maxloc = cv2.minMaxLoc(res)
        if maxval >= threshold:
            h, w = resized.shape[:2]
            return (maxloc[0] + w // 2, maxloc[1] + h // 2)
    return None
```

* * *
## [bot.py](http://bot.py)

```python
import time, random
import adb_controller as adb
import ocr, config
from human import human_delay, think_pause
from scheduler import should_be_active

def loot_enough(gold, elixir, dark):
    return gold >= config.GOLD_MIN and elixir >= config.ELIXIR_MIN

def deploy_troops():
    pts = list(config.DEPLOY_POINTS)
    random.shuffle(pts)
    for (x, y) in pts:
        adb.tap(*config.TROOP_SLOT_1)   # pilih pasukan
        adb.tap(x, y)                   # deploy di titik
        human_delay(0.4, 0.2)
    human_delay(22, 5)                  # tunggu battle
    adb.tap(*config.RETURN_HOME_BTN)

def find_and_attack():
    adb.tap(*config.ATTACK_BTN)
    human_delay(1.2, 0.4)
    adb.tap(*config.FIND_MATCH_BTN)
    human_delay(2.8, 0.6)

    for _ in range(random.randint(8, 20)):
        screen = adb.screenshot()
        if screen is None:
            human_delay(2)
            continue
        gold, elixir, dark = ocr.read_loot(
            screen, config.GOLD_REGION, config.ELIXIR_REGION, config.DARK_REGION)
        print(f"loot -> gold={gold} elixir={elixir} dark={dark}")
        if loot_enough(gold, elixir, dark):
            print("ATTACK!")
            deploy_troops()
            return
        adb.tap(*config.NEXT_BTN)   # skip base
        human_delay(1.5, 0.4)       # tunggu loot base baru ke-load
        think_pause()

def main():
    while True:
        if not should_be_active():
            print("sleeping...")
            time.sleep(300)
            continue
        try:
            find_and_attack()
        except Exception as e:
            print("error:", e)
        human_delay(mean=8, sigma=3)

if __name__ == "__main__":
    main()
```

* * *
## Cara jalanin & urutan testing
1. **Tes OCR dulu, JANGAN full loop.** Buka COC ke layar cari-base, terus di Python REPL:

```python
import adb_controller as adb, ocr, config
s = adb.screenshot()
print(ocr.read_loot(s, config.GOLD_REGION, config.ELIXIR_REGION, config.DARK_REGION))
```

  

2. Bandingin angka yang ke-print sama yang di layar. Kalau meleset, geser region di `config.py`.**Finetune koordinat tombol** Attack / Find Match / Return Home (gua kasih perkiraan, verifikasi manual pakai `shell input tap`).
3. **Baru jalanin** `python bot.py`, awasin sesi pendek dulu.