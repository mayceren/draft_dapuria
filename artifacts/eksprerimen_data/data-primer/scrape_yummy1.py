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
    for group in recipe_data.get("ingredient_type", []):
        group_name = group.get("name", "")
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


def crawl_snowball(seed_slugs: list[str], target_count: int = 300) -> list[dict]:
    """Rambat dari beberapa slug awal (seed) lewat 'slug terkait' tiap halaman,
    sampai terkumpul target_count resep unik. BFS sederhana pakai antrian."""
    visited = set()
    queue = list(seed_slugs)
    results = []

    while queue and len(results) < target_count:
        slug = queue.pop(0)
        if slug in visited:
            continue
        visited.add(slug)

        print(f"[{len(results) + 1}/{target_count}] Scraping: {slug}")
        try:
            recipe = scrape_recipe(slug)
            results.append(recipe)
        except Exception as e:
            print(f"  GAGAL scrape resep: {e}")
            continue

        sleep_random()

        try:
            related = discover_slugs_from_page(slug)
            for r in related:
                if r not in visited and r not in queue:
                    queue.append(r)
        except Exception as e:
            print(f"  GAGAL cari slug terkait: {e}")

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


if __name__ == "__main__":
    # TAHAP TES (sudah dilakukan sebelumnya, boleh dikomentari):
    # test_slug = "mie-gacoan-homemade-level-napol"
    # hasil = scrape_recipe(test_slug)
    # print(json.dumps(hasil, ensure_ascii=False, indent=2))

    # TAHAP CRAWL SKALA KECIL DULU -- jangan langsung 250-300
    seed_slugs = [
        "mie-gacoan-homemade-level-napol",
        "kentang-mustofa-21",
        "ikan-tongkol-bumbu-bali-1",
        "moon-cake-pumpkin",
    ]  # beberapa seed dari kategori berbeda (mie, kentang, ikan, dessert) biar hasil awal beragam

    results = crawl_snowball(
        seed_slugs, target_count=300
    )  # sudah lolos tes 20, sekarang full 300
    save_to_csv(results, filename="resep_primer_yummy.csv")  # nama final, tanpa "_TES"
