import os
from datetime import datetime, timedelta

import clickhouse_connect
import psycopg2
from airflow.decorators import dag, task


def source_connection():
    return psycopg2.connect(
        host=os.environ["SOURCE_DB_HOST"],
        dbname=os.environ["SOURCE_DB_NAME"],
        user=os.environ["SOURCE_DB_USER"],
        password=os.environ["SOURCE_DB_PASSWORD"],
    )


def olap_client():
    return clickhouse_connect.get_client(
        host=os.environ["CLICKHOUSE_HOST"],
        port=int(os.environ.get("CLICKHOUSE_PORT", "8123")),
        username=os.environ["CLICKHOUSE_USER"],
        password=os.environ["CLICKHOUSE_PASSWORD"],
    )


@dag(
    dag_id="crm_to_olap",
    schedule="@daily",
    start_date=datetime(2026, 11, 1),
    catchup=True,
    max_active_runs=1,
    default_args={"retries": 2, "retry_delay": timedelta(minutes=1)},
    tags=["bionicpro", "reports"],
)
def crm_to_olap():
    @task
    def extract_crm():
        with source_connection() as conn, conn.cursor() as cur:
            cur.execute(
                "SELECT id, username, full_name, country, prosthesis_model FROM crm.customers"
            )
            return [
                {"id": r[0], "username": r[1], "full_name": r[2], "country": r[3], "model": r[4]}
                for r in cur.fetchall()
            ]

    @task
    def extract_telemetry(data_interval_start=None, data_interval_end=None):
        with source_connection() as conn, conn.cursor() as cur:
            cur.execute(
                """
                SELECT customer_id,
                       COUNT(*),
                       SUM(movements),
                       AVG(response_ms),
                       SUM(errors),
                       MIN(battery_pct)
                FROM telemetry.signals
                WHERE event_time >= %s AND event_time < %s
                GROUP BY customer_id
                """,
                (data_interval_start, data_interval_end),
            )
            return {
                r[0]: {
                    "signals": int(r[1]),
                    "movements": int(r[2]),
                    "avg_response_ms": float(r[3]),
                    "errors": int(r[4]),
                    "min_battery": int(r[5]),
                }
                for r in cur.fetchall()
            }

    @task
    def join_and_load(customers, telemetry, data_interval_start=None):
        report_date = data_interval_start.date()
        rows = []
        for c in customers:
            t = telemetry.get(str(c["id"])) or telemetry.get(c["id"])
            if not t:
                continue
            rows.append(
                [
                    report_date,
                    c["username"],
                    c["full_name"],
                    c["country"],
                    c["model"],
                    t["signals"],
                    t["movements"],
                    t["avg_response_ms"],
                    t["errors"],
                    t["min_battery"],
                ]
            )
        client = olap_client()
        if rows:
            client.insert(
                "reports.user_daily_report",
                rows,
                column_names=[
                    "report_date",
                    "username",
                    "full_name",
                    "country",
                    "prosthesis_model",
                    "signals_count",
                    "movements",
                    "avg_response_ms",
                    "errors",
                    "min_battery_pct",
                ],
            )
        client.insert(
            "reports.processed_days",
            [[report_date]],
            column_names=["report_date"],
        )
        return len(rows)

    join_and_load(extract_crm(), extract_telemetry())


crm_to_olap()
