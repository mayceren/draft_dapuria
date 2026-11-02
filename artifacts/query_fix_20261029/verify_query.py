"""Re-run the reported query on the real locally cached model and recipe index."""

import json
import sys
from datetime import datetime, timedelta, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "src"))

from dapuria import RecipeService, Settings
from dapuria.recipe_selection import recipe_family

QUERY = "dada ayam 250 gr, kecap, garam, saus tiram, bawang putih, bawang bombay"

service = RecipeService(Settings(selection_policy="pantry"))
result = service.handle_user_input(QUERY)
ranked, parsed = service.rerank(QUERY, top_n=70)
by_id = {row["id"]: row for row in ranked}
assert result["status"] == "ok"
assert parsed == ["dada ayam", "kecap", "garam", "saus tiram", "bawang putih", "bawang bombay"]
assert result["results"][0]["id"] == "resep_4815"
assert result["results"][0]["missing_items"] == ["air", "minyak goreng"]
assert by_id["resep_217"]["ingredient_names"][0] == "dada ayam"
assert "bawang putih" in by_id["resep_217"]["matched_user_items"]
assert "bawang merah" in by_id["resep_217"]["missing_items"]
assert "1" not in by_id["resep_4815"]["ingredient_names"]
assert "minyak goreng" in by_id["resep_4815"]["ingredient_names"]
assert all(any(char.isalpha() for char in name) for row in ranked for name in row["ingredient_names"])
assert len({recipe_family(row["title"]) for row in result["results"]}) == len(result["results"])
report = {"verified_at": datetime.now(timezone(timedelta(hours=7))).isoformat(),
          "query": QUERY, "healthcheck": service.healthcheck(), "result": result, "candidates": ranked}
(Path(__file__).parent / "after.json").write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8")
print("Ingredients:", parsed, flush=True)
for rank, row in enumerate(result["results"], 1):
    print(rank, ascii(row["title"]), "missing:", len(row["missing_items"]), ascii(row["missing_items"]), flush=True)
print("Real model/index regression checks passed.", flush=True)
