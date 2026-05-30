# Alembic migrations

Added pragmatically. During development the app creates tables via
`Base.metadata.create_all` on startup (see `db/engine.py:ensure_schema`), so you
do **not** need to run migrations to develop.

Migrations live here for when we adopt migration discipline closer to
production. The DB URL comes from `DATABASE_URL` (read in `env.py`), not from
`alembic.ini`.

Common commands (run from the repo root):

```bash
# create a new migration from model changes
alembic revision --autogenerate -m "describe change"

# apply migrations
alembic upgrade head

# roll back one
alembic downgrade -1
```

`0001_baseline` matches the initial Phase 1 schema (`users`,
`student_profiles`, `daily_usage`). The LangGraph checkpoint tables are managed
by `AsyncPostgresSaver.setup()`, not Alembic.
