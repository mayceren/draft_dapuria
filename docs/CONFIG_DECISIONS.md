# Keputusan Konfigurasi Skripsi

Konfigurasi retrieval mengikuti implementasi yang ditemukan pada `program(1).zip`. Bobot WLC mengikuti hasil validasi yang dibekukan pada `evaluation/manifests/wlc_selected_config_FROZEN.csv`, yaitu 0,9 semantik dan 0,1 efisiensi bahan.

## Konfigurasi yang dibekukan

- Model embedding: `LazarusNLP/all-indo-e5-small-v4`
- Semantic retrieval: Top-50
- Keyword expansion: maksimal 20 kandidat tambahan
- Candidate deduplication: berdasarkan recipe ID
- Normalisasi skor semantik: min-max pada candidate pool per kueri
- WLC: 0,9 skor semantik + 0,1 harmonic ingredient efficiency
- Top output: 5 resep
- `T_jumlah = 1`
- `T_kategori`: minimal satu bahan utama dari rule-base tujuh kelompok pangan
- `T_relevansi = min(2, jumlah bahan unik pengguna)`, diterapkan pada setiap kandidat sebelum memilih Top-5 final

Main ingredient **tidak ditambahkan ke skor WLC skripsi**. Main ingredient hanya dipakai pada rule-based input validation. Ini menjaga pemisahan dari paper APJITM, yang meneliti main-ingredient-aware WLC sebagai kontribusi khusus.

## Ketidaksesuaian yang perlu disinkronkan di proposal/skripsi

Sebagian draft proposal lama masih menyebut semantic Top-20 + keyword Top-10 dan bobot 0,4/0,6. Dokumentasi implementasi sebelumnya juga menyebut bobot 0,7/0,3. Bagian metode final perlu menyebut Top-50 + maksimal 20 keyword dan bobot hasil validasi 0,9/0,1 agar dokumen dan kode sama.

Semua parameter utama dipusatkan di `src/dapuria/config.py` dan dapat dioverride dengan environment variable. Untuk eksperimen final, jangan mengubah parameter setelah test set dibuka.

## Perbaikan aplikasi setelah pembekuan evaluasi

### Pemilihan praktis pada aplikasi, 29 Oktober 2026

`RecipeService(Settings())` dan script evaluasi tetap memakai kebijakan urutan `wlc` jika tidak ada override. `app.py` secara eksplisit memakai `pantry` sebagai default UI: setelah relevansi dan batasan diperiksa, kandidat wajib memakai setidaknya satu bahan utama pengguna, diurutkan menurut jumlah bahan tambahan, coverage pengguna, dan skor WLC. Satu keluarga judul resep dipilih sekali agar varian ayam kecap tidak mengisi semua alternatif. Pengelompokan judul merupakan heuristik, bukan jaminan bahwa semua menu berbeda secara kuliner. `DAPURIA_SELECTION_POLICY=wlc` mengembalikan urutan akhir berdasarkan skor WLC.

Rumus WLC dan bobot 0,9/0,1 tidak diganti. Namun, urutan UI dalam mode pantry berbeda dari evaluasi WLC. Mode seleksi harus dicatat ketika melakukan evaluasi baru; hasil historis tidak boleh dilaporkan sebagai hasil mode pantry.

Normalisasi baru juga menangani takaran di belakang nama, alias baput/bamer/bawput, catatan persiapan, pecahan Unicode, duplikat, serta gabungan bahan. Nama numerik yang rusak pada metadata lama dapat dipulihkan dari baris bahan asli jika lookup corpus unik; corpus dan embedding tidak diubah. Perubahan coverage dan lexical matching ini berlaku pada kedua mode, sehingga evaluasi WLC versi sekarang juga perlu dijalankan sebagai run baru jika akan dibandingkan dengan versi lama.

Regresi kasus `dada ayam 250 gr, kecap, garam, saus tiram, bawang putih, bawang bombay` disimpan terpisah di `artifacts/query_fix_20261029/`. Evaluasi dan paket pengumpulan 22/27 Oktober dipertahankan sebagai rekaman versi saat dibuat.

### Catatan perubahan sebelumnya

Parser menghapus bahan duplikat sebelum validasi, penyusunan query, dan coverage. Cache lexical menyimpan metadata yang sudah diparsing; pencocokan, tie-break, dan batas kandidat tetap sama. Detail langkah yang terpotong pada indeks lama dapat dipulihkan dari corpus dengan kecocokan unik judul, bahan, dan awalan langkah. Rebuild berikutnya menyimpan langkah lengkap.

Pemrosesan input pengguna juga mendukung pembuka percakapan dan penghubung bahan sehari-hari seperti `aku punya nasi sama telur`. Aturan percakapan hanya diterapkan pada input pengguna, bukan pada corpus. Hasil normalisasi menjadi satu query kanonis (`nasi, telur`) untuk retrieval dan coverage. Bahan yang dinegasikan atau diragukan dikecualikan; nama bahan majemuk tetap utuh. Ini merupakan preprocessing rule-based, bukan ekstraksi bahan oleh Llama, dan tidak mengubah rumus WLC atau threshold.

Pada jawaban klarifikasi, konfirmasi kandidat dan ekstraksi bahan tambahan diproses terpisah. Jawaban generik dalam klausa tersendiri (`ada, ...`) hanya mengonfirmasi satu kandidat. Bahan lain yang secara eksplisit dimiliki pengguna dapat ditambahkan melalui parser rule-based, termasuk ketika kandidat ditolak. Llama tetap hanya dapat mengonfirmasi kandidat yang ditanyakan. Bahan tambahan disimpan selama konfirmasi belum jelas, dideduplikasi bersama bahan awal, lalu dipakai untuk retrieval dan reranking ulang setelah konfirmasi selesai.

Pertanyaan pelengkap memakai satu pertanyaan pendek tanpa mengulang daftar bahan.
Llama memilih salah satu variasi yang disediakan melalui keluaran JSON yang
divalidasi; keluaran bebas atau berulang memakai fallback. Pada jawaban, aturan
deterministik mengenali pola `adanya`, `yang ada`, dan varian bahan yang disebut
pengguna. Konfirmasi `kaldu` melalui `adanya kaldu jamur` menyimpan `kaldu jamur`
sebagai bahan aktual; nama generik tidak ikut ditambahkan. Penanda produk tetap
berlaku dan bahan asal tidak dapat mengonfirmasi produk turunannya. Pemilihan
varian eksplisit berasal dari teks pengguna, bukan dari keluaran model.

Alias eksplisit `telor → telur` diterapkan pada kata utuh saat preprocessing dan pencocokan bahan. Pencocokan frasa tetap dua arah (`ayam ↔ dada ayam`), dengan syarat penanda produk `kaldu`, `terasi`, `petis`, dan `kerupuk` sama pada kedua sisi. Karena itu ayam tidak memenuhi kaldu ayam, sapi tidak memenuhi kaldu sapi, jamur tidak memenuhi kaldu jamur, dan udang tidak memenuhi terasi/petis/kerupuk udang. Nama produk tetap bisa cocok di kategorinya (`kaldu ↔ bubuk kaldu ayam`). Data bahan asli di corpus/indeks tidak diganti.

Berbeda dari optimasi cache, perubahan alias dan pencocokan produk dapat mengubah kandidat lexical, coverage, kelolosan validasi, serta ranking. Bobot WLC tetap 0,9/0,1. Hasil evaluasi versi sebelumnya harus tetap dilaporkan sesuai versi saat dijalankan; lakukan evaluasi ulang pada run baru untuk menilai perubahan ini.

Artefak evaluasi yang dibekukan dan indeks embedding tidak ditulis ulang oleh perbaikan ini. Hasil evaluasi terdahulu tetap merepresentasikan versi saat evaluasi dijalankan; evaluasi ulang harus menggunakan direktori run baru.

Konteks bahan antarbalasan bekerja sebelum pemanggilan `RecipeService`.
Input langsung menjadi query kanonis setelah penambahan, penghapusan,
penggantian, dan reset diproses secara deterministik. Editor chip dan tahap
pemeriksaan bahan dibatalkan sesuai permintaan pengguna; riwayat pada tahap
tersebut dimigrasikan menjadi percakapan aktif tanpa menjalankan model otomatis.

Batasan eksplisit seperti `jangan pakai ayam` disimpan terpisah dari persediaan.
Query hanya memakai bahan yang boleh digunakan; kandidat dengan nama bahan yang
melanggar batasan disisihkan setelah perhitungan skor dan sebelum pemilihan Top-5.
Karena itu skor kandidat yang lolos identik dengan pencarian dari bahan yang sama
tanpa filter, tetapi hasil yang memenuhi syarat dapat berbeda. Tidak ada pelonggaran
batasan otomatis ketika hasil kosong. Filter memakai batas kata/frasa pada nama
bahan, termasuk produk yang menyebut bahan tersebut; ini berbeda dari ekuivalensi
bahan pantry yang tetap memisahkan `ayam` dari `kaldu ayam`.

Korpus, embedding, bobot WLC, serta threshold tidak diubah. Evaluasi input
percakapan perlu mencatat urutan balasan, bahan akhir, serta batasan yang aktif.
Rencana pengembangan lanjutan berada di `docs/FEATURE_TODO.md`.
