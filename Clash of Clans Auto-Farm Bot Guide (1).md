# config.py FINAL — Koordinat Pixel (1920x1080)

# [config.py](http://config.py) FINAL — Koordinat Pixel (1920x1080)
Resolusi terverifikasi: **1920x1080** (landscape). Device: **emulator-5554**. ADB: **BlueStacks bawaan** (`hd-adb`), bukan Homebrew.

Semua rasio dari analisa screenshot udah dikonversi ke pixel. Angka deploy/tombol masih perlu difinetune pas testing, tapi ini titik awal yang solid.

```python
# ===== config.py =====

# --- ADB ---
ADB_PATH = "/Applications/BlueStacks.app/Contents/MacOS/hd-adb"
DEVICE   = "emulator-5554"

# --- Resolusi ---
W, H = 1920, 1080

# --- Region OCR loot (x1, y1, x2, y2) ---
# Crop per-baris biar OCR gak ketuker antar angka
GOLD_REGION   = (10, 119, 269, 173)
ELIXIR_REGION = (10, 184, 269, 238)
DARK_REGION   = (10, 248, 269, 302)

# --- Tombol ---
NEXT_BTN       = (1747, 788)   # "Berikutnya" kuning kanan bawah
END_ATTACK_BTN = (115, 799)    # "Akhiri Serangan" merah kiri bawah

# --- Titik deploy pasukan (dikelilingi base) ---
DEPLOY_POINTS = [(288, 486), (1632, 486), (960, 302), (960, 756)]

# --- Baris slot pasukan (y konstan, x mulai + spacing) ---
TROOP_ROW_Y   = 950
TROOP_X_START = 96
TROOP_X_STEP  = 106

# --- Threshold loot minimum ---
GOLD_MIN   = 400_000
ELIXIR_MIN = 400_000
DARK_MIN   = 2_000
```

* * *
## Update `adb_controller.py`
Ganti pemanggilan adb ke path BlueStacks:

```python
import subprocess, random, numpy as np, cv2
from config import ADB_PATH, DEVICE
from human import human_delay, jitter

def _adb(*args):
    return subprocess.run([ADB_PATH, "-s", DEVICE, *args],
                          capture_output=True)
```

Sisanya (`screenshot`, `tap`, `swipe`) tetap sama.

* * *
## Tes cepat setelah config ini

```bash
alias badb="/Applications/BlueStacks.app/Contents/MacOS/hd-adb"

# Screenshot ke Mac
badb -s emulator-5554 exec-out screencap -p > scout.png && open scout.png

# Tes tap tombol Next
badb -s emulator-5554 shell input tap 1747 788
```

Kalau tap Next mindahin ke base berikutnya, koordinat tombol udah bener. Loot region diverifikasi pas kita jalanin OCR.