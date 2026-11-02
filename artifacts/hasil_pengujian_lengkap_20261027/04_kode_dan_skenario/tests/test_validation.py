import pytest

from dapuria.preprocessing import parse_user_ingredients
from dapuria.validation import is_relevant_enough, relevance_threshold, validate_initial


def test_requires_main_ingredient():
    valid, status = validate_initial(["garam", "gula"])
    assert not valid
    assert status == "need_main_ingredient"


def test_accepts_main_ingredient():
    valid, status = validate_initial(["telur", "garam"])
    assert valid
    assert status == "ok"


def test_relevance_threshold():
    assert relevance_threshold(["telur"]) == 1
    assert relevance_threshold(["telur", "ayam", "bawang putih"]) == 2


def test_final_relevance_check():
    candidate = {"matched_user_items": ["telur", "ayam"]}
    assert is_relevant_enough(candidate, ["telur", "ayam", "bawang putih"])


@pytest.mark.parametrize('text', [
    'kaldu ayam', 'bubuk kaldu ayam', 'kaldu sapi', 'kaldu jamur',
    'terasi udang', 'petis udang', 'kerupuk udang',
])
def test_product_names_do_not_supply_their_source_main_ingredient(text):
    assert validate_initial(parse_user_ingredients(text)) == (False, 'need_main_ingredient')


def test_egg_alias_is_a_valid_main_ingredient():
    assert validate_initial(parse_user_ingredients('telor')) == (True, 'ok')
