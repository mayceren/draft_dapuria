"""
Jalankan pipeline matching (match_ground_truth.py) terhadap data asli:
- resep_primer_yummy.csv (300 resep hasil scraping)
- resep_5000_clean_SAFE.csv (corpus utama)

CATATAN: MAIN_INGREDIENT_KEYWORDS_FLAT dan ingredient_matches() di bawah ini
disalin dari notebook 03_reranking (cell 14 dan cell 7) supaya konsisten satu
sumber definisi. Kalau notebook reranking diupdate lagi nanti, blok ini juga
perlu disinkronkan ulang -- idealnya dipindah ke 1 file bersama (util.py) yang
di-import oleh notebook maupun script ini, bukan disalin manual begini.
"""

import pandas as pd
import json
import re
import csv
import sys

sys.path.insert(0, ".")
from match_ground_truth import (
    find_best_matches,
    THRESHOLD_TITLE_MIN,
    THRESHOLD_TITLE_HIGH,
    THRESHOLD_INGREDIENT_HIGH,
)


def ingredient_matches(u: str, r: str) -> bool:
    u, r = u.lower().strip(), r.lower().strip()
    if not u or not r:
        return False
    return u in r or r in u


# --- MAIN_INGREDIENT_KEYWORDS lengkap, disalin persis dari notebook 03_reranking
# cell 14 / Lampiran 1 (7 kelompok panganku.org). Lihat catatan modul di atas
# soal risiko duplikasi manual -- idealnya di-share lewat 1 file util bersama. ---
MAIN_INGREDIENT_KEYWORDS = {
    "Serealia": {
        "beras",
        "nasi",
        "ketan",
        "jagung",
        "cantel",
        "jali",
        "jawawut",
        "jampang huma",
        "tepung beras",
        "tepung jagung",
        "tepung terigu",
        "maizena",
        "bihun",
        "mie",
        "mi",
        "misoa",
        "makaroni",
        "spaghetti",
        "roti",
    },
    "Umbi Berpati": {
        "kentang",
        "singkong",
        "ketela pohon",
        "ubi",
        "ubi jalar",
        "ubi cilembu",
        "talas",
        "gembili",
        "gadung",
        "ganyong",
        "suweg",
        "uwi",
        "sente",
        "bengkuang",
        "arrowroot",
        "sagu",
        "tapioka",
        "tepung singkong",
        "tepung kentang",
        "tepung ganyong",
        "tepung mocaf",
        "mocaf",
        "tepung arrowroot",
        "tepung ubi",
    },
    "Kacang-kacangan": {
        "kacang arab",
        "kacang bogor",
        "kacang ercis",
        "kacang gude",
        "kacang hijau",
        "kacang hitam",
        "kacang kapri",
        "kedelai",
        "kacang kedelai",
        "kacang komak",
        "kacang merah",
        "kacang mete",
        "kacang tanah",
        "kacang tolo",
        "kacang tunggak",
        "kacang panjang",
        "kenari",
        "koro",
        "lamtoro",
        "wijen",
        "tahu",
        "tempe",
        "oncom",
        "kembang tahu",
        "susu kedelai",
        "tauco",
        "tepung hunkwe",
        "hunkwe",
        "tepung jalejo",
        "tepung kacang kedelai",
        "tepung kedelai",
    },
    "Sayuran": {
        "akar tonjong",
        "bit",
        "lobak",
        "rebung",
        "umbut kelapa",
        "umbut rotan",
        "ale",
        "toge",
        "taoge",
        "taoge kacang kedelai",
        "taoge kacang tunggak",
        "andewi",
        "bayam",
        "bayam merah",
        "daun bangun-bangun",
        "daun bebuas",
        "daun belem",
        "daun bluntas",
        "daun gandaria",
        "daun gedi",
        "daun gedi besar",
        "daun gedi kecil",
        "daun gelang",
        "daun gunda",
        "daun gunda bali",
        "daun gunda serang",
        "daun jambu mete",
        "daun jampang",
        "daun jawaw seluang",
        "daun jonghe",
        "daun kacang ma",
        "daun kacang panjang",
        "daun kasbi",
        "daun singkong karet",
        "daun katuk",
        "daun kecipir",
        "daun kedondong",
        "daun kelor",
        "daun kemang",
        "daun kenikir",
        "kenikir",
        "daun kol sawi",
        "daun koro",
        "daun kubis",
        "daun kumak",
        "daun labu siam",
        "daun labu",
        "daun labu waluh",
        "daun labu kuning",
        "daun lamtoro",
        "daun leilem",
        "daun leunca",
        "daun lobak",
        "daun lompong",
        "daun lompong talas",
        "daun mangkokan",
        "daun matel ambon",
        "daun melinjo",
        "daun mengkudu",
        "daun ndusuk",
        "daun oyong",
        "daun pakis",
        "daun pakis longgiho",
        "daun pakis wambateu",
        "daun paku",
        "daun pangi",
        "daun pare",
        "daun pepaya",
        "daun pohpohan",
        "pohpohan",
        "daun semanggi",
        "semanggi",
        "daun simpur",
        "daun singkil",
        "daun singkong",
        "daun singkong ambon",
        "daun singkong ampenan",
        "daun singkong kopang",
        "daun sintrong",
        "sintrong",
        "daun talas",
        "daun tespong",
        "tespong",
        "daun ubi",
        "daun ubi kuning",
        "daun ubi merah",
        "daun ubi putih",
        "daun ubi tinta",
        "eceng",
        "genjer",
        "kalakai",
        "kangkung",
        "kangkung tondano",
        "selada",
        "selada air",
        "sawi",
        "sawi putih",
        "pecai",
        "sawi taiwan",
        "sawi tanah",
        "mostarda metan",
        "baligo",
        "buah kelor",
        "buah merah",
        "gambas",
        "oyong",
        "jagung muda",
        "jagung semi",
        "baby corn",
        "jantung pisang",
        "jotang",
        "kabau",
        "karawila",
        "kelawi",
        "kluwih",
        "ketimun",
        "timun",
        "ketimun krai",
        "ketimun madura",
        "kundur",
        "labu air",
        "labu kuning",
        "labu siam",
        "labu waluh",
        "waluh",
        "lantar",
        "leunca",
        "lumai",
        "nangka muda",
        "paria putih",
        "pare",
        "paria",
        "pepare ular",
        "pepaya muda",
        "rimbang",
        "tekokak",
        "terong",
        "terung",
        "terong asam",
        "terung belanda",
        "terung bengkulu",
        "terong hintalo",
        "terung panjang",
        "tomat",
        "tomat merah",
        "tomat muda",
        "buncis",
        "kacang mekah",
        "kacang ranti",
        "kapri muda",
        "kecipir muda",
        "komak",
        "koro kerupuk",
        "koro wedus",
        "caisin",
        "kool kembang",
        "kembang kol",
        "kol kembang",
        "kool merah",
        "kol merah",
        "kool putih",
        "kol putih",
        "kubis",
        "kol",
        "bunga pepaya",
        "bunga turi",
        "kembang turi",
        "uceng",
        "bunga melinjo",
        "jamur",
        "jamur encik",
        "jamur kuping",
        "jamur merang",
        "jamur tiram",
        "jamur sagu",
        "jengkol",
        "kerokot",
        "kulit melinjo",
        "melinjo",
        "petai",
        "putri malu",
        "rumput laut",
        "tebu terubuk",
        "terubuk",
        "wortel",
    },
    "Daging": {
        "sapi",
        "ayam",
        "angsa",
        "babi",
        "bebek",
        "itik",
        "belibis",
        "burung",
        "domba",
        "kambing",
        "kelinci",
        "kerbau",
        "kuda",
        "ulat sagu",
        "buaya",
        "menjangan",
        "punai",
        "rusa",
        "penyu",
        "anjing",
        "tikus",
        "daging",
        "babat",
        "jeroan",
        "daleman",
        "hati",
        "ginjal",
        "usus",
        "otak",
        "kikil",
        "buntut",
        "ampela",
        "ham",
        "dendeng",
        "kornet",
        "sosis",
    },
    "Ikan/Kerang/Udang/dll": {
        "belut",
        "belut laut",
        "cumi-cumi",
        "cumi",
        "ikan",
        "ikan bader",
        "ikan balong",
        "ikan bambangan",
        "ikan bandeng",
        "bandeng",
        "ikan banjar",
        "ikan baronang",
        "baronang",
        "ikan batung",
        "ikan baung",
        "baung",
        "ikan bawal",
        "bawal",
        "ikan belida",
        "belida",
        "ikan beunteur",
        "ikan biawan",
        "ikan bili",
        "ikan bubara",
        "ikan bulan-bulan",
        "ikan cakalang",
        "cakalang",
        "ikan daun",
        "ikan ekor kuning",
        "ekor kuning",
        "ikan gabus",
        "gabus",
        "ikan heu",
        "ikan hitam",
        "ikan hiu",
        "hiu",
        "ikan kacangan",
        "ikan kakap",
        "kakap",
        "kakap merah",
        "ikan kakatua",
        "ikan kalaban",
        "ikan kamera",
        "ikan kapar",
        "ikan kawalinya",
        "ikan keru-keru",
        "ikan kima",
        "ikan lais",
        "lais",
        "ikan layang",
        "layang",
        "ikan layur",
        "layur",
        "ikan lehoma",
        "ikan lemuru",
        "lemuru",
        "ikan lidah",
        "ikan malalugis",
        "ikan mamar merah",
        "ikan mas",
        "ikan mayong",
        "ikan mujahir",
        "mujahir",
        "ikan nasu metti",
        "ikan oci",
        "ikan kembung",
        "kembung",
        "ikan paling",
        "ikan papuyu",
        "papuyu",
        "betok",
        "ikan patin",
        "patin",
        "ikan pomo",
        "ikan puntin",
        "ikan saluang",
        "saluang",
        "ikan sarden",
        "sarden",
        "ikan selar",
        "selar",
        "ikan sepat",
        "sepat",
        "ikan sidat",
        "sidat",
        "ikan sunu",
        "sunu",
        "ikan tahuman",
        "ikan tarmon",
        "ikan telan",
        "ikan tembang",
        "ikan tempahas",
        "ikan terbang",
        "ikan teri",
        "teri",
        "ikan titang",
        "ikan tongkol",
        "tongkol",
        "ikan turi",
        "keong",
        "kepiting",
        "kerang",
        "kodok",
        "kura-kura",
        "kuro",
        "lokan",
        "rajungan",
        "rebon",
        "udang",
        "udang galah",
        "ikan asin",
        "ikan kering",
        "ikan asap",
        "ikan pindang",
        "pindang",
        "ikan sale",
        "ikan kayu",
        "peda",
        "jambal",
        "sarden kaleng",
        "sardines dalam kaleng",
        "rebon kering",
        "udang kering",
        "abon ikan",
        "tepung ikan",
        "tepung teri",
    },
    "Telur": {"telur"},
}
MAIN_INGREDIENT_KEYWORDS_FLAT = set().union(*MAIN_INGREDIENT_KEYWORDS.values())


def load_corpus(path: str) -> list[dict]:
    df = pd.read_csv(path)
    corpus = []
    for _, row in df.iterrows():
        try:
            ingredient_names = json.loads(row["ingredient_names"])
        except (json.JSONDecodeError, TypeError):
            ingredient_names = []
        corpus.append({"title": row["title"], "ingredients": ingredient_names})
    return corpus


def load_scraped(path: str) -> list[dict]:
    df = pd.read_csv(path)
    scraped = []
    for _, row in df.iterrows():
        ingredients = (
            str(row["ingredients_raw"]).split(" | ")
            if pd.notna(row["ingredients_raw"])
            else []
        )
        scraped.append(
            {"url": row["url"], "title": row["title"], "ingredients": ingredients}
        )
    return scraped


if __name__ == "__main__":
    print("Memuat corpus 5000...")
    corpus = load_corpus("resep_5000_clean_SAFE.csv")
    print(f"  -> {len(corpus)} resep dimuat")

    print("Memuat hasil scraping Yummy...")
    scraped = load_scraped("resep_primer_yummy.csv")
    print(f"  -> {len(scraped)} resep dimuat")

    print(
        f"\nMenjalankan matching penuh: {len(scraped)} resep x {len(corpus)} corpus..."
    )
    print("(sekitar 1 menit, sudah pernah diuji -- tidak perlu subset kecil lagi)")
    results = find_best_matches(
        scraped, corpus, MAIN_INGREDIENT_KEYWORDS_FLAT, ingredient_matches
    )

    from collections import Counter

    label_counts = Counter(r["label"] for r in results)
    print(f"\n=== RINGKASAN {len(scraped)} RESEP ===")
    for label in ["AUTO_MATCH", "MANUAL_REVIEW", "NO_MATCH"]:
        print(f"{label}: {label_counts.get(label, 0)}")

    # simpan SEMUA hasil (AUTO_MATCH + MANUAL_REVIEW + NO_MATCH) ke 1 CSV lengkap
    with open("hasil_matching_300.csv", "w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(
            f,
            fieldnames=[
                "scraped_title",
                "corpus_title",
                "label",
                "title_sim",
                "ingredient_jaccard",
                "method_style_conflict",
                "reason",
                "scraped_url",
            ],
        )
        writer.writeheader()
        for r in results:
            writer.writerow(r)
    print("\nSeluruh hasil (semua label) tersimpan ke hasil_matching_300.csv")

    # simpan KHUSUS AUTO_MATCH ke file terpisah -- ini yang perlu kamu spot-check
    # dulu (jumlahnya sedikit, cepat dicek) sebelum dipakai sebagai ground truth final
    auto_matches = [r for r in results if r["label"] == "AUTO_MATCH"]
    with open(
        "hasil_AUTO_MATCH_untuk_dicek.csv", "w", newline="", encoding="utf-8"
    ) as f:
        writer = csv.DictWriter(
            f,
            fieldnames=[
                "scraped_title",
                "corpus_title",
                "title_sim",
                "ingredient_jaccard",
                "reason",
                "scraped_url",
            ],
        )
        writer.writeheader()
        for r in auto_matches:
            writer.writerow({k: r[k] for k in writer.fieldnames})
    print(
        f"{len(auto_matches)} AUTO_MATCH tersimpan terpisah ke hasil_AUTO_MATCH_untuk_dicek.csv (cek ini dulu!)"
    )

    # simpan KHUSUS MANUAL_REVIEW, diurutkan dari yang paling mungkin valid
    # (title_sim tinggi + ingredient_jaccard tinggi duluan) -- biar peninjauan
    # manual efisien, tidak perlu diacak/urut dari atas ke bawah apa adanya
    manual_reviews = [r for r in results if r["label"] == "MANUAL_REVIEW"]
    manual_reviews.sort(
        key=lambda r: (r["title_sim"] or 0, r["ingredient_jaccard"] or 0), reverse=True
    )
    with open(
        "hasil_MANUAL_REVIEW_untuk_dicek.csv", "w", newline="", encoding="utf-8"
    ) as f:
        writer = csv.DictWriter(
            f,
            fieldnames=[
                "scraped_title",
                "corpus_title",
                "title_sim",
                "ingredient_jaccard",
                "method_style_conflict",
                "reason",
                "scraped_url",
            ],
        )
        writer.writeheader()
        for r in manual_reviews:
            writer.writerow({k: r[k] for k in writer.fieldnames})
    print(
        f"{len(manual_reviews)} MANUAL_REVIEW tersimpan terpisah ke hasil_MANUAL_REVIEW_untuk_dicek.csv "
        f"(sudah diurutkan, yang paling mungkin valid ada di baris paling atas)"
    )
