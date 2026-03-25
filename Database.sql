-- Create tables for raw multi-source indicators
CREATE TABLE conflict_data (
    record_id SERIAL PRIMARY KEY,
    region VARCHAR(100) NOT NULL,
    event_date DATE NOT NULL,
    fatalities INT DEFAULT 0,
    intensity_index FLOAT, -- Normalized score (0-1)
    cleaned BOOLEAN DEFAULT FALSE
);

CREATE TABLE currency_fluctuations (
    record_id SERIAL PRIMARY KEY,
    currency_code VARCHAR(3) NOT NULL,
    region VARCHAR(100),
    record_date DATE NOT NULL,
    exchange_rate_to_usd FLOAT,
    daily_volatility FLOAT,
    cleaned BOOLEAN DEFAULT FALSE
);

CREATE TABLE trade_volatility (
    record_id SERIAL PRIMARY KEY,
    region VARCHAR(100) NOT NULL,
    record_date DATE NOT NULL,
    export_volume_drop_pct FLOAT,
    import_tariff_spike FLOAT,
    cleaned BOOLEAN DEFAULT FALSE
);

-- Supply Chain Network Data
CREATE TABLE supply_chain_nodes (
    node_id VARCHAR(50) PRIMARY KEY,
    region VARCHAR(100) NOT NULL,
    criticality_score FLOAT, -- 0-1, how vital is this node globally?
    inventory_buffer_days INT
);

CREATE TABLE supply_chain_edges (
    source_node VARCHAR(50) REFERENCES supply_chain_nodes(node_id),
    target_node VARCHAR(50) REFERENCES supply_chain_nodes(node_id),
    dependency_weight FLOAT, -- 0-1, reliance of target on source
    PRIMARY KEY (source_node, target_node)
);

-- Example cleaning view: Identifying leading indicators of high-impact events
CREATE VIEW vw_regional_risk_indicators AS
SELECT 
    c.region,
    c.event_date,
    AVG(c.intensity_index) OVER (PARTITION BY c.region ORDER BY c.event_date ROWS BETWEEN 30 PRECEDING AND CURRENT ROW) as rolling_conflict_30d,
    AVG(curr.daily_volatility) OVER (PARTITION BY curr.region ORDER BY curr.record_date ROWS BETWEEN 30 PRECEDING AND CURRENT ROW) as rolling_fx_volatility_30d
FROM conflict_data c
LEFT JOIN currency_fluctuations curr ON c.region = curr.region AND c.event_date = curr.record_date
WHERE c.cleaned = TRUE AND curr.cleaned = TRUE;