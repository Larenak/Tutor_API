# AI Tutor

Исходный код находится в `app`, документация — в `docs`, миграции Alembic — в `app/migrations`.

## Запуск backend

1. Создать виртуальное окружение и установить зависимости: `pip install -e .[dev]`.
2. Скопировать `.env.example` в `.env` и задать секрет JWT.
3. Создать PostgreSQL-базу `ai_tutor` и применить миграции: `alembic upgrade head`.
4. Запустить API: `uvicorn app.main:app --reload`.
