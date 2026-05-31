from macos_swap_killer.privacy import redact_text


def test_redacts_tokens_and_long_values() -> None:
    text = "--api-key=sk-abcdefghijklmnopqrstuvwxyz1234567890 --token abcdefghijklmnopqrstuvwxyzABCDEF"
    redacted = redact_text(text)
    assert "abcdefghijklmnopqrstuvwxyz" not in redacted
    assert "<redacted>" in redacted


def test_redacts_url_credentials() -> None:
    redacted = redact_text("https://user:password@example.com/path")
    assert "password" not in redacted
    assert "https://<redacted>@example.com/path" == redacted


def test_redacts_home_path() -> None:
    redacted = redact_text("/Users/alice/projects/private/repo/file.txt")
    assert "alice/projects/private" not in redacted
    assert redacted.endswith("repo/file.txt")
