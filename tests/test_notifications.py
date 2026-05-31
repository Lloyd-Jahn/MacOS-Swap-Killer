from macos_swap_killer.notifications import send_notification


def test_notification_disabled_does_not_call_osascript(monkeypatch) -> None:
    called = False

    def fake_run(*_args, **_kwargs):  # noqa: ANN001
        nonlocal called
        called = True

    monkeypatch.setattr("macos_swap_killer.notifications.subprocess.run", fake_run)
    assert not send_notification("title", "message", enabled=False)
    assert not called


def test_notification_uses_osascript_when_available(monkeypatch) -> None:
    calls = []

    monkeypatch.setattr("macos_swap_killer.notifications.shutil.which", lambda name: "/usr/bin/osascript")

    def fake_run(args, **kwargs):  # noqa: ANN001
        calls.append((args, kwargs))

    monkeypatch.setattr("macos_swap_killer.notifications.subprocess.run", fake_run)

    assert send_notification("title", "message", enabled=True)
    assert calls[0][0][0] == "osascript"
    assert "display notification" in calls[0][0][2]
