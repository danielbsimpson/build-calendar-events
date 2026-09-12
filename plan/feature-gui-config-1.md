---
goal: Add a basic desktop GUI for configuring sources, email, enrichment, and running the calendar pipeline
version: 1.0
date_created: 2026-09-12
last_updated: 2026-09-12
owner: build-calendar-events maintainers
status: 'Planned'
tags: [feature, gui, ux, config]
---

# Introduction

![Status: Planned](https://img.shields.io/badge/status-Planned-blue)

This plan defines the implementation of a basic desktop GUI for the `build-calendar-events` project. The GUI lets a non-technical user select which event sources (leagues/events) to include (`f1`, `ufc`), configure per-source options, set the recipient/sender email and SMTP settings, toggle enrichment features, adjust pipeline parameters, persist these choices back to `config.yaml`, and trigger a pipeline run (including dry-run) while viewing the results and errors. The GUI is built with the Python standard-library `tkinter` toolkit so that **no new runtime dependencies** are introduced.

## 1. Requirements & Constraints

- **REQ-001**: The GUI MUST allow the user to enable/disable each available source returned by `calendar_events.sources.available_sources()` (currently `f1`, `ufc`) via checkboxes.
- **REQ-002**: The GUI MUST expose per-source options: F1 `include_sessions` (bool), UFC `ppv_only` (bool), driven by `Config.source_options`.
- **REQ-003**: The GUI MUST provide editable fields for `email.to`, `email.from` (maps to `EmailConfig.from_addr`), `email.subject_prefix`, and `email.invite_method` (choice of `PUBLISH`|`REQUEST`).
- **REQ-004**: The GUI MUST provide editable fields for SMTP `host`, `port` (int), and `use_tls` (bool). SMTP `username`/`password` MUST be editable but MUST NOT be written to `config.yaml` (they remain env/.env driven); when blank the existing env behavior is preserved.
- **REQ-005**: The GUI MUST expose enrichment toggles: `fight_card`, `weather`, `use_llm`, and text fields for `llm_backend`, `llm_model`, `llm_endpoint`.
- **REQ-006**: The GUI MUST expose pipeline parameters: `look_ahead_days` (int), `default_alarms` (comma-separated minutes), and `event_color` (string).
- **REQ-007**: The GUI MUST provide run controls mirroring the CLI flags: `dry-run`, `no-email`, `force`, and optional `limit` (int).
- **REQ-008**: The GUI MUST load the current configuration from a config file path (default `config.yaml`) on startup using `calendar_events.config.load_config`.
- **REQ-009**: The GUI MUST persist the edited configuration back to the chosen YAML path via a new `save_config` function that round-trips the `Config` dataclass to YAML.
- **REQ-010**: The GUI MUST run the pipeline via `calendar_events.pipeline.run` and display the returned `RunResult` fields (`fetched`, `new`, `updated`, `sent`, `errors`).
- **REQ-011**: The pipeline run MUST execute on a background thread so the GUI event loop does not freeze; UI updates from the worker MUST be marshalled back to the main thread.
- **REQ-012**: A new console entry point MUST launch the GUI: `python -m calendar_events.gui` and a `--gui` flag on the existing `main.py` / CLI.
- **SEC-001**: SMTP passwords entered in the GUI MUST NOT be persisted to `config.yaml` on disk under any code path.
- **SEC-002**: The password field in the GUI MUST render with masked input (`show="*"`).
- **CON-001**: No new third-party runtime dependencies may be added; the GUI MUST use only the Python standard library (`tkinter`, `tkinter.ttk`, `threading`, `queue`).
- **CON-002**: Minimum supported Python is 3.10 (existing codebase uses PEP 604 `X | None` unions).
- **CON-003**: The GUI MUST NOT change the behavior, signatures, or outputs of the existing CLI, pipeline, sources, or email code paths.
- **GUD-001**: Follow the existing code style: `from __future__ import annotations`, dataclasses, module-level docstrings, type hints.
- **GUD-002**: All new modules live under `src/calendar_events/` to match the existing package layout.
- **PAT-001**: Reuse existing loaders/models (`load_config`, `Config`, `available_sources`, `pipeline.run`, `RunResult`) rather than reimplementing config parsing.

## 2. Implementation Steps

### Implementation Phase 1

- GOAL-001: Add config serialization support so GUI edits can be persisted back to YAML without introducing dependencies or altering load behavior.

| Task | Description | Completed | Date |
|------|-------------|-----------|------|
| TASK-001 | In [src/calendar_events/config.py](../src/calendar_events/config.py), add a public function `save_config(config: Config, path: str \| Path = "config.yaml") -> None` that serializes the `Config` dataclass to a YAML dict and writes it with `yaml.safe_dump(..., sort_keys=False)` and `encoding="utf-8"`. Map `EmailConfig.from_addr` back to the YAML key `from`. Convert `Path` fields (`data_dir`, `store_file`) to `str`. Convert `default_alarms` tuple to a `list`. Emit `email.smtp.host/port/use_tls` only; MUST NOT write `smtp.username` or `smtp.password` to the file. | | |
| TASK-002 | In [src/calendar_events/config.py](../src/calendar_events/config.py), add a private helper `_config_to_dict(config: Config) -> dict` used by `save_config` producing keys in this exact order: `look_ahead_days`, `default_alarms`, `event_color`, `sources`, `data_dir`, `store_file`, `email` (`to`, `from`, `subject_prefix`, `invite_method`, `smtp` -> `host`, `port`, `use_tls`), `source_options`, `enrichment` (`fight_card`, `weather`, `use_llm`, `llm_backend`, `llm_model`, `llm_endpoint`). Omit `event_color` key when value is `None`. | | |
| TASK-003 | Add unit tests in [tests/test_config.py](../tests/test_config.py): `test_save_config_round_trip` (save then `load_config` yields an equal `Config` ignoring env-driven secrets), `test_save_config_omits_smtp_secrets` (assert `username`/`password` absent from written YAML), and `test_save_config_maps_from_addr` (assert written YAML contains key `from`). | | |

### Implementation Phase 2

- GOAL-002: Implement the tkinter GUI module presenting all configuration surfaces and run controls, backed by the models from Phase 1.

| Task | Description | Completed | Date |
|------|-------------|-----------|------|
| TASK-004 | Create [src/calendar_events/gui.py](../src/calendar_events/gui.py) with `from __future__ import annotations`, a module docstring, and a `class CalendarGui` built on `tkinter.Tk`. Constructor signature: `def __init__(self, config_path: str \| Path = "config.yaml") -> None`. Store `self.config_path` and call `self.config = load_config(config_path)`. | | |
| TASK-005 | In `CalendarGui`, build a `ttk.Notebook` with four tabs: `Sources`, `Email`, `Enrichment`, `Run`. Create `tkinter` variable objects (`StringVar`, `IntVar`, `BooleanVar`) bound to each field defined in REQ-001..REQ-007 and populate them from `self.config` in a method `_load_into_widgets(self) -> None`. | | |
| TASK-006 | Implement the `Sources` tab: one `ttk.Checkbutton` per name from `available_sources()`, bound to `BooleanVar`s in a `dict[str, BooleanVar]`; plus F1 `include_sessions` and UFC `ppv_only` checkbuttons. Initialize enabled state from `self.config.sources` and option state from `self.config.options_for(name)`. | | |
| TASK-007 | Implement the `Email` tab widgets: labeled `ttk.Entry` fields for To, From, Subject prefix; a `ttk.Combobox` for invite method (`["PUBLISH", "REQUEST"]`); SMTP Host, SMTP Port (numeric), `use_tls` checkbutton; SMTP Username entry and SMTP Password entry rendered with `show="*"` (SEC-002). | | |
| TASK-008 | Implement the `Enrichment` tab widgets: checkbuttons for `fight_card`, `weather`, `use_llm`; entries for `llm_backend`, `llm_model`, `llm_endpoint`. | | |
| TASK-009 | Implement the `Run` tab widgets: entries for `look_ahead_days`, `default_alarms` (comma-separated), `event_color`, and `limit` (blank = no limit); checkbuttons for `dry_run`, `no_email`, `force`; buttons `Save Config`, `Run Pipeline`; and a read-only `tkinter.Text` (or `ttk.Treeview`) results/log area. | | |
| TASK-010 | Implement `_collect_config(self) -> Config` that reads all widget variables back into a fresh `Config` instance: rebuild `sources` from checked boxes, `source_options` as `{"f1": {"include_sessions": bool}, "ufc": {"ppv_only": bool}}`, `email` (mapping the From field to `EmailConfig.from_addr`, including SMTP username/password in-memory only), `enrichment`, and parse `default_alarms` from the comma-separated string into a tuple of ints (ignoring blanks). | | |
| TASK-011 | Implement `_on_save(self) -> None` that calls `_collect_config()`, assigns to `self.config`, calls `save_config(self.config, self.config_path)`, and shows a `tkinter.messagebox.showinfo`/`showerror` result. | | |

### Implementation Phase 3

- GOAL-003: Wire pipeline execution on a background thread, integrate GUI launch entry points, and document/verify.

| Task | Description | Completed | Date |
|------|-------------|-----------|------|
| TASK-012 | Implement `_on_run(self) -> None` in [src/calendar_events/gui.py](../src/calendar_events/gui.py): call `_collect_config()`, disable the Run button, spawn a `threading.Thread(daemon=True)` target that calls `pipeline.run(config, source_names=<checked sources or None>, dry_run=..., no_email=..., force=..., look_ahead_days=..., limit=...)` and pushes the `RunResult` (or exception) onto a `queue.Queue`. | | |
| TASK-013 | Implement `_poll_queue(self) -> None` scheduled via `self.after(100, ...)` that drains the `queue.Queue`, renders `RunResult` fields (`fetched`, `new`, `updated`, `sent`) and each string in `errors` into the results Text widget, and re-enables the Run button when the worker finishes. | | |
| TASK-014 | Add `def main(argv: list[str] \| None = None) -> None` at the bottom of [src/calendar_events/gui.py](../src/calendar_events/gui.py) that parses an optional `--config` argument (default `config.yaml`), constructs `CalendarGui(config_path)`, and calls `.mainloop()`. Add an `if __name__ == "__main__": main()` guard so `python -m calendar_events.gui` works. | | |
| TASK-015 | In [src/calendar_events/cli.py](../src/calendar_events/cli.py), add a `--gui` boolean flag to the argument parser; when set, `import` and delegate to `calendar_events.gui.main(["--config", args.config])` and return before running the pipeline, leaving all existing CLI behavior unchanged when `--gui` is absent. | | |
| TASK-016 | In [main.py](../main.py), document the GUI entry in the module docstring/usage comment (e.g., `python main.py --gui`); no logic change beyond passing through to `cli.main()`. | | |
| TASK-017 | Add tests in a new file [tests/test_gui.py](../tests/test_gui.py) that import `calendar_events.gui`, and test the non-widget logic without opening a window: `_collect_config` round-trip (via a helper refactored to be testable, or by instantiating with `Tk` guarded by `pytest.importorskip("tkinter")` and `try/except tk.TclError: pytest.skip(...)` for headless CI), and alarm-string parsing. | | |
| TASK-018 | Update [README.md](../README.md) with a "GUI" section describing `python main.py --gui` / `python -m calendar_events.gui`, the tabs, and the note that SMTP credentials are not saved to `config.yaml`. | | |

## 3. Alternatives

- **ALT-001**: Web GUI using Flask/FastAPI + HTML — rejected because it adds runtime dependencies (CON-001) and requires a browser/server lifecycle for a "basic" local tool.
- **ALT-002**: Streamlit dashboard — rejected: heavy third-party dependency, violates CON-001, and overkill for a small config-and-run panel.
- **ALT-003**: Terminal UI (curses/`textual`) — rejected: `textual` is a new dependency; `curses` has poor Windows support and the project targets Windows users.
- **ALT-004**: PySimpleGUI/PyQt/wxPython — rejected: additional dependencies and (PyQt/wx) heavier install footprint versus stdlib `tkinter`.

## 4. Dependencies

- **DEP-001**: Python standard library `tkinter` / `tkinter.ttk` (bundled with CPython on Windows/macOS; on some Linux distros requires the OS `python3-tk` package — document in README).
- **DEP-002**: Existing internal modules: `calendar_events.config` (`load_config`, `Config`, dataclasses), `calendar_events.pipeline` (`run`, `RunResult`), `calendar_events.sources` (`available_sources`).
- **DEP-003**: `PyYAML>=6.0` (already in [requirements.txt](../requirements.txt)) for `save_config` serialization.

## 5. Files

- **FILE-001**: [src/calendar_events/config.py](../src/calendar_events/config.py) — add `save_config` and `_config_to_dict` (Phase 1).
- **FILE-002**: [src/calendar_events/gui.py](../src/calendar_events/gui.py) — new module implementing `CalendarGui` and `main` (Phases 2–3).
- **FILE-003**: [src/calendar_events/cli.py](../src/calendar_events/cli.py) — add `--gui` flag delegating to the GUI (Phase 3).
- **FILE-004**: [main.py](../main.py) — document `--gui` usage (Phase 3).
- **FILE-005**: [tests/test_config.py](../tests/test_config.py) — add `save_config` round-trip and secret-omission tests (Phase 1).
- **FILE-006**: [tests/test_gui.py](../tests/test_gui.py) — new test module for GUI non-widget logic (Phase 3).
- **FILE-007**: [README.md](../README.md) — document the GUI (Phase 3).

## 6. Testing

- **TEST-001**: `test_save_config_round_trip` — `save_config(cfg, tmp_path/"c.yaml")` then `load_config(...)` returns a `Config` equal to `cfg` for all non-secret fields.
- **TEST-002**: `test_save_config_omits_smtp_secrets` — written YAML text does not contain `username:` or `password:` under `email.smtp`.
- **TEST-003**: `test_save_config_maps_from_addr` — written YAML `email` block contains key `from` set to `EmailConfig.from_addr` value.
- **TEST-004**: `test_collect_config_sources_and_options` — after setting source checkbuttons and option vars, `_collect_config()` yields expected `sources` list and `source_options` dict.
- **TEST-005**: `test_collect_config_parses_alarms` — `"1440, 30"` parses to `(1440, 30)`; blank string parses to empty tuple.
- **TEST-006**: `test_gui_import_headless` — importing `calendar_events.gui` succeeds; GUI construction is skipped when no display is available (`pytest.importorskip` / `TclError` guard).
- **TEST-007**: `test_run_result_render` — a synthetic `RunResult` with errors renders all fields and error lines into the results widget/text buffer via the render helper.

## 7. Risks & Assumptions

- **RISK-001**: `tkinter` is not installed on some minimal Linux CI images; mitigation: guard GUI tests with `pytest.importorskip("tkinter")` and skip on `TclError` so CI stays green.
- **RISK-002**: Long-running `pipeline.run` could freeze the UI if run on the main thread; mitigated by the background-thread + queue design (REQ-011, TASK-012/013).
- **RISK-003**: `save_config` could accidentally leak SMTP credentials; mitigated by SEC-001 and TEST-002 explicitly asserting omission.
- **RISK-004**: Writing YAML may reorder/lose comments present in the hand-edited `config.yaml`; mitigated by using `sort_keys=False` and documenting that saving via GUI rewrites the file without comments.
- **ASSUMPTION-001**: The two current sources are `f1` and `ufc`; the Sources tab is generated dynamically from `available_sources()` so new sources appear automatically without GUI code changes.
- **ASSUMPTION-002**: Users run the GUI on a desktop OS (Windows/macOS/Linux-with-Tk) with a display available; headless servers will continue to use the CLI.
- **ASSUMPTION-003**: SMTP username/password continue to be supplied via environment/`.env` for actual sends; GUI-entered credentials are used only for the current in-memory run and are never persisted.

## 8. Related Specifications / Further Reading

- [plan/feature-mvp-sources-1.md](feature-mvp-sources-1.md)
- [plan/feature-event-enrichment-1.md](feature-event-enrichment-1.md)
- [plan/feature-robustness-2.md](feature-robustness-2.md)
- [Python tkinter documentation](https://docs.python.org/3/library/tkinter.html)
- [tkinter.ttk themed widgets](https://docs.python.org/3/library/tkinter.ttk.html)
- [PyYAML documentation](https://pyyaml.org/wiki/PyYAMLDocumentation)
