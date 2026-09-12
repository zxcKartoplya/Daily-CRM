# Daily CRM Backend

## Запуск приложения

```bash
source .venv/bin/activate
uvicorn app.main:app --reload
```

## Тесты

### Установка зависимостей для тестов

```bash
pip install -r requirements-test.txt
```

### Запустить все тесты

```bash
pytest
```

### Запустить с подробным выводом

```bash
pytest -v
```

### Запустить конкретный файл или тест

```bash
pytest tests/test_auth.py
pytest tests/test_auth.py::TestLogin::test_login_success_returns_token_and_user
```

### Запустить с отчётом покрытия

```bash
pytest --cov=app --cov-report=term-missing
```

## Структура тестов

```
tests/
├── conftest.py                    # фикстуры: тестовая БД, клиент, пользователи
├── test_security.py               # unit-тесты: хэши паролей, JWT-токены
├── test_auth.py                   # /api/auth/login, /me, /bootstrap-admin
├── test_tasks.py                  # /api/admin/tasks — CRUD, проверка ролей
├── test_daily_entries.py          # /api/employee/daily — день, линии работ, правила
├── test_schedule.py               # график работы: наследование от профессии, валидация
├── test_employee_statistics.py    # /api/employee/statistics — регулярность, линии
└── test_department_dailies.py     # /api/admin/departments/{id}/dailies
```

Тесты используют SQLite in-memory — PostgreSQL для запуска не нужен.

## Миграции

```bash
alembic upgrade head
```

## Docker

```bash
# Собрать и запустить
docker compose up -d

# Запустить тесты внутри Docker
docker build --target tester -t daily-backend:test .
docker run --rm daily-backend:test
```

## Дейлики

Запись дня адресуется датой, а не id: пара `(user_id, date)` уникальна, поэтому
отдельный шаг «создать запись» не нужен.

```
GET    /api/employee/daily/{date}           день: запись, открытые линии, пропущенные дни
PUT    /api/employee/daily/{date}           upsert: day_type и полный состав пунктов
POST   /api/employee/daily/{date}/submit    отправить запись
PUT    /api/employee/daily-bulk             несколько дат разом: только day_type = off
GET    /api/employee/daily?date_from&date_to  история записей
GET    /api/employee/daily-chains/{chain_id}  все пункты линии работы по возрастанию даты
GET    /api/admin/departments/{id}/dailies?date_from&date_to  сводка по департаменту
```

Пункт с `chain_id` продолжает линию работы, без него — начинает новую. `PUT`
заменяет состав дня целиком. Нерабочий день — это `{"day_type": "off", "items": []}`.

Правила, которые держит бэк:

- один пункт на линию в день, одна запись на дату
- черновик правится всегда, отправленная запись — только в день, к которому относится
- заполнение задним числом ограничено окном `DAILY_BACKFILL_WINDOW_DAYS` (по умолчанию 7 дней)
- `open_chains` считаются по пунктам строго раньше запрошенной даты, поэтому
  закрытая сегодня линия из списка не исчезает

`DayView` отдаёт `editable_from` — раннюю дату, доступную для правки, чтобы клиент
не пересчитывал окно у себя. Каждая открытая линия несёт `history` — точки
`{date, status}` по возрастанию даты, поэтому рисовать линию можно без запроса
за `ChainHistory`.

`PUT /api/employee/daily-bulk` закрывает пропущенные дни одним запросом: принимает
`{"dates": [...], "day_type": "off"}`, ставит записи сразу отправленными и работает
по принципу «всё или ничего» — если хоть одна дата вне окна или закрыта отправкой,
не пишется ничего. Пункты массово не проставляются: один текст, размноженный по
дням, создал бы мусорные линии.

## Контракт для клиентов

Схема OpenAPI лежит в `openapi.json` и коммитится вместе с кодом — из неё фронты
генерируют типы. После любого изменения контракта:

```bash
python scripts/dump_openapi.py
```

`tests/test_openapi_contract.py` падает, если закоммиченный файл разошёлся с
приложением, поэтому расхождение видно в CI и в диффе PR, а не на фронте.

## График работы

`schedule_type` и `work_days` (дни недели, 1 — понедельник) живут на профессии и
на работнике. У работника это копия графика профессии, снятая при создании, —
дальше она правится независимо. `schedule_type = none` — без графика (почасовая
занятость): регулярность и пропущенные дни для таких сотрудников не считаются.
