import csv
import runpy
import sys
from pathlib import Path
from types import SimpleNamespace

import numpy as np


def test_rebuild_preserves_full_steps_without_loading_a_real_model(tmp_path, monkeypatch):
    steps = 'Langkah memasak. ' * 150 + 'Sajikan selagi hangat.'
    corpus_path = tmp_path / 'corpus.csv'
    row = {
        'title_clean': 'Telur dadar', 'ingredient_names': '["telur"]',
        'steps_text': steps, 'text_for_embedding': 'telur dadar telur',
        'num_ingredients_clean': 1,
    }
    with corpus_path.open('w', encoding='utf-8', newline='') as handle:
        writer = csv.DictWriter(handle, fieldnames=list(row))
        writer.writeheader()
        writer.writerow(row)

    batches = []
    collection = SimpleNamespace(upsert=lambda **kwargs: batches.append(kwargs), count=lambda: 1)
    client = SimpleNamespace(delete_collection=lambda name: None,
                             get_or_create_collection=lambda **kwargs: collection)
    model = SimpleNamespace(encode=lambda texts, **kwargs: np.array([[1.0, 0.0]]))
    monkeypatch.setitem(sys.modules, 'chromadb', SimpleNamespace(PersistentClient=lambda **kwargs: client))
    monkeypatch.setitem(sys.modules, 'sentence_transformers',
                        SimpleNamespace(SentenceTransformer=lambda name: model))
    monkeypatch.setattr(sys, 'argv', ['rebuild_index', '--corpus', str(corpus_path),
                                     '--chroma-dir', str(tmp_path / 'index')])
    script = Path(__file__).resolve().parents[1] / 'scripts' / 'rebuild_index.py'
    runpy.run_path(str(script), run_name='__main__')
    assert len(batches) == 1
    assert batches[0]['metadatas'][0]['steps_text'] == steps
    assert batches[0]['metadatas'][0]['steps_text'].endswith('Sajikan selagi hangat.')
