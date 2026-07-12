# Koordinat & Region Hasil Analisa Screenshot (Layar Scout)

# Koordinat & Region Hasil Analisa Screenshot (Layar Scout)
Berdasarkan screenshot layar scout/cari-base yang dikirim. Koordinat ditulis dalam **rasio (fraksi lebar/tinggi layar)** biar aman ke resolusi apapun. Konversi ke pixel: `x_pixel = frac_x * W`, `y_pixel = frac_y * H`, di mana `W x H` dari `adb shell wm size`.

* * *
## Elemen yang teridentifikasi

| Elemen | Rasio X | Rasio Y | Catatan |
| ---| ---| ---| --- |
| Panel loot (Gold) | ~0.02 | ~0.13 | angka penuh, spasi = pemisah ribuan |
| Panel loot (Elixir) | ~0.02 | ~0.19 |  |
| Panel loot (Dark Elixir) | ~0.02 | ~0.25 |  |
| Tombol Berikutnya/Next | ~0.91 | ~0.73 | tombol kuning kanan bawah |
| Tombol Akhiri Serangan/End Attack | ~0.06 | ~0.74 | tombol merah kiri bawah |
| Baris slot pasukan | mulai ~0.05, spacing ~0.055 | ~0.88 | 12+ slot |

## LOOT\_REGION (buat OCR)
Crop area tiga angka loot di kiri atas. Rasio bounding box:

```plain
(x1, y1, x2, y2) = (0.005*W, 0.09*H, 0.14*W, 0.29*H)
```

Contoh kalau resolusi 1600x740:

```python
LOOT_REGION = (8, 67, 224, 215)
```

* * *
## 🔥 Gotcha: spasi pemisah ribuan
Di layar ini loot ditulis `543 654`, `1 357 894`. EasyOCR sering pisah jadi token terpisah (`['543','654']`). **Gabungin dulu** semua token dalam region jadi satu string sebelum parse:

```python
def read_loot_line(crop):
    tokens = reader.readtext(crop, detail=0)
    joined = ''.join(re.sub(r'[^0-9.KMkm]', '', t) for t in tokens)
    return parse_loot(joined)
```

Atau lebih aman: crop **per baris** (gold/elixir/dark terpisah), tiap crop cuma berisi 1 angka, lalu gabung digit dalam baris itu. Lebih akurat karena gak ada risiko ketuker antar baris.

```python
GOLD_REGION   = (0.005*W, 0.11*H, 0.14*W, 0.16*H)
ELIXIR_REGION = (0.005*W, 0.17*H, 0.14*W, 0.22*H)
DARK_REGION   = (0.005*W, 0.23*H, 0.14*W, 0.28*H)
```

* * *
## Update fungsi deploy & next

```python
# Konversi rasio -> pixel sekali di awal
W, H = get_screen_size()   # dari `adb shell wm size`

NEXT_BTN = (int(0.91*W), int(0.73*H))
END_ATTACK_BTN = (int(0.06*W), int(0.74*H))

# Titik deploy di sekeliling base (rasio), acak urutannya
DEPLOY_POINTS = [(0.15,0.45),(0.85,0.45),(0.50,0.28),(0.50,0.70)]
```

* * *
## Yang masih dibutuhkan
1. **`adb shell wm size`** → buat konversi rasio ke pixel presisi.
2. Screenshot **home village** → lokasi tombol Attack.
3. Screenshot **pas battle jalan** → tombol Surrender + Return Home.
4. Screenshot **layar hasil battle** (menang/kalah + loot didapat) → buat deteksi selesai.