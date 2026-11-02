import pytest

from dapuria.reranking import (
    coverage_stats,
    harmonic_efficiency,
    minmax_normalize,
    weighted_linear_score,
)


def test_coverage_stats():
    stats = coverage_stats(["telur", "ayam"], ["telur ayam", "dada ayam", "garam"])
    assert stats["coverage_user"] == pytest.approx(1.0)
    assert stats["coverage_recipe"] == pytest.approx(2 / 3)
    assert "garam" in stats["missing_items"]


def test_harmonic_efficiency_zero_safe():
    assert harmonic_efficiency(0.0, 0.0) == 0.0


def test_minmax_equal_values_is_defined():
    values = minmax_normalize([0.5, 0.5])
    assert values.tolist() == [0.0, 0.0]


def test_wlc_frozen_weights_example():
    from dapuria.config import Settings
    settings = Settings()
    assert weighted_linear_score(
        0.8, 0.5, settings.semantic_weight, settings.ingredient_weight
    ) == pytest.approx(0.77)


def test_stock_is_missing_even_when_the_user_has_chicken():
    stats = coverage_stats(['ayam'], ['dada ayam', 'paha ayam', 'kaldu ayam', 'bubuk kaldu ayam'])
    assert stats['matched_recipe_items'] == ['dada ayam', 'paha ayam']
    assert stats['matched_user_items'] == ['ayam']
    assert stats['missing_items'] == ['kaldu ayam', 'bubuk kaldu ayam']
    assert stats['coverage_recipe'] == pytest.approx(0.5)
    assert stats['coverage_user'] == pytest.approx(1.0)


def test_derived_shrimp_products_do_not_supply_shrimp_coverage():
    stats = coverage_stats(['udang'], ['terasi udang', 'petis udang', 'kerupuk udang'])
    assert stats['matched_user_items'] == []
    assert stats['matched_recipe_items'] == []
    assert stats['coverage_recipe'] == stats['coverage_user'] == 0.0
    assert stats['missing_items'] == ['terasi udang', 'petis udang', 'kerupuk udang']


def test_recipe_alias_is_canonicalized_without_mutating_input():
    source = ['telor ayam', 'garam']
    stats = coverage_stats(['telur'], source)
    assert stats['matched_recipe_items'] == ['telur ayam']
    assert stats['matched_user_items'] == ['telur']
    assert stats['missing_items'] == ['garam']
    assert source == ['telor ayam', 'garam']


def test_duplicate_and_combined_recipe_items_do_not_inflate_availability():
    stats = coverage_stats(['garam', 'kecap'], ['garam dan lada', 'kecap', 'kecap', '1'])
    assert stats['matched_recipe_items'] == ['garam', 'kecap']
    assert stats['missing_items'] == ['lada']
    assert stats['coverage_recipe'] == pytest.approx(2 / 3)
    combined = coverage_stats(['garam', 'kecap'], ['kecap garam merica'])
    assert combined['matched_recipe_items'] == ['kecap', 'garam']
    assert combined['missing_items'] == ['merica']


def test_known_seasoning_comma_keeps_both_items_but_decimal_and_notes_stay_intact():
    stats = coverage_stats(['garam'], [
        'Secukupnya garam, merica hitam bubuk', '1,5 sdm minyak goreng',
        '2 siung bawang putih, cincang halus',
    ])
    assert stats['matched_recipe_items'] == ['garam']
    assert stats['missing_items'] == ['merica hitam bubuk', 'minyak goreng', 'bawang putih']
