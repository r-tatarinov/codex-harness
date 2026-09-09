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
  |     +-- длина функции
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

Например, если до изменения уже существовал метод длиной 93 строки:

```text
до:    93 строки
после: 93 строки
```

это не считается новой ошибкой агента.

Если Codex ухудшил существующий код:

```text
до:    93 строки
после: 110 строк
```

Harness зафиксирует регрессию.

Длина функции и метрики Ruff (`C901`, `PLR0912`, `PLR1702`) сравниваются численно по правилу и полному имени функции. Уменьшение превышения, например с 15 до 14 ветвей при лимите 12, допускается. Перенос функции на другие строки не считается регрессией.

Остальные диагностики Ruff сравниваются по коду, тексту сообщения и количеству повторений.

Если новый метод сразу нарушает ограничения — это также считается регрессией.

Таким образом:

```text
старый технический долг != ошибка Codex

новый технический долг = ошибка

ухудшение существующего кода = ошибка
```

## Текущие проверки

### Размер функции

По умолчанию:

```toml
max_lines = 80
```

Если новая функция превышает 80 строк или существующее превышение растёт, Harness возвращает Codex конкретное замечание. Считаются физические строки от `def` / `async def` до конца тела включительно: комментарии, пустые строки и docstring внутри этого диапазона тоже входят в длину. Декораторы не входят.

Пример:

```text
PaymentService.process has 114 lines (maximum 80)
```

### Вложенность

По умолчанию:

```toml
max-nested-blocks = 4
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
max-branches = 12
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

Это ограничение объёма управляющей логики. Например, Ruff считает `if/else` двумя ветвями. Значение `max-branches` относится к этой метрике.

### Сложность функции

По умолчанию:

```toml
max-complexity = 10
```

Для расчёта используется Ruff `C901` (McCabe).

Правило ограничивает структурную сложность функций, методов и вложенных функций. `and/or`, условные выражения и comprehension не повышают C901. Например, `return a and b and c` даёт C901 = 1. C901 также учитывает вложенные определения при оценке внешней функции; вложенные функции диагностируются и отдельно.

Описание правил: [C901](https://docs.astral.sh/ruff/rules/complex-structure/), [PLR0912](https://docs.astral.sh/ruff/rules/too-many-branches/), [PLR1702](https://docs.astral.sh/ruff/rules/too-many-nested-blocks/).

### Ruff

Ruff запускается после изменения Python-кода в двух проходах для исходников до и после изменения:

- Глобальные метрики `C901`, `PLR0912` и `PLR1702`: изолированный запуск с лимитами из `pyproject.toml` Harness и preview lint. Настройки целевого проекта и `noqa` не отключают эти ограничения.
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
├── checks/
│   ├── code_quality/
│   │   ├── __init__.py
│   │   ├── __main__.py
│   │   ├── cli.py
│   │   ├── config.py
│   │   └── service.py
│   ├── code_quality.py       # совместимый CLI-launcher
│   ├── comparison.py
│   ├── finding.py
│   ├── python_ruff/
│   │   ├── __init__.py
│   │   ├── __main__.py
│   │   ├── cli.py
│   │   ├── parsing.py
│   │   ├── runner.py
│   │   └── schema.py
│   ├── python_ruff.py        # совместимый CLI-launcher
│   ├── regression.py
│   ├── ruff_metrics/
│   │   ├── __init__.py
│   │   ├── config.py
│   │   ├── normalization.py
│   │   └── service.py
│   ├── ruff_regression.py
│   ├── rules/
│   │   ├── __init__.py
│   │   └── function_length.py
│   └── symbols.py
│
├── config/
│   └── quality.toml
│
├── hooks/
│   ├── pre_tool.py
│   ├── post_tool.py
│   └── retry_state.py
│
├── state/
│   └── retry/<scope_hash>/ (attempts.json, patch snapshots, scope.lock)
└── pyproject.toml
```

`state/` содержит временные снимки файлов и состояние verification retry; не хранится в Git.

### Ответственность модулей checks

Ruff вычисляет C901 (complexity), PLR0912 (branches), PLR1702 (nesting) и проверяет PLC0415 (imports outside top level). В Harness нет параллельных реализаций этих правил. Три числовые метрики применяются с лимитами Harness; PLC0415, как и остальные обычные правила, выполняется в проходе с конфигурацией целевого проекта.

| Модуль | Ответственность |
| --- | --- |
| `python_ruff/` | `schema.py` содержит `RuffFinding`; `runner.py` запускает Ruff; `parsing.py` проверяет JSON и нормализует диагностики; `cli.py` отвечает за вывод и exit code. Путь к executable `RUFF` принадлежит runner. |
| `ruff_metrics/` | `config.py` хранит `CONFIG_PATH`, `METRIC_SETTINGS`, `METRIC_CODES`, читает лимиты и строит CLI options; `normalization.py` связывает диагностики с функциями, разбирает числовые значения и сводит PLR1702; `service.py` выполняет check flow. AST не вычисляет метрики повторно. |
| `ruff_regression.py` | Чтение снимков и сравнение обычных Ruff-диагностик по коду, сообщению и количеству повторений; исключение метрик, сравниваемых численно. |
| `finding.py` | Общая числовая диагностика для длины функции и метрик Ruff. |
| `comparison.py` | Числовая regression-policy: новая диагностика или рост значения по паре `(rule, symbol)`. |
| `regression.py` | Применение числовой regression-policy к состоянию файлов до/после; восстановление после синтаксически некорректного baseline. |
| `symbols.py` | Полные имена функций, методов и вложенных функций для устойчивого сравнения при переносе строк. |
| `rules/function_length.py` | Единственное custom-правило: физическая длина функции/метода, включая комментарии, пустые строки и docstring. `rules/__init__.py` обозначает пакет правил. |
| `code_quality/` | `config.py` загружает quality TOML и валидирует retry limit; `service.py` содержит parsing исходника, `SourceSyntaxError` и общий анализ; `cli.py` формирует вывод и exit code. |

Несколько диагностик PLR1702 для одной функции сводятся к максимальному значению, уже вычисленному Ruff. Это часть regression-policy: она позволяет сравнивать глубину до/после, не вычисляя вложенность повторно. Числовое сравнение и сравнение обычных диагностик разделены, поскольку у них разные ключи и семантика: улучшение превышенной метрики допускается, а повторения обычных нарушений учитываются по количеству.

Каждый новый package предоставляет публичный API через `__init__.py` с явным `__all__`; бизнес-логики в фасадах нет. Потребители продолжают использовать `from python_ruff import RuffFinding, run_check`, `from ruff_metrics import check, METRIC_CODES` и `from code_quality import analyze_source, load_config, load_max_attempts, SourceSyntaxError`. Внутри packages используются относительные импорты.

`finding.py` остаётся самостоятельной структурой числовой диагностики: отдельный каталог с единственным `schema.py` здесь не добавил бы ответственности. Компактные regression-модули, comparison, symbols и custom-правило также остаются обычными файлами.

Старые команды `python3 checks/code_quality.py ...` и `python3 checks/python_ruff.py ...` сохранены короткими launcher-файлами. Обычный импорт выбирает одноимённый package. Когда `checks/` находится в пути поиска Python, доступны и `python3 -m code_quality ...`, `python3 -m python_ruff ...` через `__main__.py`; они используют тот же CLI.

## Требования

Рекомендуется:

```text
Python 3.12+
Codex CLI с поддержкой lifecycle hooks
Ruff
```

Проверить Python:

```bash
python3 --version
```

Проверить Ruff:

```bash
ruff --version
```

Миграция и тесты проверены с Ruff 0.16.6. Harness использует исполняемый файл `~/.local/bin/ruff`. Числовые значения Ruff сейчас доступны в тексте JSON-диагностики; если его формат изменится, Harness вернёт ошибку анализа, а не пропустит проверку.

## Установка

Клонировать Harness в глобальную директорию Codex:

```bash
mkdir -p ~/.codex
cd ~/.codex

git clone https://github.com/r-tatarinov/codex-harness.git harness
```

Сделать hooks исполняемыми:

```bash
chmod +x ~/.codex/harness/hooks/pre_tool.py
chmod +x ~/.codex/harness/hooks/post_tool.py
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
            "command": "/home/USER/.pyenv/shims/python3 /home/USER/.codex/harness/hooks/pre_tool.py",
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
            "command": "/home/USER/.pyenv/shims/python3 /home/USER/.codex/harness/hooks/post_tool.py",
            "timeout": 30,
            "statusMessage": "Checking code quality regression"
          }
        ]
      }
    ]
  }
}
```

`USER` необходимо заменить на имя пользователя.

Путь до используемого Python можно проверить:

```bash
which python3
```

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

Ограничения длины функции и количества verification attempts находятся в:

```text
config/quality.toml
```

Текущая конфигурация:

```toml
[verification]
max_attempts = 3

[python.functions]
max_lines = 80
```

Архитектурные проверки и проверки зависимостей между слоями пока не реализованы; неиспользуемая настройка `python.architecture.block_unexpected_module_functions` удалена.

Лимиты Ruff находятся в `pyproject.toml` Harness и применяются hook ко всем проверяемым проектам:

```toml
[tool.ruff]
target-version = "py312"

[tool.ruff.lint]
extend-select = ["C901", "PLC0415", "PLR0912", "PLR1702"]
preview = true
explicit-preview-rules = true

[tool.ruff.lint.mccabe]
max-complexity = 10

[tool.ruff.lint.pylint]
max-branches = 12
max-nested-blocks = 4
```

Самописных проверок количества statements, arguments и returns в проекте нет. Их аналоги Ruff (`PLR0915`, `PLR0913`, `PLR0911`) не включаются как новые глобальные ограничения. Количество statements не заменяет длину функции в строках.

`preview` задан в секции `tool.ruff.lint`, а не в общей секции `tool.ruff`. Formatter использует стабильный режим. `explicit-preview-rules` требует явного выбора preview-правил; в общем наборе метрик таким правилом является PLR1702.

### max_lines

Максимальная длина функции или метода.

Например:

```toml
max_lines = 120
```

увеличит допустимый размер функции до 120 строк.

### max-branches

Максимальное количество ветвлений внутри функции.

```toml
max-branches = 12
```

### max-nested-blocks

Максимальная глубина вложенности управляющих конструкций.

```toml
max-nested-blocks = 4
```

### max-complexity

Максимально допустимая сложность функции.

```toml
max-complexity = 10
```

## Ручная проверка файла

Quality rules можно запускать независимо от Codex:

```bash
python3 ~/.codex/harness/checks/code_quality.py path/to/file.py
```

Например:

```bash
python3 ~/.codex/harness/checks/code_quality.py \
    project/services/payment.py
```

Если ограничения нарушены:

```text
CODE QUALITY CHECK FAILED

- PaymentService.process has 110 lines (maximum 80)
- C901 PaymentService.process: `process` is too complex (18 > 10)
```

Ruff можно проверить отдельно:

```bash
python3 ~/.codex/harness/checks/python_ruff.py path/to/file.py
```

Эта команда использует настройки целевого проекта. Для всех глобальных ограничений Harness, включая метрики Ruff, используйте `code_quality.py`.

## Проверка самого Harness

Из корня репозитория:

```bash
ruff check .
ruff format --check .
```

Постоянной директории тестов в репозитории нет. При изменении проверок можно выполнять разовые сценарии на исходниках в памяти и во временных каталогах: границы метрик, числовые регрессии и цикл `PreToolUse` / `PostToolUse`.

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
- PaymentService.process has 110 lines (maximum 80)

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

Невозможность запустить checker, timeout (10 секунд на один процесс Ruff), filesystem/permission error, неверная конфигурация, повреждённый retry state, malformed checker response, внутреннее исключение или неопределимый scope блокируют операцию с исходной инфраструктурной диагностикой, сохраняя attempts и `last_failure`. Они не считаются PASS. Тип ошибки определяется структурно; произвольный SyntaxError внутри Harness не считается ошибкой исходника агента.

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

