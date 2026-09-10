[English](README.md) | **Русский**

# Codex Harness

Codex Harness — локальная система контроля изменений вокруг Codex. Она фиксирует состояние до редактирования, анализирует результат, сравнивает два набора findings и разрешает или блокирует workflow по детерминированной policy.

Правила в промптах, skills и инструкциях модели продолжают направлять Codex, но не являются границей принудительного контроля. Эту границу задаёт Harness: lifecycle-интеграция, baseline, оркестрация analyzers, решения о регрессии, лимиты повторных попыток и — через отдельные checkers — архитектурные правила, которые можно применять независимо от модели.

Ruff и Flake8 — внешние analyzers, подключённые к Harness. Они возвращают диагностики и метрики, но не определяют архитектуру Harness и не решают, разрешить ли изменение.

## Overview и lifecycle

Контрольный путь выглядит так:

```text
Codex → Hooks → Harness → Analyzers → Findings → Regression Policy → Allow / Block
```

Текущая интеграция использует два lifecycle hooks Codex вокруг `apply_patch`:

- `PreToolUse` определяет execution scope, проверяет retry budget и сохраняет baseline затрагиваемых Python-файлов до изменения;
- `PostToolUse` анализирует baseline и получившийся source, нормализует результаты analyzers в findings и применяет regression policy.

```text
Codex запрашивает apply_patch
          |
          v
PreToolUse hook
  +-- retry limit исчерпан? -------------------------> block до изменения
  +-- сохранить baseline ДО
          |
          v
apply_patch изменяет файлы
          |
          v
PostToolUse hook
  +-- запустить подключённые analyzers для ДО и ПОСЛЕ
  +-- нормализовать метрики и диагностики в findings
  +-- применить активные checker- и regression-policy
          |
          v
Regression comparison
  +-- новых или ухудшившихся findings нет -----------> allow
  +-- есть регрессия --------------------------------> block и отчёт в Codex
                                                         |
                                                         +-- Codex может исправить
                                                         +-- retry limit остановит новые patches
```

Сейчас реализованы правила качества Python. Та же граница checkers предназначена для архитектурных правил и правил зависимостей без привязки lifecycle-контроля к конкретному analyzer. Проверки OOP и зависимостей между слоями приложения перечислены в roadmap и пока не реализованы.

## Regression policy

Harness оценивает изменение Codex, а не весь накопленный технический долг целевого проекта. Существующие findings входят в baseline и сами по себе не блокируют несвязанное изменение.

```text
старый технический долг != ошибка Codex
новый технический долг  = регрессия
ухудшение старого кода   = регрессия
```

Например, неизменившаяся функция с 63 statements допускается, а рост с 63 до 70 считается регрессией. Новая функция, которая сразу превышает лимит, также считается регрессией.

Числовые метрики (`CFQ001`, `C901`, `PLR0912`, `PLR0915` и `PLR1702`) сравниваются по правилу и полному имени функции. Новое нарушение или рост значения блокируется. Уменьшение существующего превышения, например с 82 до 81 строки при лимите 80, допускается. Перенос функции на другие строки не создаёт регрессию.

Обычные диагностики analyzers сравниваются по коду, тексту сообщения и количеству повторений. Существующий `F401` остаётся частью baseline; дополнительный `F401` считается регрессией. Синтаксические ошибки в изменённом source считаются code failure. Infrastructure failure закрывает проход, но не расходует retry budget исправления кода.

## Tools, analyzers и findings

Harness определяет, какие измерения обязательны и как сравнивать их findings. Значения вычисляют внешние analyzers:

| Метрика | Правило | Analyzer | Лимит по умолчанию |
| --- | --- | --- | ---: |
| Физическая длина функции | `CFQ001` | Flake8 + `flake8-functions` | `max_lines = 80` |
| Сложность функции | `C901` | Ruff | `max_complexity = 10` |
| Ветвления | `PLR0912` | Ruff | `max_branches = 12` |
| Statements | `PLR0915` | Ruff | `max_statements = 50` |
| Вложенные блоки | `PLR1702` | Ruff | `max_nested_blocks = 4` |

Эти правила измеряют разные свойства. В частности, физические строки и statements независимы: пустые строки и комментарии могут влиять на `CFQ001`, но не являются statements для `PLR0915`. Семантика правил остаётся семантикой analyzer; Harness не содержит их параллельных реализаций.

Flake8 запускается в изолированном проходе Harness для `CFQ001`. Plugin `flake8-functions` возвращает измеренную длину, а Harness связывает её с полным именем функции. Конфигурация Flake8 целевого проекта и `noqa` не отключают это глобальное ограничение.

Ruff возвращает остальные четыре числовые метрики в изолированном проходе с лимитами из `~/.codex/harness/config/quality.toml`; для этого прохода включён lint preview. Второй проход Ruff находит обычную конфигурацию целевого проекта и возвращает остальные включённые правила, например `F401` или `PLC0415`. Метрики Harness исключены из второго сравнения, чтобы не дублировать findings. Лимиты метрик целевого проекта не заменяют лимиты Harness, а обычный ручной запуск Ruff продолжает использовать настройки проекта.

Ruff, Flake8, Pylint, Black и MyPy реализуют единый интерфейс analyzer. Registry выбирает только tools с `enabled = true`. Adapters отвечают за запуск процессов и разбор tool-specific output; orchestrator и lifecycle hooks работают только с нормализованными findings. Поэтому новый analyzer можно добавить без изменения hooks, а реализации внешних правил остаются в исходных tools.

Диагностики Pylint и MyPy используют ту же regression-policy по количеству вхождений, что и обычные диагностики Ruff. Black работает только в режиме проверки форматирования и никогда не изменяет source: уже неформатированный файл остаётся baseline, а новая formatting regression блокируется.

Ссылки на правила: [`CFQ001`](https://github.com/best-doctor/flake8-functions), [`C901`](https://docs.astral.sh/ruff/rules/complex-structure/), [`PLR0912`](https://docs.astral.sh/ruff/rules/too-many-branches/), [`PLR0915`](https://docs.astral.sh/ruff/rules/too-many-statements/), [`PLR1702`](https://docs.astral.sh/ruff/rules/too-many-nested-blocks/).

## Архитектура Harness и структура проекта

```text
codex-harness/
├── hooks/                   # lifecycle-контроль, baseline, scope и retry state
├── checks/                  # adapters, findings и regression policy
│   ├── config/              # schema, paths, loading, validation и migration
│   ├── code_quality/        # общий CLI и legacy public imports
│   ├── analyzers/           # общий интерфейс, catalog, registry и policy
│   │   ├── ruff/            # adapter, runner, parsing, schema и configuration
│   │   ├── flake8/          # adapter, runner, parsing, schema и configuration
│   │   ├── pylint/          # adapter, runner, parsing и configuration
│   │   ├── black/           # adapter, check-only runner и configuration
│   │   └── mypy/            # adapter, runner, parsing и configuration
│   ├── function_length/     # нормализация finding CFQ001
│   ├── python_flake8/       # compatibility re-exports прежнего public API
│   ├── python_ruff/         # compatibility re-exports и Ruff console entry point
│   └── ruff_metrics/        # нормализация числовых findings Ruff
├── src/codex_harness/       # package metadata и встроенные defaults
├── tests/                   # тесты policy, adapters, configuration и hooks
└── pyproject.toml
```

После установки исполняемый код берётся из Python package и не зависит от clone. Пользовательские данные находятся отдельно:

```text
~/.codex/harness/
├── config/quality.toml
└── state/retry/<scope_hash>/
```

Отсутствующий `quality.toml` создаётся автоматически из встроенного шаблона. Legacy-конфигурация `[python.*]` атомарно мигрирует в версионированную схему `[tools.*]`, а исходник сохраняется как `quality.toml.v0.bak`. Версионированные файлы не переписываются; отсутствующие параметры получают текущие defaults.

### Ответственность внутри `checks/`

`checks/` — граница policy и analyzers в Harness. Она преобразует tool-specific output в стабильные findings и сравнивает их, не перенося специфику конкретных tools в lifecycle hooks.

| Модуль | Ответственность |
| --- | --- |
| `config/` | Разделяет schema конфигурации, filesystem paths, встроенные defaults, loading, validation, serialization и legacy migration. `config/__init__.py` служит стабильным API конфигурации. |
| `code_quality/` | Предоставляет общий CLI и сохраняет сложившиеся импорты quality checks. |
| `analyzers/` | Определяет нормализованные findings, общее regression-сравнение, catalog конфигураций, runtime registry adapters и orchestration. |
| `analyzers/<tool>/` | Содержит schema конфигурации конкретного tool, subprocess runner, parser output, локальную schema диагностик при необходимости и adapter Harness. Стабильный API каждого пакета доступен через `__init__.py`. |
| `finding.py`, `symbols.py` | Задают нормализованные числовые findings и стабильные идентификаторы symbols при переносе строк. |
| `comparison.py`, `regression.py` | Применяют числовую before/after policy, включая восстановление после синтаксически некорректного baseline. |
| `ruff_regression.py` | Сравнивает обычные диагностики из конфигурации проекта по коду, сообщению и количеству повторений. |
| `python_flake8/`, `python_ruff/` | Сохраняют прежние public imports через re-export соответствующих analyzer packages и не содержат реализацию analyzers. |
| `function_length/`, `ruff_metrics/` | Адаптируют измерения analyzers к общей модели числовой регрессии. |

Числовые findings и обычные диагностики сравниваются отдельно, потому что их regression semantics различаются: превышенная числовая метрика может улучшиться, не достигнув лимита, а обычные нарушения отслеживаются по количеству повторений. Analyzer-specific normalization обрабатывает детали вроде сведения нескольких отчётов `PLR1702` для одной функции к максимальному значению, уже вычисленному Ruff.

Все импорты находятся в namespace `codex_harness`. Для ручного запуска и lifecycle hooks используются установленные console scripts; старые файловые launchers не поддерживаются.

## Требования

Рекомендуется:

```text
Python 3.12+
Codex CLI с поддержкой lifecycle hooks
```

Проверить Python:

```bash
python3 --version
```

`pip install .` устанавливает полный analyzer toolchain. Отдельно устанавливать линтеры не требуется. Посмотреть установленные версии можно командами:

```bash
python3 -m flake8 --version
python3 -m ruff --version
python3 -m pylint --version
python3 -m black --version
python3 -m mypy --version
```

Совместимые диапазоны версий, включая `flake8-functions`, записаны как прямые зависимости пакета в `pyproject.toml`. Harness запускает все tools через тот же Python, в который установлен пакет.

## Установка

Клонировать исходники в любой временный или постоянный каталог и установить пакет:

```bash
git clone https://github.com/r-tatarinov/codex-harness.git
cd codex-harness
python3 -m pip install .
```

После установки clone не нужен для выполнения Harness. Найти абсолютные пути console scripts:

```bash
command -v codex-harness-pre-tool
command -v codex-harness-post-tool
```

## Подключение к Codex

Создать глобальный файл:

```text
~/.codex/hooks.json
```

Пример:

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

Пути в примере необходимо заменить результатами `command -v`. Старые команды через `hooks/pre_tool.py` и `hooks/post_tool.py` не поддерживаются.

После изменения `hooks.json` необходимо полностью перезапустить Codex.

При первом запуске Codex покажет:

```text
Hooks need review
```

Необходимо проверить hooks и разрешить их выполнение.

После запуска состояние можно посмотреть командой:

```text
/hooks
```

Должно быть активно:

```text
PreToolUse     1 installed / 1 active
PostToolUse    1 installed / 1 active
```

## Настройка tools и правил

Все переключатели tools, правила, лимиты и поддерживаемые нативные options находятся в:

```text
~/.codex/harness/config/quality.toml
```

При отсутствии файла первый hook создаёт его автоматически. Основная часть default-конфигурации:

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

Для включения или отключения tool измените его `enabled`. Чтобы изменить лимит `CFQ001`, отредактируйте:

```toml
[tools.flake8.limits]
CFQ001 = 120
```

При `use_project_config = true` analyzer находит обычный конфиг проекта, после чего `rules`, `limits` и `options` Harness имеют приоритет. При `false` adapter использует изолированную конфигурацию tool. Неизвестные tools, правила, plugins, options, неверные типы и некорректные положительные лимиты дают fail-closed ошибку с путём параметра. Harness не реализует внешние правила повторно.

Ruff и Flake8 принимают selectors `select`/`extend_select`/`ignore`, Pylint — `enable`/`disable`, MyPy — `enable_error_code`/`disable_error_code`. Поддерживаемые `options` охватывают Python targets, line/complexity limits, режимы formatter и основные MyPy strictness switches; служебные process/output/write options остаются под контролем Harness.

## Ручная проверка файла

Общий анализ Harness можно запускать независимо от Codex:

```bash
codex-harness-check path/to/file.py
```

Например:

```bash
codex-harness-check \
    project/services/payment.py
```

Если ограничения нарушены:

```text
CODE QUALITY CHECK FAILED

- payment.py:10:1: [flake8] CFQ001 Function process has length 81 that exceeds max allowed length 80
- payment.py:10:1: [ruff] PLR0915 Too many statements (63 > 50)
- payment.py:10:1: [ruff] C901 `process` is too complex (18 > 10)
```

Adapter analyzer Ruff также можно запустить отдельно:

```bash
codex-harness-ruff path/to/file.py
```

Эта команда использует настройки целевого проекта. Для всех глобальных ограничений Harness, включая `CFQ001` и метрики Ruff, используйте `codex-harness-check`.

## Проверка самого Harness

Из корня репозитория:

```bash
codex-harness-check checks hooks tests
ruff format --check .
python3 -m unittest discover -v
```

Тесты проверяют границу 80/81, числовые regression-сценарии, автоматическое создание конфигурации и полный цикл `PreToolUse` / `PostToolUse` через установленные console scripts.

## Политика block и retry

`PostToolUse` не откатывает изменение автоматически.

Он возвращает Codex информацию о найденной регрессии.

Например:

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

После этого агент получает конкретную диагностику через `reason` и `additionalContext` и может исправить код следующей итерацией, пока бюджет текущего turn не исчерпан.

### Лимит последовательных verification FAIL

`[verification] max_attempts = 3` означает максимум три последовательных неуспешных correction attempts внутри одного пользовательского turn. Если параметр отсутствует, используется `3`. Допускаются только целые числа `>= 1`; boolean, строки и дробные значения недопустимы. Параметр читается существующим TOML loader.

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

После последнего FAIL и при запрете следующего `apply_patch` агент получает:

```text
Verification failed.
Verification attempt 3/3
Retry limit reached for the current turn.

Last diagnostics:
<последняя фактическая диагностика проверки>
```

`PreToolUse` возвращает `permissionDecision: "deny"` до изменения файлов, не создаёт снимок и не увеличивает attempts. Значение `4/3` не возникает. Запрет распространяется на любой следующий `apply_patch` в том же scope, включая непроверяемые файлы.

Один attempt расходуется на один фактически изменяющий Python-код patch с общим результатом FAIL, независимо от количества файлов, правил или диагностик. Смена причины отказа, например PLC0415 → F401, не начинает отдельный бюджет.

Релевантный PASS немедленно удаляет `attempts.json` текущего scope: `FAIL → FAIL → PASS → FAIL` даёт `1/3 → 2/3 → reset → 1/3`. PASS сохраняет существующую семантику отсутствия новых регрессий относительно снимка перед патчем, а не требует устранения всего старого технического долга. Изменение только README или другого непроверяемого файла, no-op Python patch, повторный hook и обычные действия агента не расходуют и не сбрасывают бюджет. Проверки запускаются только при изменении содержимого или существования отслеживаемого Python-файла.

### Scope и состояние

Scope — стабильный SHA-256 от JSON-массива `[session_identifier, resolved_cwd, turn_id]`. Используется `session_id` из payload; при отсутствии — `CODEX_THREAD_ID`, затем `CODEX_SESSION_ID`. Для turn требуется непустой корректный `turn_id` из payload: session-wide и глобального fallback нет. Новый turn получает другой каталог, не удаляя состояние предыдущего. Разные session и cwd также изолированы.

`state/retry/<scope_hash>/attempts.json` содержит только `consecutive_failed_attempts` и `last_failure`. Снимки находятся в том же каталоге; их имена получаются из `tool_use_id`, который не входит в retry scope. Старые снимки непосредственно в `state/` новый механизм не использует.

Операции защищены файловой блокировкой scope; JSON записывается через временный файл и атомарный replace. Post-hook забирает снимок переименованием перед verification и удаляет его перед сохранением результата. Повторная или конкурентная доставка того же PostToolUse не выполняет проверку заново и не увеличивает счётчик. При прерывании процесса может остаться файл `.processing`; он не обрабатывается повторно.

Состояние прошлых turns — transient runtime state: оно не участвует в новых execution scopes. Автоматический garbage collector не добавлен.

### Code failure и infrastructure failure

Нарушения кода, сообщённые analyzers, quality-регрессии и SyntaxError при parsing изменённого source расходуют попытку. Ошибка parsing сохраняет имя файла, строку, колонку и сообщение. Если старый снимок синтаксически некорректен, прежние quality metrics считаются недоступными; исправленный файл проверяется по действующим лимитам. Это позволяет исправить SyntaxError в оставшиеся попытки.

Невозможность запустить checker или plugin, timeout (10 секунд на один процесс Ruff или Flake8), filesystem/permission error, неверная конфигурация, повреждённый retry state, malformed checker response, внутреннее исключение или неопределимый scope блокируют операцию с исходной инфраструктурной диагностикой, сохраняя attempts и `last_failure`. Они не считаются PASS. Тип ошибки определяется структурно; произвольный SyntaxError внутри Harness не считается ошибкой исходника агента.

Известное ограничение адаптера: Ruff может вернуть `code: null` для синтаксической ошибки старого снимка. Текущий parser ожидает строковый код и в таком случае возвращает infrastructure failure даже после исправления source. Это существовавшее поведение сохранено при очистке модулей; восстановление после SyntaxError зависит от формата ответа установленного Ruff.

### Подагенты

Встроенные схемы установленного Codex предусматривают `agent_id`/`agent_type`, но не предоставляют root user turn identifier в tool hooks. При наличии этой явной agent metadata Harness блокирует патч как infrastructure failure без отдельного retry budget. Равенство parent/subagent `turn_id` не предполагается; связь не выводится из PID, времени или transcript.

Ограничение: **shared retry budget for subagents is not supported without a reliable root turn identifier**. Проверка встроенной схемы не означает, что выполнен живой end-to-end тест подагента.

Retry формируется последовательностью tool calls самого агента. Harness не запускает LLM, retry-agent, собственный agent loop или final verification gate.

## Текущие ограничения

Сейчас Harness ориентирован в первую очередь на Python.

Проверки подключены к:

```text
apply_patch
```

Поэтому текущий quality flow рассчитан на изменения, которые Codex выполняет через этот инструмент.

Изменения через произвольные shell-команды пока не входят в этот же механизм сравнения.

Также пока не реализованы:

- архитектурные правила ООП;
- правила зависимостей между слоями приложения;
- JavaScript / TypeScript / Vue проверки;
- финальный `Stop` quality gate;
- автоматический запуск тестов и проверок всего проекта перед завершением задачи;
- semantic review сложных архитектурных изменений.

## План развития

Следующие направления:

```text
ООП / architecture rules
        |
        +-- новые функции вне классов в class-oriented модулях
        +-- нарушение существующей структуры проекта
        +-- неправильные зависимости между слоями

Stop hook
        |
        +-- финальная проверка перед завершением задачи
        +-- tests
        +-- typing
        +-- project-wide checks

Другие языки
        |
        +-- ESLint
        +-- TypeScript
        +-- Vue
        +-- HTML
```

Основная цель проекта — вынести контроль качества кода из вероятностного поведения модели в отдельный детерминированный слой вокруг агента.

## Поддержка документации

При изменении документации обновляйте `README.md` и `README.ru.md` синхронно, сохраняя одинаковые по смыслу содержание и структуру обеих языковых версий.

