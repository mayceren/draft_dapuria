"""
Scrape 16 resep hasil pencarian manual (ground_truth_bagian2_perlu_discrape.csv)
untuk melengkapi data bahan/langkah, disamakan formatnya dengan bagian 1.
Jalankan file ini di folder yang sama dengan scrape_yummy.py.
"""

import pandas as pd
from scrape_yummy import scrape_recipe, sleep_random
import re

df = pd.read_csv("ground_truth_bagian2_perlu_discrape.csv")

results = []
for _, row in df.iterrows():
    slug = row["scraped_url"].rstrip("/").split("/")[-1]
    print(f"Scraping: {slug}")
    try:
        data = scrape_recipe(slug)
        results.append(
            {
                "scraped_title": data["title"],
                "corpus_title": row["corpus_title"],
                "scraped_url": row["scraped_url"],
                "ingredients_raw": " | ".join(data["ingredients_raw"]),
                "steps": " | ".join(data["steps"]),
                "sumber": "pencarian_manual",
            }
        )
    except Exception as e:
        print(f"  GAGAL: {e}")
    sleep_random()

out = pd.DataFrame(results)
out.to_csv("ground_truth_bagian2_lengkap.csv", index=False)
print(f"\nSelesai. {len(out)} resep tersimpan ke ground_truth_bagian2_lengkap.csv")
