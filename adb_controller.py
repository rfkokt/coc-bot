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

def tap_fast(x, y):
    """Tap cepat buat deploy (spam) — tanpa delay panjang."""
    _adb("shell", "input", "tap", str(x), str(y))

def swipe(x1, y1, x2, y2, dur=None):
    dur = dur or random.randint(250, 600)
    _adb("shell", "input", "swipe", str(x1), str(y1), str(x2), str(y2), str(dur))
    human_delay(0.6, 0.2)
