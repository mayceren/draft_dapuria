"""Real retrieval with deterministic clarification wording and isolated history."""

import runpy
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "src"))
from dapuria.llama_service import LlamaService

LlamaService.available = lambda self: False
runpy.run_path(str(ROOT / "app.py"), run_name="__main__")
