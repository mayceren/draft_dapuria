import pytest

from dapuria import recipe_service
from dapuria.config import Settings
from dapuria.recipe_service import RecipeService


def test_duplicate_input_keeps_scores_and_relevance_identical(monkeypatch):
    class Retriever:
        def __init__(self, settings):
            self.queries = []

        def retrieve(self, query, ingredients):
            self.queries.append((query, ingredients))
            return [{'id': 'r1', 'title': 'Telur dadar', 'ingredient_names': ['telur', 'garam'],
                     'sbert_score': 0.8, 'steps_text': 'Goreng telur.'}]

    monkeypatch.setattr(recipe_service, 'HybridRetriever', Retriever)
    service = RecipeService(Settings())
    single = service.handle_user_input('telur')
    repeated = service.handle_user_input('2 butir Telor, telur')
    assert single['status'] == 'ok'
    assert repeated == single
    assert single['results'][0]['coverage_user'] == 1.0
    assert service.retriever.queries == [('telur', ['telur']), ('telur', ['telur'])]


@pytest.fixture
def inventory_service(monkeypatch):
    class Retriever:
        def __init__(self, settings):
            self.queries = []

        def retrieve(self, query, ingredients):
            self.queries.append((query, ingredients))
            return [{'id': 'r1', 'title': 'Nasi telur', 'ingredient_names': ['nasi', 'telur', 'garam'],
                     'sbert_score': 0.8, 'steps_text': 'Masak nasi dan telur.'}]

    monkeypatch.setattr(recipe_service, 'HybridRetriever', Retriever)
    return RecipeService(Settings())


@pytest.mark.parametrize('query', [
    'aku punya nasi sama telur',
    'di rumah ada nasi dan telur nih',
    'tolong carikan resep dari nasi sama telur',
    'aku punya nasi sama telur, bisa masak apa?',
])
def test_conversation_uses_identical_query_scores_and_relevance(inventory_service, query):
    expected = inventory_service.handle_user_input('nasi, telur')
    actual = inventory_service.handle_user_input(query)
    assert expected['status'] == 'ok'
    assert actual == expected
    assert actual['results'][0]['matched_user_items'] == ['nasi', 'telur']
    assert inventory_service.retriever.queries[-1] == ('nasi, telur', ['nasi', 'telur'])


def test_unavailable_ingredients_are_excluded_before_retrieval(inventory_service):
    result = inventory_service.handle_user_input('aku punya nasi tapi telur habis')
    assert result['user_ingredients'] == ['nasi']
    assert inventory_service.retriever.queries == [('nasi', ['nasi'])]
    assert result['results'][0]['matched_user_items'] == ['nasi']


def test_unavailable_inventory_does_not_reach_retrieval(inventory_service):
    result = inventory_service.handle_user_input('aku tidak punya nasi dan telur')
    assert result['status'] == 'no_ingredients'
    assert inventory_service.retriever.queries == []


def test_high_semantic_score_cannot_count_stock_as_chicken(monkeypatch):
    class Retriever:
        def __init__(self, settings):
            pass

        def retrieve(self, query, ingredients):
            return [
                {'id': 'stock', 'title': 'Kaldu', 'ingredient_names': ['kaldu ayam'],
                 'sbert_score': 0.99, 'steps_text': 'Siapkan kaldu.'},
                {'id': 'chicken', 'title': 'Ayam', 'ingredient_names': ['dada ayam'],
                 'sbert_score': 0.6, 'steps_text': 'Masak ayam.'},
            ]

    monkeypatch.setattr(recipe_service, 'HybridRetriever', Retriever)
    service = RecipeService(Settings())
    ranked, _ = service.rerank('ayam')
    assert ranked[0]['id'] == 'stock'
    assert ranked[0]['matched_user_items'] == []
    result = service.handle_user_input('ayam')
    assert result['status'] == 'ok'
    assert [row['id'] for row in result['results']] == ['chicken']


def test_clarification_still_asks_for_stock_when_user_has_chicken(inventory_service):
    from dapuria.reranking import coverage_stats

    result = {'status': 'ok', 'user_ingredients': ['ayam'], 'results': [
        coverage_stats(['ayam'], ['dada ayam', 'kaldu ayam'])
    ]}
    assert inventory_service.clarification_candidates(result) == ['kaldu']


def test_exclusions_filter_before_top_five_and_keep_original_scores(monkeypatch):
    class Retriever:
        def __init__(self, settings):
            self.queries = []

        def retrieve(self, query, ingredients):
            self.queries.append((query, ingredients))
            return [{'id': str(i), 'title': f'Resep {i}',
                     'ingredient_names': ['nasi', 'telur', 'kaldu ayam' if i < 4 else 'bayam'],
                     'sbert_score': 1 - i / 20, 'steps_text': 'Masak bahan.'} for i in range(10)]

    monkeypatch.setattr(recipe_service, 'HybridRetriever', Retriever)
    service = RecipeService(Settings())
    baseline, _ = service.rerank('nasi, telur', top_n=20)
    result = service.handle_user_input('aku punya nasi sama telur, jangan pakai ayam')
    assert result['status'] == 'ok'
    assert len(result['results']) == 5
    assert result['excluded_ingredients'] == ['ayam']
    assert service.retriever.queries[-1] == ('nasi, telur', ['nasi', 'telur'])
    by_id = {row['id']: row for row in baseline}
    for row in result['results']:
        assert int(row['id']) >= 4
        assert row['final_score'] == by_id[row['id']]['final_score']


def test_forbidden_inventory_not_used_as_query_or_recipe_coverage(inventory_service):
    result = inventory_service.handle_user_input('nasi, telur', excluded_ingredients=['telur'])
    assert result['user_ingredients'] == ['nasi']
    assert inventory_service.retriever.queries == [('nasi', ['nasi'])]
    assert result['status'] == 'no_match'
    assert result['excluded_ingredients'] == ['telur']
    assert 'Batasan bahan tetap diterapkan' in result['message']


def test_shortage_alone_does_not_filter_recipes(inventory_service):
    result = inventory_service.handle_user_input('nasi, tapi telur habis')
    assert result['status'] == 'ok'
    assert 'telur' in result['results'][0]['ingredient_names']
    assert 'excluded_ingredients' not in result
