import csv
import json

from dapuria.recipe_details import RecipeDetails


def write_corpus(path, rows):
    with path.open('w', encoding='utf-8', newline='') as handle:
        writer = csv.DictWriter(handle, fieldnames=['title_clean', 'ingredient_names', 'steps_text'])
        writer.writeheader()
        writer.writerows(rows)


def test_legacy_steps_restored_without_changing_recipe_or_scores(tmp_path):
    steps = 'Langkah memasak. ' * 150 + 'Sajikan selagi hangat.'
    path = tmp_path / 'corpus.csv'
    write_corpus(path, [{
        'title_clean': 'Telur dadar', 'ingredient_names': json.dumps(['telur']),
        'steps_text': steps,
    }])
    details = RecipeDetails(path)
    recipe = {'title': 'Telur dadar', 'ingredient_names': ['telur'],
              'steps_text': steps[:2000], 'final_score': 0.9, 'id': 'legacy_id'}
    restored = details.restore_steps(recipe)
    assert restored == {**recipe, 'steps_text': steps}
    assert recipe['steps_text'] == steps[:2000]
    # Subsequent lookups use the cache even when the file becomes unavailable.
    path.unlink()
    assert details.restore_steps(recipe) == restored


def test_missing_corpus_or_nonmatching_recipe_keeps_original_steps(tmp_path):
    recipe = {'title': 'Telur', 'ingredient_names': ['telur'], 'steps_text': 'a' * 2000}
    assert RecipeDetails(tmp_path / 'absent.csv').restore_steps(recipe) == recipe
    path = tmp_path / 'corpus.csv'
    for title, names, steps in [
        ('Tahu', ['telur'], 'a' * 2001),
        ('Telur', ['tahu'], 'a' * 2001),
        ('Telur', ['telur'], 'b' * 2001),
    ]:
        write_corpus(path, [{'title_clean': title, 'ingredient_names': json.dumps(names),
                             'steps_text': steps}])
        assert RecipeDetails(path).restore_steps(recipe) == recipe


def test_ambiguous_steps_are_never_guessed(tmp_path):
    path = tmp_path / 'corpus.csv'
    write_corpus(path, [
        {'title_clean': 'Telur', 'ingredient_names': '["telur"]',
         'steps_text': 'a' * 2000 + ending}
        for ending in ['Rebus.', 'Goreng.']
    ])
    recipe = {'title': 'Telur', 'ingredient_names': ['telur'], 'steps_text': 'a' * 2000}
    assert RecipeDetails(path).restore_steps(recipe) == recipe
