from __future__ import annotations

from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parents[1]
SRC = ROOT / "src"
if str(SRC) not in sys.path:
    sys.path.insert(0, str(SRC))

from dapuria import RecipeService, Settings


def main() -> None:
    service = RecipeService(Settings())
    print("HEALTHCHECK:", service.healthcheck())
    for query in [
        "garam, gula, kecap manis",
        "telur, tahu",
        "2 butir telur, 100 gr dada ayam, 2 siung bawang putih",
    ]:
        result = service.handle_user_input(query)
        print("\nQUERY:", query)
        print("STATUS:", result["status"])
        if result["status"] == "ok":
            for rank, recipe in enumerate(result["results"], 1):
                print(rank, recipe["title"], f"score={recipe['final_score']:.4f}")
        else:
            print(result["message"])


if __name__ == "__main__":
    main()
