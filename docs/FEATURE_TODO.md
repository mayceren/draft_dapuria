# Pengembangan fitur Dapuria

Daftar ini menggabungkan rekomendasi fitur dan permintaan pengguna. Prioritas saat
ini adalah percakapan langsung, konteks bahan, batasan bahan, penguncian input,
dan bubble chat. Favorit serta daftar belanja ditunda sesuai permintaan pengguna.

## Sudah diterapkan

- [x] Konteks bahan per percakapan: tambahan bahan mempertahankan daftar sebelumnya.
- [x] Perintah penghapusan, penggantian, dan reset bahan, misalnya `telurnya habis`,
  `ganti nasi dengan kentang`, dan `mulai dari awal`.
- [x] Input langsung diproses untuk mencari resep tanpa tahap pemeriksaan bahan.
- [x] Penyimpanan konteks, batasan, dan klarifikasi dalam riwayat lokal; riwayat
  lama tetap dapat dibuka tanpa menjalankan model ulang.
- [x] Setelah hasil akhir muncul, kolom chat diganti **Lanjutkan percakapan** dan
  **Cari resep baru**. Melanjutkan memakai konteks yang sama; mencari
  resep baru membuka percakapan kosong dengan riwayat sebelumnya tetap tersimpan.
- [x] Kolom chat, tombol kirim, jawaban cepat, dan navigasi percakapan
  dinonaktifkan saat sebuah permintaan diproses. Input dibuka kembali jika gagal.
- [x] Bubble asisten di kiri dan pengguna di kanan, ukuran mengikuti isi dengan
  batas lebar, pembungkusan teks panjang, dan animasi pesan terbaru. Pengaturan
  sistem untuk mengurangi animasi tetap dihormati.
- [x] Alias pasti `telor → telur` otomatis pada preprocessing.
- [x] Bahan yang dihindari terpisah dari persediaan: `jangan pakai ayam`,
  `hindari udang`, dan `tanpa bawang putih` menyaring resep, sedangkan
  `ayam habis` hanya mengubah persediaan.
- [x] Batasan bertahan dalam percakapan dan riwayat; `boleh pakai ayam` serta
  `hapus batasan ayam` melepas satu batasan, `hapus batasan` melepas semuanya,
  dan pencarian baru atau `mulai dari awal` mengosongkan bahan serta batasan.
- [x] Filter nama bahan memakai batas kata/frasa, termasuk `kaldu ayam` saat
  menghindari `ayam`, tanpa menyaring `bayam`. Penyaringan berlaku sebelum
  mengambil Top-5 dan tidak melonggarkan batasan otomatis ketika hasil kosong.
- [x] Menu per baris riwayat untuk rename, hapus, pin, dan lepas pin tanpa
  membuka chat. Chat yang dipin muncul pada kelompok Disematkan, tetap bisa
  dicari, serta mempertahankan judul dan pin setelah restart atau percakapan baru.
- [x] Migrasi database lama menambahkan pin tanpa mengubah pesan dan resep.
- [x] Penjelasan rekomendasi dari bahan yang cocok dan bahan yang belum tersedia
  pada resep utama, alternatif, dialog detail, serta hasil dalam riwayat. Data
  yang tidak lengkap diberi keterangan; skor bukan persentase kecocokan.
- [x] Pertanyaan pelengkap singkat tanpa mengulang daftar bahan. Model memilih
  satu variasi pertanyaan yang dibatasi, sehingga tidak bisa menambah pertanyaan
  berulang atau meminta seluruh bahan sekaligus.
- [x] Jawaban jenis spesifik seperti `adanya kaldu jamur` mengonfirmasi `kaldu`
  sambil menyimpan `kaldu jamur` secara utuh, tanpa memperluasnya menjadi kaldu
  generik. Negasi, keraguan, pertanyaan, dan rencana membeli tetap dibedakan.

## Berikutnya

- [ ] Kembangkan penanganan typo pada alur percakapan tanpa editor. Ukur
  kesalahan koreksi, kasus ambigu, singkatan, serta typo lebih dari satu huruf.
  Bahan yang belum dikenal tetap dapat digunakan.
- [ ] Masukan **Cocok / Kurang cocok** disimpan bersama ID resep, versi sistem,
  dan konteks pencarian. Masukan tidak otomatis mengubah bobot WLC.
- [ ] Evaluasi versi terbaru pada direktori run baru. Bandingkan relevansi,
  kesalahan parsing dan pencocokan, serta waktu respons. Jangan menimpa hasil
  evaluasi yang dibekukan; bobot WLC tetap 0,9/0,1 sampai ada evaluasi perubahan.

## Ditunda sesuai permintaan

- [ ] Favorit resep, terpisah dari riwayat percakapan.
- [ ] Daftar belanja dari bahan yang belum tersedia, dengan kotak centang dan
  unduhan daftar.

## Dibatalkan sesuai permintaan

- Editor chip, tahap pemeriksaan sebelum pencarian, dan tombol koreksi bahan.
- Tombol saran typo yang menjadi bagian editor tersebut. Alias pasti tetap aktif.
