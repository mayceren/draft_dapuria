"""Isolated browser harness: real RecipeService with slow fixture retrieval."""
import os
import runpy
import sys
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "src"))
from dapuria import recipe_service
from dapuria.llama_service import LlamaService


class PreviewRetriever:
    def __init__(self, settings):
        pass

    def retrieve(self, text, ingredients):
        time.sleep(float(os.getenv("DAPURIA_PREVIEW_DELAY", "3")))
        return [{
            "id": f"preview-{i}", "title": f"Resep uji {i}",
            "ingredient_names": list(dict.fromkeys(ingredients + ["garam"] + (["kaldu ayam"] if i < 2 else []))),
            "sbert_score": 0.95 - i * 0.04,
            "steps_text": "Langkah contoh untuk pengujian UI."
        } for i in range(7)]

recipe_service.HybridRetriever = PreviewRetriever
LlamaService.available = lambda self: False
runpy.run_path(str(ROOT / "app.py"), run_name="__main__")
