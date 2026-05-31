from macos_swap_killer.launchd import build_agent_plist


def test_build_agent_plist_defaults_to_dry_run() -> None:
    plist = build_agent_plist(execute=False, python_executable="/usr/bin/python3")
    assert plist["ProgramArguments"][-1] == "--dry-run"
    assert plist["ProgramArguments"][:3] == ["/usr/bin/python3", "-m", "macos_swap_killer.cli"]


def test_build_agent_plist_execute_mode() -> None:
    plist = build_agent_plist(execute=True, python_executable="/usr/bin/python3")
    assert plist["ProgramArguments"][-1] == "--execute"
