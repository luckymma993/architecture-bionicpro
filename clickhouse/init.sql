CREATE DATABASE IF NOT EXISTS reports;

CREATE TABLE IF NOT EXISTS reports.crm_customers (
    customer_id UInt32,
    username String,
    full_name String,
    country String,
    prosthesis_model String,
    loaded_at DateTime DEFAULT now()
) ENGINE = ReplacingMergeTree(loaded_at)
ORDER BY customer_id;

CREATE TABLE IF NOT EXISTS reports.telemetry_daily (
    report_date Date,
    customer_id UInt32,
    signals_count UInt32,
    movements UInt32,
    avg_response_ms Float32,
    errors UInt32,
    min_battery_pct UInt8,
    loaded_at DateTime DEFAULT now()
) ENGINE = ReplacingMergeTree(loaded_at)
PARTITION BY toYYYYMM(report_date)
ORDER BY (customer_id, report_date);

CREATE TABLE IF NOT EXISTS reports.user_daily_report (
    report_date Date,
    username String,
    full_name String,
    country String,
    prosthesis_model String,
    signals_count UInt32,
    movements UInt32,
    avg_response_ms Float32,
    errors UInt32,
    min_battery_pct UInt8,
    loaded_at DateTime DEFAULT now()
) ENGINE = ReplacingMergeTree(loaded_at)
PARTITION BY toYYYYMM(report_date)
ORDER BY (username, report_date);

CREATE TABLE IF NOT EXISTS reports.processed_days (
    report_date Date,
    processed_at DateTime DEFAULT now()
) ENGINE = ReplacingMergeTree(processed_at)
ORDER BY report_date;
