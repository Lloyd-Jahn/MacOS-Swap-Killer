from macos_swap_killer.models import ProcessInfo
from macos_swap_killer.playbooks import advise_process


def process(name: str, exe: str, cmdline: list[str], *, is_gui_main: bool = False) -> ProcessInfo:
    return ProcessInfo(
        pid=123,
        ppid=1,
        user="jiangyi",
        name=name,
        exe=exe,
        cmdline=cmdline,
        rss_bytes=1,
        is_gui_main=is_gui_main,
    )


def test_browser_renderer_is_auto_eligible() -> None:
    advice = advise_process(
        process(
            "Microsoft Edge Helper (Renderer)",
            "/Applications/Microsoft Edge.app/Contents/Frameworks/Microsoft Edge Helper.app/Contents/MacOS/Microsoft Edge Helper",
            ["Microsoft Edge Helper", "--type=renderer"],
        )
    )
    assert advice.app_family == "browser"
    assert advice.auto_eligible


def test_vscode_extension_host_requires_confirmation() -> None:
    advice = advise_process(
        process(
            "Code Helper (Plugin)",
            "/Applications/Visual Studio Code.app/Contents/Frameworks/Code Helper.app/Contents/MacOS/Code Helper",
            ["Code Helper", "--type=utility", "--utility-sub-type=node.mojom.NodeService"],
        )
    )
    assert advice.app_family == "vscode"
    assert advice.recommendation == "ask_confirm"
