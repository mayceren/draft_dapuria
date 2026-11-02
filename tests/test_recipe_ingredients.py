import csv
import json

from dapuria.recipe_ingredients import prepare_recipe_ingredients


def corpus(path, raw_variants):
    with path.open('w', encoding='utf-8', newline='') as handle:
        writer = csv.DictWriter(handle, fieldnames=['title_clean', 'ingredient_names', 'ingredients'])
        writer.writeheader()
        for raw in raw_variants:
            writer.writerow({'title_clean': 'Ayam Kecap', 'ingredient_names': '["ayam potong", "baput", "1"]',
                             'ingredients': json.dumps(raw)})


def test_legacy_decimal_error_recovers_actual_ingredient_from_original_line(tmp_path):
    path = tmp_path / 'corpus.csv'
    corpus(path, [['1 potong ayam potong', '2 siung baput', '1,5 sdm minyak goreng']])
    source = {'title': 'Ayam Kecap', 'ingredient_names': ['ayam potong', 'baput', '1']}
    result = prepare_recipe_ingredients(source, path)
    assert result['ingredient_names'] == ['ayam', 'bawang putih', 'minyak goreng']
    assert result['source_ingredient_names'] == source['ingredient_names']
    assert source['ingredient_names'] == ['ayam potong', 'baput', '1']


def test_ambiguous_source_recovery_does_not_guess_which_ingredient_number_means(tmp_path):
    path = tmp_path / 'corpus.csv'
    corpus(path, [['ayam', 'baput', '1,5 sdm minyak goreng'], ['ayam', 'baput', '1,5 sdm kecap']])
    result = prepare_recipe_ingredients({'title': 'Ayam Kecap', 'ingredient_names': ['ayam potong', 'baput', '1']}, path)
    assert result['ingredient_names'] == ['ayam', 'bawang putih']


def test_missing_corpus_still_normalizes_aliases_and_drops_numbers(tmp_path):
    result = prepare_recipe_ingredients({'ingredient_names': ['baput', 'bawang putih', 'bamer', '1']}, tmp_path / 'missing.csv')
    assert result['ingredient_names'] == ['bawang putih', 'bawang merah']
