**English** | [Русский](README.ru.md)

# Codex Harness

Codex Harness is a local change-control system around Codex. It captures the state before an edit, analyzes the result, compares the two sets of findings, and allows or blocks the workflow according to a deterministic policy.

Rules in prompts, skills, and model instructions still guide Codex, but they are not the enforcement boundary. The Harness owns that boundary: lifecycle integration, baselines, analyzer orchestration, regression decisions, retry limits, and—through dedicated checkers—the architectural rules that can be enforced independently of the model.

Ruff and Flake8 are external analyzers connected to the Harness. They produce diagnostics and metrics; they do not define the Harness architecture or decide whether a change is allowed.

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
  +-- apply the active checker and regression policies
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

Numeric metrics (`CFQ001`, `C901`, `PLR0912`, `PLR0915`, and `PLR1702`) are compared by rule and fully qualified function name. A new violation or an increased value is blocked. Reducing an existing excess, such as 82 to 81 lines with a limit of 80, is allowed. Moving a function to other lines does not create a regression.

Regular analyzer diagnostics are compared by code, message, and occurrence count. An existing `F401` remains baseline; an additional `F401` is a regression. Syntax errors in changed source are treated as code failures. Infrastructure failures fail closed but do not consume the code-correction retry budget.

## Tools, analyzers, and findings

The Harness defines which measurements are mandatory and how their findings are compared. External analyzers calculate the measurements:

| Metric | Rule | Analyzer | Default limit |
| --- | --- | --- | ---: |
| Physical function length | `CFQ001` | Flake8 + `flake8-functions` | `max_lines = 80` |
| Function complexity | `C901` | Ruff | `max_complexity = 10` |
| Branches | `PLR0912` | Ruff | `max_branches = 12` |
| Statements | `PLR0915` | Ruff | `max_statements = 50` |
| Nested blocks | `PLR1702` | Ruff | `max_nested_blocks = 4` |

These rules measure different properties. In particular, physical lines and statements are independent: blank lines and comments can affect `CFQ001`, but they are not statements for `PLR0915`. Rule semantics remain those of the analyzer; the Harness does not maintain parallel implementations.

Flake8 runs in an isolated Harness pass for `CFQ001`. The `flake8-functions` plugin supplies the measured length, and the Harness associates it with a fully qualified function name. The target project's Flake8 configuration and `noqa` do not disable this global constraint.

Ruff supplies the other four numeric metrics in an isolated pass with limits from `~/.codex/harness/config/quality.toml`; lint preview is enabled for that pass. A second Ruff pass discovers the target project's normal configuration and reports its other enabled rules, such as `F401` or `PLC0415`. Harness metrics are excluded from the second comparison to avoid duplicate findings. The target project's metric limits do not replace the Harness limits, and a regular manual Ruff run continues to use the project's own settings.

Ruff, Flake8, Pylint, Black, and MyPy all implement one analyzer interface. The registry selects only tools whose `enabled` flag is true. Adapters own process invocation and tool-specific parsing; the orchestrator and lifecycle hooks see only normalized findings. This keeps external rule implementations in their original tools and allows another analyzer to be added without changing either hook.

Pylint and MyPy diagnostics use the same occurrence-count regression policy as ordinary Ruff diagnostics. Black runs only in formatting-check mode and never changes source; a file that was already unformatted remains baseline, while a newly introduced formatting regression is blocked.

Rule references: [`CFQ001`](https://github.com/best-doctor/flake8-functions), [`C901`](https://docs.astral.sh/ruff/rules/complex-structure/), [`PLR0912`](https://docs.astral.sh/ruff/rules/too-many-branches/), [`PLR0915`](https://docs.astral.sh/ruff/rules/too-many-statements/), [`PLR1702`](https://docs.astral.sh/ruff/rules/too-many-nested-blocks/).

## Harness architecture and project structure

```text
codex-harness/
├── hooks/                   # lifecycle control, baselines, scopes, and retry state
├── checks/                  # analysis adapters, findings, and regression policy
│   ├── config/              # schema, paths, loading, validation, and migration
│   ├── code_quality/        # combined CLI and legacy public imports
│   ├── analyzers/           # common interface, catalog, registry, and policy
│   │   ├── ruff/            # adapter, runner, parsing, schema, and configuration
│   │   ├── flake8/          # adapter, runner, parsing, schema, and configuration
│   │   ├── pylint/          # adapter, runner, parsing, and configuration
│   │   ├── black/           # adapter, check-only runner, and configuration
│   │   └── mypy/            # adapter, runner, parsing, and configuration
│   ├── function_length/     # CFQ001 finding normalization
│   ├── python_flake8/       # compatibility re-exports for the former public API
│   ├── python_ruff/         # compatibility re-exports and Ruff console entry point
│   └── ruff_metrics/        # numeric Ruff finding normalization
├── src/codex_harness/       # package metadata and built-in defaults
├── tests/                   # policy, adapter, configuration, and hook tests
└── pyproject.toml
```

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
| `config/` | Separates configuration schema, filesystem paths, packaged defaults, loading, validation, serialization, and legacy migration. `config/__init__.py` is the stable configuration API. |
| `code_quality/` | Provides the combined CLI and preserves established quality-check imports. |
| `analyzers/` | Defines normalized findings, shared regression comparison, configuration catalog, runtime adapter registry, and orchestration. |
| `analyzers/<tool>/` | Owns one tool's configuration schema, subprocess runner, output parser, local diagnostic schema where needed, and Harness adapter. Each package exposes its stable API through `__init__.py`. |
| `finding.py`, `symbols.py` | Provide normalized numeric findings and stable symbol identities across line movements. |
| `comparison.py`, `regression.py` | Apply numeric before/after policy, including recovery from a syntactically invalid baseline. |
| `ruff_regression.py` | Compares regular project-configured diagnostics by code, message, and occurrence count. |
| `python_flake8/`, `python_ruff/` | Preserve the former public imports by re-exporting the corresponding analyzer packages; they contain no analyzer implementation. |
| `function_length/`, `ruff_metrics/` | Adapt analyzer measurements to the common numeric regression model. |

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

If the file is absent, the first hook creates it automatically. The essential default configuration is:

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

With `use_project_config = true`, the analyzer discovers its normal project configuration and Harness `rules`, `limits`, and `options` take precedence. With `false`, the adapter uses an isolated tool configuration. Unknown tools, rules, plugins, options, incorrect types, and invalid positive limits fail closed with a configuration path in the error. Harness does not reimplement any external rule.

Ruff and Flake8 accept `select`/`extend_select`/`ignore` rule selectors, Pylint accepts `enable`/`disable`, and MyPy accepts `enable_error_code`/`disable_error_code`. Supported `options` cover Python targets, line and complexity limits, formatter modes, and the common MyPy strictness switches; reserved process/output/write options remain controlled by Harness.

## Checking a file manually

The combined Harness analysis can be run independently of Codex:

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

- payment.py:10:1: [flake8] CFQ001 Function process has length 81 that exceeds max allowed length 80
- payment.py:10:1: [ruff] PLR0915 Too many statements (63 > 50)
- payment.py:10:1: [ruff] C901 `process` is too complex (18 > 10)
```

The Ruff analyzer adapter can also be run separately:

```bash
codex-harness-ruff path/to/file.py
```

This command uses the target project's settings. For all global Harness constraints, including `CFQ001` and Ruff metrics, use `codex-harness-check`.

## Checking the Harness itself

From the repository root:

```bash
codex-harness-check checks hooks tests
ruff format --check .
python3 -m unittest discover -v
```

Tests cover the 80/81 boundary, numeric regression scenarios, automatic configuration creation, and the complete `PreToolUse` / `PostToolUse` cycle through the installed console scripts.

## Block and retry policy

`PostToolUse` does not automatically revert a change.

It reports the detected regression to Codex.

For example:

```text
Verification failed.
Verification attempt 1/3

Last diagnostics:
Code quality regression detected.

Quality rules:
- CFQ001 PaymentService.process: Function process has length 81 that exceeds max allowed length 80

Ruff:
- F401 `os` imported but unused
```

The agent then receives the specific diagnostic through `reason` and `additionalContext` and can fix the code in the next iteration while the current turn's budget remains available.

### Consecutive verification FAIL limit

`[verification] max_attempts = 3` means at most three consecutive unsuccessful correction attempts within one user turn. If the parameter is absent, `3` is used. Only integers `>= 1` are accepted; booleans, strings, and fractional values are invalid. The parameter is read by the existing TOML loader.

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

Analyzer-reported code violations, quality regressions, and SyntaxError while parsing changed source consume an attempt. A parsing error preserves the file name, line, column, and message. If the old snapshot is syntactically invalid, the previous quality metrics are considered unavailable; the corrected file is checked against the active limits. This makes it possible to fix a SyntaxError with the remaining attempts.

An inability to start a checker or plugin, a timeout (10 seconds per Ruff or Flake8 process), a filesystem or permission error, invalid configuration, corrupted retry state, malformed checker response, internal exception, or indeterminate scope blocks the operation with the original infrastructure diagnostic while preserving attempts and `last_failure`. These outcomes are not considered PASS. Error types are determined structurally; an arbitrary SyntaxError inside the Harness is not treated as an agent source-code error.

Known adapter limitation: Ruff may return `code: null` for a syntax error in an old snapshot. The current parser expects a string code and, in that case, returns an infrastructure failure even after the source is fixed. This pre-existing behavior was preserved during module cleanup; recovery after a SyntaxError depends on the response format of the installed Ruff version.

### Subagents

The installed Codex schemas include `agent_id`/`agent_type`, but do not provide the root user turn identifier in tool hooks. When this explicit agent metadata is present, the Harness blocks the patch as an infrastructure failure without a separate retry budget. Equality between parent and subagent `turn_id` values is not assumed; the relationship is not inferred from PID, time, or transcript.

Limitation: **a shared retry budget for subagents is not supported without a reliable root turn identifier**. Checking the built-in schema does not mean that a live end-to-end subagent test has been performed.

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
- automatic tests and project-wide checks before task completion;
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
        +-- tests
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

## Documentation maintenance

When changing the documentation, update `README.md` and `README.ru.md` together, keeping the content and structure of both language versions semantically equivalent.
