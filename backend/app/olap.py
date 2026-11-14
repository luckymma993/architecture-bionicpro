import os
from datetime import date

import clickhouse_connect


def client():
    return clickhouse_connect.get_client(
        host=os.environ["CLICKHOUSE_HOST"],
        port=int(os.environ.get("CLICKHOUSE_PORT", "8123")),
        username=os.environ["CLICKHOUSE_USER"],
        password=os.environ["CLICKHOUSE_PASSWORD"],
    )


def fetch_report(username: str, date_from: date, date_to: date) -> dict:
    ch = client()
    processed_through = ch.query(
        "SELECT max(report_date) FROM reports.processed_days FINAL"
    ).result_rows[0][0]
    rows = ch.query(
        """
        SELECT r.report_date, r.full_name, r.country, r.prosthesis_model,
               r.signals_count, r.movements, r.avg_response_ms, r.errors, r.min_battery_pct
        FROM reports.user_daily_report AS r FINAL
        INNER JOIN (SELECT DISTINCT report_date FROM reports.processed_days FINAL) AS p
            ON p.report_date = r.report_date
        WHERE r.username = {username:String}
          AND r.report_date BETWEEN {date_from:Date} AND {date_to:Date}
        ORDER BY r.report_date
        """,
        parameters={"username": username, "date_from": date_from, "date_to": date_to},
    ).result_rows
    return {
        "username": username,
        "date_from": date_from.isoformat(),
        "date_to": date_to.isoformat(),
        "processed_through": processed_through.isoformat() if processed_through and processed_through.year > 1970 else None,
        "days": [
            {
                "date": r[0].isoformat(),
                "full_name": r[1],
                "country": r[2],
                "prosthesis_model": r[3],
                "signals_count": r[4],
                "movements": r[5],
                "avg_response_ms": round(r[6], 1),
                "errors": r[7],
                "min_battery_pct": r[8],
            }
            for r in rows
        ],
    }
