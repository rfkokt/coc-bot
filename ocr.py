import easyocr, re, warnings, cv2
warnings.filterwarnings('ignore', message='.*pin_memory.*')
try:
    import torch
    torch.set_num_threads(2)   # ponytail: cap 2 core — default EasyOCR embat semua core → Mac ngelag
except ImportError:
    pass
reader = easyocr.Reader(['en'], gpu=False)

def parse_loot(text):
    text = text.upper().replace(',', '')
    # Cek suffix K atau M eksplisit (misal 1.5M, 250K)
    m = re.search(r'([\d.]+)\s*([KM])', text)
    if m:
        try:
            num = float(m.group(1))
            return int(num * {'K': 1_000, 'M': 1_000_000}[m.group(2)])
        except ValueError:
            pass
    # Angka biasa (dengan spasi atau titik pemisah ribuan, misal 333 923 atau 1.234.567)
    digits = ''.join(re.findall(r'\d+', text))
    if not digits:
        return None
    val = int(digits)
    # Sanity check: Di COC loot multiplayer maksimal ~2.5M. Jika OCR baca digit 0 berlebih (>3M)
    while val > 3_000_000 and val % 10 == 0:
        val //= 10
    return val

def read_region(screen, region, upscale=3):
    if screen is None:
        return None
    x1, y1, x2, y2 = region
    crop = screen[y1:y2, x1:x2]
    if crop.size == 0:
        return None
    if upscale > 1:
        crop = cv2.resize(crop, None, fx=upscale, fy=upscale, interpolation=cv2.INTER_LINEAR)
    tokens = reader.readtext(crop, detail=0, allowlist='0123456789 .,KMkm')
    text = ' '.join(tokens)
    return parse_loot(text)

def read_loot(screen, gold_r, elixir_r, dark_r=None):
    gold   = read_region(screen, gold_r)   or 0
    elixir = read_region(screen, elixir_r) or 0
    dark   = read_region(screen, dark_r)   or 0 if dark_r else 0
    return gold, elixir, dark
