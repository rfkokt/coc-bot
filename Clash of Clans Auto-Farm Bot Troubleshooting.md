# Detail Step + Analisa Error & Troubleshooting

# Detail Step + Analisa Error & Troubleshooting
Halaman ini ngebedah tiap fase lebih dalam, plus **titik error yang paling mungkin muncul** dan cara handle-nya. Gua urutin per fase sesuai urutan pengerjaan.

* * *
## FASE 1 — Setup & ADB (paling banyak drama di sini)
### Langkah detail
1. `brew install android-platform-tools` → verifikasi `adb version`.
2. Install BlueStacks Air, install COC dari Play Store.
3. Enable ADB di **Settings → Advanced**, catat port.
4. `adb connect localhost:5555` → `adb devices`.
5. Tes `adb exec-out screencap -p > test.png` dan `adb shell input tap 540 960`.
### ⚠️ Error yang paling mungkin

| Gejala | Penyebab | Solusi |
| ---| ---| --- |
| `adb devices` kosong / `offline` | ADB belum enable di BlueStacks, atau port salah | Cek port di Settings. BlueStacks Air kadang pakai port lain (5555/5556/dst). Coba `adb connect localhost:5556`. |
| `cannot connect to localhost:5555` | ADB server belum jalan / bentrok | `adb kill-server && adb start-server`, lalu connect ulang. |
| `more than one device/emulator` | Ada beberapa device kebaca | Selalu pakai flag `-s localhost:5555` (udah gua handle di `adb_controller.py`). |
| Screenshot hasilnya hitam polos | GPU/hardware acceleration bikin screencap gagal capture | Ganti renderer BlueStacks ke DirectX/Compatibility mode di graphics settings, atau turunin ke OpenGL. |
| Screenshot corrupt / gagal decode | Output binary kebaca sbagai teks | Di Mac aman (kita baca `stdout` binary langsung). Pastikan pakai `exec-out`, BUKAN `shell` (shell nambahin newline yang ngerusak PNG). |
| Tap gak bereaksi | Koordinat di luar layar / resolusi beda | Cek resolusi asli: `adb shell wm size`. Sesuaikan semua koordinat ke resolusi itu. |

> **Catatan Apple Silicon:** BlueStacks Air native ARM, COC versi ARM jalan mulus. Kalau nemu emulator lama yang x86-only, bakal lemot/crash di M-series. Pastikan pakai yang Air.
* * *
## FASE 2 — Fondasi Kode
### Langkah detail
1. Bikin venv: `python3 -m venv venv && source venv/bin/activate`.
2. `pip install -r requirements.txt`.
3. Tulis `human.py`, `adb_controller.py`, `scheduler.py`.
4. Tes: import `adb_controller`, panggil `screenshot()`, simpan hasil, pastikan gambar valid.
### ⚠️ Error yang paling mungkin

| Gejala | Penyebab | Solusi |
| ---| ---| --- |
| `pip install easyocr` lama / gagal | EasyOCR narik PyTorch yang gede | Sabar (bisa 5-10 menit). Kalau gagal, install torch dulu terpisah: `pip install torch torchvision`. Di M-series pakai wheel ARM resmi. |
| `swipe()` error `random not defined` | Lupa `import random` di `adb_controller.py` | Tambah `import random` di atas file. (Gua kelupaan di draft awal, pastikan ada.) |
| Screenshot balik `None` / kosong | `screencap` gagal (lihat Fase 1) | Debug di shell dulu sebelum salahin Python. |
| `cv2.imdecode` return `None` | Buffer kosong / bukan PNG | Cek `len(raw)` > 0. Kalau 0, ADB-nya yang bermasalah. |

* * *
## FASE 3 — Perception (di sini akurasi diuji)
### Langkah detail
1. Screenshot manual, crop tombol penting (Attack, Find Match, Next, End Battle, Return Home) → simpan ke `templates/`.
2. Tes `vision.find()` satu-satu per tombol, print koordinat, verifikasi.
3. Tes `ocr.read_loot()` di layar cari-base, print angka, bandingkan sama layar.
### ⚠️ Error yang paling mungkin (INI BAGIAN TERSULIT)
**1\. Template matching gagal karena beda skala/resolusi.**
`cv2.matchTemplate` **gak** scale-invariant. Kalau template di-crop dari resolusi beda dari runtime, matching-nya ambyar. Solusi: crop template dari resolusi yang SAMA dengan runtime, atau pakai **multi-scale matching**:

```python
def find_scaled(screen, template_path, threshold=0.8):
    tpl = cv2.imread(template_path)
    for scale in [0.8, 0.9, 1.0, 1.1, 1.2]:
        resized = cv2.resize(tpl, None, fx=scale, fy=scale)
        if resized.shape[0] > screen.shape[0]: continue
        res = cv2.matchTemplate(screen, resized, cv2.TM_CCOEFF_NORMED)
        _, maxval, _, maxloc = cv2.minMaxLoc(res)
        if maxval >= threshold:
            h, w = resized.shape[:2]
            return (maxloc[0] + w//2, maxloc[1] + h//2)
    return None
```

**2\. 🔥 OCR salah baca angka loot (BUG KRITIS di draft awal).**
COC nampilin loot dalam format **singkatan**: `1.2M`, `450K`, bukan `1200000`. Regex `read_loot` versi awal (`re.sub(r'[^0-9]', '')`) bakal ngubah `1.2M` jadi `12` → salah total, bot bakal skip semua base. **Wajib** parse suffix K/M:

```python
def parse_loot(text):
    text = text.upper().replace(',', '').replace(' ', '')
    m = re.search(r'([\d.]+)\s*([KM]?)', text)
    if not m: return None
    num = float(m.group(1))
    mult = {'K': 1_000, 'M': 1_000_000, '': 1}[m.group(2)]
    return int(num * mult)

def read_loot(screen, region):
    x1, y1, x2, y2 = region
    crop = screen[y1:y2, x1:x2]
    texts = reader.readtext(crop, detail=0)
    return [parse_loot(t) for t in texts if parse_loot(t) is not None]
```

**3\. OCR lemot / makan CPU.** EasyOCR di CPU berat. Jangan panggil OCR tiap frame. Cukup panggil sekali per base baru. `gpu=False` wajib di Mac (gak ada CUDA).

**4\. OCR misread digit** (`0`↔`8`, `1`↔`7`). Kasih toleransi threshold, atau crop region loot se-ketat mungkin biar bersih.

* * *
## FASE 4 — Decision Loop (di sini bot nyangkut)
### Langkah detail
1. Set threshold di `config.py`.
2. Rangkai `find_and_attack()` → `deploy_troops()` → `main()`.
3. Test sesi pendek sambil diawasi.
### ⚠️ Error yang paling mungkin

| Gejala | Penyebab | Solusi |
| ---| ---| --- |
| Bot nyangkut di popup (event, reward, OTW promo) | Layar tak terduga, gak ada template yang match | Bikin fungsi `recover()`: kalau X frame berturut gak nemu tombol yang diharapkan, cari tombol close/back generik atau tekan `adb shell input keyevent 4` (tombol back). |
| Deploy pasukan ngasal / gak ngeluarin troop | Slot pasukan koordinatnya salah, atau belum select troop | Kalibrasi slot pasukan manual. Deploy = pilih slot dulu, baru tap peta. Ulang per titik. |
| Battle kelar tapi bot gak balik | `end_battle`/`return_home` gak kedeteksi | Tambah template `return_home.png` + `okay.png`, loop cek beberapa detik. |
| Loop `find_and_attack` skip base terus, gak pernah nyerang | Threshold ketinggian ATAU OCR salah baca (lihat bug #2) | Turunin threshold sementara buat tes, verifikasi OCR bener dulu. |
| Bot jalan tapi kena ban | Behavior masih terlalu robotik | Balik ke checklist anti-ban: rapatin timing acak, pastikan scheduler tidur aktif, tambah imperfection. |
| Army kosong terus nyerang | Gak ngecek pasukan udah siap | Sebelum attack, cek indikator army full (template match bar pasukan) sebelum masuk `find_a_match`. |

> **Gotcha halus:** Kalau tiap `Next` kepencet kecepetan sebelum loot ke-load, OCR baca angka lama/kosong. Kasih `human_delay` setelah tap Next SEBELUM screenshot berikutnya.
* * *
## FASE 5 — Hardening (biar jalan berjam-jam tanpa diawasi)
1. **State machine, bukan linear script.** Ganti flow linear jadi state (`HOME`, `SEARCHING`, `ATTACKING`, `RETURNING`, `STUCK`). Tiap loop: screenshot → deteksi state dari yang ada di layar → aksi sesuai state. Jauh lebih tahan banting daripada asumsi urutan.
2. **Watchdog / recovery global.** Kalau state gak berubah dalam N detik, anggap nyangkut → tekan back / restart app: `adb shell am force-stop com.supercell.clashofclans` lalu buka lagi.
3. **Logging.** Simpan screenshot + keputusan tiap siklus ke folder log biar bisa debug kenapa bot salah ambil keputusan.
4. **Batas harian.** Meski scheduler udah atur jam, tambah hard cap jumlah serangan/hari biar makin manusiawi.

* * *
## TL;DR titik gagal paling berbahaya
1. **ADB gak konek / screenshot hitam** (Fase 1) — kalau ini gagal, semua percuma.
2. **OCR salah parse** **`1.2M`****/****`450K`** (Fase 3) — bug senyap yang bikin bot skip semua base atau nyerang base miskin.
3. **Template matching beda skala** (Fase 3) — tombol gak kedeteksi → bot mati gaya.
4. **Nyangkut di popup tak terduga** (Fase 4) — wajib ada recovery/back.
5. **Behavior terlalu robotik** → ban. Timing acak + jadwal tidur itu non-negotiable.