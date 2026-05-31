from macos_swap_killer.reporting import render_summary, summarize_events


def test_report_summary_counts_incidents_and_vetoes() -> None:
    summary = summarize_events(
        [
            {
                "timestamp": "2026-01-01T00:00:00Z",
                "event": "incident",
                "result": {
                    "swap": {"used_gib": 12.0},
                    "actions": [{"status": "dry_run", "process_name": "node"}],
                    "vetoes": [{"reason": "main GUI application process requires manual confirmation", "name": "Code"}],
                    "decisions": [{"action": "ASK_CONFIRM", "process_name": "Code"}],
                },
            }
        ]
    )
    assert summary["incident_count"] == 1
    assert summary["max_swap_gib"] == 12.0
    assert summary["top_veto_reasons"]["main GUI application process requires manual confirmation"] == 1
    assert "MacOS Swap Killer Report" in render_summary(summary)
