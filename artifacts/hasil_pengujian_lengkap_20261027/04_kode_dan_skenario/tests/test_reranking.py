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


def test_recipe_alias_is_matched_without_rewriting_source_names():
    stats = coverage_stats(['telur'], ['telor ayam', 'garam'])
    assert stats['matched_recipe_items'] == ['telor ayam']
    assert stats['matched_user_items'] == ['telur']
    assert stats['missing_items'] == ['garam']
