from macos_swap_killer.config import AppConfig
from macos_swap_killer.models import SwapInfo
from macos_swap_killer.ui import collect_dashboard_snapshot


def test_collect_dashboard_snapshot_formats_status() -> None:
    snapshot = collect_dashboard_snapshot(
        config_loader=lambda: AppConfig(api_key="secret", model="mock-model", swap_threshold_gib=8),
        swap_loader=lambda: SwapInfo(
            used_gib=3.25,
            total_gib=8.0,
            free_gib=4.75,
            source="test",
            memory_free_percent=42,
        ),
        events_loader=lambda: [
            {
                "timestamp": "2026-01-01T00:00:00Z",
                "event": "incident",
                "result": {"swap": {"used_gib": 3.25}},
            }
        ],
        agent_loader=lambda: {"loaded": False, "plist_exists": True},
    )

    assert snapshot.swap_used == "3.25 GiB"
    assert snapshot.swap_total == "8.00 GiB"
    assert snapshot.memory_free == "42%"
    assert snapshot.api_status == "configured"
    assert snapshot.model == "mock-model"
    assert snapshot.threshold == "8 GiB"
    assert snapshot.incidents == "1"
    assert snapshot.agent == "installed"


def test_collect_dashboard_snapshot_survives_swap_collection_errors() -> None:
    def raise_error() -> SwapInfo:
        raise RuntimeError("sysctl unavailable")

    snapshot = collect_dashboard_snapshot(
        config_loader=lambda: AppConfig(api_key=None),
        swap_loader=raise_error,
        events_loader=list,
        agent_loader=lambda: {"loaded": False, "plist_exists": False},
    )

    assert snapshot.swap_used == "n/a"
    assert snapshot.swap_source == "unavailable"
    assert snapshot.api_status == "missing"
    assert snapshot.agent == "not installed"
