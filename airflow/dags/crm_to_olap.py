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
    def load_crm():
        with source_connection() as conn, conn.cursor() as cur:
            cur.execute(
                "SELECT id, username, full_name, country, prosthesis_model FROM crm.customers"
            )
            rows = [list(r) for r in cur.fetchall()]
        olap_client().insert(
            "reports.crm_customers",
            rows,
            column_names=["customer_id", "username", "full_name", "country", "prosthesis_model"],
        )
        return len(rows)

    @task
    def load_telemetry(data_interval_start=None, data_interval_end=None):
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
            report_date = data_interval_start.date()
            rows = [
                [report_date, r[0], int(r[1]), int(r[2]), float(r[3]), int(r[4]), int(r[5])]
                for r in cur.fetchall()
            ]
        if rows:
            olap_client().insert(
                "reports.telemetry_daily",
                rows,
                column_names=[
                    "report_date",
                    "customer_id",
                    "signals_count",
                    "movements",
                    "avg_response_ms",
                    "errors",
                    "min_battery_pct",
                ],
            )
        return len(rows)

    @task
    def build_mart(data_interval_start=None):
        report_date = data_interval_start.date()
        olap_client().command(
            """
            INSERT INTO reports.user_daily_report
                (report_date, username, full_name, country, prosthesis_model,
                 signals_count, movements, avg_response_ms, errors, min_battery_pct)
            SELECT t.report_date, c.username, c.full_name, c.country, c.prosthesis_model,
                   t.signals_count, t.movements, t.avg_response_ms, t.errors, t.min_battery_pct
            FROM reports.telemetry_daily AS t FINAL
            INNER JOIN reports.crm_customers AS c FINAL ON c.customer_id = t.customer_id
            WHERE t.report_date = {report_date:Date}
            """,
            parameters={"report_date": report_date},
        )

    @task
    def mark_processed(data_interval_start=None):
        olap_client().insert(
            "reports.processed_days",
            [[data_interval_start.date()]],
            column_names=["report_date"],
        )

    [load_crm(), load_telemetry()] >> build_mart() >> mark_processed()


crm_to_olap()
