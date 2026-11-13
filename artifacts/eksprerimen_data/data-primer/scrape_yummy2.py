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
    "User-Agent": "Mozilla/5.0 (compatible; ThesisResearchBot/1.0; academic research"
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


def fetch_next_data(slug: str) -> tuple[dict, str]:
    """Download 1 halaman resep dan kembalikan (__NEXT_DATA__, url).
    Satu request dipakai untuk isi resep SEKALIGUS slug terkait."""
    url = f"{BASE_URL}/resep/{slug}"
    resp = requests.get(url, headers=HEADERS, timeout=15)
    resp.raise_for_status()
    return extract_next_data(resp.text), url


def parse_recipe(data: dict, slug: str, url: str) -> dict:
    """Ambil 1 resep dari __NEXT_DATA__ berdasarkan slug (bagian akhir URL, mis. 'mie-gacoan-homemade-level-napol')."""
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

    # pakai `or` (bukan default .get) karena field di JSON bisa bernilai null
    ingredients_flat = []
    ingredient_groups = []
    for group in recipe_data.get("ingredient_type") or []:
        group_name = group.get("name") or ""
        for item in group.get("ingredients") or []:
            desc = (item.get("description") or "").strip()
            if desc:
                ingredients_flat.append(desc)
                ingredient_groups.append(group_name)

    steps = [
        (s.get("text") or "").strip() for s in recipe_data.get("cooking_step") or []
    ]
    steps = [s for s in steps if s]

    category = recipe_data.get("category") or {}
    author = recipe_data.get("author") or {}
    return {
        "source_id": recipe_data.get("id"),
        "title": recipe_data.get("title"),
        "slug": recipe_data.get("slug"),
        "url": url,
        "category": category.get("name") or "",
        "ingredients_raw": ingredients_flat,
        "ingredient_groups": ingredient_groups,
        "steps": steps,
        "author_name": author.get("name") or "",
        "author_is_official": author.get("is_official", False),
    }


def scrape_recipe(slug: str) -> dict:
    """Ambil 1 resep berdasarkan slug."""
    data, url = fetch_next_data(slug)
    return parse_recipe(data, slug, url)


def find_related_slugs(data: dict) -> list[str]:
    """Bonus: 1 halaman resep juga membawa data beberapa resep TERKAIT/rekomendasi.
    Bisa dipakai menemukan slug baru tanpa scrape halaman listing /resep?page=N."""
    queries = data["props"]["pageProps"]["dehydratedState"]["queries"]

    found_slugs = []
    for q in queries:
        key = q.get("queryKey", [])
        if len(key) == 2 and key[0] == "recipe-detail":
            found_slugs.append(key[1])
    return found_slugs


def crawl_snowball(
    seed_slugs: list[str],
    target_count: int = 300,
    already_have: set | None = None,
    checkpoint_file: str | None = None,
    checkpoint_every: int = 25,
) -> list[dict]:
    """Rambat dari beberapa slug awal (seed) lewat 'slug terkait' tiap halaman,
    sampai terkumpul target_count resep BARU (unik). BFS sederhana pakai antrian.

    already_have: slug yang SUDAH pernah discrape sebelumnya. Slug ini TETAP
    di-fetch untuk mencari 'resep terkait'-nya (supaya bisa jadi jembatan ke
    slug baru), tapi TIDAK dihitung/disimpan sebagai hasil baru.

    checkpoint_file: kalau diisi, hasil disimpan tiap `checkpoint_every` resep baru,
    supaya tidak hilang semua kalau proses berhenti di tengah jalan.
    Tekan Ctrl+C untuk berhenti lebih awal; hasil yang sudah terkumpul tetap dikembalikan."""
    already_have = already_have or set()
    scraped_this_run = set()
    queue = list(seed_slugs)
    queued = set(queue)
    results = []

    try:
        while queue and len(results) < target_count:
            slug = queue.pop(0)
            if slug in scraped_this_run:
                continue
            scraped_this_run.add(slug)

            try:
                data, url = fetch_next_data(slug)
            except Exception as e:
                print(f"  GAGAL download halaman '{slug}': {e}")
                sleep_random()
                continue

            try:
                related = find_related_slugs(data)
                for r in related:
                    if r not in scraped_this_run and r not in queued:
                        queue.append(r)
                        queued.add(r)
            except Exception as e:
                print(f"  GAGAL cari slug terkait untuk '{slug}': {e}")

            if slug not in already_have:
                try:
                    results.append(parse_recipe(data, slug, url))
                    print(
                        f"[{len(results)}/{target_count}] Scraping (BARU): {slug}  (antrian: {len(queue)})"
                    )
                    if checkpoint_file and len(results) % checkpoint_every == 0:
                        save_to_csv(results, filename=checkpoint_file)
                except Exception as e:
                    print(f"  GAGAL parse resep '{slug}': {e}")
            else:
                print(
                    f"[skip hitung, sudah ada] Scraping ulang untuk cari terkait: {slug}"
                )

            sleep_random()
    except KeyboardInterrupt:
        print(
            f"\nDihentikan manual (Ctrl+C). {len(results)} resep baru terkumpul akan disimpan."
        )

    if not queue and len(results) < target_count:
        print(
            f"\nAntrian slug habis sebelum target tercapai ({len(results)}/{target_count}). "
            "Tambah seed_slugs kalau butuh lebih banyak."
        )
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
    print(f"  -> {len(results)} resep tersimpan ke {filename}")


if __name__ == "__main__":
    # baca slug yang SUDAH pernah discrape sebelumnya, supaya tidak dobel
    already_have = set()
    try:
        with open("resep_primer_yummy.csv", encoding="utf-8") as f:
            reader = csv.DictReader(f)
            for row in reader:
                already_have.add(row["slug"])
        print(
            f"Sudah ada {len(already_have)} resep dari batch sebelumnya (akan dilewati)"
        )
    except FileNotFoundError:
        print("Belum ada resep_primer_yummy.csv sebelumnya, mulai dari nol")

    # Seed: SEMUA dari slug yang sudah terkonfirmasi valid dari batch pertama
    # (bukan tebakan), dipilih yang jelas-jelas masakan Indonesia mainstream
    # (bukan dessert/fusion ala Barat), supaya "resep terkait" yang ditemukan
    # dari sini lebih besar peluang relevan dengan corpus 5000.
    seed_slugs = [
        "opor-ayam-100",
        "ikan-goreng-balado",
        "tumis-tempe-kangkung-2",
        "semur-daging-sapi-21",
        "rempeyek-udang-7",
        "ayam-kecap-67",
        "tahu-telur-4",
        "mangut-kepala-manyung",
        "nasi-tim-ayam-jamur-7",
        "tumis-jamur-ayam-1",
    ]  # catatan: seed ini SENDIRI tidak dihitung sebagai hasil baru (sudah ada
    # di batch pertama), fungsinya cuma jadi titik awal menjelajah slug lain

    target_baru = 600  # berdasarkan yield 18% dari batch pertama, target lebih besar
    print(
        f"\nMenargetkan {target_baru} resep BARU (di luar {len(already_have)} yang sudah ada)..."
    )
    output_file = "resep_primer_yummy_batch2.csv"
    results = crawl_snowball(
        seed_slugs,
        target_count=target_baru,
        already_have=already_have,
        checkpoint_file=output_file,
    )
    save_to_csv(results, filename=output_file)
    print(f"\nSelesai. Total {len(results)} resep baru.")
