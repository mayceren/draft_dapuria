import pytest

from dapuria.preprocessing import (
    ingredient_matches,
    parse_ingredient,
    parse_user_ingredients,
)


def test_parser_removes_quantity_and_unit():
    assert parse_user_ingredients(
        "2 butir telur, 100 gr dada ayam, 2 siung bawang putih"
    ) == ["telur", "dada ayam", "bawang putih"]


def test_phrase_boundary_prevents_teri_terigu_false_positive():
    assert ingredient_matches("teri", "terigu") is False


def test_general_name_can_match_specific_name():
    assert ingredient_matches("ayam", "dada ayam") is True


def test_parse_user_ingredients_with_dan():
    assert parse_user_ingredients("telur dan tahu") == ["telur", "tahu"]


def test_parse_user_ingredients_with_semicolon():
    assert parse_user_ingredients("telur; tahu") == ["telur", "tahu"]


@pytest.mark.parametrize('message', [
    'adanya kaldu jamur', 'yang ada kaldu jamur', 'cuma ada kaldu jamur',
    'kaldu jamur aja yang ada',
])
def test_colloquial_availability_keeps_the_specific_ingredient(message):
    assert parse_user_ingredients(message) == ['kaldu jamur']


def test_parse_mixed_natural_input():
    assert parse_user_ingredients("nasi, 1 telur dan kecap") == [
        "nasi",
        "telur",
        "kecap",
    ]


def test_parse_equivalent_separators():
    assert parse_user_ingredients("telur, tahu") == ["telur", "tahu"]
    assert parse_user_ingredients("telur dan tahu") == ["telur", "tahu"]
    assert parse_user_ingredients("telur; tahu") == ["telur", "tahu"]


def test_duplicates_are_removed_after_normalization_in_original_order():
    assert parse_user_ingredients("2 butir Telur, tahu, telur, 100 gr tahu") == [
        "telur", "tahu"
    ]


def test_multiline_input_keeps_ingredients_separate():
    assert parse_user_ingredients("telur\r\ntahu\nbawang putih") == [
        "telur", "tahu", "bawang putih"
    ]


@pytest.mark.parametrize('text', [
    'aku punya nasi sama telur',
    'Saya punya nasi dan telur.',
    'gue cuma punya nasi sama telur nih',
    'di kulkas ada nasi serta telur',
    'bahan yang aku punya: nasi, telur',
    'bahan: nasi & telur',
    'nasi + telur',
    'nasi plus telur',
    'aku punya nasi, aku juga punya telur',
    'Halo Dapuria, aku punya nasi sama telur dong!',
    'aku mau masak pakai nasi dan telur',
    'tolong carikan resep dari nasi sama telur',
    'aku punya nasi sama telur, bisa masak apa ya?',
    'aku punya nasi sama telur. Bisa dibikin apa?',
    'nasi sama telur aja nih',
    'aku punya nasi. Aku punya telur juga.',
    'AKU PUNYA NASI SAMA TELUR',
])
def test_conversational_input_equals_explicit_inventory(text):
    assert parse_user_ingredients(text) == ['nasi', 'telur']


@pytest.mark.parametrize('text,expected', [
    ('aku punya 1 piring nasi sama 2 butir telur', ['nasi', 'telur']),
    ('aku punya bawang putih sama kecap manis', ['bawang putih', 'kecap manis']),
    ('aku punya asam jawa sama daun salam', ['asam jawa', 'daun salam']),
    ('aku punya nasi sama telur sama nasi', ['nasi', 'telur']),
    ('aku punya 0,5 kg ayam sama 1.5 kg kentang', ['ayam', 'kentang']),
    ('nasi &amp; telur', ['nasi', 'telur']),
    ('aku punya nasi tapi telur habis', ['nasi']),
    ('aku punya nasi, tapi tidak punya telur', ['nasi']),
    ('aku tidak punya nasi dan telur', []),
    ('tidak ada nasi sama telur, tapi aku punya tahu', ['tahu']),
    ('aku punya nasi tanpa telur', ['nasi']),
    ('aku punya nasi, tanpa telur', ['nasi']),
    ('aku punya nasi dan mungkin ada telur', ['nasi']),
    ('mungkin ada nasi dan telur', []),
    ('nasi atau telur', []),
    ('aku punya', []),
    ('bahan:', []),
    ('garam ada, lada juga ada', ['garam', 'lada']),
])
def test_conversation_keeps_names_quantities_and_ownership_consistent(text, expected):
    assert parse_user_ingredients(text) == expected


@pytest.mark.parametrize('text,expected', [
    ('telor', ['telur']),
    ('2 butir TELOR', ['telur']),
    ('aku punya nasi sama telor', ['nasi', 'telur']),
    ('telor, telur, telor ayam', ['telur', 'telur ayam']),
    ('teloran', ['teloran']),
])
def test_registered_alias_is_normalized_before_deduplication(text, expected):
    assert parse_user_ingredients(text) == expected


def test_alias_preserves_raw_ingredient_text():
    assert parse_ingredient('2 butir Telor ayam') == {
        'raw': '2 butir Telor ayam', 'name': 'telur ayam'
    }


@pytest.mark.parametrize('left,right,expected', [
    ('ayam', 'ayam', True),
    ('ayam', 'dada ayam', True),
    ('ayam', 'paha ayam', True),
    ('ayam', 'kaldu ayam', False),
    ('ayam', 'bubuk kaldu ayam', False),
    ('sapi', 'kaldu sapi', False),
    ('jamur', 'kaldu jamur', False),
    ('udang', 'terasi udang', False),
    ('udang', 'petis udang', False),
    ('udang', 'kerupuk udang', False),
    ('ayam', 'kaldu ayam (bubuk)', False),
    ('udang', 'kerupuk udang mentah', False),
    ('kaldu', 'bubuk kaldu ayam', True),
    ('kaldu ayam', 'bubuk kaldu ayam', True),
    ('kaldu sapi', 'kaldu ayam', False),
    ('terasi', 'terasi udang', True),
    ('petis', 'petis udang', True),
    ('kerupuk', 'kerupuk udang', True),
    ('terasi udang', 'petis udang', False),
    ('telor', 'telur', True),
    ('telur', 'telor ayam', True),
    (' AYAM ', 'Dada  Ayam', True),
    ('ayam', 'Kaldu  Ayam', False),
    ('teri', 'terigu', False),
])
def test_matching_respects_aliases_phrases_and_product_categories(left, right, expected):
    assert ingredient_matches(left, right) is expected
    assert ingredient_matches(right, left) is expected
