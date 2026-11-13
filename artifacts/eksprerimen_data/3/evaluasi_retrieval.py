"""
Script Evaluasi Retrieval & Reranking - Chatbot Rekomendasi Resep
====================================================================

Tujuan:
    Mengukur performa retrieval SBERT (sebelum reranking) dan performa
    setelah reranking (skor SBERT + skor efisiensi bahan), menggunakan
    metrik Precision@K, Recall@K, dan NDCG@K.

Cara pakai singkat:
    1. Siapkan daftar query test (kombinasi bahan yang user mungkin input).
    2. Definisikan ground truth relevansi secara OTOMATIS berdasarkan
       overlap bahan (lihat fungsi `build_ground_truth`), supaya tidak perlu
       labeling manual satu-satu (cepat, reproducible, defensible ke dospem).
    3. Jalankan fungsi retrieval SBERT kamu sendiri (ganti bagian
       `dummy_retrieval_function`), dapatkan top-K hasil SEBELUM reranking
       dan SESUDAH reranking.
    4. Panggil `evaluate_run()` untuk masing-masing (before/after) dan
       bandingkan hasilnya.

Catatan penting soal ground truth:
    Karena kamu tidak punya label relevansi manual, cara paling objektif
    dan cepat adalah mendefinisikan resep "relevan" terhadap suatu query
    jika proporsi bahan resep yang match dengan bahan yang dimiliki user
    berada di atas suatu threshold (misal >= 0.5 artinya minimal separuh
    bahan resep sudah dimiliki user). Ini bisa dihitung otomatis untuk
    seluruh 5000 resep tanpa perlu human labeling, dan tetap valid secara
    metodologis untuk dijelaskan ke dospem (relevansi = ingredient coverage).

    Kamu bisa juga membuat 2 level relevansi (graded relevance) untuk NDCG,
    misal:
        overlap_ratio >= 0.8  -> relevance = 2 (sangat relevan)
        overlap_ratio >= 0.5  -> relevance = 1 (relevan)
        overlap_ratio <  0.5  -> relevance = 0 (tidak relevan)
"""

import re
import math
from typing import List, Dict, Set, Callable


# ---------------------------------------------------------------------------
# 1. UTILITAS NORMALISASI BAHAN
# ---------------------------------------------------------------------------

# Kata-kata satuan/ukuran yang perlu dibuang agar perbandingan bahan lebih adil
UNIT_WORDS = {
    "sdm",
    "sdt",
    "gr",
    "gram",
    "kg",
    "ml",
    "liter",
    "l",
    "butir",
    "buah",
    "siung",
    "lembar",
    "batang",
    "ekor",
    "potong",
    "ruas",
    "genggam",
    "secukupnya",
    "sejumput",
    "sesuai",
    "selera",
    "bungkus",
    "sachet",
    "biji",
    "ikat",
    "cm",
    "ons",
}


def normalize_ingredient(raw: str) -> str:
    """
    Ubah string bahan mentah (misal '2 butir telur ayam') menjadi bentuk
    yang lebih bisa dibandingkan (misal 'telur ayam').
    Ini SANGAT sederhana (rule-based) - sesuaikan dengan preprocessing
    yang kamu pakai di pipeline utama supaya konsisten.
    """
    text = raw.lower().strip()
    text = re.sub(r"\(.*?\)", "", text)  # hapus keterangan dalam kurung
    text = re.sub(r"[0-9/.,]+", "", text)  # hapus angka
    tokens = [t for t in text.split() if t not in UNIT_WORDS]
    return " ".join(tokens).strip()


def ingredient_set(ingredients: List[str]) -> Set[str]:
    return {normalize_ingredient(i) for i in ingredients if normalize_ingredient(i)}


# ---------------------------------------------------------------------------
# 2. GROUND TRUTH OTOMATIS BERDASARKAN OVERLAP BAHAN
# ---------------------------------------------------------------------------


def ingredient_overlap_ratio(
    query_ingredients: Set[str], recipe_ingredients: Set[str]
) -> float:
    """
    Proporsi bahan RESEP yang sudah tercakup oleh bahan yang dimiliki user.
    overlap_ratio = |query ∩ recipe| / |recipe|
    (dipilih dibagi |recipe|, bukan |query|, karena yang ingin diukur adalah
    'seberapa besar resep ini bisa dibuat hanya dengan bahan yang dimiliki user')
    """
    if not recipe_ingredients:
        return 0.0
    overlap = query_ingredients & recipe_ingredients
    return len(overlap) / len(recipe_ingredients)


def build_ground_truth(
    query_ingredients: Set[str],
    all_recipes: List[Dict],
    threshold_relevant: float = 0.5,
    threshold_highly_relevant: float = 0.8,
) -> Dict[int, int]:
    """
    Bangun ground truth graded relevance untuk SATU query, terhadap semua
    resep di dataset (dipakai untuk hitung Recall, karena Recall butuh tahu
    total resep relevan di SELURUH dataset, bukan cuma yang di-retrieve).

    Return: dict {recipe_index: relevance_level}
        relevance_level: 0 (tidak relevan), 1 (relevan), 2 (sangat relevan)
    """
    ground_truth = {}
    for idx, recipe in enumerate(all_recipes):
        recipe_ing = ingredient_set(recipe["ingredients"])
        ratio = ingredient_overlap_ratio(query_ingredients, recipe_ing)
        if ratio >= threshold_highly_relevant:
            ground_truth[idx] = 2
        elif ratio >= threshold_relevant:
            ground_truth[idx] = 1
        else:
            ground_truth[idx] = 0
    return ground_truth


# ---------------------------------------------------------------------------
# 3. METRIK EVALUASI
# ---------------------------------------------------------------------------


def precision_at_k(
    retrieved_ids: List[int], ground_truth: Dict[int, int], k: int
) -> float:
    """Precision@K: dari K resep teratas yang direkomendasikan, berapa % yang relevan (relevance >= 1)."""
    top_k = retrieved_ids[:k]
    if not top_k:
        return 0.0
    relevant_count = sum(1 for rid in top_k if ground_truth.get(rid, 0) >= 1)
    return relevant_count / len(top_k)


def recall_at_k(
    retrieved_ids: List[int], ground_truth: Dict[int, int], k: int
) -> float:
    """Recall@K: dari SEMUA resep relevan di dataset, berapa % yang berhasil masuk top-K."""
    total_relevant = sum(1 for v in ground_truth.values() if v >= 1)
    if total_relevant == 0:
        return 0.0
    top_k = retrieved_ids[:k]
    relevant_found = sum(1 for rid in top_k if ground_truth.get(rid, 0) >= 1)
    return relevant_found / total_relevant


def ndcg_at_k(retrieved_ids: List[int], ground_truth: Dict[int, int], k: int) -> float:
    """
    NDCG@K: mengukur kualitas URUTAN rekomendasi, bukan cuma relevan/tidak.
    Cocok dipakai untuk membandingkan before vs after reranking, karena
    reranking tujuannya menaikkan posisi resep yang paling efisien bahannya.
    """
    top_k = retrieved_ids[:k]

    # DCG: dampak posisi (resep di rank 1 lebih berharga dari rank 10)
    dcg = 0.0
    for i, rid in enumerate(top_k):
        rel = ground_truth.get(rid, 0)
        dcg += rel / math.log2(
            i + 2
        )  # i+2 karena rank dimulai dari 1, log2(1)=0 -> pakai i+2

    # IDCG: skor DCG ideal jika resep diurutkan sempurna berdasar relevansi
    ideal_relevances = sorted(ground_truth.values(), reverse=True)[:k]
    idcg = sum(rel / math.log2(i + 2) for i, rel in enumerate(ideal_relevances))

    if idcg == 0:
        return 0.0
    return dcg / idcg


def ingredient_efficiency_score(
    retrieved_ids: List[int],
    all_recipes: List[Dict],
    query_ingredients: Set[str],
    k: int,
) -> float:
    """
    Metrik tambahan (bukan dari IR klasik, tapi relevan untuk skripsi ini):
    rata-rata overlap_ratio dari top-K hasil akhir.
    Menjawab pertanyaan "seberapa efisien bahan yang dipakai dari resep yang direkomendasikan".
    """
    top_k = retrieved_ids[:k]
    if not top_k:
        return 0.0
    scores = []
    for rid in top_k:
        recipe_ing = ingredient_set(all_recipes[rid]["ingredients"])
        scores.append(ingredient_overlap_ratio(query_ingredients, recipe_ing))
    return sum(scores) / len(scores)


# ---------------------------------------------------------------------------
# 4. EVALUASI SATU RUN (untuk satu query, di satu tahap: before/after rerank)
# ---------------------------------------------------------------------------


def evaluate_run(
    retrieved_ids: List[int],
    ground_truth: Dict[int, int],
    all_recipes: List[Dict],
    query_ingredients: Set[str],
    k_values: List[int] = [5, 10],
) -> Dict[str, float]:
    results = {}
    for k in k_values:
        results[f"precision@{k}"] = precision_at_k(retrieved_ids, ground_truth, k)
        results[f"recall@{k}"] = recall_at_k(retrieved_ids, ground_truth, k)
        results[f"ndcg@{k}"] = ndcg_at_k(retrieved_ids, ground_truth, k)
        results[f"ingredient_efficiency@{k}"] = ingredient_efficiency_score(
            retrieved_ids, all_recipes, query_ingredients, k
        )
    return results


# ---------------------------------------------------------------------------
# 5. EVALUASI BANYAK QUERY SEKALIGUS + PERBANDINGAN BEFORE vs AFTER RERANKING
# ---------------------------------------------------------------------------


def evaluate_before_after(
    test_queries: List[List[str]],  # list of ingredient-lists, satu per query test
    all_recipes: List[
        Dict
    ],  # seluruh 5000 resep (list of dict dengan key "ingredients")
    sbert_retrieval_fn: Callable[
        [List[str]], List[int]
    ],  # fungsi retrieval SBERT-mu, return list index recipe (sebelum rerank)
    reranking_fn: Callable[
        [List[int], List[str]], List[int]
    ],  # fungsi reranking-mu, input top-K SBERT + query, return urutan baru
    k_values: List[int] = [5, 10],
    threshold_relevant: float = 0.5,
    threshold_highly_relevant: float = 0.8,
):
    """
    Jalankan evaluasi untuk semua query test, lalu rata-ratakan hasilnya.
    Mengembalikan dua dict metrik: sebelum reranking dan sesudah reranking.
    """
    before_all = []
    after_all = []

    for raw_query in test_queries:
        query_ing = ingredient_set(raw_query)

        # ground truth dihitung sekali per query, dipakai untuk before & after
        gt = build_ground_truth(
            query_ing,
            all_recipes,
            threshold_relevant=threshold_relevant,
            threshold_highly_relevant=threshold_highly_relevant,
        )

        # --- BEFORE reranking (murni skor SBERT) ---
        retrieved_before = sbert_retrieval_fn(raw_query)
        before_all.append(
            evaluate_run(retrieved_before, gt, all_recipes, query_ing, k_values)
        )

        # --- AFTER reranking ---
        retrieved_after = reranking_fn(retrieved_before, raw_query)
        after_all.append(
            evaluate_run(retrieved_after, gt, all_recipes, query_ing, k_values)
        )

    def average_metrics(list_of_dicts):
        keys = list_of_dicts[0].keys()
        return {k: sum(d[k] for d in list_of_dicts) / len(list_of_dicts) for k in keys}

    return {
        "before_reranking": average_metrics(before_all),
        "after_reranking": average_metrics(after_all),
    }


# ---------------------------------------------------------------------------
# 6. CONTOH PENGGUNAAN (GANTI DENGAN FUNGSI RETRIEVAL & RERANKING ASLI KAMU)
# ---------------------------------------------------------------------------

if __name__ == "__main__":
    # Contoh dataset mini (GANTI dengan load dari parquet 5000 resep asli kamu)
    all_recipes = [
        {
            "ingredients": [
                "2 butir telur",
                "100 gr dada ayam",
                "2 siung bawang putih",
                "1 sdt garam",
            ]
        },
        {"ingredients": ["1 ekor ikan bandeng", "4 buah tahu", "1 buah tomat"]},
        {"ingredients": ["2 butir telur", "1 buah tomat", "1 sdm kecap manis"]},
        # ... isi dengan 5000 resep asli
    ]

    test_queries = [
        ["2 butir telur", "100 gr dada ayam", "2 siung bawang putih"],
        # tambahkan 30-50 query test lain di sini
    ]

    def dummy_sbert_retrieval(query_ingredients_list):
        # GANTI: panggil ChromaDB query dengan embedding SBERT, return top-K index
        return [0, 2, 1]

    def dummy_reranking(top_k_ids, query_ingredients_list):
        # GANTI: panggil algoritma reranking kamu (skor SBERT + skor efisiensi bahan)
        return top_k_ids  # sementara dummy, urutan sama

    hasil = evaluate_before_after(
        test_queries=test_queries,
        all_recipes=all_recipes,
        sbert_retrieval_fn=dummy_sbert_retrieval,
        reranking_fn=dummy_reranking,
        k_values=[3],  # ganti jadi [5, 10] kalau dataset sudah penuh
    )

    print("=== SEBELUM RERANKING ===")
    for k, v in hasil["before_reranking"].items():
        print(f"  {k}: {v:.4f}")

    print("\n=== SESUDAH RERANKING ===")
    for k, v in hasil["after_reranking"].items():
        print(f"  {k}: {v:.4f}")
