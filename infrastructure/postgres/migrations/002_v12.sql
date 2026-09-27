-- PricePilot V1.2 migration: live commerce intelligence.
-- Adaptive polling, prediction ledger columns, conversation state, purchase workflow.
-- Safe to run on V1.1. Fresh installs get this via init.sql + create_all.

-- 1. Adaptive polling on listings
ALTER TABLE listings ADD COLUMN IF NOT EXISTS poll_interval_seconds INTEGER DEFAULT 14400;
ALTER TABLE listings ADD COLUMN IF NOT EXISTS last_collected_at TIMESTAMPTZ;

-- 2. Prediction ledger: calibration artifact + retailer market provenance
ALTER TABLE predictions ADD COLUMN IF NOT EXISTS calibration_version VARCHAR(64);
ALTER TABLE predictions ADD COLUMN IF NOT EXISTS retailer_id UUID REFERENCES retailers(id);
ALTER TABLE predictions ADD COLUMN IF NOT EXISTS calibration_key_used VARCHAR(255);

-- 3. Conversational planning state (multi-turn constraints)
CREATE TABLE IF NOT EXISTS conversation_states (
    conversation_id VARCHAR(64) PRIMARY KEY,
    state JSONB NOT NULL DEFAULT '{}',
    updated_at TIMESTAMPTZ NOT NULL DEFAULT now()
);

-- 4. Purchase workflow
CREATE TABLE IF NOT EXISTS shopping_sessions (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    user_id UUID REFERENCES users(id),
    conversation_id VARCHAR(64),
    product_variant_id UUID NOT NULL REFERENCES product_variants(id),
    selected_listing_id UUID REFERENCES listings(id),
    strategy VARCHAR(32) NOT NULL DEFAULT 'IMMEDIATE',
    status VARCHAR(32) NOT NULL DEFAULT 'SEARCHING',
    checkout_total NUMERIC(12, 2),
    delivery_estimate VARCHAR(255),
    selected_offer JSONB,
    provider_session_id VARCHAR(255),
    created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
    updated_at TIMESTAMPTZ NOT NULL DEFAULT now(),
    expires_at TIMESTAMPTZ
);
CREATE INDEX IF NOT EXISTS ix_shopping_sessions_user ON shopping_sessions (user_id);
CREATE INDEX IF NOT EXISTS ix_shopping_sessions_status ON shopping_sessions (status);
CREATE INDEX IF NOT EXISTS ix_shopping_sessions_variant ON shopping_sessions (product_variant_id);

CREATE TABLE IF NOT EXISTS purchase_orders (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    session_id UUID NOT NULL REFERENCES shopping_sessions(id),
    provider VARCHAR(64) NOT NULL,
    retailer_name VARCHAR(255),
    order_ref VARCHAR(255),
    status VARCHAR(32) NOT NULL DEFAULT 'TRACKING',
    total NUMERIC(12, 2),
    tracking_url VARCHAR(1000),
    last_status VARCHAR(500),
    placed_at TIMESTAMPTZ NOT NULL DEFAULT now()
);
CREATE INDEX IF NOT EXISTS ix_purchase_orders_session ON purchase_orders (session_id);
