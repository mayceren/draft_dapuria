"""
Scraper data primer yummy.co.id untuk proposal skripsi.
PENDEKATAN: situs ini (Next.js) menanam seluruh data resep sebagai JSON terstruktur
di dalam tag <script id="__NEXT_DATA__">, sehingga TIDAK PERLU Playwright/rendering
JS -- cukup requests biasa + ekstraksi JSON.

Kebijakan etis: robots.txt kosong (tidak ada larangan eksplisit), delay acak,
volume kecil (~150-300 resep), tujuan non-komersial/akademis.
"""

import requests
import json
import re
import time
import random
import csv

BASE_URL = "https://www.yummy.co.id"
HEADERS = {
    "User-Agent": "Mozilla/5.0 (compatible; SkripsiResearchBot/1.0; "
    "academic research, Universitas Tarumanagara; contact: <emailmu>)"
}
DELAY_RANGE_SECONDS = (2, 5)


def sleep_random():
    time.sleep(random.uniform(*DELAY_RANGE_SECONDS))


def extract_next_data(html: str) -> dict:
    """Ekstrak JSON dari tag <script id="__NEXT_DATA__">...</script>."""
    match = re.search(
        r'<script id="__NEXT_DATA__"[^>]*>(.*?)</script>', html, re.DOTALL
    )
    if not match:
        raise ValueError(
            "Tag __NEXT_DATA__ tidak ditemukan -- struktur halaman mungkin berubah"
        )
    return json.loads(match.group(1))


def scrape_recipe(slug: str) -> dict:
    """Ambil 1 resep berdasarkan slug (bagian akhir URL, mis. 'mie-gacoan-homemade-level-napol')."""
    url = f"{BASE_URL}/resep/{slug}"
    resp = requests.get(url, headers=HEADERS, timeout=15)
    resp.raise_for_status()
    data = extract_next_data(resp.text)

    requested_slug = data.get("props", {}).get("pageProps", {}).get("slug")
    if requested_slug != slug:
        print(f"  PERINGATAN: slug diminta '{slug}' tapi dapat '{requested_slug}'")

    queries = data["props"]["pageProps"]["dehydratedState"]["queries"]
    recipe_data = None
    for q in queries:
        key = q.get("queryKey", [])
        if len(key) == 2 and key[0] == "recipe-detail" and key[1] == slug:
            recipe_data = q["state"]["data"]["data"]
            break

    if recipe_data is None:
        raise ValueError(
            f"Data resep untuk slug '{slug}' tidak ditemukan di dehydratedState"
        )

    ingredients_flat = []
    ingredient_groups = []
    # Filter grup yang JELAS bukan bahan makanan (alat masak/perlengkapan) --
    # ditemukan lewat pertanyaan user bahwa beberapa halaman Yummy punya grup
    # "Alat & Perlengkapan" di dalam ingredient_type yang sama, bukan cuma
    # "Bahan Utama"/"Bumbu Halus". Tanpa filter ini, alat masak (wajan, kompor,
    # spatula) bisa ikut kehitung seolah-olah bahan masakan.
    NON_INGREDIENT_GROUP_KEYWORDS = ["alat", "perlengkapan", "peralatan"]
    for group in recipe_data.get("ingredient_type", []):
        group_name = group.get("name", "")
        if any(kw in group_name.lower() for kw in NON_INGREDIENT_GROUP_KEYWORDS):
            continue  # skip grup alat/perlengkapan
        for item in group.get("ingredients", []):
            desc = item.get("description", "").strip()
            if desc:
                ingredients_flat.append(desc)
                ingredient_groups.append(group_name)

    steps = [
        s.get("text", "").strip()
        for s in recipe_data.get("cooking_step", [])
        if s.get("text")
    ]

    return {
        "source_id": recipe_data.get("id"),
        "title": recipe_data.get("title"),
        "slug": recipe_data.get("slug"),
        "url": url,
        "category": recipe_data.get("category", {}).get("name", ""),
        "ingredients_raw": ingredients_flat,
        "ingredient_groups": ingredient_groups,
        "steps": steps,
        "author_name": recipe_data.get("author", {}).get("name", ""),
        "author_is_official": recipe_data.get("author", {}).get("is_official", False),
    }


def discover_slugs_from_page(slug: str) -> list[str]:
    """Bonus: 1 halaman resep juga membawa data beberapa resep TERKAIT/rekomendasi.
    Bisa dipakai menemukan slug baru tanpa scrape halaman listing /resep?page=N."""
    url = f"{BASE_URL}/resep/{slug}"
    resp = requests.get(url, headers=HEADERS, timeout=15)
    resp.raise_for_status()
    data = extract_next_data(resp.text)
    queries = data["props"]["pageProps"]["dehydratedState"]["queries"]

    found_slugs = []
    for q in queries:
        key = q.get("queryKey", [])
        if len(key) == 2 and key[0] == "recipe-detail":
            found_slugs.append(key[1])
    return found_slugs


if __name__ == "__main__":
    import csv as csv_module

    # baca slug yang SUDAH pernah discrape sebelumnya (batch 1 + batch 2 = 900),
    # supaya batch 3 ini tidak mengulang resep yang sama
    already_have = set()
    for fname in ["resep_primer_yummy.csv", "resep_primer_yummy_batch2.csv"]:
        try:
            with open(fname, encoding="utf-8") as f:
                reader = csv_module.DictReader(f)
                for row in reader:
                    already_have.add(row["slug"])
        except FileNotFoundError:
            print(f"  (catatan: {fname} tidak ditemukan, dilewati)")
    print(
        f"Sudah ada {len(already_have)} resep dari 2 batch sebelumnya (akan dilewati)"
    )

    # Seed BATCH 3: bukan tebakan lagi, tapi SEMUA 93 slug yang SUDAH TERBUKTI
    # valid (cocok ke corpus 5000) dari batch 1+2. Hipotesis: "resep terkait"
    # yang direkomendasikan Yummy dari resep bertema mainstream Indonesia yang
    # sudah terbukti match, punya peluang lebih besar untuk menemukan resep
    # sejenis lagi, dibanding seed acak/tebakan sebelumnya.
    with open("seed_slugs_valid.txt", encoding="utf-8") as f:
        seed_slugs = [line.strip() for line in f if line.strip()]
    print(f"Menggunakan {len(seed_slugs)} seed dari resep yang sudah terbukti valid")

    target_baru = 400  # mulai moderat dulu, cek yield sebelum nambah lagi
    print(
        f"\nMenargetkan {target_baru} resep BARU (di luar {len(already_have)} yang sudah ada)..."
    )
    results = crawl_snowball(
        seed_slugs, target_count=target_baru, already_have=already_have
    )
    save_to_csv(results, filename="resep_primer_yummy_batch3.csv")


def crawl_snowball(
    seed_slugs: list[str], target_count: int = 300, already_have: set = None
) -> list[dict]:
    """Rambat dari beberapa slug awal (seed) lewat 'slug terkait' tiap halaman,
    sampai terkumpul target_count resep BARU (unik). BFS sederhana pakai antrian.

    already_have: slug yang SUDAH pernah discrape sebelumnya. Slug ini TETAP
    di-fetch untuk mencari 'resep terkait'-nya (supaya bisa jadi jembatan ke
    slug baru), tapi TIDAK dihitung/disimpan sebagai hasil baru."""
    already_have = already_have or set()
    scraped_this_run = set()
    queue = list(seed_slugs)
    results = []

    while queue and len(results) < target_count:
        slug = queue.pop(0)
        if slug in scraped_this_run:
            continue
        scraped_this_run.add(slug)

        is_new = slug not in already_have
        try:
            recipe = scrape_recipe(slug)
            if is_new:
                results.append(recipe)
                print(f"[{len(results)}/{target_count}] Scraping (BARU): {slug}")
            else:
                print(
                    f"[skip hitung, sudah ada] Scraping ulang untuk cari terkait: {slug}"
                )
        except Exception as e:
            print(f"  GAGAL scrape resep '{slug}': {e}")
            continue

        sleep_random()

        try:
            related = discover_slugs_from_page(slug)
            for r in related:
                if r not in scraped_this_run and r not in queue:
                    queue.append(r)
        except Exception as e:
            print(f"  GAGAL cari slug terkait untuk '{slug}': {e}")

        sleep_random()

    return results


def save_to_csv(results: list[dict], filename: str = "resep_primer_yummy.csv"):
    with open(filename, "w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(
            f,
            fieldnames=[
                "source_id",
                "title",
                "slug",
                "url",
                "category",
                "ingredients_raw",
                "steps",
                "author_name",
                "author_is_official",
            ],
        )
        writer.writeheader()
        for r in results:
            writer.writerow(
                {
                    "source_id": r["source_id"],
                    "title": r["title"],
                    "slug": r["slug"],
                    "url": r["url"],
                    "category": r["category"],
                    "ingredients_raw": " | ".join(r["ingredients_raw"]),
                    "steps": " | ".join(r["steps"]),
                    "author_name": r["author_name"],
                    "author_is_official": r["author_is_official"],
                }
            )
    print(f"\nSelesai. {len(results)} resep tersimpan ke {filename}")
