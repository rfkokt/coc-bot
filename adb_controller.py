import subprocess, random, numpy as np, cv2
from config import ADB_PATH, _detect_device
from human import human_delay, jitter

def _adb(*args):
    return subprocess.run([ADB_PATH, "-s", _detect_device(), *args], capture_output=True)

def healthy():
    """Cek ADB bener2 hidup: screenshot balik gambar (bukan None).
    Dipanggil tiap siklus bot biar gak nge-tap ke device mati."""
    from config import _detect_device
    dev = _detect_device()
    if not dev:
        return False
    r = subprocess.run([ADB_PATH, "-s", dev, "get-state"], capture_output=True, timeout=5)
    return r.stdout.strip() == b"device" or r.stdout.strip() == "device"

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

def tap_fast(x, y):
    """Tap cepat buat deploy (spam) — tanpa delay panjang."""
    _adb("shell", "input", "tap", str(x), str(y))

def swipe(x1, y1, x2, y2, dur=None):
    dur = dur or random.randint(250, 600)
    _adb("shell", "input", "swipe", str(x1), str(y1), str(x2), str(y2), str(dur))
    human_delay(0.6, 0.2)
