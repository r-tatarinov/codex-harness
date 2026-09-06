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
  |     +-- вложенность
  |     +-- количество ветвлений
  |     +-- сложность функции
  |
  +-- Ruff
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

То же самое работает для сложности, вложенности, ветвлений и Ruff.

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

Если новая или изменённая функция становится больше 80 строк, Harness возвращает Codex конкретное замечание.

Пример:

```text
PaymentService.process has 114 lines (maximum 80)
```

### Вложенность

По умолчанию:

```toml
max_nesting = 4
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

### Количество ветвлений

По умолчанию:

```toml
max_branches = 10
```

Учитываются управляющие конструкции вроде:

```text
if
elif
for
while
except
match / case
```

Если в одной функции начинает накапливаться слишком много разных путей выполнения, Harness предлагает разделить логику.

### Сложность функции

По умолчанию:

```toml
max_complexity = 12
```

Для расчёта используется `radon`.

Это позволяет ловить методы, которые формально могут быть не очень длинными, но имеют слишком большое количество вариантов выполнения.

### Ruff

Ruff запускается после изменения Python-кода.

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
│   ├── rules/
│   │   ├── branches.py
│   │   ├── complexity.py
│   │   ├── function_length.py
│   │   └── nesting.py
│   │
│   ├── code_quality.py
│   ├── comparison.py
│   ├── finding.py
│   ├── python_ruff.py
│   ├── regression.py
│   ├── ruff_regression.py
│   └── symbols.py
│
├── config/
│   └── quality.toml
│
├── hooks/
│   ├── pre_tool.py
│   └── post_tool.py
│
└── state/
    └── runtime snapshots
```

`state/` содержит временные снимки файлов и не хранится в Git.

## Требования

Рекомендуется:

```text
Python 3.12+
Codex CLI с поддержкой lifecycle hooks
Ruff
Radon
```

Проверить Python:

```bash
python3 --version
```

Проверить Ruff:

```bash
ruff --version
```

Установить Radon:

```bash
python3 -m pip install radon
```

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

Все основные ограничения находятся в:

```text
config/quality.toml
```

Текущая конфигурация:

```toml
[python.functions]
max_lines = 80
max_branches = 10
max_nesting = 4
max_complexity = 12

[python.architecture]
block_unexpected_module_functions = true
```

### max_lines

Максимальная длина функции или метода.

Например:

```toml
max_lines = 120
```

увеличит допустимый размер функции до 120 строк.

### max_branches

Максимальное количество ветвлений внутри функции.

```toml
max_branches = 10
```

### max_nesting

Максимальная глубина вложенности управляющих конструкций.

```toml
max_nesting = 4
```

### max_complexity

Максимально допустимая сложность функции.

```toml
max_complexity = 12
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
- PaymentService.process has complexity 18 (maximum 12)
```

Ruff можно проверить отдельно:

```bash
python3 ~/.codex/harness/checks/python_ruff.py path/to/file.py
```

## Что происходит при ошибке

`PostToolUse` не откатывает изменение автоматически.

Он возвращает Codex информацию о найденной регрессии.

Например:

```text
Code quality regression detected.

Fix the following issues before continuing:

Quality rules:
- PaymentService.process has 110 lines (maximum 80)

Ruff:
- F401 `os` imported but unused
```

После этого агент получает информацию о проблеме и может исправить код следующей итерацией.

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
- тесты и проверки всего проекта перед завершением задачи;
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
