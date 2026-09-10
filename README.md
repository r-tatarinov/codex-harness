**English** | [Русский](README.ru.md)

# Codex Harness

A local harness for Codex that adds deterministic code quality checks on top of the agent's work.

The core idea is not to rely only on rules in prompts, skills, or model instructions.

Codex can generate working code that nevertheless becomes progressively harder to maintain: methods grow, nesting increases, unnecessary branching appears, and linter rules are violated.

The Harness adds a separate technical layer that checks changes after the agent's actions and reports problems back to Codex.

## How it works

The Harness currently integrates with Codex through two lifecycle hooks:

- `PreToolUse` — runs before code is changed;
- `PostToolUse` — runs after code is changed.

Current flow:

```text
Codex
  |
  | apply_patch
  v
PreToolUse
  |
  | the state of Python files before the change is saved
  v
apply_patch
  |
  v
PostToolUse
  |
  +-- Quality rules
  |     +-- function length (flake8-functions CFQ001)
  |     +-- number of statements (Ruff PLR0915)
  |     +-- nesting (Ruff PLR1702)
  |     +-- number of branches (Ruff PLR0912)
  |     +-- function complexity (Ruff C901)
  |
  +-- other Ruff rules from the target project's configuration
  |
  v
compare BEFORE / AFTER states
  |
  +-- no regression -> continue
  |
  +-- new bad code appeared -> Codex receives an error
```

## Why only regressions are checked

The Harness does not force the agent to fix all existing technical debt in a project.

For example, if a method already had 63 statements before the change:

```text
before: 63 statements
after:  63 statements
```

this is not considered a new agent error.

If Codex makes existing code worse:

```text
before: 63 statements
after:  70 statements
```

the Harness records a regression.

`CFQ001` and the Ruff metrics (`C901`, `PLR0912`, `PLR0915`, `PLR1702`) are compared numerically by rule and fully qualified function name. Reducing an excess, for example from 82 to 81 lines with a limit of 80, is allowed. Moving a function to different lines is not considered a regression.

Other Ruff diagnostics are compared by code, message text, and occurrence count.

If a new method violates the limits immediately, that is also considered a regression.

Therefore:

```text
existing technical debt != Codex error

new technical debt = error

worsening existing code = error
```

## Current checks

### Function length

Default:

```toml
max_lines = 80
```

Physical length is calculated by the [`flake8-functions`](https://github.com/best-doctor/flake8-functions) plugin using rule `CFQ001`. 80 lines are allowed; 81 lines are a violation. The Harness does not count lines itself: it runs Flake8, obtains the measurement from `CFQ001`, and uses the AST only to determine the fully qualified function name.

The plugin counts the range from the first statement in the body after an optional docstring to the function's last AST node. The header, decorators, and a standalone docstring are excluded; blank lines and comments within the range affect the length. The target project's Flake8 settings and `noqa` cannot disable the Harness's global check.

Example:

```text
CFQ001 PaymentService.process: Function process has length 81 that exceeds max allowed length 80
```

### Number of statements

Default:

```toml
max_statements = 50
```

This independent metric continues to be calculated by Ruff `PLR0915`. Blank lines and comments are not statements, so `CFQ001` and `PLR0915` control different properties of a function.

### Nesting

Default:

```toml
max_nested_blocks = 4
```

The Harness tracks excessively deep control structures.

For example:

```python
if condition:
    for item in items:
        if other_condition:
            try:
                if something:
                    ...
```

Such code becomes harder to read, test, and change.

Depth is calculated by Ruff `PLR1702`. Ruff semantics are used: `match` itself does not add a level, while blocks in nested functions can affect the enclosing function's score. Preview is enabled only for linting; formatter preview is disabled.

PLR1702 may report several blocks within one function. The Harness associates each diagnostic with the innermost function containing the beginning of the reported block and compares the maximum value by fully qualified function name. When depths are equal, the first block by location is selected. For example, changing a depth from 6 to 5 is allowed, while changing it from 5 to 6 is blocked; reordering blocks without changing the maximum is allowed.

### Number of branches

Default:

```toml
max_branches = 12
```

The metric is calculated by Ruff `PLR0912`. It accounts for control-flow constructs such as:

```text
if
elif
else
for
while
except
except*
finally
match / case
```

This limits the amount of control-flow logic. For example, Ruff counts `if/else` as two branches. The `max_branches` value applies to this metric.

### Function complexity

Default:

```toml
max_complexity = 10
```

Ruff `C901` (McCabe) is used for the calculation.

The rule limits the structural complexity of functions, methods, and nested functions. `and/or`, conditional expressions, and comprehensions do not increase C901. For example, `return a and b and c` gives C901 = 1. C901 also includes nested definitions when scoring an enclosing function; nested functions are diagnosed separately as well.

Rule descriptions: [C901](https://docs.astral.sh/ruff/rules/complex-structure/), [PLR0912](https://docs.astral.sh/ruff/rules/too-many-branches/), [PLR0915](https://docs.astral.sh/ruff/rules/too-many-statements/), [PLR1702](https://docs.astral.sh/ruff/rules/too-many-nested-blocks/).

### Ruff

After Python code changes, Ruff runs in two passes for the source before and after the change:

- Global metrics `C901`, `PLR0912`, `PLR0915`, and `PLR1702`: an isolated run with limits from `~/.codex/harness/config/quality.toml` and lint preview enabled. The target project's settings and `noqa` do not disable these limits.
- Other rules: normal Ruff configuration discovery in the target project. Metrics are excluded from this pass's comparison to avoid duplicate messages and to allow improvements in numeric values.

The target project's metric limits also do not replace the Harness limits. Running regular Ruff manually in the target project continues to use the project's own settings.

It follows the same before/after state comparison principle.

If an error already existed:

```text
before: F401
after:  F401
```

it does not block the work.

If Codex adds a new error:

```text
before: clean
after:  F401
```

the Harness reports it to the agent.

## Project structure

```text
codex-harness/
├── src/codex_harness/       # package metadata and default configuration
├── checks/
│   ├── code_quality/        # combined quality CLI and configuration
│   ├── function_length/     # CFQ001 normalization
│   ├── python_flake8/       # isolated Flake8 runner and parser
│   ├── python_ruff/         # Ruff runner and parser
│   └── ruff_metrics/        # numeric Ruff metrics
├── hooks/                   # installed PreToolUse/PostToolUse entry points
├── tests/
└── pyproject.toml
```

After installation, executable code is loaded from the Python package and does not depend on the clone. User data is stored separately:

```text
~/.codex/harness/
├── config/quality.toml
└── state/retry/<scope_hash>/
```

If `quality.toml` is missing, it is created automatically from the built-in template. An existing file is not overwritten; parameters missing from it receive the current default values.

### Responsibilities of the checks modules

Ruff calculates C901 (complexity), PLR0912 (branches), PLR0915 (statements), PLR1702 (nesting), and checks PLC0415 (imports outside the top level). The Harness has no parallel implementations of these rules. The four numeric metrics use Harness limits; PLC0415, like other regular rules, runs in the pass configured by the target project.

| Module | Responsibility |
| --- | --- |
| `python_flake8/` | Runs `python -m flake8` from the Harness environment, requires the installed `flake8-functions` plugin, and strictly parses only `CFQ001`. |
| `function_length/` | Validates the plugin measurement and associates the diagnostic with the fully qualified function name; it does not count lines itself. |
| `python_ruff/` | Runs `python -m ruff`, validates JSON, and normalizes diagnostics. |
| `ruff_metrics/` | Reads global limits, builds immutable Ruff options, and normalizes numeric metrics. |
| `ruff_regression.py` | Reads snapshots and compares regular Ruff diagnostics by code, message, and occurrence count; excludes metrics that are compared numerically. |
| `finding.py` | Common numeric diagnostic for CFQ001 and Ruff metrics. |
| `comparison.py` | Numeric regression policy: a new diagnostic or an increased value for a `(rule, symbol)` pair. |
| `regression.py` | Applies the numeric regression policy to file states before and after a change; handles recovery from a syntactically invalid baseline. |
| `symbols.py` | Fully qualified names of functions, methods, and nested functions for stable comparison when line positions change. |
| `code_quality/` | Creates and loads user configuration, validates limits, runs the combined analysis, and produces CLI output. |

Multiple PLR1702 diagnostics for one function are reduced to the maximum value already calculated by Ruff. This is part of the regression policy: it allows before/after depth comparison without recalculating nesting. Numeric comparison and regular diagnostic comparison are separate because they use different keys and semantics: improving an exceeded metric is allowed, while repeated regular violations are tracked by count.

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

After installation, check the toolchain:

```bash
python3 -m flake8 --version
python3 -m ruff --version
```

The verified combination is Flake8 7.3.0, flake8-functions 0.1.0, and Ruff 0.16.6. Compatible version ranges are recorded in `pyproject.toml`. The Harness runs all tools through the same Python installation into which the package was installed.

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

## Configuring rules

All runtime limits are stored in:

```text
~/.codex/harness/config/quality.toml
```

If the file is absent, the first hook creates it automatically. Current defaults:

```toml
[verification]
max_attempts = 3

[python.functions]
max_lines = 80

[python.ruff]
max_complexity = 10
max_branches = 12
max_statements = 50
max_nested_blocks = 4
```

To change the `CFQ001` limit, edit:

```toml
[python.functions]
max_lines = 120
```

All values must be integers `>= 1`. An existing file is not overwritten when the Harness is updated; new missing keys use the built-in defaults. Architectural checks and dependency checks between layers are unchanged.

## Checking a file manually

Quality rules can be run independently of Codex:

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

- CFQ001 PaymentService.process: Function process has length 81 that exceeds max allowed length 80
- PLR0915 PaymentService.process: Too many statements (63 > 50)
- C901 PaymentService.process: `process` is too complex (18 > 10)
```

Ruff can be checked separately:

```bash
codex-harness-ruff path/to/file.py
```

This command uses the target project's settings. For all global Harness constraints, including `CFQ001` and Ruff metrics, use `codex-harness-check`.

## Checking the Harness itself

From the repository root:

```bash
ruff check .
ruff format --check .
python3 -m unittest discover -v
```

Tests cover the 80/81 boundary, numeric regression scenarios, automatic configuration creation, and the complete `PreToolUse` / `PostToolUse` cycle through the installed console scripts.

## What happens on failure

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

Ruff violations, quality regressions, and SyntaxError while parsing changed source consume an attempt. A parsing error preserves the file name, line, column, and message. If the old snapshot is syntactically invalid, the previous quality metrics are considered unavailable; the corrected file is checked against the active limits. This makes it possible to fix a SyntaxError with the remaining attempts.

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
