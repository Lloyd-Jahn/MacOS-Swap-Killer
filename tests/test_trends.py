from macos_swap_killer.models import SwapInfo
from macos_swap_killer.trends import TrendStore


def test_trend_store_triggers_on_growth(tmp_path):
    store = TrendStore(tmp_path / "history.jsonl", window_sec=600, growth_threshold_gib=2.0, max_samples=10)
    first = store.record(SwapInfo(used_gib=1.0, total_gib=4, free_gib=3, source="test"), now=1000)
    second = store.record(SwapInfo(used_gib=3.5, total_gib=4, free_gib=0.5, source="test"), now=1100)

    assert not first.triggered
    assert second.triggered
    assert second.growth_gib == 2.5


def test_trend_store_drops_old_samples(tmp_path):
    store = TrendStore(tmp_path / "history.jsonl", window_sec=10, growth_threshold_gib=2.0, max_samples=10)
    store.record(SwapInfo(used_gib=1.0, source="test"), now=1000)
    latest = store.record(SwapInfo(used_gib=5.0, source="test"), now=1020)

    assert latest.sample_count == 1
    assert not latest.triggered
