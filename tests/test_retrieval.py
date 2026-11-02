import json
from types import SimpleNamespace

import numpy as np
import pytest

from dapuria.config import Settings
from dapuria.retrieval import HybridRetriever


def test_lexical_cache_parses_once_and_preserves_candidate_order_and_scores():
    retriever = HybridRetriever.__new__(HybridRetriever)
    retriever.settings = Settings(max_keyword_extra=2)
    retriever._all_docs_cache = None
    calls = []
    def get(**kwargs):
        calls.append(kwargs)
        return {
            'ids': ['semantic', 'b', 'a', 'c'],
            'metadatas': [{'ingredient_names': json.dumps(names)} for names in [
                ['telur'], ['telur', 'garam'], ['telur'], ['tahu']
            ]],
            'documents': ['', '', '', ''],
            'embeddings': [[1.0, 0.0], [0.6, 0.8], [0.8, 0.6], [0.0, 1.0]],
        }
    retriever.collection = SimpleNamespace(get=get)
    parsed = []
    def parse(meta):
        parsed.append(meta)
        return HybridRetriever._parse_meta(meta)
    retriever._parse_meta = parse
    retriever._semantic_candidates = lambda query: (
        np.array([1.0, 0.0]), [{'id': 'semantic', 'sbert_score': 1.0}]
    )
    first = retriever.retrieve('telur', ['telur'])
    second = retriever.retrieve('telur', ['telur'])
    assert first == second
    assert [row['id'] for row in first] == ['semantic', 'a', 'b']
    assert [row['sbert_score'] for row in first] == [1.0, 0.8, 0.6]
    assert [row['retrieval_source'] for row in first[1:]] == ['keyword', 'keyword']
    assert len(calls) == 1
    assert len(parsed) == 4


def test_disabling_lexical_expansion_does_not_load_corpus():
    retriever = HybridRetriever.__new__(HybridRetriever)
    retriever.settings = Settings(max_keyword_extra=0)
    assert retriever._keyword_candidates(['telur'], set()) == []


@pytest.mark.parametrize('ingredient,expected_ids', [
    ('ayam', {'chicken', 'chicken-breast', 'chicken-thigh'}),
    ('sapi', set()),
    ('jamur', set()),
    ('udang', {'shrimp'}),
    ('kaldu', {'stock-chicken', 'stock-beef', 'stock-mushroom'}),
    ('terasi', {'shrimp-paste'}),
    ('telur', {'egg-alias'}),
])
def test_lexical_expansion_uses_alias_and_product_matching(ingredient, expected_ids):
    retriever = HybridRetriever.__new__(HybridRetriever)
    retriever.settings = Settings(max_keyword_extra=20)
    retriever._all_docs_cache = [
        (doc_id, {'ingredient_names': [name]}, '', [1.0, 0.0])
        for doc_id, name in [
            ('chicken', 'ayam'), ('chicken-breast', 'dada ayam'),
            ('chicken-thigh', 'paha ayam'), ('stock-chicken', 'bubuk kaldu ayam'),
            ('stock-beef', 'kaldu sapi'), ('stock-mushroom', 'kaldu jamur'),
            ('shrimp', 'udang'), ('shrimp-paste', 'terasi udang'),
            ('shrimp-petis', 'petis udang'), ('shrimp-crackers', 'kerupuk udang'),
            ('egg-alias', 'telor'),
        ]
    ]
    candidates = retriever._keyword_candidates([ingredient], set())
    assert {row[2] for row in candidates} == expected_ids
