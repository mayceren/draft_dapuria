# Dapuria

## Arsitektur implementasi

```text
skripsi_final_clean/
├── app.py
├── requirements.txt
├── pyproject.toml
├── src/dapuria/
│   ├── config.py
│   ├── preprocessing.py
│   ├── main_ingredients.py
│   ├── retrieval.py
│   ├── reranking.py
│   ├── validation.py
│   ├── recipe_service.py
│   └── llama_service.py
├── data/
│   ├── corpus/
│   ├── chroma_db/
│   └── evaluation_source/
├── evaluation/
├── scripts/
├── tests/
└── docs/
```

## Metode skripsi yang diimplementasikan

1. Input bahan diparsing, dinormalisasi, dan dideduplikasi secara rule-based. Daftar bahan maupun pola percakapan umum seperti `aku punya nasi sama telur` didukung.
2. `T_jumlah` dan `T_kategori` diperiksa sebelum retrieval.
3. Query di-encode dengan `LazarusNLP/all-indo-e5-small-v4`.
4. Hybrid candidate retrieval menggabungkan Top-50 semantic retrieval dan maksimal 20 lexical additions yang belum muncul di semantic results.
5. Semua kandidat memiliki semantic score pada skala yang sama; semantic score dinormalisasi min-max dalam candidate pool.
6. Ingredient efficiency dihitung dari harmonic mean antara recipe coverage dan user coverage.
7. WLC final = `0.9 * normalized_semantic + 0.1 * harmonic_ingredient_efficiency`, mengikuti `evaluation/manifests/wlc_selected_config_FROZEN.csv`.
8. Hasil diranking dan `T_relevansi` diperiksa pada setiap kandidat sebelum memilih Top-5 final.
9. Llama 3 melalui Ollama hanya dipakai untuk menyusun pertanyaan klarifikasi dan memverbaliskan hasil yang sudah ditentukan sistem. Llama 3 tidak menentukan candidate retrieval, score, rank, atau threshold.

Pada aplikasi interaktif, pemilihan akhir memakai kebijakan `pantry`: kandidat yang sudah lolos validasi diurutkan berdasarkan jumlah bahan tambahan paling sedikit, coverage bahan pengguna, lalu skor WLC. Kandidat harus memakai setidaknya satu bahan utama yang dimiliki; resep dari keluarga judul yang sama, seperti beberapa varian ayam kecap, tidak memenuhi seluruh slot alternatif. Jika keluarga resep yang memenuhi syarat kurang dari lima, hasil dapat lebih sedikit. Skor WLC tetap dihitung dengan bobot 0,9/0,1. Script evaluasi menggunakan urutan `wlc` secara default; `DAPURIA_SELECTION_POLICY` dapat diisi `pantry` atau `wlc` untuk memilih kebijakan secara eksplisit.

Lihat `docs/CONFIG_DECISIONS.md` untuk alasan pemilihan konfigurasi dan bagian proposal yang perlu disinkronkan.

## Instalasi

Disarankan Python 3.11 atau 3.12.

```bash
python -m venv .venv
# Windows
.venv\Scripts\activate
# macOS/Linux
source .venv/bin/activate

pip install -r requirements.txt
pip install -e .
```

Model SBERT akan diunduh dari Hugging Face pada penggunaan pertama jika belum tersedia di cache lokal.

### Llama 3 / Ollama

Llama tidak wajib agar retrieval/reranking berjalan. Untuk mengaktifkan narasi dan klarifikasi:

```bash
ollama serve
ollama pull llama3
```

Jika Ollama tidak tersedia, aplikasi tetap berjalan menggunakan fallback deterministik.

## Menjalankan aplikasi

```bash
streamlit run app.py
```

atau

```bash
python -m streamlit run app.py
```

Input bisa berupa daftar bahan atau kalimat percakapan sederhana, misalnya:

```text
telur, dada ayam, bawang putih
aku punya nasi sama telur
di kulkas ada tahu dan bawang putih
aku punya 2 butir telur sama 100 gr dada ayam nih
```

Parser menghapus pembuka percakapan, mengenali pemisah `dan`, `sama`, `serta`, `plus`, `juga`, `&`, `+`, koma, titik koma, serta baris baru. Nama majemuk seperti `bawang putih` dan `kecap manis` tetap utuh. Bahan duplikat dihapus setelah normalisasi dan jumlah desimal seperti `0,5 kg ayam` didukung.

Bahan yang secara eksplisit tidak tersedia atau diragukan tidak ditambahkan. Contoh: `aku punya nasi tapi telur habis` menghasilkan `nasi`, sedangkan `aku tidak punya nasi dan telur` tidak menghasilkan bahan. Negasi atau keraguan berlaku pada daftar sesudahnya sampai ada pernyataan kepemilikan baru atau penghubung kontras. Alternatif seperti `nasi atau telur` tidak dianggap sebagai kepemilikan keduanya. Parser menggunakan aturan untuk pola umum, sehingga kalimat yang lebih kompleks sebaiknya ditulis ulang sebagai daftar bahan. Hasil menampilkan bahan yang terbaca agar pengguna dapat memeriksanya.

Alias eksplisit `telor → telur`, `baput/bawput → bawang putih`, dan `bamer → bawang merah` diterapkan pada kata utuh. Takaran di belakang nama, misalnya `dada ayam 250 gr`, dinormalisasi menjadi `dada ayam`; pecahan desimal dan Unicode seperti `1,5 sdm` dan `½ sdt` juga dikenali. Catatan persiapan seperti `iris tipis/kecil2 sesuai selera` dibuang dari nama untuk pencocokan. `Bamer` tidak disamakan dengan bawang bombay.

Metadata bahan resep dinormalisasi ketika dibaca tanpa menulis ulang corpus atau indeks. Angka saja dan label bagian dibuang, duplikat tidak menambah hitungan bahan, dan daftar gabungan seperti `garam dan lada` dipisahkan. Kesalahan indeks lama seperti nama `1` dipulihkan menjadi `minyak goreng` dari baris sumber `1,5 sdm minyak goreng` hanya jika kecocokan judul dan daftar bahan sumber tidak ambigu. Nama sumber disimpan sebagai `source_ingredient_names` untuk jejak data dan pemulihan langkah lama.

Pertanyaan pelengkap cukup satu pertanyaan singkat, misalnya `Ada kaldu juga? Kalau nggak ada, kita lanjut pakai bahan yang kamu punya.` Daftar bahan awal tidak diulang. Jika Llama tersedia, model hanya memilih satu pertanyaan dari variasi yang disediakan; keluaran bebas, berulang, atau tidak valid memakai pertanyaan bawaan.

Jawaban seperti `adanya kaldu jamur`, `yang ada kaldu jamur`, atau `kaldu jamur aja yang ada` mengonfirmasi kandidat umum `kaldu` dan menyimpan bahan spesifik `kaldu jamur`. Sistem tidak menambahkan `kaldu` generik, sehingga `kaldu ayam` tetap tidak terhitung sebagai bahan yang dimiliki. Pertanyaan, keraguan, dan rencana membeli tidak dianggap sebagai kepemilikan. Jenis yang berbeda dari kandidat spesifik juga tidak otomatis mengonfirmasi kandidat tersebut.

Pencocokan membedakan produk bertanda `kaldu`, `terasi`, `petis`, dan `kerupuk` dari bahan asalnya dalam kedua arah:

| Pasangan bahan                                     | Cocok |
| -------------------------------------------------- | ----- |
| ayam ↔ ayam / dada ayam / paha ayam                | Ya    |
| ayam ↔ kaldu ayam / bubuk kaldu ayam               | Tidak |
| sapi ↔ kaldu sapi                                  | Tidak |
| jamur ↔ kaldu jamur                                | Tidak |
| udang ↔ terasi udang / petis udang / kerupuk udang | Tidak |
| kaldu ↔ kaldu ayam / bubuk kaldu ayam              | Ya    |
| terasi ↔ terasi udang                              | Ya    |

Aturan yang sama dipakai untuk lexical retrieval, coverage, validasi bahan utama, dan pemilihan bahan klarifikasi. Perubahan ini dapat mengubah kandidat serta ranking, sehingga hasil evaluasi lama tidak otomatis merepresentasikan versi ini; simpan evaluasi ulang sebagai run baru.

## Riwayat chat dan tampilan aplikasi

Untuk pemakaian lokal di laptop, percakapan disimpan otomatis di `data/local_history/chats.sqlite3`. Sidebar menyediakan percakapan baru, pencarian judul, serta akses ke percakapan lama. Menu **⋯** pada setiap baris riwayat menyediakan **Pin chat / Lepas pin**, penggantian judul, dan **Hapus chat** tanpa perlu membuka chat tersebut. Di dialog **Ubah nama**, tekan Enter atau **Simpan judul** untuk menyimpan perubahan; **Batal** menutup dialog tanpa menyimpan. Chat yang dipin masuk kelompok **Disematkan** di atas riwayat lain; pencarian judul tetap mencakup keduanya. Judul dan pin bertahan setelah aplikasi ditutup maupun setelah chat dilanjutkan. Database lama mendapat kolom pin otomatis tanpa mengganti isi percakapan. Lokasi penyimpanan dapat dioverride dengan environment variable `DAPURIA_HISTORY_PATH`.

Riwayat menyimpan pesan, hasil resep asli beserta skor saat pencarian dilakukan, dan tahap klarifikasi beserta bahan tambahan. Membuka riwayat tidak menjalankan retrieval ulang. Jika percakapan memiliki beberapa pencarian, tombol **Lihat rekomendasi ini** pada balasan lama membuka kembali hasil tersebut. Langkah memasak ditampilkan sebagai daftar bernomor dari teks sumber. Pilihan **Lanjutkan percakapan** dan **Cari resep baru** berada di bawah seluruh hasil resep.

Input langsung diproses untuk mencari resep, tanpa editor chip atau tahap pemeriksaan bahan. Bahan tetap tersimpan dalam konteks percakapan; `aku juga punya wortel` menambah bahan, `telurnya ternyata habis` menghapus telur, `ganti nasi dengan kentang` mengganti bahan, dan `mulai dari awal` mengosongkan daftar beserta batasan. Parsing ini memakai aturan untuk pola percakapan umum.

Sesudah hasil akhir ditampilkan, kolom chat diganti tombol **Lanjutkan percakapan** untuk memakai konteks yang sama dan **Cari resep baru** untuk membuka percakapan kosong. Selama pencarian atau klarifikasi diproses, input, tombol kirim, jawaban cepat, dan navigasi percakapan dikunci; kegagalan yang tertangani mengaktifkannya kembali. Bubble asisten berada di kiri dan pengguna di kanan, dengan ukuran mengikuti teks serta animasi pesan terbaru.

Pengguna bisa memberi batasan, misalnya `aku punya nasi sama telur, jangan pakai ayam`, `hindari udang`, atau `tanpa bawang putih`. Batasan berlaku pada percakapan yang sama sampai dilepas dengan `boleh pakai ayam`, `hapus batasan ayam`, atau `hapus batasan` untuk melepas semuanya. **Cari resep baru** mengosongkan bahan dan batasan. Pernyataan `ayam habis` atau `tidak punya ayam` hanya mengubah persediaan, bukan menyaring resep. Batasan ditampilkan di percakapan dan disimpan dalam riwayat.

Penyaringan memakai nama bahan yang tercatat pada resep dengan batas kata: `ayam` menyaring `dada ayam` dan `kaldu ayam`, tetapi bukan `bayam`. Filter tidak menebak komposisi yang tidak tercantum atau nama turunannya melalui ontologi. Bahan yang dimiliki tetap tersimpan meskipun sementara dihindari, sehingga `boleh pakai ayam` tidak mengharuskan pengguna menyebut persediaannya lagi. Resep yang melanggar batasan disisihkan sebelum mengambil Top-5; skor WLC kandidat yang tersisa tetap sama. Hasil lama dalam riwayat mempertahankan resep dan batasan saat pencarian tersebut dilakukan.

Alias pasti seperti `telor → telur` tetap otomatis. Editor koreksi dan tombol saran typo telah dibatalkan sesuai permintaan pengguna; pengembangan penanganan typo berikutnya tercatat di [daftar fitur dan perbaikan](docs/FEATURE_TODO.md).

Halaman awal dan riwayat bisa dibuka sebelum model SBERT dimuat. Model baru dimuat ketika pengguna mengirim bahan untuk mencari resep. Animasi meliputi ilustrasi dapur, indikator proses, transisi balasan terbaru, dan indikator jumlah bahan tersedia; pengaturan sistem `prefers-reduced-motion` dihormati. Tampilan menyesuaikan layar desktop dan ponsel.

Logo bawaan aplikasi berada di `src/dapuria/assets/image/`: `logo_utama.png` dipakai pada header, sidebar, ikon tab, dan avatar asisten; `magnifying_glass_icon.png` menjadi ilustrasi halaman awal pada layar lebar. Folder ini merupakan bagian dari paket Python, dan file PNG ikut disertakan saat membangun wheel. Lokasi aset dihitung dari modul aplikasi sehingga tidak bergantung pada direktori kerja saat aplikasi dijalankan.

Riwayat lokal ini dipakai bersama oleh browser yang membuka aplikasi di laptop yang sama dan belum memiliki login pengguna. Untuk kebutuhan penggunaan banyak akun, tambahkan autentikasi dan gunakan identitas akun sebagai `owner_id` pada penyimpanan riwayat. Database riwayat terpisah dari indeks resep, diabaikan oleh Git, dan tidak mengubah artefak evaluasi.

## Menjalankan test

```bash
pytest -q
```

Test unit tidak membutuhkan model SBERT atau ChromaDB karena fokus pada parser, ingredient matching, coverage/WLC, dan threshold.

Untuk smoke test penuh setelah dependencies/model tersedia:

```bash
python scripts/smoke_test.py
```

## Rebuild indeks

Project sudah menyertakan indeks ChromaDB production. Jika ingin membangun ulang dari corpus:

```bash
python scripts/rebuild_index.py --force
```

## Blind evaluation

Lihat `evaluation/README.md`. Workflow menghasilkan dua grading pass dengan urutan kandidat yang diacak dan file mapping privat yang tidak boleh dibuka selama grading.

## Human evaluation

`evaluation/human_evaluation_template.csv` digunakan ketika pemilik kantin mencoba aplikasi secara langsung. Evaluasi ini berbeda dari blind relevance judgment oleh peneliti: human evaluation menilai penggunaan aplikasi dan kelayakan rekomendasi dalam praktik.

## Catatan data Yummy.co.id

`data/evaluation_source/yummy_recipes_1300.csv` adalah sumber penyusunan query evaluasi. File matching/ground-truth lama tidak dibawa ke project final karena rancangan terbaru tidak menganggap satu resep sumber sebagai satu-satunya jawaban benar.

## Perbaikan klarifikasi bahan (v1.0.1)

Klarifikasi bahan dilakukan satu bahan pada satu waktu. Jawaban generik seperti `ya` atau `tidak` diproses secara deterministik ketika hanya satu bahan yang ditanyakan, sehingga Llama 3 tidak dapat menganggap bahan lain yang tidak ditanyakan sebagai bahan yang dikonfirmasi pengguna.

Jawaban memiliki tiga status: dikonfirmasi, ditolak, atau belum jelas. Pertanyaan seperti `garam apa?` dan jawaban ragu seperti `mungkin ada` mempertahankan tahap klarifikasi; `garamnya ada` dikenali sebagai konfirmasi. Tombol konfirmasi tetap dapat digunakan untuk melanjutkan.

Pengguna juga dapat menyebut bahan lain secara eksplisit saat menjawab. Jika yang ditanyakan adalah bawang putih, `ada, aku juga ada garam sama lada` menambahkan bawang putih, garam, dan lada. `tidak ada bawang putih, tapi aku punya garam sama lada` hanya menambahkan garam dan lada. Bahan baru diekstrak dari pernyataan kepemilikan pengguna menggunakan parser rule-based; keluaran Llama tetap dibatasi pada kandidat yang ditanyakan. Jika bahan yang ditanyakan belum dijawab, tambahan bahan dicatat selama tahap klarifikasi dan digabung saat pengguna melanjutkan. Input untuk pencarian ulang dibangun dari nama bahan yang sudah dinormalisasi agar kalimat penutup pada pesan awal tidak menghapus bahan tambahan.

Ringkasan Llama menggunakan JSON dengan pembuka yang diizinkan dan daftar ID resep sesuai urutan hasil. Sistem menolak pembuka, ID, urutan, atau field tambahan yang tidak sesuai, lalu menggunakan fallback. Judul dan seluruh fakta resep selalu berasal dari data sistem.

Langkah memasak disimpan lengkap saat rebuild indeks. Untuk indeks lama yang memotong langkah pada 2.000 karakter, aplikasi memulihkan teks dari corpus jika judul, daftar bahan, dan awalan langkah cocok secara unik. Lokasi corpus dapat diatur melalui `DAPURIA_CORPUS_PATH`. Pemulihan detail tidak mengubah skor atau urutan rekomendasi.
