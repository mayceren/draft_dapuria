# Data dalam project

## Corpus utama

`corpus/resep_5000_clean_SAFE.csv` dan versi Parquet berasal dari data production yang ditemukan bersama `program(1).zip`. Corpus ini berisi 5.000 resep yang dipakai oleh indeks ChromaDB.

`chroma_db/` adalah indeks vektor production yang sudah tersedia. Karena itu aplikasi dapat langsung memakai indeks ini setelah dependency dan model SBERT tersedia. Jika indeks perlu dibangun ulang, gunakan `scripts/rebuild_index.py`.

## Sumber kueri evaluasi

`evaluation_source/yummy_recipes_1300.csv` adalah gabungan tiga batch scraping Yummy.co.id yang ditemukan pada `data-primer.zip` (300 + 600 + 400 halaman, URL unik). File ini disimpan sebagai **sumber penyusunan query**, bukan sebagai predefined ground truth.

File matching/ground-truth lama sengaja tidak disalin ke project final karena rancangan evaluasi terbaru menggunakan blind relevance judgment.
