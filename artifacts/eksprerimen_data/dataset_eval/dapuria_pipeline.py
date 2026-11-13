"""
Dapuria production retrieval + reranking pipeline.

Frozen configuration based on validation/test evaluation:
- SBERT: LazarusNLP/all-indo-e5-small-v4
- Semantic retrieval: top 50
- Keyword extra: max 20
- Semantic normalization: min-max per candidate pool
- WLC: 0.7 semantic + 0.3 harmonic ingredient efficiency
- Guardrails: T_jumlah=1, T_kategori>=1 main ingredient,
  T_relevansi=min(2, number of user ingredients)

Llama 3 is intentionally NOT used for parsing, retrieval, reranking,
threshold decisions, or recipe generation. It may only verbalize the
structured result returned by handle_user_input().
"""

from __future__ import annotations

import html
import json
import re
from dataclasses import dataclass, asdict
from collections.abc import Mapping
from typing import Any

import chromadb
import numpy as np
from sentence_transformers import SentenceTransformer


# ============================================================
# 1. Frozen configuration
# ============================================================

MODEL_NAME = "LazarusNLP/all-indo-e5-small-v4"
CHROMA_DIR = "chroma_db"
COLLECTION_NAME = "resep_masakan"

TOP_K_SBERT = 50
MAX_KEYWORD_EXTRA = 20
W1_FINAL = 0.7
W2_FINAL = 0.3
TOP_N_DEFAULT = 5

T_JUMLAH = 1


def add_query_prefix(text: str) -> str:
    return f"query: {text}"


# ============================================================
# 2. User ingredient parser
# ============================================================

UNITS = [
    "sendok makan",
    "sendok teh",
    "sdm",
    "sdt",
    "gram",
    "gr",
    "kg",
    "ons",
    "ml",
    "mili",
    "liter",
    "ltr",
    "l",
    "butir",
    "btr",
    "buah",
    "bh",
    "siung",
    "lembar",
    "lbr",
    "batang",
    "btg",
    "ikat",
    "ruas",
    "cm",
    "potong",
    "ptg",
    "biji",
    "bj",
    "ekor",
    "ekr",
    "genggam",
    "bungkus",
    "bks",
    "sachet",
    "sct",
    "papan",
    "buku",
    "helai",
    "hlai",
    "gelas",
    "gls",
    "cup",
    "mangkuk",
    "piring",
    "sisir",
    "kotak",
    "ktk",
    "kaleng",
    "klg",
    "botol",
    "btl",
]
UNITS_SORTED = sorted(UNITS, key=len, reverse=True)
UNIT_PATTERN = "|".join(re.escape(u) for u in UNITS_SORTED)

QTY_PATTERN = (
    r"\d+\s*-\s*\d+"
    r"|\d+\s+\d+\s*/\s*\d+"
    r"|\d+\s*/\s*\d+"
    r"|\d+[.,]\d+"
    r"|\d+"
    r"|sesuai selera"
    r"|secukupnya"
    r"|sejumput"
    r"|beberapa"
)

INGREDIENT_REGEX = re.compile(
    rf"^\s*(?P<qty>{QTY_PATTERN})?\s*(?:(?P<unit>{UNIT_PATTERN})\b)?\.?\s*(?P<name>.+?)\s*$",
    re.IGNORECASE,
)


def clean_name(name: str) -> str:
    name = str(name).lower().strip()
    name = re.sub(r"\(.*?\)", "", name)
    name = re.sub(r"\s+", " ", name).strip()
    return name


def parse_ingredient(raw: str) -> dict[str, str]:
    raw = html.unescape(str(raw)).strip()
    raw = re.sub(r"^[\-\*•]+\s*", "", raw)
    main = raw.split(",", 1)[0].strip()
    m = INGREDIENT_REGEX.match(main)
    name = clean_name(m.group("name")) if (m and m.group("name")) else clean_name(main)
    return {"raw": raw, "name": name}


def parse_user_ingredients(text: str) -> list[str]:
    items = [t.strip() for t in str(text).split(",") if t.strip()]
    parsed = [parse_ingredient(item) for item in items]
    return [p["name"] for p in parsed if p["name"]]


# ============================================================
# 3. Ingredient matching + efficiency
# ============================================================


def ingredient_matches(user_name: str, recipe_name: str) -> bool:
    """Phrase-aware two-way match with word boundaries.

    Fixes substring false positives such as 'teri' matching 'terigu'.
    Still allows 'ayam' to match 'dada ayam'.
    """
    u = str(user_name).lower().strip()
    r = str(recipe_name).lower().strip()

    if not u or not r:
        return False
    if u == r:
        return True

    pattern_u = rf"(?<!\w){re.escape(u)}(?!\w)"
    pattern_r = rf"(?<!\w){re.escape(r)}(?!\w)"

    return bool(re.search(pattern_u, r) or re.search(pattern_r, u))


def coverage_stats(
    user_ingredients: list[str],
    recipe_ingredients: list[str],
) -> dict[str, Any]:
    if not recipe_ingredients:
        return {
            "coverage_recipe": 0.0,
            "coverage_user": 0.0,
            "matched_recipe_items": [],
            "matched_user_items": [],
            "missing_items": [],
        }

    matched_recipe_items: list[str] = []
    matched_user_items: set[str] = set()

    for recipe_name in recipe_ingredients:
        hit = False
        for user_name in user_ingredients:
            if ingredient_matches(user_name, recipe_name):
                hit = True
                matched_user_items.add(user_name)
        if hit:
            matched_recipe_items.append(recipe_name)

    missing_items = [r for r in recipe_ingredients if r not in matched_recipe_items]

    coverage_recipe = len(matched_recipe_items) / len(recipe_ingredients)
    coverage_user = (
        len(matched_user_items) / len(user_ingredients) if user_ingredients else 0.0
    )

    return {
        "coverage_recipe": coverage_recipe,
        "coverage_user": coverage_user,
        "matched_recipe_items": matched_recipe_items,
        "matched_user_items": sorted(matched_user_items),
        "missing_items": missing_items,
    }


def harmonic_efficiency(cr: float, cu: float) -> float:
    if cr + cu == 0:
        return 0.0
    return (2 * cr * cu) / (cr + cu)


# ============================================================
# 4. Main-ingredient rule base
# ============================================================

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
        "kacang panjang",
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
    "Telur": {
        "telur",
    },
}

MAIN_INGREDIENT_KEYWORDS_FLAT = set().union(*MAIN_INGREDIENT_KEYWORDS.values())


def is_main_ingredient(name: str) -> bool:
    name = str(name).lower().strip()
    for kw in MAIN_INGREDIENT_KEYWORDS_FLAT:
        if ingredient_matches(name, kw):
            return True
    return False


def classify_ingredient(name: str) -> str:
    return "bahan_utama" if is_main_ingredient(name) else "belum_terklasifikasi"


def has_main_ingredient(user_ingredients: list[str]) -> bool:
    return any(is_main_ingredient(u) for u in user_ingredients)


# ============================================================
# 5. Production service
# ============================================================


class DapuriaRecipeService:
    def __init__(
        self,
        chroma_dir: str = CHROMA_DIR,
        collection_name: str = COLLECTION_NAME,
        model_name: str = MODEL_NAME,
    ):
        self.model = SentenceTransformer(model_name)
        self.client = chromadb.PersistentClient(path=chroma_dir)
        self.collection = self.client.get_collection(collection_name)
        self._all_docs_cache: list[tuple[str, Any, Any, Any]] | None = None

    def healthcheck(self) -> dict[str, Any]:
        return {
            "model_name": MODEL_NAME,
            "collection_name": COLLECTION_NAME,
            "document_count": self.collection.count(),
            "config": {
                "top_k_sbert": TOP_K_SBERT,
                "max_keyword_extra": MAX_KEYWORD_EXTRA,
                "w1": W1_FINAL,
                "w2": W2_FINAL,
            },
        }

    @staticmethod
    def _parse_meta(meta: Mapping[str, Any] | None) -> dict[str, Any]:
        meta = meta or {}
        return {
            "title": meta.get("title", ""),
            "ingredient_names": json.loads(str(meta.get("ingredient_names") or "[]")),
            "steps_text": meta.get("steps_text", ""),
            "num_ingredients": meta.get("num_ingredients"),
        }

    def _semantic_candidates(
        self, user_text: str
    ) -> tuple[np.ndarray, list[dict[str, Any]]]:
        query_embedding = self.model.encode(
            [add_query_prefix(user_text)],
            normalize_embeddings=True,
            convert_to_numpy=True,
        )[0]

        results = self.collection.query(
            query_embeddings=[query_embedding.tolist()],
            n_results=TOP_K_SBERT,
            include=["documents", "metadatas", "distances"],
        )

        metadatas = results["metadatas"]
        distances = results["distances"]
        if metadatas is None or distances is None:
            raise RuntimeError("Chroma query did not return metadatas/distances.")

        candidates = []
        for i, recipe_id in enumerate(results["ids"][0]):
            meta = self._parse_meta(metadatas[0][i])
            candidates.append(
                {
                    "id": recipe_id,
                    **meta,
                    "sbert_score": float(1 - distances[0][i]),
                    "retrieval_source": "semantic",
                }
            )

        return query_embedding, candidates

    def _get_all_documents(self) -> list[tuple[str, Any, Any, Any]]:
        if self._all_docs_cache is None:
            raw = self.collection.get(include=["metadatas", "documents", "embeddings"])
            metadatas = raw["metadatas"]
            documents = raw["documents"]
            embeddings = raw["embeddings"]
            if metadatas is None or documents is None or embeddings is None:
                raise RuntimeError(
                    "Chroma get did not return metadatas/documents/embeddings."
                )
            self._all_docs_cache = list(
                zip(
                    raw["ids"],
                    metadatas,
                    documents,
                    embeddings,
                )
            )
        return self._all_docs_cache

    def _keyword_candidates(
        self,
        user_ingredients: list[str],
        exclude_ids: set[str],
    ) -> list[tuple]:
        scored = []

        for doc_id, meta, document, embedding in self._get_all_documents():
            if doc_id in exclude_ids:
                continue

            parsed_meta = self._parse_meta(meta)
            names = parsed_meta["ingredient_names"]

            matched_count = sum(
                1
                for u in user_ingredients
                if any(ingredient_matches(u, n) for n in names)
            )

            if matched_count <= 0:
                continue

            coverage_recipe_lexical = matched_count / len(names) if names else 0.0

            scored.append(
                (
                    matched_count,
                    coverage_recipe_lexical,
                    doc_id,
                    parsed_meta,
                    document,
                    embedding,
                )
            )

        scored.sort(key=lambda x: (-x[0], -x[1], str(x[2])))

        return scored[:MAX_KEYWORD_EXTRA]

    def retrieve_candidates(
        self,
        user_text: str,
        user_ingredients: list[str],
    ) -> list[dict[str, Any]]:
        query_embedding, candidates = self._semantic_candidates(user_text)
        existing_ids = {c["id"] for c in candidates}

        keyword_extra = self._keyword_candidates(
            user_ingredients,
            exclude_ids=existing_ids,
        )

        for (
            matched_count,
            _coverage_lexical,
            doc_id,
            meta,
            _document,
            embedding,
        ) in keyword_extra:
            semantic_score = float(np.dot(query_embedding, np.asarray(embedding)))

            candidates.append(
                {
                    "id": doc_id,
                    **meta,
                    "sbert_score": semantic_score,
                    "retrieval_source": "keyword",
                    "keyword_matched_count": int(matched_count),
                }
            )

        return candidates

    def rerank(
        self,
        user_text: str,
        top_n: int = TOP_N_DEFAULT,
    ) -> tuple[list[dict[str, Any]], list[str]]:
        user_ingredients = parse_user_ingredients(user_text)

        candidates = self.retrieve_candidates(
            user_text,
            user_ingredients,
        )

        if not candidates:
            return [], user_ingredients

        semantic_scores = np.asarray(
            [c["sbert_score"] for c in candidates],
            dtype=float,
        )

        s_min = float(semantic_scores.min())
        s_max = float(semantic_scores.max())

        semantic_norm = (semantic_scores - s_min) / (s_max - s_min + 1e-9)

        ranked = []

        for c, s_norm in zip(candidates, semantic_norm):
            stats = coverage_stats(
                user_ingredients,
                c["ingredient_names"],
            )

            efficiency = harmonic_efficiency(
                stats["coverage_recipe"],
                stats["coverage_user"],
            )

            final_score = W1_FINAL * float(s_norm) + W2_FINAL * efficiency

            ranked.append(
                {
                    **c,
                    **stats,
                    "skor_efisiensi_bahan": float(efficiency),
                    "sbert_score_norm": float(s_norm),
                    "final_score": float(final_score),
                }
            )

        ranked.sort(
            key=lambda c: (
                -c["final_score"],
                -c["sbert_score_norm"],
                str(c["id"]),
            )
        )

        return ranked[:top_n], user_ingredients

    @staticmethod
    def is_relevant_enough(
        candidate: dict[str, Any] | None,
        user_ingredients: list[str],
    ) -> bool:
        if not candidate or not user_ingredients:
            return False

        t_relevansi = min(2, len(user_ingredients))
        matched_user_count = len(candidate.get("matched_user_items", []))

        return matched_user_count >= t_relevansi

    def handle_user_input(
        self,
        user_text: str,
        top_n: int = TOP_N_DEFAULT,
    ) -> dict[str, Any]:
        user_ingredients = parse_user_ingredients(user_text)

        # T_jumlah = 1
        if len(user_ingredients) < T_JUMLAH:
            return {
                "status": "no_ingredients",
                "user_ingredients": [],
                "template": (
                    "Sepertinya belum ada bahan yang terdeteksi dari pesanmu. "
                    "Boleh sebutkan bahan yang kamu punya?"
                ),
            }

        # T_kategori: minimal satu bahan utama
        if not has_main_ingredient(user_ingredients):
            return {
                "status": "need_main_ingredient",
                "user_ingredients": user_ingredients,
                "template": (
                    f"Bahan yang kamu sebutkan ({', '.join(user_ingredients)}) "
                    "belum memuat bahan utama yang dikenali. "
                    "Tambahkan minimal satu bahan utama, misalnya ayam, telur, tahu, "
                    "tempe, ikan, nasi, kentang, atau sayuran."
                ),
            }

        results, parsed = self.rerank(
            user_text,
            top_n=top_n,
        )

        # T_relevansi checked on top-1 candidate.
        if not self.is_relevant_enough(
            results[0] if results else None,
            parsed,
        ):
            return {
                "status": "no_match",
                "user_ingredients": parsed,
                "template": (
                    "Sistem belum menemukan resep yang cukup cocok untuk kombinasi "
                    f"bahan ({', '.join(parsed)}). Coba tambahkan bahan lain atau "
                    "gunakan kombinasi berbeda."
                ),
            }

        return {
            "status": "ok",
            "user_ingredients": parsed,
            "results": results,
            "config": {
                "top_k_sbert": TOP_K_SBERT,
                "max_keyword_extra": MAX_KEYWORD_EXTRA,
                "w1": W1_FINAL,
                "w2": W2_FINAL,
            },
        }

    @staticmethod
    def build_nlg_payload(pipeline_result: dict[str, Any]) -> dict[str, Any]:
        """Return only grounded content that may be verbalized by Llama 3."""
        if pipeline_result.get("status") != "ok":
            return {
                "status": pipeline_result.get("status"),
                "template": pipeline_result.get("template", ""),
            }

        recipes = []
        for r in pipeline_result["results"]:
            recipes.append(
                {
                    "recipe_id": r["id"],
                    "title": r["title"],
                    "ingredients": r["ingredient_names"],
                    "steps": r.get("steps_text", ""),
                    "matched_user_items": r["matched_user_items"],
                    "missing_items": r["missing_items"],
                }
            )

        return {
            "status": "ok",
            "instruction": (
                "Gunakan hanya data resep berikut. Jangan menambah bahan, langkah, "
                "nama resep, atau fakta yang tidak ada pada data."
            ),
            "user_ingredients": pipeline_result["user_ingredients"],
            "recipes": recipes,
        }


if __name__ == "__main__":
    service = DapuriaRecipeService()
    print(service.healthcheck())

    smoke_tests = [
        "garam, gula, kecap manis",
        "telur, tahu",
        "2 butir telur, 100gr dada ayam, 2 siung bawang putih",
    ]

    for query in smoke_tests:
        result = service.handle_user_input(query)
        print("\nQUERY:", query)
        print("STATUS:", result["status"])
        if result["status"] == "ok":
            for i, rec in enumerate(result["results"], start=1):
                print(
                    f"{i}. {rec['title']} | "
                    f"score={rec['final_score']:.4f} | "
                    f"source={rec['retrieval_source']}"
                )
        else:
            print(result["template"])
