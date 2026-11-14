CREATE SCHEMA crm;

CREATE TABLE crm.customers (
    id SERIAL PRIMARY KEY,
    username TEXT NOT NULL UNIQUE,
    full_name TEXT NOT NULL,
    country TEXT NOT NULL,
    prosthesis_model TEXT NOT NULL,
    contract_date DATE NOT NULL
);

INSERT INTO crm.customers (username, full_name, country, prosthesis_model, contract_date) VALUES
    ('prothetic1', 'Prothetic One', 'Россия', 'BionicHand X1', '2026-01-15'),
    ('prothetic2', 'Prothetic Two', 'Германия', 'BionicLeg L2', '2026-03-02'),
    ('prothetic3', 'Prothetic Three', 'Испания', 'BionicHand X2', '2026-05-20');

CREATE SCHEMA telemetry;

CREATE TABLE telemetry.signals (
    id BIGSERIAL PRIMARY KEY,
    customer_id INT NOT NULL REFERENCES crm.customers (id),
    event_time TIMESTAMPTZ NOT NULL,
    movements INT NOT NULL,
    response_ms INT NOT NULL,
    errors INT NOT NULL,
    battery_pct INT NOT NULL
);

CREATE INDEX signals_time_idx ON telemetry.signals (event_time);

INSERT INTO telemetry.signals (customer_id, event_time, movements, response_ms, errors, battery_pct)
SELECT
    c.id,
    t,
    20 + ((c.id * 7 + EXTRACT(HOUR FROM t)::INT * 3 + EXTRACT(DAY FROM t)::INT) % 40),
    80 + ((c.id * 13 + EXTRACT(HOUR FROM t)::INT * 5 + EXTRACT(DAY FROM t)::INT * 2) % 60),
    CASE WHEN (EXTRACT(HOUR FROM t)::INT + c.id + EXTRACT(DAY FROM t)::INT) % 11 = 0 THEN 1 ELSE 0 END,
    100 - EXTRACT(HOUR FROM t)::INT * 3
FROM crm.customers c,
     generate_series('2026-11-01 00:00:00+00'::TIMESTAMPTZ, '2026-11-14 23:00:00+00'::TIMESTAMPTZ, INTERVAL '1 hour') AS t;
