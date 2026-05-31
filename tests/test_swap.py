from macos_swap_killer.swap import parse_memory_pressure, parse_sysctl_swapusage, parse_top_swap


def test_parse_sysctl_swapusage_gib() -> None:
    info = parse_sysctl_swapusage("vm.swapusage: total = 16.00G  used = 12.50G  free = 3.50G  (encrypted)")
    assert info.used_gib == 12.5
    assert info.total_gib == 16.0
    assert info.free_gib == 3.5


def test_parse_sysctl_swapusage_mib() -> None:
    info = parse_sysctl_swapusage("vm.swapusage: total = 2048.00M  used = 512.00M  free = 1536.00M")
    assert info.used_gib == 0.5


def test_parse_top_swap() -> None:
    info = parse_top_swap("Swap: 1024M used, 2048M free.")
    assert info.used_gib == 1.0
    assert info.free_gib == 2.0


def test_parse_memory_pressure() -> None:
    info = parse_memory_pressure("System-wide memory free percentage: 46%")
    assert info.used_gib is None
    assert info.memory_free_percent == 46
