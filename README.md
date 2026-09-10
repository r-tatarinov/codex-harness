# Codex Harness

Локальный Harness для Codex, который добавляет детерминированные проверки качества кода поверх работы агента.

Основная идея — не полагаться только на правила в промптах, skills или инструкциях модели.

Codex может сгенерировать рабочий код, который при этом постепенно становится сложнее: разрастаются методы, увеличивается вложенность, появляется лишнее ветвление, нарушаются правила линтера.

Harness добавляет отдельный технический слой, который проверяет изменения после действий агента и возвращает проблему обратно в Codex.

## Как это работает

Сейчас Harness подключается к Codex через два lifecycle hook:

- `PreToolUse` — выполняется до изменения кода;
- `PostToolUse` — выполняется после изменения кода.

Текущий flow:

```text
Codex
  |
  | apply_patch
  v
PreToolUse
  |
  | сохраняется состояние Python-файлов до изменения
  v
apply_patch
  |
  v
PostToolUse
  |
  +-- Quality rules
  |     +-- длина функции (flake8-functions CFQ001)
  |     +-- количество statements (Ruff PLR0915)
  |     +-- вложенность (Ruff PLR1702)
  |     +-- количество ветвлений (Ruff PLR0912)
  |     +-- сложность функции (Ruff C901)
  |
  +-- остальные правила Ruff из настроек целевого проекта
  |
  v
сравнение состояния ДО / ПОСЛЕ
  |
  +-- ухудшений нет -> продолжаем
  |
  +-- появился новый плохой код -> Codex получает ошибку
```

## Почему проверяется именно регрессия

Harness не заставляет агента исправлять весь старый технический долг проекта.

Например, если до изменения уже существовал метод с 63 statements:

```text
до:    63 statements
после: 63 statements
```

это не считается новой ошибкой агента.

Если Codex ухудшил существующий код:

```text
до:    63 statements
после: 70 statements
```

Harness зафиксирует регрессию.

`CFQ001` и метрики Ruff (`C901`, `PLR0912`, `PLR0915`, `PLR1702`) сравниваются численно по правилу и полному имени функции. Уменьшение превышения, например с 82 до 81 строки при лимите 80, допускается. Перенос функции на другие строки не считается регрессией.

Остальные диагностики Ruff сравниваются по коду, тексту сообщения и количеству повторений.

Если новый метод сразу нарушает ограничения — это также считается регрессией.

Таким образом:

```text
старый технический долг != ошибка Codex

новый технический долг = ошибка

ухудшение существующего кода = ошибка
```

## Текущие проверки

### Длина функции

По умолчанию:

```toml
max_lines = 80
```

Физическую длину вычисляет plugin [`flake8-functions`](https://github.com/best-doctor/flake8-functions) по правилу `CFQ001`. 80 строк разрешены, 81 строка считается нарушением. Harness не считает строки самостоятельно: он запускает Flake8, получает измерение из `CFQ001` и использует AST только для полного имени функции.

Plugin считает диапазон от первого выражения тела после необязательного docstring до последнего AST-узла функции. Заголовок, декораторы и отдельный docstring не входят; пустые строки и комментарии внутри диапазона влияют на длину. Настройки Flake8 целевого проекта и `noqa` не могут отключить глобальную проверку Harness.

Пример:

```text
CFQ001 PaymentService.process: Function process has length 81 that exceeds max allowed length 80
```

### Количество statements

По умолчанию:

```toml
max_statements = 50
```

Эту независимую метрику продолжает вычислять Ruff `PLR0915`. Пустые строки и комментарии не являются statements, поэтому `CFQ001` и `PLR0915` контролируют разные свойства функции.

### Вложенность

По умолчанию:

```toml
max_nested_blocks = 4
```

Harness отслеживает слишком глубокую управляющую структуру.

Например:

```python
if condition:
    for item in items:
        if other_condition:
            try:
                if something:
                    ...
```

Такой код становится сложнее читать, тестировать и изменять.

Глубину вычисляет Ruff `PLR1702`. Принимается семантика Ruff: сам `match` не добавляет уровень, а блоки во вложенных функциях могут влиять на оценку внешней функции. Для правила включён preview только lint; preview formatter выключен.

PLR1702 может сообщать о нескольких блоках внутри функции. Harness связывает каждую диагностику с самой внутренней функцией, содержащей начало указанного блока, и сравнивает максимальное значение по полному имени функции. При одинаковой глубине выбирается первый блок по расположению. Например, переход с глубины 6 на 5 допускается, с 5 на 6 блокируется; перестановка блоков с сохранением максимума допускается.

### Количество ветвлений

По умолчанию:

```toml
max_branches = 12
```

Метрику вычисляет Ruff `PLR0912`. Учитываются управляющие конструкции вроде:

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

Это ограничение объёма управляющей логики. Например, Ruff считает `if/else` двумя ветвями. Значение `max_branches` относится к этой метрике.

### Сложность функции

По умолчанию:

```toml
max_complexity = 10
```

Для расчёта используется Ruff `C901` (McCabe).

Правило ограничивает структурную сложность функций, методов и вложенных функций. `and/or`, условные выражения и comprehension не повышают C901. Например, `return a and b and c` даёт C901 = 1. C901 также учитывает вложенные определения при оценке внешней функции; вложенные функции диагностируются и отдельно.

Описание правил: [C901](https://docs.astral.sh/ruff/rules/complex-structure/), [PLR0912](https://docs.astral.sh/ruff/rules/too-many-branches/), [PLR0915](https://docs.astral.sh/ruff/rules/too-many-statements/), [PLR1702](https://docs.astral.sh/ruff/rules/too-many-nested-blocks/).

### Ruff

Ruff запускается после изменения Python-кода в двух проходах для исходников до и после изменения:

- Глобальные метрики `C901`, `PLR0912`, `PLR0915` и `PLR1702`: изолированный запуск с лимитами из `~/.codex/harness/config/quality.toml` и preview lint. Настройки целевого проекта и `noqa` не отключают эти ограничения.
- Остальные правила: обычный поиск конфигурации Ruff в целевом проекте. Метрики исключаются из сравнения этого прохода, чтобы не дублировать сообщения и не блокировать улучшение числовых значений.

Лимиты метрик целевого проекта также не заменяют лимиты Harness. Ручной запуск обычного Ruff в целевом проекте продолжает использовать его собственные настройки.

Он работает по тому же принципу сравнения состояния до/после.

Если ошибка уже существовала:

```text
до:    F401
после: F401
```

она не блокирует работу.

Если Codex добавил новую ошибку:

```text
до:    clean
после: F401
```

Harness возвращает её агенту.

## Структура проекта

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

После установки исполняемый код берётся из Python package и не зависит от clone. Пользовательские данные находятся отдельно:

```text
~/.codex/harness/
├── config/quality.toml
└── state/retry/<scope_hash>/
```

Отсутствующий `quality.toml` создаётся автоматически из встроенного шаблона. Существующий файл не перезаписывается; отсутствующие в нём параметры получают текущие значения по умолчанию.

### Ответственность модулей checks

Ruff вычисляет C901 (complexity), PLR0912 (branches), PLR0915 (statements), PLR1702 (nesting) и проверяет PLC0415 (imports outside top level). В Harness нет параллельных реализаций этих правил. Четыре числовые метрики применяются с лимитами Harness; PLC0415, как и остальные обычные правила, выполняется в проходе с конфигурацией целевого проекта.

| Модуль | Ответственность |
| --- | --- |
| `python_flake8/` | Запускает `python -m flake8` из окружения Harness, требует установленный `flake8-functions` и строго разбирает только `CFQ001`. |
| `function_length/` | Проверяет измерение plugin и связывает диагностику с полным именем функции; собственного подсчёта строк нет. |
| `python_ruff/` | Запускает `python -m ruff`, проверяет JSON и нормализует диагностики. |
| `ruff_metrics/` | Читает глобальные лимиты, строит неизменённые Ruff options и нормализует числовые метрики. |
| `ruff_regression.py` | Чтение снимков и сравнение обычных Ruff-диагностик по коду, сообщению и количеству повторений; исключение метрик, сравниваемых численно. |
| `finding.py` | Общая числовая диагностика для CFQ001 и метрик Ruff. |
| `comparison.py` | Числовая regression-policy: новая диагностика или рост значения по паре `(rule, symbol)`. |
| `regression.py` | Применение числовой regression-policy к состоянию файлов до/после; восстановление после синтаксически некорректного baseline. |
| `symbols.py` | Полные имена функций, методов и вложенных функций для устойчивого сравнения при переносе строк. |
| `code_quality/` | Создаёт и загружает user config, валидирует лимиты, запускает общий анализ и формирует CLI-вывод. |

Несколько диагностик PLR1702 для одной функции сводятся к максимальному значению, уже вычисленному Ruff. Это часть regression-policy: она позволяет сравнивать глубину до/после, не вычисляя вложенность повторно. Числовое сравнение и сравнение обычных диагностик разделены, поскольку у них разные ключи и семантика: улучшение превышенной метрики допускается, а повторения обычных нарушений учитываются по количеству.

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

После установки проверить toolchain:

```bash
python3 -m flake8 --version
python3 -m ruff --version
```

Проверенная комбинация — Flake8 7.3.0, flake8-functions 0.1.0 и Ruff 0.16.6. Совместимые диапазоны записаны в `pyproject.toml`. Harness запускает все инструменты через тот же Python, в который установлен пакет.

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

## Настройка правил

Все runtime-лимиты находятся в:

```text
~/.codex/harness/config/quality.toml
```

При отсутствии файла первый hook создаёт его автоматически. Текущие defaults:

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

Чтобы изменить лимит `CFQ001`, отредактировать:

```toml
[python.functions]
max_lines = 120
```

Все значения должны быть целыми числами `>= 1`. Существующий файл не переписывается при обновлении Harness; новые отсутствующие ключи используют встроенные defaults. Архитектурные проверки и проверки зависимостей между слоями не изменяются.

## Ручная проверка файла

Quality rules можно запускать независимо от Codex:

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

- CFQ001 PaymentService.process: Function process has length 81 that exceeds max allowed length 80
- PLR0915 PaymentService.process: Too many statements (63 > 50)
- C901 PaymentService.process: `process` is too complex (18 > 10)
```

Ruff можно проверить отдельно:

```bash
codex-harness-ruff path/to/file.py
```

Эта команда использует настройки целевого проекта. Для всех глобальных ограничений Harness, включая `CFQ001` и метрики Ruff, используйте `codex-harness-check`.

## Проверка самого Harness

Из корня репозитория:

```bash
ruff check .
ruff format --check .
python3 -m unittest discover -v
```

Тесты проверяют границу 80/81, числовые regression-сценарии, автоматическое создание конфигурации и полный цикл `PreToolUse` / `PostToolUse` через установленные console scripts.

## Что происходит при ошибке

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

Нарушения Ruff, quality-регрессии и SyntaxError при parsing изменённого source расходуют попытку. Ошибка parsing сохраняет имя файла, строку, колонку и сообщение. Если старый снимок синтаксически некорректен, прежние quality metrics считаются недоступными; исправленный файл проверяется по действующим лимитам. Это позволяет исправить SyntaxError в оставшиеся попытки.

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

