-- TimescaleDB bootstrap for PricePilot.
-- The API also runs CREATE EXTENSION + create_hypertable on startup
-- (idempotent), so this is belt-and-suspenders for fresh volumes.

CREATE EXTENSION IF NOT EXISTS timescaledb;

DO $$
BEGIN
    IF NOT EXISTS (
        SELECT 1 FROM pg_extension WHERE extname = 'timescaledb'
    ) THEN
        RAISE NOTICE 'timescaledb not available; hypertable setup deferred to app startup';
    END IF;
END $$;
