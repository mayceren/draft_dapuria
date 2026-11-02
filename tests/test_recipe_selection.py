from dapuria.recipe_selection import recipe_family, select_pantry_recipes
from dapuria.reranking import coverage_stats


def candidate(recipe_id, title, names, score):
    return {'id': recipe_id, 'title': title, 'ingredient_names': names, 'final_score': score,
            **coverage_stats(['ayam', 'garam'], names)}


def test_pantry_choice_prefers_fewer_missing_items_without_changing_wlc():
    rows = [candidate('sate', 'Sate ayam', ['ayam', 'garam', 'kemiri', 'kecap', 'bawang'], .95),
            candidate('simple', 'Ayam kecap', ['ayam', 'garam', 'kecap'], .7)]
    selected = select_pantry_recipes(rows, ['ayam', 'garam'], 5)
    assert [row['id'] for row in selected] == ['simple', 'sate']
    assert selected[0]['final_score'] == .7
    assert [row['id'] for row in rows] == ['sate', 'simple']


def test_equivalent_kecap_titles_do_not_fill_alternative_slots():
    assert recipe_family('826) Ayam Kecap Bombay') == recipe_family('Ayam bumbu kecap')
    assert recipe_family('Ayam kecap pedes manis') == recipe_family('Ayam Kecap Mentega Simple, Juara')
    rows = [candidate('a', 'Ayam Kecap Bombay', ['ayam', 'garam'], .9),
            candidate('b', 'Ayam bumbu kecap', ['ayam', 'garam'], .8),
            candidate('c', 'Sate Ayam Kecap', ['ayam', 'garam', 'kecap'], .7),
            candidate('d', 'Ayam saus tiram', ['ayam', 'garam', 'saus tiram'], .6)]
    assert [row['id'] for row in select_pantry_recipes(rows, ['ayam', 'garam'], 5)] == ['a', 'c', 'd']


def test_pantry_selection_requires_at_least_one_available_main_ingredient():
    rows = [candidate('fish', 'Ikan garam', ['ikan', 'garam'], .9),
            candidate('chicken', 'Ayam garam', ['ayam', 'garam', 'minyak'], .7)]
    assert [row['id'] for row in select_pantry_recipes(rows, ['ayam', 'garam'], 5)] == ['chicken']
