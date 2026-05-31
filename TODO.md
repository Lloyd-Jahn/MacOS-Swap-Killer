# MacOS Swap Killer TODO

This list tracks the next-stage improvements requested after the initial MVP.

- [x] Add interactive confirmation mode for `ASK_CONFIRM` decisions.
- [x] Add local user rules in `rules.toml`.
- [x] Add trend-aware triggering so incidents can fire on fast swap growth, not only an absolute threshold.
- [x] Add app-specific playbooks for browsers, VS Code, Python/Jupyter, Node, Docker, local AI, messaging, and notes apps.
- [x] Add user launchd agent install/uninstall/status commands.
- [x] Add macOS Notification Center alerts for incidents.
- [x] Replace raw-only reports with a useful summary of incidents, swap peaks, decisions, actions, vetoes, and top processes.
- [x] Keep all automatic termination behind local hard safety checks and explicit `--execute`.
- [x] Cover the new behavior with focused tests.
