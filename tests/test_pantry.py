import pytest

from dapuria.pantry import update_inventory


def test_continued_legacy_inventory_normalizes_trailing_quantities_and_aliases():
    assert update_inventory(['dada ayam 250 gr', 'baput'], 'garam') == ['dada ayam', 'bawang putih', 'garam']


@pytest.mark.parametrize("message,expected", [
    ("aku juga punya wortel", ["nasi", "telur", "wortel"]),
    ("tambahin wortel sama garam", ["nasi", "telur", "wortel", "garam"]),
    ("telurnya ternyata habis", ["nasi"]),
    ("aku tidak punya telur", ["nasi"]),
    ("hapus nasi dan telur", []),
    ("telur habis, tapi aku punya tahu", ["nasi", "tahu"]),
    ("telur habis dan nasi, tapi aku punya wortel", ["wortel"]),
    ("ganti nasi dengan kentang", ["telur", "kentang"]),
    ("mulai dari awal", []),
    ("mulai dari awal, aku punya tahu", ["tahu"]),
    ("mungkin ada wortel dan garam", ["nasi", "telur"]),
    ("telur mungkin habis", ["nasi", "telur"]),
    ("aku tidak yakin punya telur", ["nasi", "telur"]),
    ("aku punya nasi sama telor", ["nasi", "telur"]),
    ("aku punya 0,5 kg ayam", ["nasi", "telur", "ayam"]),
])
def test_inventory_edits_keep_conversation_context(message, expected):
    current = ["nasi", "telur"]
    assert update_inventory(current, message) == expected
    assert current == ["nasi", "telur"]


def test_removal_preserves_product_distinctions_and_specificity():
    items = ["ayam", "dada ayam", "kaldu ayam", "bubuk kaldu ayam", "terasi udang"]
    assert update_inventory(items, "ayamnya habis") == items[2:]
    assert update_inventory(items, "dada ayam habis") == [items[0], *items[2:]]
    assert update_inventory(items, "udang habis") == items

