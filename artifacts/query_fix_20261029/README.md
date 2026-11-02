# Regresi query bahan ayam — 29 Oktober 2026

Kasus: input `dada ayam 250 gr, kecap, garam, saus tiram`, dilengkapi `bawang putih` dan `bawang bombay`. Persediaan akhir yang diuji adalah enam bahan tersebut; air/minyak tidak diasumsikan tersedia.

## Temuan dan perbaikan

- Takaran di belakang nama dibuang dari nama kanonis: `dada ayam 250 gr` menjadi `dada ayam`.
- Alias `baput`/`bawput` menjadi bawang putih, `bamer` menjadi bawang merah. Bawang merah tetap berbeda dari bawang bombay.
- Catatan seperti `iris tipis/kecil2 sesuai selera` tidak lagi menghalangi pencocokan dada ayam.
- Pada resep `826) Ayam Kecap Bombay`, angka `1` adalah hasil parsing lama yang keliru terhadap `1,5 sdm minyak goreng`. Nama asli dipulihkan dari baris sumber yang cocok secara unik, menjadi minyak goreng.
- Pecahan Unicode, satuan `mil`, bahan duplikat, dan gabungan bumbu yang dikenali ditangani. Angka tanpa nama bahan tidak dihitung sebagai bahan. Catatan persiapan setelah koma tidak diperlakukan sebagai bahan baru.
- Aplikasi memilih kandidat relevan dengan bahan utama pengguna, mendahulukan jumlah bahan tambahan paling sedikit, lalu cakupan persediaan dan skor WLC. Varian satu keluarga judul dipilih sekali. Penyaringan keluarga memakai heuristik judul; tidak menjamin semua menu berbeda secara kuliner.

## Sebelum

`before.json` merekam hasil versi sebelum perbaikan, dengan model/index asli. Urutannya: Sate Ayam Kecap (8 bahan tambahan), Ayam Bumbu Kecap (7), Ayam bumbu kecap (6), 826) Ayam Kecap Bombay (3), Ayam kecap (6). Hitungan ini berasal dari parsing lama, sehingga bukan patokan kebenaran bahan.

## Sesudah

`after.json` merekam hasil aktual model `LazarusNLP/all-indo-e5-small-v4` dengan indeks lokal 5.000 resep, tanpa rebuild atau penggantian corpus. Waktu dan konfigurasi tersedia di dalam file.

| Peringkat | Resep | Bahan belum tersedia |
| --- | --- | --- |
| 1 | 826) Ayam Kecap Bombay | 2: air, minyak goreng |
| 2 | Sosis Ayam | 3: tepung tapioka, daun bawang, lada |
| 3 | Ayam teriyaki | 4: jahe bubuk, ladaku, saos teriyaki, gula |
| 4 | Ayam Goreng Mentega | 5: mentega, saus tomat, gula, lada, cabe hijau |
| 5 | Honey Garlic Chicken | 5: tepung maizena, merica hitam bubuk, madu, air, minyak wijen |

Nama merek atau ejaan yang tidak tercakup alias eksplisit tetap mengikuti sumber. Jumlah ini menghitung jenis bahan, bukan kecukupan takaran persediaan. Pemilihan dilakukan dari candidate pool retrieval, bukan pencarian minimum bahan secara global di semua 5.000 resep.

## Validasi

- `pytest.xml`: 309 tes lulus, termasuk regresi kasus pengguna, perlindungan bahan asal versus kaldu/produk turunan, sumber ambigu, pemulihan langkah, serta mode WLC dan pantry.
- `verify_query.py`: menjalankan query pada model/index asli; memeriksa nama kanonis, pemulihan minyak goreng, kecocokan ayam/bawang putih, bawang merah yang tetap belum tersedia, dan keluarga hasil yang berbeda.
- `browser_verification.json`: pemeriksaan browser Edge pada desktop 1440×1100 dan ponsel 390×844, termasuk pembukaan detail alternatif dan pemulihan riwayat.
- `results-*.png`, `alternatives-*.png`, `detail-*.png`: screenshot tampilan aktual.
- `preview_query.py`: server pembuktian memakai layanan resep asli dan menonaktifkan Llama agar teks fallback deterministik. `history.sqlite3` hanya riwayat pengujian ini.

## Perbedaan dengan evaluasi skripsi

Rumus WLC tetap 0,9 semantik + 0,1 efisiensi bahan. Default `app.py` memakai `pantry`; default `RecipeService(Settings())`/CLI memakai `wlc`. `DAPURIA_SELECTION_POLICY=wlc` dapat dipakai untuk memilih urutan skor WLC pada aplikasi.

Normalisasi bahan baru memengaruhi coverage dan lexical matching pada kedua mode. Hasil historis tidak ditulis ulang dan tidak boleh disebut sebagai hasil versi baru. Evaluasi ulang harus disimpan sebagai run baru dengan kebijakan seleksi yang dicatat. Riwayat chat lama mempertahankan snapshot hasil semula; ulangi pencarian untuk mendapatkan hasil baru.

## Menjalankan ulang dari root project (PowerShell)

Model dan indeks lokal harus sudah tersedia. Tidak ada panggilan API Llama pada verifier resep.

```powershell
$env:HF_HUB_OFFLINE = '1'
$env:TRANSFORMERS_OFFLINE = '1'
.venv\Scripts\python.exe artifacts/query_fix_20261029/verify_query.py
.venv\Scripts\python.exe -m pytest -q --junitxml=artifacts/query_fix_20261029/pytest.xml
```

Untuk memeriksa browser, gunakan terminal terpisah (Playwright dan Edge diperlukan pada Python yang menjalankan checker):

```powershell
$env:DAPURIA_HISTORY_PATH = Join-Path (Get-Location) 'artifacts/query_fix_20261029/history.sqlite3'
$env:HF_HUB_OFFLINE = '1'
$env:TRANSFORMERS_OFFLINE = '1'
.venv\Scripts\python.exe -m streamlit run artifacts/query_fix_20261029/preview_query.py --server.headless true --server.address 127.0.0.1 --server.port 8518 --server.fileWatcherType none --browser.gatherUsageStats false
```

```powershell
python artifacts/query_fix_20261029/check_browser.py
```
