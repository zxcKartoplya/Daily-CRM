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
├── conftest.py              # фикстуры: тестовая БД, клиент, пользователи
├── test_security.py         # unit-тесты: хэши паролей, JWT-токены
├── test_auth.py             # /api/auth/login, /me, /bootstrap-admin
├── test_tasks.py            # /api/admin/tasks — CRUD, проверка ролей
└── test_daily_reports.py    # /api/employee/daily-reports — CRUD
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
