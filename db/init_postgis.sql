-- 1. Enable PostGIS Extension
CREATE EXTENSION IF NOT EXISTS postgis;

-- 2. Raw Multi-Source Indicators with Geospatial Types
CREATE TABLE conflict_data (
    record_id SERIAL PRIMARY KEY,
    location GEOMETRY(Point, 4326) NOT NULL, -- Point location
    event_date DATE NOT NULL,
    fatalities INT DEFAULT 0,
    intensity_index FLOAT, -- Normalized score (0-1)
    event_type VARCHAR(100),
    cleaned BOOLEAN DEFAULT FALSE
);

CREATE TABLE currency_fluctuations (
    record_id SERIAL PRIMARY KEY,
    currency_code VARCHAR(10) NOT NULL,
    location GEOMETRY(Point, 4326),
    record_date DATE NOT NULL,
    exchange_rate_to_usd FLOAT,
    daily_volatility FLOAT,
    cleaned BOOLEAN DEFAULT FALSE
);

CREATE TABLE trade_volatility (
    record_id SERIAL PRIMARY KEY,
    location GEOMETRY(Point, 4326) NOT NULL,
    record_date DATE NOT NULL,
    export_volume_drop_pct FLOAT,
    import_tariff_spike FLOAT,
    cleaned BOOLEAN DEFAULT FALSE
);

-- 3. Supply Chain Network Data
CREATE TABLE supply_chain_nodes (
    node_id VARCHAR(50) PRIMARY KEY,
    location GEOMETRY(Point, 4326) NOT NULL,
    criticality_score FLOAT, -- 0-1, how vital is this node globally?
    inventory_buffer_days INT
);

CREATE TABLE supply_chain_edges (
    source_node VARCHAR(50) REFERENCES supply_chain_nodes(node_id),
    target_node VARCHAR(50) REFERENCES supply_chain_nodes(node_id),
    route GEOMETRY(LineString, 4326), -- LineString representing the route between nodes
    dependency_weight FLOAT, -- 0-1, reliance of target on source
    PRIMARY KEY (source_node, target_node)
);

-- 4. Exponential Decay Calculations
-- Calculates the decayed risk R(t) = R0 * e^(-lambda * t)
-- lambda is approximately 0.0495 for a half-life of 14 days
CREATE OR REPLACE FUNCTION calculate_decayed_risk(
    initial_risk FLOAT,
    event_date DATE,
    eval_date DATE,
    half_life_days FLOAT DEFAULT 14.0
) RETURNS FLOAT AS $$
DECLARE
    elapsed_days FLOAT;
    lambda FLOAT;
BEGIN
    elapsed_days := eval_date - event_date;
    IF elapsed_days < 0 THEN
        RETURN initial_risk; -- Cannot calculate for future events, return initial
    END IF;
    
    -- lambda = ln(2) / half_life
    lambda := ln(2.0) / half_life_days;
    
    RETURN initial_risk * exp(-lambda * elapsed_days);
END;
$$ LANGUAGE plpgsql;

-- View to get current decayed risk for all conflict events within last 180 days
CREATE VIEW vw_decayed_conflict_events AS
SELECT 
    record_id,
    location,
    event_date,
    intensity_index as initial_intensity,
    calculate_decayed_risk(intensity_index, event_date, CURRENT_DATE) as active_intensity
FROM conflict_data
WHERE event_date >= CURRENT_DATE - INTERVAL '180 days';
