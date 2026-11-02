import pytest

from dapuria.preferences import ingredient_is_excluded, update_preferences
from dapuria.preprocessing import parse_user_ingredients


@pytest.mark.parametrize("message,inventory,excluded", [
    ("aku punya nasi sama telur, jangan pakai ayam", ["nasi", "telur"], ["ayam"]),
    ("nasi dan telur tanpa ayam dan udang", ["nasi", "telur"], ["ayam", "udang"]),
    ("jangan pakai ayam, aku punya nasi dan telur", ["nasi", "telur"], ["ayam"]),
    ("aku tidak mau ayam, tapi aku punya nasi", ["nasi"], ["ayam"]),
    ("aku punya nasi, hindari bawang putih sama telur", ["nasi"], ["bawang putih", "telur"]),
    ("nasi, jangan pakai telor", ["nasi"], ["telur"]),
    ("ayam habis, tapi aku punya nasi", ["nasi"], []),
    ("aku tidak punya ayam, tapi aku punya nasi", ["nasi"], []),
    ("aku punya nasi dan telur, bisa masak apa?", ["nasi", "telur"], []),
    ("aku punya 0,5 kg ayam, jangan pakai garam", ["ayam"], ["garam"]),
])
def test_preferences_are_separate_from_inventory(message, inventory, excluded):
    update = update_preferences([], message)
    assert parse_user_ingredients(update.inventory_text) == inventory
    assert update.excluded == excluded


def test_constraints_persist_can_be_lifted_and_reset_independently():
    initial = ["ayam", "udang"]
    assert update_preferences(initial, "aku juga punya wortel").excluded == initial
    allowed = update_preferences(initial, "boleh pakai ayam")
    assert allowed.excluded == ["udang"]
    assert allowed.inventory_text == ""
    cleared = update_preferences(initial, "hapus batasan")
    assert cleared.excluded == [] and cleared.inventory_text == ""
    reset = update_preferences(initial, "mulai dari awal, aku punya tahu")
    assert reset.excluded == []
    assert update_preferences([], "jangan pakai ayam dan ayam").excluded == ["ayam"]
    assert initial == ["ayam", "udang"]
    assert update_preferences(initial, "boleh pakai ayam lagi").excluded == ["udang"]
    cleared_one = update_preferences(initial, "hapus batasan ayam")
    assert cleared_one.excluded == ["udang"] and cleared_one.inventory_text == ""


@pytest.mark.parametrize("ingredient,excluded,expected", [
    ("dada ayam", ["ayam"], True),
    ("kaldu ayam", ["ayam"], True),
    ("bubuk kaldu ayam", ["ayam"], True),
    ("bayam", ["ayam"], False),
    ("terigu", ["teri"], False),
    ("bawang-putih", ["bawang putih"], True),
    ("telor ayam", ["telur"], True),
    ("kaldu jamur", ["ayam"], False),
    ("terasi udang", ["udang"], True),
])
def test_exclusions_match_whole_names_including_derived_products(ingredient, excluded, expected):
    assert ingredient_is_excluded(ingredient, excluded) is expected
