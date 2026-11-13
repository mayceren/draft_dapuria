"""
Matching data primer (hasil scraping) terhadap corpus 5.000 resep utama,
untuk membangun ground truth evaluasi (sub-bab 3.1.3.11.1).

Alur: Tahap 1 (kemiripan judul) -> Tahap 2 (overlap bahan utama, difilter
Lampiran 1) -> Tahap 3 (cek konflik kata kunci metode/gaya masak).
Keluaran per pasangan: AUTO_MATCH, MANUAL_REVIEW, atau NO_MATCH.

CATATAN: ambang batas (THRESHOLD_*) di bawah ini adalah nilai AWAL yang masuk akal,
BUKAN hasil kalibrasi/tuning. Setelah dijalankan ke data asli, sebaiknya diperiksa
manual sebagian hasil AUTO_MATCH (pastikan tidak ada yang keliru) dan sebagian
NO_MATCH dengan skor mepet ambang (pastikan tidak ada pasangan valid yang tersaring),
baru ambang batas disesuaikan bila perlu -- sama seperti proses grid search w1/w2.
"""

import re
import json
import difflib

THRESHOLD_TITLE_MIN = 0.55
THRESHOLD_TITLE_HIGH = 0.85
THRESHOLD_INGREDIENT_HIGH = 0.5

METHOD_KEYWORDS = {
    "goreng",
    "bakar",
    "panggang",
    "rebus",
    "kukus",
    "tumis",
    "oseng",
    "presto",
    "sangrai",
    "blansir",
}
DISH_STYLE_KEYWORDS = {
    "semur",
    "gulai",
    "opor",
    "kari",
    "kare",
    "balado",
    "pepes",
    "sup",
    "sop",
    "rica-rica",
    "rica",
    "woku",
    "rendang",
    "asam manis",
    "asam pedas",
    "saus tiram",
    "teriyaki",
    "bumbu bali",
    "mangut",
    "betutu",
}
METHOD_STYLE_KEYWORDS = METHOD_KEYWORDS | DISH_STYLE_KEYWORDS

TITLE_STOPWORDS = {
    "resep",
    "cara",
    "membuat",
    "ala",
    "istimewa",
    "spesial",
    "enak",
    "praktis",
    "sederhana",
}


def normalize_title(title: str) -> str:
    t = title.lower()
    t = re.sub(r"[^\w\s]", " ", t)
    words = [w for w in t.split() if w not in TITLE_STOPWORDS]
    return " ".join(words)


def title_similarity(title_a: str, title_b: str) -> float:
    a, b = normalize_title(title_a), normalize_title(title_b)
    return difflib.SequenceMatcher(None, a, b).ratio()


def extract_main_ingredients(
    ingredient_list, main_ingredient_keywords_flat, ingredient_matches_fn
):
    found = set()
    for raw_item in ingredient_list:
        raw_item_lower = raw_item.lower()
        for kw in main_ingredient_keywords_flat:
            if len(kw) > 5:
                if ingredient_matches_fn(raw_item_lower, kw):
                    found.add(kw)
            else:
                if re.search(rf"\b{re.escape(kw)}\b", raw_item_lower):
                    found.add(kw)
    return found


def jaccard(set_a: set, set_b: set) -> float:
    if not set_a and not set_b:
        return 0.0
    union = set_a | set_b
    if not union:
        return 0.0
    return len(set_a & set_b) / len(union)


def extract_method_style(title: str) -> set:
    t = title.lower()
    found = set()
    for kw in METHOD_STYLE_KEYWORDS:
        if re.search(rf"\b{re.escape(kw)}\b", t):
            found.add(kw)
    return found


def match_recipe_pair(
    scraped_title,
    scraped_ingredients,
    corpus_title,
    corpus_ingredients,
    main_ingredient_keywords_flat,
    ingredient_matches_fn,
) -> dict:
    t_sim = title_similarity(scraped_title, corpus_title)

    if t_sim < THRESHOLD_TITLE_MIN:
        return {
            "label": "NO_MATCH",
            "title_sim": t_sim,
            "ingredient_jaccard": None,
            "method_style_conflict": None,
            "reason": "judul di bawah ambang minimum",
        }

    main_a = extract_main_ingredients(
        scraped_ingredients, main_ingredient_keywords_flat, ingredient_matches_fn
    )
    main_b = extract_main_ingredients(
        corpus_ingredients, main_ingredient_keywords_flat, ingredient_matches_fn
    )
    ing_jaccard = jaccard(main_a, main_b)

    style_a = extract_method_style(scraped_title)
    style_b = extract_method_style(corpus_title)
    has_conflict = bool(style_a) and bool(style_b) and not (style_a & style_b)

    if has_conflict:
        return {
            "label": "MANUAL_REVIEW",
            "title_sim": t_sim,
            "ingredient_jaccard": ing_jaccard,
            "method_style_conflict": f"{style_a} vs {style_b}",
            "reason": "kata kunci metode/gaya berbeda, wajib verifikasi manusia",
        }

    if t_sim >= THRESHOLD_TITLE_HIGH and ing_jaccard >= THRESHOLD_INGREDIENT_HIGH:
        return {
            "label": "AUTO_MATCH",
            "title_sim": t_sim,
            "ingredient_jaccard": ing_jaccard,
            "method_style_conflict": None,
            "reason": "judul & bahan utama sama-sama tinggi, tidak ada konflik",
        }

    # tambahan: kalau judul SAMA PERSIS (identik setelah normalisasi) itu sinyal
    # sangat kuat sendirian -- tidak perlu ingredient_jaccard setinggi kasus umum,
    # cukup pastikan ada minimal SEDIKIT kesamaan bahan (bukan nol) sebagai
    # penguat. Ditemukan lewat pengecekan data asli: banyak pasangan title_sim=1.0
    # (mis. "Ayam Kecap" vs "Ayam kecap") tertahan di MANUAL_REVIEW hanya karena
    # jaccard sedikit di bawah 0.5, padahal judul identik sudah sangat meyakinkan.
    if t_sim >= 0.95 and ing_jaccard > 0.0:
        return {
            "label": "AUTO_MATCH",
            "title_sim": t_sim,
            "ingredient_jaccard": ing_jaccard,
            "method_style_conflict": None,
            "reason": "judul identik/nyaris identik, didukung kesamaan bahan (meski di bawah ambang umum)",
        }

    # tambahan: kalau TIDAK ADA satupun bahan utama yang sama (jaccard persis 0),
    # kemiripan judul kemungkinan besar cuma kebetulan struktur kalimat, bukan
    # kesamaan hidangan -- turunkan ke NO_MATCH, jangan bebani manual review
    # dengan pasangan yang sudah jelas tidak nyambung (ditemukan lewat pengecekan
    # data asli: "Kentang Mustofa" vs "Rendang Sapi" title_sim=0.59 tapi jaccard=0.0)
    if ing_jaccard == 0.0:
        return {
            "label": "NO_MATCH",
            "title_sim": t_sim,
            "ingredient_jaccard": ing_jaccard,
            "method_style_conflict": None,
            "reason": "tidak ada kesamaan bahan utama sama sekali, kemiripan judul kemungkinan kebetulan",
        }

    return {
        "label": "MANUAL_REVIEW",
        "title_sim": t_sim,
        "ingredient_jaccard": ing_jaccard,
        "method_style_conflict": None,
        "reason": "skor di zona ambigu",
    }


def find_best_matches(
    scraped_recipes,
    corpus_recipes,
    main_ingredient_keywords_flat,
    ingredient_matches_fn,
):
    results = []
    for scraped in scraped_recipes:
        best = None
        for corpus in corpus_recipes:
            quick_sim = title_similarity(scraped["title"], corpus["title"])
            if quick_sim < THRESHOLD_TITLE_MIN:
                continue
            if best is None or quick_sim > best[0]:
                best = (quick_sim, corpus)

        if best is None:
            results.append(
                {
                    "scraped_url": scraped["url"],
                    "scraped_title": scraped["title"],
                    "corpus_title": None,
                    "label": "NO_MATCH",
                    "title_sim": None,
                    "ingredient_jaccard": None,
                    "reason": "tidak ada kandidat di atas ambang minimum",
                }
            )
            continue

        _, corpus = best
        match_result = match_recipe_pair(
            scraped["title"],
            scraped["ingredients"],
            corpus["title"],
            corpus["ingredients"],
            main_ingredient_keywords_flat,
            ingredient_matches_fn,
        )
        results.append(
            {
                "scraped_url": scraped["url"],
                "scraped_title": scraped["title"],
                "corpus_title": corpus["title"],
                **match_result,
            }
        )
    return results
