# MacOS Swap Killer TODO

## Done

- [x] Add interactive confirmation mode for `ASK_CONFIRM` decisions.
- [x] Add local user rules in `rules.toml`.
- [x] Add trend-aware triggering so incidents can fire on fast swap growth.
- [x] Add app-specific playbooks for browsers, VS Code, Python/Jupyter, Node, Docker, local AI, messaging, and notes apps.
- [x] Add user launchd agent install/uninstall/status commands.
- [x] Add macOS Notification Center alerts for incidents.
- [x] Replace raw-only reports with useful incident, decision, action, veto, and process summaries.
- [x] Keep all automatic termination behind local hard safety checks and explicit `--execute`.
- [x] Redesign the README in a cleaner product-style format.
- [x] Split README language versions with a top-right language switch.
- [x] Add a lightweight Mac UI for status, dry-run scans, reports, and config/rules access.

## Next

- [ ] Package the UI as a double-clickable `.app`.
- [ ] Add a README screenshot after running the UI on a real macOS desktop.
- [ ] Add a UI settings panel for threshold, model, notifications, and trend trigger options.
- [ ] Add a small rules editor for protected, ask-confirm, and auto-terminate entries.
- [ ] Add UI-level smoke coverage that can run in CI without opening a desktop window.
- [ ] Add more App playbooks for design tools, IDEs, database clients, and local development servers.
