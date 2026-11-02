# Evaluasi Skripsi

Folder ini memisahkan dua evaluasi yang berbeda.

## 1. Blind evaluation Top-5

Tujuannya adalah menilai kualitas output ranking tanpa melihat skor dan peringkat asli saat memberi grade.

1. Siapkan `query_manifest.csv` dari template. Setiap `query_id` harus unik. `query_text` berisi 2–3 bahan yang telah dibersihkan dari sumber Yummy.co.id. Kolom `source_title` dan `source_url` hanya untuk jejak data; judul sumber tidak diberikan sebagai input ke sistem.
2. Setelah query final disetujui, bekukan manifest dan simpan hash-nya:

   ```bash
   python evaluation/freeze_query_manifest.py --input evaluation/query_manifest.csv --output evaluation/query_manifest_FROZEN.csv
   ```

3. Jalankan:

   ```bash
   python evaluation/prepare_blind_eval.py --queries evaluation/query_manifest_FROZEN.csv --out-dir evaluation/runs/final
   ```

4. Isi `grade` pada `blind_judgment_pass1.csv` dengan 0/1/2. Jangan membuka `blind_mapping_PRIVATE.csv`.
5. Setelah jeda penilaian, isi `blind_judgment_pass2.csv` secara terpisah.
6. Jalankan:

   ```bash
   python evaluation/score_blind_eval.py --run-dir evaluation/runs/final
   ```

7. Jika ada grade yang berbeda antar-pass, script membuat `grading_disagreements_to_resolve.csv`. Tinjau kasus tersebut, isi `resolved_grade`, lalu jalankan ulang:

   ```bash
   python evaluation/score_blind_eval.py --run-dir evaluation/runs/final --reconciliation evaluation/runs/final/grading_disagreements_to_resolve.csv
   ```

Rubrik:
- **2** = sangat relevan / strong recommendation.
- **1** = dapat diterima tetapi lebih parsial atau kurang langsung.
- **0** = tidak cukup sesuai untuk direkomendasikan.

Metrik akhir:
- Acceptable Success@5: minimal satu grade 1 atau 2.
- Strong Success@5: minimal satu grade 2.
- Acceptable Precision@5: proporsi lima output dengan grade >= 1.
- Strong Precision@5: proporsi lima output dengan grade 2.
- nDCG@5: kualitas urutan berdasarkan grade 0/1/2 dengan gain `2^grade - 1` dan discount logaritmik.

Karena hanya kandidat yang ditampilkan sistem yang diberi grade, metrik ini diinterpretasikan sebagai **kualitas output Top-5**, bukan recall terhadap seluruh corpus 5.000 resep.

## 2. Human evaluation aplikasi

Gunakan `human_evaluation_template.csv` ketika pemilik kantin mencoba aplikasi secara langsung. Lima aspek 1–5 sengaja mencakup kualitas rekomendasi dan pengalaman penggunaan aplikasi, sehingga evaluasi ini berbeda dari blind grading oleh peneliti.

Untuk human evaluation yang sudah diisi, ringkasan rata-rata per aspek dapat dihitung dengan:

```bash
python evaluation/score_human_eval.py --input evaluation/human_evaluation_filled.csv --output evaluation/human_evaluation_summary.csv
```
