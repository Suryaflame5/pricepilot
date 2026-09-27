-- PricePilot V1.1 migration: raw observations, quality pipeline, model registry, outcomes.
-- Safe to run on an existing V1 database. Fresh installs get this via init.sql + create_all.

-- 1. Extend price_observations with quality/source fields
ALTER TABLE price_observations ADD COLUMN IF NOT EXISTS rating NUMERIC(4, 2);
ALTER TABLE price_observations ADD COLUMN IF NOT EXISTS review_count INTEGER;
ALTER TABLE price_observations ADD COLUMN IF NOT EXISTS delivery_estimate VARCHAR(255);
ALTER TABLE price_observations ADD COLUMN IF NOT EXISTS source VARCHAR(64);
ALTER TABLE price_observations ADD COLUMN IF NOT EXISTS source_metadata JSONB;
ALTER TABLE price_observations ADD COLUMN IF NOT EXISTS quality_score NUMERIC(6, 4);
ALTER TABLE price_observations ADD COLUMN IF NOT EXISTS trust_tier VARCHAR(16);

-- 2. Raw observations (quarantine-first intake)
CREATE TABLE IF NOT EXISTS raw_observations (
    id BIGSERIAL PRIMARY KEY,
    source VARCHAR(64) NOT NULL,
    collector_run_id VARCHAR(64),
    listing_id UUID REFERENCES listings(id),
    retailer_name VARCHAR(255),
    identity JSONB,
    payload JSONB,
    collected_at TIMESTAMPTZ NOT NULL,
    received_at TIMESTAMPTZ NOT NULL DEFAULT now(),
    status VARCHAR(16) NOT NULL DEFAULT 'RAW',
    validation_errors JSONB,
    anomaly_score NUMERIC(8, 6),
    anomaly_reasons JSONB,
    anomaly_status VARCHAR(16),
    quality_score NUMERIC(6, 4),
    match_confidence NUMERIC(8, 6),
    match_method VARCHAR(64),
    resolved_listing_id UUID REFERENCES listings(id)
);
CREATE INDEX IF NOT EXISTS ix_raw_obs_listing_time ON raw_observations (listing_id, collected_at);
CREATE INDEX IF NOT EXISTS ix_raw_obs_status ON raw_observations (status);

-- 3. Persistent event log (replay + audit)
CREATE TABLE IF NOT EXISTS system_events (
    id BIGSERIAL PRIMARY KEY,
    event_id VARCHAR(64) UNIQUE NOT NULL,
    event_type VARCHAR(64) NOT NULL,
    occurred_at TIMESTAMPTZ NOT NULL,
    entity_type VARCHAR(64),
    entity_id VARCHAR(64),
    payload JSONB
);
CREATE INDEX IF NOT EXISTS ix_system_events_type_time ON system_events (event_type, occurred_at);
CREATE INDEX IF NOT EXISTS ix_system_events_entity ON system_events (entity_type, entity_id);

-- 4. Match review queue (0.95 <= score < 0.995)
CREATE TABLE IF NOT EXISTS match_candidates (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    raw_observation_id BIGINT REFERENCES raw_observations(id),
    listing_id UUID REFERENCES listings(id),
    suggested_variant_id UUID REFERENCES product_variants(id),
    identity JSONB,
    score NUMERIC(8, 6) NOT NULL,
    method VARCHAR(64),
    details JSONB,
    status VARCHAR(16) NOT NULL DEFAULT 'PENDING',
    created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
    reviewed_at TIMESTAMPTZ
);

-- 5. Model registry (champion/challenger)
CREATE TABLE IF NOT EXISTS model_registry (
    id BIGSERIAL PRIMARY KEY,
    model_id VARCHAR(64) UNIQUE NOT NULL,
    name VARCHAR(255) NOT NULL,
    status VARCHAR(16) NOT NULL DEFAULT 'EXPERIMENT',
    model_type VARCHAR(64),
    category VARCHAR(255),
    horizon_hours INTEGER,
    features_version VARCHAR(32),
    calibration_version VARCHAR(32),
    conformal_version VARCHAR(32),
    metrics JSONB,
    metadata_ JSONB,
    created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
    promoted_at TIMESTAMPTZ,
    retired_at TIMESTAMPTZ,
    notes TEXT
);
CREATE INDEX IF NOT EXISTS ix_model_registry_status ON model_registry (status);

-- 6. Prediction outcomes (reliability contract raw material)
CREATE TABLE IF NOT EXISTS prediction_outcomes (
    id BIGSERIAL PRIMARY KEY,
    prediction_id UUID REFERENCES predictions(id) NOT NULL,
    actual_price NUMERIC(12, 2),
    actual_effective_price NUMERIC(12, 2),
    realized_at TIMESTAMPTZ,
    in_interval BOOLEAN,
    error_median NUMERIC(12, 2),
    error_abs NUMERIC(12, 2),
    created_at TIMESTAMPTZ NOT NULL DEFAULT now()
);
CREATE INDEX IF NOT EXISTS ix_prediction_outcomes_prediction ON prediction_outcomes (prediction_id);
