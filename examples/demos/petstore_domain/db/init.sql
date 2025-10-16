-- Enhanced Petstore Database Schema
-- Supports event sourcing, audit trails, and multi-datasource patterns

-- Enable UUID extension
CREATE EXTENSION IF NOT EXISTS "uuid-ossp";

-- Pet Catalog Table
CREATE TABLE pet_catalog (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    pet_id VARCHAR(255) UNIQUE NOT NULL,
    name VARCHAR(255) NOT NULL,
    category VARCHAR(100) NOT NULL,
    breed VARCHAR(255),
    age_months INTEGER,
    price DECIMAL(10,2) NOT NULL,
    description TEXT,
    vaccinated BOOLEAN DEFAULT FALSE,
    available BOOLEAN DEFAULT TRUE,
    special_care BOOLEAN DEFAULT FALSE,
    image_url VARCHAR(500),
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    version INTEGER DEFAULT 1
);

-- Customers Table
CREATE TABLE customers (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    customer_id VARCHAR(255) UNIQUE NOT NULL,
    name VARCHAR(255) NOT NULL,
    email VARCHAR(255) UNIQUE NOT NULL,
    phone VARCHAR(50),
    address TEXT,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    version INTEGER DEFAULT 1
);

-- Orders Table with Event Sourcing Support
CREATE TABLE orders (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    order_id VARCHAR(255) UNIQUE NOT NULL,
    customer_id VARCHAR(255) NOT NULL REFERENCES customers(customer_id),
    pet_id VARCHAR(255) NOT NULL REFERENCES pet_catalog(pet_id),
    amount DECIMAL(10,2) NOT NULL,
    status VARCHAR(100) NOT NULL,
    special_instructions TEXT,
    correlation_id VARCHAR(255) NOT NULL,
    saga_id VARCHAR(255),
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    version INTEGER DEFAULT 1
);

-- Order Events Table for Event Sourcing
CREATE TABLE order_events (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    order_id VARCHAR(255) NOT NULL REFERENCES orders(order_id),
    event_type VARCHAR(100) NOT NULL,
    event_data JSONB NOT NULL,
    correlation_id VARCHAR(255) NOT NULL,
    causation_id VARCHAR(255),
    event_version INTEGER NOT NULL,
    occurred_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

-- Payments Table
CREATE TABLE payments (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    payment_id VARCHAR(255) UNIQUE NOT NULL,
    order_id VARCHAR(255) NOT NULL REFERENCES orders(order_id),
    amount DECIMAL(10,2) NOT NULL,
    payment_method VARCHAR(100) NOT NULL,
    status VARCHAR(100) NOT NULL,
    correlation_id VARCHAR(255) NOT NULL,
    processed_at TIMESTAMP,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

-- Deliveries Table
CREATE TABLE deliveries (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    delivery_id VARCHAR(255) UNIQUE NOT NULL,
    order_id VARCHAR(255) NOT NULL REFERENCES orders(order_id),
    status VARCHAR(100) NOT NULL,
    estimated_delivery TIMESTAMP,
    actual_delivery TIMESTAMP,
    delivery_address TEXT,
    correlation_id VARCHAR(255) NOT NULL,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

-- Saga State Table for Workflow Management
CREATE TABLE saga_state (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    saga_id VARCHAR(255) UNIQUE NOT NULL,
    saga_type VARCHAR(100) NOT NULL,
    correlation_id VARCHAR(255) NOT NULL,
    status VARCHAR(100) NOT NULL,
    current_step VARCHAR(100),
    context_data JSONB,
    compensation_data JSONB,
    started_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    completed_at TIMESTAMP,
    last_updated TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

-- Audit Trail Table for Compliance
CREATE TABLE audit_trail (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    entity_type VARCHAR(100) NOT NULL,
    entity_id VARCHAR(255) NOT NULL,
    action VARCHAR(100) NOT NULL,
    old_values JSONB,
    new_values JSONB,
    user_id VARCHAR(255),
    correlation_id VARCHAR(255),
    timestamp TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

-- Configuration Table for Feature Flags and Settings
CREATE TABLE configuration (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    config_key VARCHAR(255) UNIQUE NOT NULL,
    config_value JSONB NOT NULL,
    config_type VARCHAR(100) NOT NULL,
    description TEXT,
    is_active BOOLEAN DEFAULT TRUE,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

-- Insert Sample Data
INSERT INTO pet_catalog (pet_id, name, category, breed, age_months, price, description, vaccinated, available, special_care, image_url) VALUES
('golden-retriever-001', 'Buddy', 'dog', 'Golden Retriever', 8, 1200.00, 'Friendly and energetic Golden Retriever puppy', true, true, false, '/images/golden-retriever.jpg'),
('persian-cat-002', 'Princess', 'cat', 'Persian Cat', 12, 800.00, 'Beautiful Persian cat with long fluffy coat', true, true, true, '/images/persian-cat.jpg'),
('cockatiel-003', 'Sunny', 'bird', 'Cockatiel', 6, 300.00, 'Social and intelligent cockatiel with beautiful crest', true, true, false, '/images/cockatiel.jpg'),
('goldfish-004', 'Bubbles', 'fish', 'Goldfish', 3, 25.00, 'Peaceful goldfish perfect for beginners', false, true, false, '/images/goldfish.jpg'),
('bearded-dragon-005', 'Spike', 'reptile', 'Bearded Dragon', 18, 150.00, 'Calm and friendly bearded dragon', true, true, true, '/images/bearded-dragon.jpg');

INSERT INTO customers (customer_id, name, email, phone, address) VALUES
('customer-001', 'Alice Johnson', 'alice@example.com', '+1-555-0101', '123 Pet Lover Lane, Dogtown, ST 12345'),
('customer-002', 'Bob Smith', 'bob@example.com', '+1-555-0102', '456 Cat Avenue, Kittyville, ST 12346'),
('customer-003', 'Carol Wilson', 'carol@example.com', '+1-555-0103', '789 Bird Street, Feathertown, ST 12347');

-- Insert Feature Flags and Configuration
INSERT INTO configuration (config_key, config_value, config_type, description) VALUES
  ('feature_flags.order_processing', '"true"', 'feature_flag', 'Enable enhanced order processing'),
  ('feature_flags.payment_gateway', '"sandbox"', 'feature_flag', 'Payment gateway mode'),
  ('feature_flags.delivery_tracking', '"true"', 'feature_flag', 'Enable delivery tracking'),
  ('thresholds.circuit_breaker_failures', '"5"', 'threshold', 'Circuit breaker failure threshold'),
  ('thresholds.rate_limit_per_minute', '"100"', 'threshold', 'API rate limit per minute'),
  ('notification.email_enabled', '"true"', 'notification', 'Enable email notifications'),
  ('notification.sms_enabled', '"false"', 'notification', 'Enable SMS notifications');

-- Create all indexes separately
CREATE INDEX idx_orders_correlation_id ON orders(correlation_id);
CREATE INDEX idx_orders_status ON orders(status);
CREATE INDEX idx_orders_customer_id ON orders(customer_id);

CREATE INDEX idx_order_events_correlation_id ON order_events(correlation_id);
CREATE INDEX idx_order_events_timestamp ON order_events(occurred_at);
CREATE INDEX idx_order_events_type ON order_events(event_type);

CREATE INDEX idx_payments_order_id ON payments(order_id);
CREATE INDEX idx_payments_status ON payments(status);
CREATE INDEX idx_payments_correlation_id ON payments(correlation_id);

CREATE INDEX idx_deliveries_order_id ON deliveries(order_id);
CREATE INDEX idx_deliveries_status ON deliveries(status);
CREATE INDEX idx_deliveries_correlation_id ON deliveries(correlation_id);

CREATE INDEX idx_saga_state_correlation_id ON saga_state(correlation_id);
CREATE INDEX idx_saga_state_status ON saga_state(status);
CREATE INDEX idx_saga_state_type ON saga_state(saga_type);

CREATE INDEX idx_audit_trail_entity_type ON audit_trail(entity_type);
CREATE INDEX idx_audit_trail_entity_id ON audit_trail(entity_id);
CREATE INDEX idx_audit_trail_timestamp ON audit_trail(timestamp);

CREATE INDEX idx_config_key ON configuration(config_key);
CREATE INDEX idx_config_type ON configuration(config_type);-- Create Functions for Audit Triggers
CREATE OR REPLACE FUNCTION audit_trigger_function()
RETURNS TRIGGER AS $$
BEGIN
    IF TG_OP = 'INSERT' THEN
        INSERT INTO audit_trail (entity_type, entity_id, action, new_values, timestamp)
        VALUES (TG_TABLE_NAME, NEW.id::TEXT, 'INSERT', row_to_json(NEW), CURRENT_TIMESTAMP);
        RETURN NEW;
    ELSIF TG_OP = 'UPDATE' THEN
        INSERT INTO audit_trail (entity_type, entity_id, action, old_values, new_values, timestamp)
        VALUES (TG_TABLE_NAME, NEW.id::TEXT, 'UPDATE', row_to_json(OLD), row_to_json(NEW), CURRENT_TIMESTAMP);
        RETURN NEW;
    ELSIF TG_OP = 'DELETE' THEN
        INSERT INTO audit_trail (entity_type, entity_id, action, old_values, timestamp)
        VALUES (TG_TABLE_NAME, OLD.id::TEXT, 'DELETE', row_to_json(OLD), CURRENT_TIMESTAMP);
        RETURN OLD;
    END IF;
    RETURN NULL;
END;
$$ LANGUAGE plpgsql;

-- Create Audit Triggers
CREATE TRIGGER pet_catalog_audit_trigger
    AFTER INSERT OR UPDATE OR DELETE ON pet_catalog
    FOR EACH ROW EXECUTE FUNCTION audit_trigger_function();

CREATE TRIGGER customers_audit_trigger
    AFTER INSERT OR UPDATE OR DELETE ON customers
    FOR EACH ROW EXECUTE FUNCTION audit_trigger_function();

CREATE TRIGGER orders_audit_trigger
    AFTER INSERT OR UPDATE OR DELETE ON orders
    FOR EACH ROW EXECUTE FUNCTION audit_trigger_function();

-- Create indexes for performance
CREATE INDEX CONCURRENTLY idx_pet_catalog_category ON pet_catalog(category);
CREATE INDEX CONCURRENTLY idx_pet_catalog_available ON pet_catalog(available);
CREATE INDEX CONCURRENTLY idx_pet_catalog_price ON pet_catalog(price);
CREATE INDEX CONCURRENTLY idx_customers_email ON customers(email);
CREATE INDEX CONCURRENTLY idx_orders_created_at ON orders(created_at);
CREATE INDEX CONCURRENTLY idx_order_events_occurred_at ON order_events(occurred_at);
