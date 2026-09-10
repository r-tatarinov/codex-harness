# Codex Harness Engineering Rules

These instructions apply to the entire repository. Preserve them when extending or refactoring the project.

## Source code

- Do not add comments, docstrings, shebangs, or inline suppression directives to Python source. Express intent through precise names, types, and small components. Put necessary explanations in documentation.
- Preserve operational string literals and external-tool arguments, including options that control how analyzers handle comments in user code.
- Keep type hints on component interfaces and functions. Keep classes and methods focused and reasonably sized.
- Do not introduce utility classes, classes containing only static methods, meaningless wrappers around individual functions, or God Objects. Avoid names such as Utils, Helpers, or Manager without a concrete domain responsibility.

## Module boundaries

- Define data schemas, Protocol contracts, exception classes, implementation classes, and module-level functions in separate modules. The separation applies to definitions, not imports.
- Use dataclass, TypedDict, enum, and type aliases for schemas and value objects. Schema modules may also contain related constants. Validation of a value object's own data and computed properties are allowed; service orchestration and infrastructure lifecycle do not belong in schemas.
- Keep Protocol definitions separate from their implementations. Use Protocol for replaceable component contracts.
- Several related definitions of the same architectural category may share a module. Do not enforce one class per file or create a directory merely to contain one file.
- Use module-level functions for pure local transformations, parsing, normalization, serialization, validation of supplied values, and presentation. Do not turn these functions into methods solely to satisfy module separation.
- CLI entry points and tool-specific internal runner functions are explicit exceptions to the pure-function rule. They may perform their necessary I/O. A runner is an implementation detail of an analyzer adapter, not a parallel checking service.
- Use classes for domain entities, policies, orchestration, lifecycle, persistence, and components with dependencies. Inject service dependencies through constructors; do not add a DI framework or container.
- Keep dependencies directional and imports acyclic. Expose only useful package entry points through explicit exports. Do not add dynamic compatibility exports or wrappers for obsolete internal imports.

## Analyzer architecture

- All external analyzers implement the AnalyzerAdapter contract in checks/analyzers/base.py. Ruff, Flake8, Pylint, Black, and MyPy have the same external analyze interface.
- Each adapter owns its tool's execution, configuration details, parsing, and normalization. Tool-specific diagnostic schemas and pure helpers remain inside the tool package.
- Normalize analyzer output into ToolFinding. Do not restore a separate legacy numeric Finding model or parallel tool-specific quality services.
- AnalyzerOrchestrator owns the configured analyzer set and the common execution process. It receives settings and adapters explicitly and returns analyzer-neutral findings.
- Keep concrete tool imports in adapter packages and composition/catalog/registry modules. Shared regression and snapshot layers must not import Ruff or any other concrete analyzer.
- Validate external-tool output and normalize syntax diagnostics inside the responsible adapter. Infrastructure failures must remain distinguishable from source findings.

## Regression policy

- DefaultRegressionPolicy in checks/regression.py is the sole canonical before/after comparison implementation. Its RegressionPolicy contract lives separately in checks/contracts.py.
- Existing technical debt is allowed; new technical debt is a regression. Reducing existing debt is allowed even when a metric remains above its limit.
- Scope ordinary findings by file, tool, code, and message, and account for occurrence counts. Line movement within a file does not create a regression. Debt in one file or tool cannot offset debt in another.
- Scope metrics by file, tool, code, and qualified symbol. Compare values numerically: a new over-limit metric or an increase is a regression; an equal or lower existing value is allowed.
- Keep analyzer-specific aggregation, such as Ruff nesting normalization, inside the adapter. Do not duplicate regression decisions in adapters, hooks, or CLI code.
- Do not reintroduce independent find_regressions or tool-specific check_snapshot implementations.

## Snapshots, hooks, and persistence

- SnapshotChecker owns before/after verification and coordinates an injected AnalyzerOrchestrator, RegressionPolicy, and SnapshotStore.
- SnapshotStore owns snapshot capture, persistence, changed-file filtering, claiming, and consumption. Keep snapshot schemas separate from pure parsing functions. Deleted files do not introduce new findings and need no analyzer execution.
- Keep PreToolHook and PostToolHook separate from console entry points and pure response formatting. Hooks must not contain analyzer-specific logic.
- RetryStore and RetryScope own turn-scoped retry persistence and locking. Preserve scope identity, retry limits, successful-check reset behavior, and snapshot redelivery handling.
- Consume a claimed snapshot before committing its verification outcome. Infrastructure failures must not advance the retry counter or overwrite the last diagnostics. Replayed PostToolUse events must not count the same snapshot again.
- Keep configuration loading, migration lifecycle, pure mapping transformations, schema validation, and environment policies in their respective components.
- Use AtomicFile for shared atomic persistence. Preserve exclusive default-config creation, legacy backups, versioned user configuration, and cleanup behavior after a committed write.
- Keep fail-closed exception handling at the two hook entry points. The narrowly scoped BLE001 exceptions in pyproject.toml exist for these boundaries; do not broaden them, disable analyzer rules globally, or restore inline suppressions.

## Compatibility and documentation

- Preserve all four console script names and their CLI behavior, output formats, and exit codes.
- Preserve PreToolUse/PostToolUse response formats, snapshot JSON, user configuration, analyzer selection, and quality/regression semantics unless the requested task explicitly changes them.
- Internal imports may change. Migrate all callers and remove superseded implementations instead of retaining a second architecture for compatibility.
- Keep README.md and README.ru.md semantically aligned. Update inaccurate descriptions without filling user documentation with internal implementation details.
- Do not change user configuration or dependencies merely to make repository quality checks pass.

## Verification

- Do not create tests/, add unit or integration tests, restore the deleted test suite, or add test dependencies.
- Verify changes using Ruff, Black in check mode, MyPy with check_untyped_defs, existing Harness CLI/snapshot checks, and relevant CLI smoke scenarios.
- Audit Python source with tokenize and AST when changing source organization. Prefer existing Harness verification capabilities; temporary inspection scripts may be used when no existing check covers the invariant. Do not commit ad-hoc audit scripts solely for repository self-checks.
- Check for cyclic imports, stale internal imports, duplicate regression logic, unused legacy modules, and concrete analyzer dependencies in shared layers.
- For runtime changes, verify existing and new debt, occurrence counts, equal/decreasing/increasing metrics, hook failure responses, snapshot redelivery, and retry limits as relevant.
- For packaging changes, build a wheel from a clean source tree, install it in an isolated environment, and verify imports and console entry points. Do not let stale build artifacts reintroduce removed modules.
- Report the checks actually run and any failures or limitations. Do not claim a check passed unless its result was observed.
