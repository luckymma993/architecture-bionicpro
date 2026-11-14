# Задание 2. Сервис отчётов

## Файлы

| Путь | Содержимое |
|------|-----------|
| `Task2/BionicPRO_reports_architecture.drawio`, `.png` | Схема: Airflow ETL, ClickHouse и API на основе исходной C4-диаграммы |
| `airflow/` | Образ Airflow и DAG `dags/crm_to_olap.py` |
| `sources/` | Схемы и данные CRM и телеметрии (PostgreSQL) |
| `clickhouse/init.sql` | Витрина `user_daily_report` и таблица `processed_days` |
| `backend/` | Reports API на FastAPI, `GET /reports` |
| `frontend/src/components/ReportPage.tsx` | Кнопка Download Report и таблица отчёта |
| `Task2/check_api.py` | Проверка API: вход по PKCE, запросы за разных пользователей |

## Как работает

1. DAG `crm_to_olap` запускается ежедневно (`catchup=True` догоняет дни с 1 ноября 2026). Задачи: `load_crm` копирует клиентов из CRM в `reports.crm_customers`, `load_telemetry` агрегирует телеметрию за сутки по клиентам в `reports.telemetry_daily`, `build_mart` объединяет их запросом `INSERT ... SELECT ... JOIN` в витрину `reports.user_daily_report` (строка на клиента и день), `mark_processed` записывает день в `reports.processed_days`.
2. `GET /reports?date_from=&date_to=` берёт имя пользователя только из проверенного токена Keycloak. Без токена ответ 401, без роли `prothetic_user` ответ 403.
3. Запрос объединяет витрину с `processed_days`, поэтому в отчёт попадают только дни, которые Airflow уже обработал. Дата последнего обработанного дня возвращается в поле `processed_through`, а если запрошенный период выходит за неё, ответ содержит `partial: true` и сообщение, а интерфейс показывает предупреждение.
4. Повторный запуск DAG за тот же день не создаёт дублей: таблицы ReplacingMergeTree читаются с `FINAL`.

## Запуск

```bash
docker compose up -d --build
```

| Сервис | Адрес |
|--------|-------|
| Frontend | http://localhost:3000 |
| Keycloak | http://localhost:8080 (admin / admin) |
| Airflow | http://localhost:18081 (admin / admin) |
| Reports API | http://localhost:8000/docs |
| ClickHouse HTTP | http://localhost:18123 |

Пользователи для входа: `prothetic1`, `prothetic2`, `prothetic3` (пароль `prothetic123`). `user1` (пароль `password123`) входит, но отчёт не получает.

После запуска Airflow сам обработает дни с 1 по 13 ноября. Проверка API:

```bash
python Task2/check_api.py
```

## Результат проверки

- без токена: 401;
- неверный токен: 401;
- `prothetic1` и `prothetic2`: по 13 дней, каждый видит только своё имя, `processed_through` = 2026-11-13;
- `user1` без роли: 403.
