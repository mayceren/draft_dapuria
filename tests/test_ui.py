import pytest

pytest.importorskip('streamlit')
from dapuria.ui import (
    ingredient_names,
    recipe_html,
    split_cooking_steps,
)


def test_recipe_content_is_escaped_and_missing_data_is_honest():
    html = recipe_html({'title': '<script>bad()</script>',
        'ingredient_names': ['<img src=x onerror=bad()>']}, 1)
    assert '<script>' not in html
    assert '<img' not in html
    assert '&lt;script&gt;' in html
    assert 'Langkah memasak belum tersedia' in html


def test_full_ingredients_and_original_steps_are_retained():
    recipe = {'title': 'Telur', 'ingredient_names': ['telur', 'garam', 'minyak'],
              'matched_recipe_items': ['telur'], 'missing_items': ['garam', 'minyak'],
              'steps_text': '1. Kocok telur.\n2. Masak hingga matang.'}
    html = recipe_html(recipe, 1)
    assert '<li>garam</li>' in html
    assert '<ol class="steps-list"><li>Kocok telur.</li><li>Masak hingga matang.</li></ol>' in html
    assert recipe['steps_text'] == '1. Kocok telur.\n2. Masak hingga matang.'
    assert 'Yang perlu disiapkan' in html
    assert ingredient_names(recipe) == ['telur', 'garam', 'minyak']


@pytest.mark.parametrize('text,expected', [
    ('1. Kocok telur. 2. Panaskan minyak. Goreng hingga matang. 3. Sajikan.',
     ['Kocok telur.', 'Panaskan minyak. Goreng hingga matang.', 'Sajikan.']),
    ('1. Rebus.\nTutup pancinya.\n2. Tiriskan.', ['Rebus.\nTutup pancinya.', 'Tiriskan.']),
    ('1) Kocok telur. 2) Goreng.', ['Kocok telur.', 'Goreng.']),
    ('1.Kocok telur. 2.Goreng.', ['Kocok telur.', 'Goreng.']),
    ('1. Tambahkan 1.5 sdm minyak dan 2 butir telur. 2. Masak 10 menit pukul 12.30.',
     ['Tambahkan 1.5 sdm minyak dan 2 butir telur.', 'Masak 10 menit pukul 12.30.']),
    ('Rebus dengan 1.5 liter air. Masak 2 menit.', ['Rebus dengan 1.5 liter air. Masak 2 menit.']),
    ('Cuci bahan.\n\nPotong bahan.\nMasak.', ['Cuci bahan.', 'Potong bahan.', 'Masak.']),
    ('- Cuci bahan.\n• Masak.', ['Cuci bahan.', 'Masak.']),
    (None, []), ('   ', []),
])
def test_cooking_steps_preserve_instructions_and_quantities(text, expected):
    assert split_cooking_steps(text) == expected


def test_cooking_step_list_escapes_html():
    html = recipe_html({'steps_text': '1. Cuci <b>bahan</b>. 2. Aduk & masak.'}, 1)
    assert '<li>Cuci &lt;b&gt;bahan&lt;/b&gt;.</li><li>Aduk &amp; masak.</li>' in html
    assert '<b>bahan</b>' not in html


def test_available_ingredient_meter_uses_counts_from_recipe_data():
    html = recipe_html({'title': 'Telur', 'ingredient_names': ['telur', 'garam'],
                        'matched_recipe_items': ['telur'], 'missing_items': ['garam']}, 1)
    assert '1 dari 2' in html
    assert 'aria-valuenow="1"' in html
    assert 'aria-valuemax="2"' in html
    assert 'width:50%' in html


def test_ingredient_text_is_escaped_without_changing_recipe():
    names = ['<script>alert(1)</script>', 'telur', 'garam', 'minyak', 'lada']
    recipe = {'ingredient_names': names, 'matched_recipe_items': names, 'missing_items': []}
    html = recipe_html(recipe, 1)
    assert '<script>' not in html
    assert '&lt;script&gt;' in html
    assert recipe['ingredient_names'] == names
