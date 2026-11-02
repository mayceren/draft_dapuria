# Berkas Hasil Uji Coba Dapuria — Data Sebelum Agregasi

## Berkas untuk dikumpulkan

1. `01_file_asli/` memuat CSV asli yang disalin tanpa mengubah byte, kolom, urutan baris, nilai, atau catatan. Inilah berkas utama untuk permintaan **file asli dan belum diolah**.
2. `DATA_UJI_MENTAH.xlsx` adalah salinan tabel agar mudah dibuka di Excel. Setiap sheet mengikuti satu CSV sumber. Sel ditulis sebagai teks, termasuk ID, angka, dan nilai kosong. Tidak ada penggabungan pass, pembersihan data, perhitungan metrik, formula, atau grafik.
3. `manifest_sha256.csv` menunjukkan path sumber, path salinan, nama sheet, jumlah baris data, ukuran file, dan checksum. `VERIFIKASI.json` mencatat pemeriksaan kesamaan file dan sel Excel.
4. `02_referensi/` berisi rubrik, catatan konfigurasi, serta rekaman environment yang sudah tersedia. File di folder ini merupakan pendukung, bukan data penilaian mentah.
5. `03_template_belum_diisi/` dan sheet `TEMPLATE_RESPONDEN` berisi template kosong. Jangan disajikan sebagai hasil pengujian responden.

ZIP berisi seluruh paket ini. Untuk permintaan file asli, sertakan ZIP atau folder CSV aslinya bersama Excel, bukan hanya Excel hasil konversi.

## Asal data dan ruang lingkup

| Kelompok | Masukan uji | Kandidat/penilaian yang tersedia |
| --- | --- | --- |
| Uji akhir | 70 kueri | 258 baris kandidat pada pass 1 dan 258 pada pass 2; mapping 516 baris |
| Validasi WLC | 30 kueri | 197 kandidat pooled pada masing-masing pass; 1.232 baris keluaran per konfigurasi WLC |
| Pilot | 10 kueri | 48 kandidat pada masing-masing pass; dipisahkan dari uji akhir |

Angka tersebut menjelaskan isi file, bukan rata-rata atau metrik performa. Dua pass bukan dua kelompok responden. Mapping dan tabel kandidat dapat merujuk resep yang sama; jangan menjumlahkan seluruh sheet sebagai jumlah percobaan atau responden.

Uji akhir berasal dari arsip `evaluation/archive/final_test_20261022`. Nilai arsip diperiksa terhadap checksum yang sudah tersimpan. Validasi dan pilot berasal dari file yang tersedia di `evaluation/runs/`, sedangkan masukan kueri berasal dari manifest yang dibekukan. Daftar sumber rinci tercantum dalam manifest paket.

Paket ini disiapkan pada 27 Oktober 2026 dari data historis yang sudah tersedia. **Tidak dilakukan eksperimen baru atau pengisian nilai oleh pembuat paket.** Hasil historis tidak otomatis merepresentasikan perubahan parser, pencocokan, dan UI sesudah run tersebut.

Grade dan notes disalin sebagaimana ditemukan. Identitas penilai, tanggal setiap penilaian, dan apakah penilaian dilakukan manusia tidak ditambahkan karena tidak tersedia sebagai metadata terverifikasi pada tabel tersebut. Konfirmasikan asal grade sebelum menyebutnya sebagai penilaian manusia atau responden.

## Data yang sengaja tidak dijadikan hasil mentah

- Rata-rata, nDCG, Precision, Success, agreement, dan tabel ringkasan metrik tidak dimasukkan sebagai data mentah.
- Label final hasil rekonsiliasi tidak menggantikan nilai asli pass 1 dan pass 2.
- Gambar serta database `artifacts/ui` memakai data preview untuk dokumentasi UI dan tidak dijadikan bukti eksperimen.
- Template responden masih kosong; belum ditemukan data responden yang terisi di project pada saat paket dibuat.

## Cara membaca sheet Excel

| Awalan/nama | Isi |
| --- | --- |
| `FINAL_` | Kueri, status, penilaian dua pass, dan mapping untuk uji akhir |
| `VALID_` | Kueri validasi, status, kandidat pooled, keluaran tiap bobot, dan penilaian dua pass |
| `PILOT_` | Data pilot terpisah |
| `TEMPLATE_RESPONDEN` | Header formulir responden, tanpa hasil penilaian |
| `DAFTAR_SUMBER` | Jejak sumber dan checksum setiap file |

`grade` merupakan nilai 0/1/2 sesuai rubrik yang disertakan. `notes` merupakan catatan yang sudah ada. `blind_code` adalah kode kandidat pada formulir blind grading. `original_rank` dan `final_score` adalah keluaran sistem yang dicatat pada file sumber, bukan perhitungan baru dalam workbook. `n_displayed` mencatat jumlah rekomendasi yang ditampilkan untuk kueri tersebut.

File berlabel `PRIVATE` dan sheet `MAPPING` membuka hubungan kode blind, resep, serta skor/urutan jika tersedia. Gunakan untuk pemeriksaan oleh pembimbing; jangan dibagikan kepada penilai yang masih menjalankan blind grading.

## Jika yang dimaksud pembimbing adalah uji pengguna atau black-box

Data di paket ini adalah data evaluasi rekomendasi yang sudah tersedia. Template responden kosong tidak memenuhi permintaan hasil penilaian pengguna. Jika diminta uji pengguna, lakukan sesi uji dan simpan jawaban asli menggunakan template. Jika diminta uji fungsi aplikasi, rekam hasil eksekusi skenario atau laporan pengujian sebenarnya dalam berkas terpisah. Jangan mengganti nama data rekomendasi ini menjadi hasil responden atau black-box.
