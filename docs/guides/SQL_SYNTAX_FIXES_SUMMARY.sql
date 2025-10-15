-- Example of INCORRECT INDEX syntax (what was causing the PostgreSQL error)
CREATE TABLE orders (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    order_id VARCHAR(255) UNIQUE NOT NULL,
    status VARCHAR(100) NOT NULL,
    correlation_id VARCHAR(255) NOT NULL,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,

    -- THIS IS WRONG - PostgreSQL doesn't support inline INDEX in CREATE TABLE
    INDEX idx_orders_correlation_id (correlation_id),
    INDEX idx_orders_status (status)
);

-- Example of CORRECT INDEX syntax (what the MMF template produces)
-- 1. First create the table
CREATE TABLE orders (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    order_id VARCHAR(255) UNIQUE NOT NULL,
    status VARCHAR(100) NOT NULL,
    correlation_id VARCHAR(255) NOT NULL,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

-- 2. Then create indexes separately
CREATE INDEX idx_orders_correlation_id ON orders(correlation_id);
CREATE INDEX idx_orders_status ON orders(status);

-- Example of INCORRECT JSONB values (what was causing the JSON error)
INSERT INTO configuration (config_key, config_value, config_type) VALUES
  ('feature_flags.payment_gateway', 'sandbox', 'feature_flag');  -- WRONG: bare string for JSONB

-- Example of CORRECT JSONB values
INSERT INTO configuration (config_key, config_value, config_type) VALUES
  ('feature_flags.payment_gateway', '"sandbox"', 'feature_flag');  -- CORRECT: JSON-quoted string
