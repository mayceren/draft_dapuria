# Paket Lengkap Hasil Pengujian Dapuria

## Berkas utama

- **HASIL_PENGUJIAN_LENGKAP.xlsx**: tabel historis per kueri/penilaian dan salinan hasil per kasus tes otomatis, tanpa formula atau perhitungan metrik baru.
- **01_evaluasi_mentah/**: paket CSV asli evaluasi rekomendasi beserta tambahan salinan arsip/run yang tersedia. Sumber dan salinan identik byte demi byte; beberapa arsip berisi salinan data yang sama, sehingga jumlah file bukan jumlah eksperimen yang berbeda.
- **02_log_pengujian_otomatis/**: stdout/stderr dan JUnit asli dari eksekusi pytest baru, rekaman perintah, waktu, environment, dan salinan tabel per kasus.
- **03_hasil_olahan_dan_referensi/**: hasil metrik, agreement, rekonsiliasi, label final, masukan serta laporan pemeriksaan manifest, dan catatan yang sudah tersedia. Bagian ini disertakan untuk kelengkapan, tetapi bukan data mentah.
- **04_kode_dan_skenario/**: salinan kode, test case, dan konfigurasi yang dipakai saat tes otomatis direkam.

Untuk permintaan **file asli dan belum diolah**, prioritaskan file CSV pada bagian 01 dan log/XML asli pada bagian 02. Excel merupakan salinan baca dari data tersebut. `salinan_per_kasus.csv` adalah konversi per kasus dari JUnit, bukan log sumber. Jangan mengganti data mentah dengan metrik ringkasan pada bagian 03.

## Cakupan dan tanggal

| Jenis | Isi | Kedudukan |
| --- | --- | --- |
| Uji akhir rekomendasi | 70 kueri, 258 kandidat pada setiap pass penilaian | Data historis dari arsip 22 Oktober 2026 |
| Validasi bobot WLC | 30 kueri, 197 kandidat pooled pada setiap pass, keluaran 11 konfigurasi | Data historis; dipisahkan dari uji akhir |
| Pilot | 10 kueri, 48 kandidat pada setiap pass | Uji pendahuluan; tidak digabung ke uji akhir |
| Tes otomatis aplikasi | 286 kasus dieksekusi pada 2026-10-27; 286 lulus; exit code 0 | Eksekusi baru dari test suite yang tersedia |
| Penilaian responden | Belum ditemukan hasil terisi | Template tetap kosong |
| Uji black-box manual oleh pengguna | Belum ditemukan lembar hasil pelaksanaan | Tidak dibuat atau diisi sebagai hasil nyata |

Tes otomatis benar-benar dijalankan, tetapi sebagian layanan/model diganti dengan mocks sesuai skenario test. Kelulusan tes ini tidak membuktikan hasil pengukuran SBERT produksi, waktu respons produksi, atau penilaian pengguna. Durasi pada JUnit merupakan waktu eksekusi test, bukan benchmark aplikasi bagi pengguna.

Nilai grade historis tidak dibuat ulang. Metadata yang ditemukan belum menetapkan identitas penilai dan asal setiap grade; konfirmasikan hal tersebut sebelum menyebut data tersebut sebagai hasil responden atau penilaian manusia. Dua pass adalah dua putaran grading, bukan bukti dua responden berbeda.

Perbaikan UI/parser setelah run historis tidak mengubah atau memperbarui hasil rekomendasi tahun/tanggal tersebut secara otomatis. Pernyataan “tidak dilakukan eksperimen baru” dalam README paket bagian 01 merujuk evaluasi rekomendasi historis; tes otomatis pada bagian 02 direkam baru secara terpisah.

## Keutuhan data

`manifest_salinan_sumber.csv` memetakan setiap salinan ke sumber dan SHA-256. `manifest_semua_berkas.json` memuat checksum berkas dalam paket, termasuk log dan workbook. Salinan Excel diperiksa per sel terhadap CSV dan tabel JUnit.

Tidak ada rata-rata, normalisasi, penggabungan grade, pengisian nilai kosong, atau grafik baru dalam workbook. Hasil olahan lama tetap dipisahkan dan tidak dinamai sebagai data mentah. Database serta screenshot preview UI tidak digunakan sebagai hasil pengujian rekomendasi.

File PRIVATE/mapping dapat membuka skor dan urutan asli; gunakan untuk pemeriksaan pembimbing, bukan untuk penilai yang belum menyelesaikan blind grading.
