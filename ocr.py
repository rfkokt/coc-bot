import easyocr, re
try:
    import torch
    torch.set_num_threads(2)   # ponytail: cap 2 core — default EasyOCR embat semua core → Mac ngelag
except ImportError:
    pass
reader = easyocr.Reader(['en'], gpu=False)

def parse_loot(text):
    text = text.upper().replace(',', '').replace(' ', '')
    m = re.search(r'([\d.]+)\s*([KM]?)', text)
    if not m:
        return None
    num_s, suf = m.group(1), m.group(2)
    if suf:                                   # 1.5M / 250K → titik = desimal
        try:
            num = float(num_s)
        except ValueError:
            return None
        return int(num * {'K': 1_000, 'M': 1_000_000}[suf])
    # tanpa suffix: titik = pemisah ribuan (OCR baca 1.234.567), bukan desimal
    digits = num_s.replace('.', '')
    if not digits:
        return None
    return int(digits)

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
