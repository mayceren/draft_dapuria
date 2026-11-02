# Screenshot UI Dapuria

Screenshot aktif di folder ini mengikuti tampilan aplikasi terbaru: panel **Detail penelitian** disembunyikan, langkah memasak berbentuk daftar, dan tombol lanjut/chat baru berada di bawah seluruh rekomendasi.

| Berkas | Tampilan |
| --- | --- |
| `home-*`, `mobile-top-check.png` | Halaman awal |
| `main-conversation-*`, `direct-results-*` | Percakapan dan hasil pencarian |
| `results-*`, `recommendation-results-*`, `features-results-*` | Resep utama dan alternatif |
| `cooking-steps-*`, `recipe-detail-*` | Langkah memasak dan dialog detail resep |
| `results-bottom-actions-*` | Pilihan lanjut/chat baru di akhir hasil |
| `history-menu-*`, `history-rename-*` | Menu riwayat dan dialog ubah nama |
| `history-no-horizontal-scroll-*` | Riwayat panjang dengan scroll vertikal |
| `filtered-results-*` | Hasil dengan batasan bahan |
| `direct-loading-*`, `loading-disabled-*`, `search-loading.png` | Input dinonaktifkan saat pemrosesan |
| `clarification-question-*`, `clarification-variant-*` | Pertanyaan pelengkap dan jawaban “adanya kaldu jamur” |

Akhiran `desktop` menggunakan viewport 1440 × 1100; `mobile` menggunakan 390 × 844. Capture menonaktifkan animasi agar gambar stabil. Metadata waktu, ukuran, dan checksum gambar tersimpan di `manifest.json`.

Contoh resep untuk screenshot hasil diambil dari `data/corpus/resep_5000_clean_SAFE.csv`, dengan daftar bahan dan langkah asli. Urutan contoh disiapkan untuk dokumentasi tampilan. Screenshot loading/konfirmasi menggunakan retriever uji dari `preview_chat.py`, sehingga tidak perlu memuat SBERT. Semua riwayat preview tersimpan terpisah di `artifacts-preview.sqlite3`.

## Mengambil ulang screenshot

Dari root project, jalankan server preview di terminal pertama:

```powershell
$env:DAPURIA_HISTORY_PATH = Join-Path (Get-Location) 'artifacts/ui/artifacts-preview.sqlite3'
$env:DAPURIA_PREVIEW_DELAY = '6'
.\.venv\Scripts\python.exe -m streamlit run artifacts/ui/preview_chat.py --server.headless true --server.address 127.0.0.1 --server.port 8518 --browser.gatherUsageStats false
```

Di terminal kedua, gunakan Python yang memiliki Playwright dan Microsoft Edge:

```powershell
python artifacts/ui/refresh_artifacts.py
```

Script memperbarui screenshot sekaligus mengecek panel penelitian tidak tampil pada resep utama maupun dialog detail, tombol unduh tidak muncul, rename lewat Enter berhasil, dan riwayat tidak memiliki scrollbar horizontal.

Gambar fitur lama yang sudah dihapus dan screenshot pembanding sebelum perbaikan dipertahankan di [`archive`](archive/README.md).
