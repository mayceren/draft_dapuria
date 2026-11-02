# Catatan Migrasi dari Folder Eksperimen

Project ini dibuat untuk menghindari pencampuran kode skripsi dengan eksperimen paper.

- `program(1).zip` → sumber utama core production retrieval/reranking.
- `new-new-new.zip` → arsip eksperimen pemilihan konfigurasi, bukan source production.
- `3.zip` → sumber konsep interaksi Llama 3/clarification lama; hanya ide yang aman dan grounded yang diadopsi ulang.
- `gpt.zip`, `dataset_eval.zip`, `blind_eval*.zip`, `eksperimen*.zip` → tidak dipakai sebagai source utama skripsi karena sudah bercampur dengan eksperimen paper.
- `data-primer.zip` → sumber data Yummy.co.id. Project bersih hanya membawa gabungan 1.300 halaman resep Yummy dan tidak membawa file ground-truth lama agar tidak membingungkan dengan blind evaluation baru.

## Pemetaan kode

- Parsing dan matching → `src/dapuria/preprocessing.py`
- Rule-base bahan utama → `src/dapuria/main_ingredients.py`
- Retrieval → `src/dapuria/retrieval.py`
- Coverage, harmonic efficiency, WLC → `src/dapuria/reranking.py`
- Threshold → `src/dapuria/validation.py`
- Orkestrasi sistem → `src/dapuria/recipe_service.py`
- Llama/Ollama → `src/dapuria/llama_service.py`
- Antarmuka → `app.py`
- Blind evaluation → `evaluation/`
