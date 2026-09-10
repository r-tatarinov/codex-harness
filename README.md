**English** | [Русский](README.ru.md)

# Codex Harness

Codex Harness is a local change-control system around Codex. It captures the state before an edit, analyzes the result, compares the two sets of findings, and allows or blocks the workflow according to a deterministic policy.

Prompts, skills, and model instructions guide Codex. Harness enforces the implemented checks through lifecycle hooks, baselines, analyzer orchestration, regression decisions, and retry limits. Automated architectural and application-layer dependency checks remain roadmap items.

Harness connects Ruff, Flake8, Pylint, Black, and MyPy as external analyzers. They produce diagnostics and metrics; Harness decides whether those findings represent a regression.

## Project version and releases

The package version is `0.1.0`, as recorded in [pyproject.toml](pyproject.toml). Published versions are listed on [GitHub Releases](https://github.com/r-tatarinov/codex-harness/releases).

## Overview and lifecycle

The control path is:

```text
Codex → Hooks → Harness → Analyzers → Findings → Regression Policy → Allow / Block
```

The current integration uses two Codex lifecycle hooks around `apply_patch`:

- `PreToolUse` resolves the execution scope, enforces the retry budget, and saves a baseline of affected Python files before the edit;
- `PostToolUse` analyzes both the baseline and the resulting source, normalizes analyzer output into findings, and applies the regression policy.

```text
Codex requests apply_patch
          |
          v
PreToolUse hook
  +-- retry limit reached? --------------------------> block before edit
  +-- capture BEFORE baseline
          |
          v
apply_patch changes files
          |
          v
PostToolUse hook
  +-- run connected analyzers on BEFORE and AFTER
  +-- normalize metrics and diagnostics as findings
  +-- apply the shared regression policy
          |
          v
Regression comparison
  +-- no new or worsened finding --------------------> allow
  +-- regression ------------------------------------> block and report to Codex
                                                         |
                                                         +-- Codex may retry
                                                         +-- retry limit stops more patches
```

The current implementation enforces Python quality rules. The same checker boundary is intended for architectural and dependency rules without coupling lifecycle control to a particular analyzer. OOP and application-layer dependency checkers are listed in the roadmap and are not implemented yet.

## Regression policy

The Harness evaluates the change made by Codex, not the entire history of technical debt in the target project. Existing findings are kept as the baseline and do not block an unrelated edit by themselves.

```text
existing technical debt != Codex error
new technical debt       = regression
worsening existing code  = regression
```

For example, an unchanged function with 63 statements is allowed, while increasing it from 63 to 70 is a regression. A newly added function that immediately exceeds a limit is also a regression.

Numeric metrics (`CFQ001`, `C901`, `PLR0912`, `PLR0915`, and `PLR1702`) are compared by file, analyzer, rule, and fully qualified function name. A new over-limit metric or an increased value is blocked. Reducing an existing excess, such as 82 to 81 lines with a limit of 80, is allowed. Moving a function to other lines within the same file does not create a regression.

Regular analyzer diagnostics are compared by file, analyzer, code, message, and occurrence count. An existing `F401` remains baseline; an additional occurrence of the same diagnostic is a regression. Debt in one file or analyzer cannot offset a new violation in another. Syntax errors in changed source are treated as code failures. Infrastructure failures fail closed but do not consume the code-correction retry budget.

## Tools, analyzers, and findings

The configuration determines which analyzers and rules run. Ruff and Flake8 are enabled by default and provide the following numeric metrics:

| Metric | Rule | Analyzer | Default limit |
| --- | --- | --- | ---: |
| Physical function length | `CFQ001` | Flake8 + `flake8-functions` | `80` |
| Function complexity | `C901` | Ruff | `10` |
| Branches | `PLR0912` | Ruff | `12` |
| Statements | `PLR0915` | Ruff | `50` |
| Nested blocks | `PLR1702` | Ruff | `4` |

These rules measure different properties. In particular, physical lines and statements are independent: blank lines and comments can affect `CFQ001`, but they are not statements for `PLR0915`. Rule semantics remain those of the analyzer; the Harness does not maintain parallel implementations.

When `CFQ001` is selected, Flake8 runs it in an isolated Harness pass. The `flake8-functions` plugin supplies the measured length, and Harness associates it with a fully qualified function name. The target project's Flake8 configuration and `noqa` do not disable this selected metric.

When Ruff is enabled, it supplies the other four numeric metrics in an isolated pass with limits from `~/.codex/harness/config/quality.toml`; lint preview is enabled for that pass. A separate regular pass follows `use_project_config` and the configured rule selectors. By default, it uses the project's settings and adds `PLC0415`. Numeric findings are compared only once. Project metric limits do not replace Harness limits, while a direct manual Ruff run uses the project's own settings.

Ruff, Flake8, Pylint, Black, and MyPy implement one analyzer interface. Only tools whose `enabled` flag is true run. Adapters own process invocation and tool-specific parsing; orchestration and hooks work with normalized findings. Another analyzer can be added without changing either hook.

Pylint and MyPy diagnostics use the same occurrence-count regression policy as ordinary Ruff diagnostics. Black runs only in formatting-check mode and never changes source; a file that was already unformatted remains baseline, while a newly introduced formatting regression is blocked.

Rule references: [`CFQ001`](https://github.com/best-doctor/flake8-functions), [`C901`](https://docs.astral.sh/ruff/rules/complex-structure/), [`PLR0912`](https://docs.astral.sh/ruff/rules/too-many-branches/), [`PLR0915`](https://docs.astral.sh/ruff/rules/too-many-statements/), [`PLR1702`](https://docs.astral.sh/ruff/rules/too-many-nested-blocks/).

## Harness architecture and project structure

```text
codex-harness/
├── hooks/                   # hook responses, turn scopes, and retry state
├── checks/                  # analyzer-neutral checking and snapshot lifecycle
│   ├── config/              # schema, loading, validation, and migration
│   ├── code_quality/        # combined quality-check CLI
│   ├── analyzers/           # adapter contract, catalog, registry, and orchestration
│   │   ├── ruff/            # Ruff diagnostics, metrics, and direct Ruff CLI
│   │   ├── flake8/          # Flake8 diagnostics and CFQ001 metrics
│   │   ├── pylint/          # Pylint integration
│   │   ├── black/           # formatting checks
│   │   └── mypy/            # type checking
│   ├── snapshots/          # capture, persistence, and before/after verification
│   ├── regression.py       # shared occurrence and numeric regression policy
│   ├── storage.py          # atomic file persistence
│   └── symbols.py          # qualified symbol identities
├── config/quality.toml      # repository copy of configuration
├── src/codex_harness/       # package metadata and built-in defaults
│   └── defaults/quality.toml # authoritative packaged default configuration
└── pyproject.toml
```

The authoritative default template is [src/codex_harness/defaults/quality.toml](src/codex_harness/defaults/quality.toml), which is included in the package. The repository-root `config/quality.toml` is a separate copy, not the installation template. Runtime configuration is read from the user path below, regardless of where the repository was cloned.

After installation, executable code is loaded from the Python package and does not depend on the clone. User data is stored separately:

```text
~/.codex/harness/
├── config/quality.toml
└── state/retry/<scope_hash>/
```

If `quality.toml` is missing, it is created automatically from the built-in template. A legacy `[python.*]` configuration is migrated atomically to the versioned `[tools.*]` schema and retained as `quality.toml.v0.bak`. Versioned files are not rewritten; missing parameters receive current defaults.

### Responsibilities inside `checks/`

`checks/` is the policy and analyzer boundary of the Harness. It converts tool-specific output into stable findings, then compares those findings without putting tool-specific behavior into the lifecycle hooks.

| Module | Responsibility |
| --- | --- |
| `config/` | Loads and validates configuration, supplies defaults, and migrates legacy user settings. |
| `code_quality/` | Provides the combined quality-check CLI. |
| `analyzers/` | Defines normalized findings and the common adapter contract; runs the configured analyzers. |
| `analyzers/<tool>/` | Owns the tool's configuration, execution, parsing, and finding normalization. |
| `regression.py` | Compares occurrence counts and numeric metrics through one analyzer-neutral policy. Debt is scoped to its file and tool. |
| `snapshots/` | Captures and consumes snapshots, obtains before/after source, and coordinates analysis with the regression policy. |
| `storage.py`, `symbols.py` | Provide atomic persistence and qualified symbol identities, respectively. |

Numeric findings and regular diagnostics are compared separately because their regression semantics differ: an exceeded numeric metric may improve without reaching its limit, while ordinary violations are tracked by occurrence count. Analyzer-specific normalization handles details such as reducing multiple `PLR1702` reports for one function to the maximum value supplied by Ruff.

All imports use the `codex_harness` namespace. Installed console scripts are used for manual runs and lifecycle hooks; legacy file-based launchers are not supported.

## Requirements

Recommended:

```text
Python 3.12+
Codex CLI with lifecycle hook support
```

Check Python:

```bash
python3 --version
```

`pip install .` installs the complete analyzer toolchain. No separate linter installation is required. To inspect the installed versions:

```bash
python3 -m flake8 --version
python3 -m ruff --version
python3 -m pylint --version
python3 -m black --version
python3 -m mypy --version
```

Compatible version ranges, including `flake8-functions`, are recorded as direct package dependencies in `pyproject.toml`. The Harness runs every tool through the same Python installation into which the package was installed.

## Installation

Clone the sources into any temporary or permanent directory and install the package:

```bash
git clone https://github.com/r-tatarinov/codex-harness.git
cd codex-harness
python3 -m pip install .
```

After installation, the clone is not needed to run the Harness. Find the absolute paths of the console scripts:

```bash
command -v codex-harness-pre-tool
command -v codex-harness-post-tool
```

## Connecting to Codex

Create the global file:

```text
~/.codex/hooks.json
```

Example:

```json
{
  "description": "Central local Codex harness",
  "hooks": {
    "PreToolUse": [
      {
        "matcher": "^apply_patch$",
        "hooks": [
          {
            "type": "command",
            "command": "/absolute/path/to/codex-harness-pre-tool",
            "timeout": 10,
            "statusMessage": "Saving code quality baseline"
          }
        ]
      }
    ],
    "PostToolUse": [
      {
        "matcher": "^apply_patch$",
        "hooks": [
          {
            "type": "command",
            "command": "/absolute/path/to/codex-harness-post-tool",
            "timeout": 30,
            "statusMessage": "Checking code quality regression"
          }
        ]
      }
    ]
  }
}
```

Replace the paths in the example with the results of `command -v`. Legacy commands using `hooks/pre_tool.py` and `hooks/post_tool.py` are not supported.

After changing `hooks.json`, fully restart Codex.

On the first run, Codex displays:

```text
Hooks need review
```

Review the hooks and allow them to run.

After startup, inspect their state with:

```text
/hooks
```

The following should be active:

```text
PreToolUse     1 installed / 1 active
PostToolUse    1 installed / 1 active
```

## Configuring tools and rules

All tool switches, rules, limits, and supported native options are stored in:

```text
~/.codex/harness/config/quality.toml
```

If the user configuration is absent, the first configuration load creates it from the packaged default [src/codex_harness/defaults/quality.toml](src/codex_harness/defaults/quality.toml). Schema version `1` stores the retry limit under `[verification]` and analyzer settings under `[tools.<name>]`, with `rules`, `limits`, and `options` subsections. The essential default configuration is:

```toml
schema_version = 1

[verification]
max_attempts = 3

[tools.ruff]
enabled = true
use_project_config = true
timeout_seconds = 10

[tools.ruff.rules]
extend_select = ["PLC0415"]

[tools.ruff.limits]
C901 = 10
PLR0912 = 12
PLR0915 = 50
PLR1702 = 4

[tools.ruff.options]
target_version = "py312"
preview = true
explicit_preview_rules = true

[tools.flake8]
enabled = true
use_project_config = false
timeout_seconds = 10
plugins = ["flake8-functions"]

[tools.flake8.rules]
select = ["CFQ001"]

[tools.flake8.limits]
CFQ001 = 80

[tools.pylint]
enabled = false
use_project_config = true
timeout_seconds = 10

[tools.pylint.rules]
enable = []
disable = []

[tools.black]
enabled = false
use_project_config = true
timeout_seconds = 10

[tools.mypy]
enabled = false
use_project_config = true
timeout_seconds = 10

[tools.mypy.rules]
enable_error_code = []
disable_error_code = []
```

Set a tool's `enabled` value to activate or deactivate it. To change the `CFQ001` limit, edit:

```toml
[tools.flake8.limits]
CFQ001 = 120
```

With `use_project_config = true`, the analyzer discovers its normal project configuration; explicitly supplied Harness rules and options take precedence. With `false`, the adapter uses an isolated tool configuration. Numeric metric passes remain isolated in either case and use Harness limits. Unknown settings, invalid types, unavailable configured plugins, and tool-rejected rules or options cause a verification failure. Configuration validation reports the parameter path; errors from external tools retain their diagnostics.

Ruff accepts `select`, `extend_select`, and `ignore`; Flake8 accepts `select` and `ignore`; Pylint accepts `enable` and `disable`; MyPy accepts `enable_error_code` and `disable_error_code`. Supported `options` cover Python targets, line and complexity limits, formatter modes, and MyPy strictness switches. Harness controls process, output, and write options.

Each analyzer has a `timeout_seconds` setting, defaulting to `10` seconds per process. This is separate from the hook timeouts in `hooks.json`.

## Checking a file manually

The combined Harness analysis can be run independently of Codex. The command accepts one or more Python-file paths and reports current findings from the enabled analyzers; it does not compare against a snapshot:

```bash
codex-harness-check path/to/file.py
```

For example:

```bash
codex-harness-check \
    project/services/payment.py
```

If limits are violated:

```text
CODE QUALITY CHECK FAILED
- /project/services/payment.py:1:1: [ruff] F401 `os` imported but unused
- /project/services/payment.py:10:1: [ruff] PLR0915 Too many statements (63 > 50)
- /project/services/payment.py:10:5: [flake8] CFQ001 Function process has length 81 that exceeds max allowed length 80
```

The Ruff analyzer adapter can also be run separately:

```bash
codex-harness-ruff path/to/file.py
```

This command uses the target project's settings. For all global Harness constraints, including `CFQ001` and Ruff metrics, use `codex-harness-check`.

Both commands exit with `0` when no findings are reported and with `1` when findings or execution errors occur.

## Checking the Harness itself

After installing the current checkout as described under Installation, run these commands from the repository root:

```bash
find checks hooks src -type f -name '*.py' -exec codex-harness-check {} +
python3 -m ruff check checks hooks src
python3 -m black --check --target-version py312 checks hooks src
python3 -m mypy --check-untyped-defs --follow-untyped-imports -p codex_harness
```

These commands check the Python sources, formatting, and types without changing source files. The `find` command passes individual files because `codex-harness-check` does not traverse directories. Harness uses the active user configuration. MyPy checks the installed `codex_harness` package with its resolved package structure; reinstall the current checkout after source changes. Use the same Python environment for `python3` and the installed console scripts.

## Block and retry policy

`PostToolUse` does not automatically revert a change.

It reports the detected regression to Codex.

For example:

```text
Verification failed.
Verification attempt 1/3

Last diagnostics:
Code quality regression detected.

ruff:
- /project/services/payment.py:1:1: F401 `os` imported but unused
- /project/services/payment.py:10:1: PLR0915 Too many statements (63 > 50) [PaymentService.process: 63 > 50]

flake8:
- /project/services/payment.py:10:5: CFQ001 Function process has length 81 that exceeds max allowed length 80 [PaymentService.process: 81 > 80]
```

The agent then receives the specific diagnostic through `reason` and `additionalContext` and can fix the code in the next iteration while the current turn's budget remains available.

### Consecutive verification FAIL limit

`max_attempts = 3` in the `[verification]` section allows at most three consecutive failed code-correction attempts within one user turn. If omitted, the default is `3`. Only integers `>= 1` are accepted; booleans, strings, and fractional values are invalid.

```text
turn A
patch            → FAIL 1/3
correction patch → FAIL 2/3
correction patch → FAIL 3/3
next apply_patch → denied before changing files

human sends a new message
turn B           → fresh retry budget
patch            → FAIL 1/3
```

After the last FAIL and when the next `apply_patch` is denied, the agent receives:

```text
Verification failed.
Verification attempt 3/3
Retry limit reached for the current turn.

Last diagnostics:
<last actual verification diagnostic>
```

`PreToolUse` returns `permissionDecision: "deny"` before files are changed, does not create a snapshot, and does not increment attempts. A value of `4/3` cannot occur. The denial applies to every subsequent `apply_patch` in the same scope, including patches to files that are not checked.

One attempt is consumed by one patch that actually changes Python code and has an overall FAIL result, regardless of the number of files, rules, or diagnostics. Changing the failure reason, for example from PLC0415 to F401, does not start a separate budget.

A relevant PASS immediately deletes the current scope's `attempts.json`: `FAIL → FAIL → PASS → FAIL` produces `1/3 → 2/3 → reset → 1/3`. PASS preserves the existing semantics of having no new regressions relative to the snapshot before the patch; it does not require all old technical debt to be eliminated. A change only to README or another unchecked file, a no-op Python patch, a repeated hook, and regular agent actions neither consume nor reset the budget. Checks run only when the contents or existence of a tracked Python file change.

### Scope and state

The scope is a stable SHA-256 hash of the JSON array `[session_identifier, resolved_cwd, turn_id]`. `session_id` from the payload is used; if it is absent, `CODEX_THREAD_ID` is used, followed by `CODEX_SESSION_ID`. A non-empty valid `turn_id` from the payload is required for the turn: there is no session-wide or global fallback. A new turn receives a different directory without deleting the previous turn's state. Different sessions and working directories are isolated as well.

`state/retry/<scope_hash>/attempts.json` contains only `consecutive_failed_attempts` and `last_failure`. Snapshots are stored in the same directory; their names are derived from `tool_use_id`, which is not part of the retry scope. The new mechanism does not use legacy snapshots stored directly in `state/`.

Operations are protected by a per-scope file lock; JSON is written through a temporary file and an atomic replace. The post-hook claims a snapshot by renaming it before verification and deletes it before saving the result. Repeated or concurrent delivery of the same PostToolUse does not run verification again or increment the counter. If the process is interrupted, a `.processing` file may remain; it is not processed again.

State from previous turns is transient runtime state: it does not participate in new execution scopes. No automatic garbage collector has been added.

### Code failure and infrastructure failure

New or worsened findings reported by analyzers, including syntax errors in changed source, consume a correction attempt. Diagnostics include the file, line, column, and message. If the old snapshot is syntactically invalid, previous numeric metrics are unavailable; the corrected source is checked against the active limits. Fixing the syntax error is allowed when it introduces no other regressions.

An inability to start an analyzer or plugin, a process timeout, a filesystem or permission error, invalid configuration, corrupted retry state, malformed analyzer output, an internal exception, or an indeterminate scope blocks the operation with an infrastructure diagnostic while preserving attempts and `last_failure`. These outcomes are not PASS. Source syntax errors are classified inside adapters; an arbitrary `SyntaxError` inside Harness remains an infrastructure failure.

Ruff syntax diagnostics with `code: null` and `name: "invalid-syntax"` are normalized as syntax findings. This response format does not by itself prevent recovery from an invalid baseline.

### Subagents

When a hook payload contains `agent_id` or `agent_type`, the current Harness implementation blocks the patch as an infrastructure failure. It does not allocate a separate retry budget or infer the relationship between parent and subagent turns from PID, time, or transcript.

A shared retry budget for subagents requires a reliable root user turn identifier and is not implemented. This is a limitation of the current Harness integration.

Retries are formed by the agent's own sequence of tool calls. The Harness does not run an LLM, retry agent, custom agent loop, or final verification gate.

## Current limitations

The Harness currently focuses primarily on Python.

Checks are connected to:

```text
apply_patch
```

Therefore, the current quality flow is designed for changes that Codex makes through this tool.

Changes made through arbitrary shell commands are not yet included in the same comparison mechanism.

Also not yet implemented:

- OOP architectural rules;
- dependency rules between application layers;
- JavaScript / TypeScript / Vue checks;
- a final `Stop` quality gate;
- project-wide checks before task completion;
- semantic review of complex architectural changes.

## Roadmap

Next directions:

```text
OOP / architecture rules
        |
        +-- new functions outside classes in class-oriented modules
        +-- violations of the project's existing structure
        +-- incorrect dependencies between layers

Stop hook
        |
        +-- final check before task completion
        +-- typing
        +-- project-wide checks

Other languages
        |
        +-- ESLint
        +-- TypeScript
        +-- Vue
        +-- HTML
```

The project's main goal is to move code quality control out of the model's probabilistic behavior and into a separate deterministic layer around the agent.

## License

Licensed under the Apache License 2.0.
See [LICENSE](LICENSE) for details.

Copyright © 2026 Roman Tatarinov.

## Documentation maintenance

When changing the documentation, update `README.md` and `README.ru.md` together, keeping the content and structure of both language versions semantically equivalent.
