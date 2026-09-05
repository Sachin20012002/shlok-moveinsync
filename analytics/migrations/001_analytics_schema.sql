BEGIN;

CREATE TABLE IF NOT EXISTS trips (
    trip_id BIGINT NOT NULL,
    business_unit VARCHAR,
    office VARCHAR,
    product_type VARCHAR,
    trip_date DATE NOT NULL,
    shift_type VARCHAR,
    trip_direction VARCHAR,
    actual_escort BOOLEAN,
    vendor_id VARCHAR,
    planned_cab_registration VARCHAR,
    actual_cab_registration VARCHAR,
    actual_cab_capacity INTEGER,
    planned_km DOUBLE PRECISION,
    traveled_km DOUBLE PRECISION,
    planned_start_epoch BIGINT,
    planned_end_epoch BIGINT,
    actual_start_epoch BIGINT,
    actual_end_epoch BIGINT,
    delay_reason VARCHAR,
    delay_minutes INTEGER,
    route_source VARCHAR,
    actual_cab_fuel_type VARCHAR,
    is_driver_nc BOOLEAN,
    is_cab_nc BOOLEAN,
    trip_nodal VARCHAR,
    planned_employee_count INTEGER,
    actual_employee_count INTEGER,
    no_show_count INTEGER,
    PRIMARY KEY (trip_id, trip_date)
);

CREATE TABLE IF NOT EXISTS alerts (
    event_id UUID PRIMARY KEY,
    business_unit VARCHAR,
    trip_id BIGINT,
    stwid BIGINT,
    event_type VARCHAR,
    start_time TIMESTAMP,
    acknowledge_time TIMESTAMP NULL,
    state_text VARCHAR,
    severity VARCHAR NULL,
    source VARCHAR NULL
);

CREATE TABLE IF NOT EXISTS bills (
    id BIGINT GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
    business_unit VARCHAR,
    office VARCHAR,
    vendor VARCHAR,
    cycle_start TIMESTAMP,
    cycle_end TIMESTAMP,
    trip_id BIGINT,
    contract VARCHAR,
    slab_name VARCHAR NULL,
    total_trip_km DOUBLE PRECISION,
    trip_cost NUMERIC(14,2)
);

CREATE TABLE IF NOT EXISTS sla_config (
    id BIGINT GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
    metric_name VARCHAR UNIQUE NOT NULL,
    target_value DOUBLE PRECISION NOT NULL,
    unit VARCHAR,
    description VARCHAR
);

INSERT INTO sla_config (metric_name, target_value, unit, description)
VALUES
    ('OTA_PERCENT', 90, 'percent', 'Minimum on-time arrival target'),
    ('ALERT_ACK_MINUTES', 5, 'minutes', 'Maximum target alert acknowledgement time')
ON CONFLICT (metric_name) DO UPDATE SET
    target_value = EXCLUDED.target_value,
    unit = EXCLUDED.unit,
    description = EXCLUDED.description;

CREATE INDEX IF NOT EXISTS idx_trips_trip_date ON trips (trip_date);
CREATE INDEX IF NOT EXISTS idx_trips_vendor_id ON trips (vendor_id);
CREATE INDEX IF NOT EXISTS idx_trips_office ON trips (office);
CREATE INDEX IF NOT EXISTS idx_trips_business_unit ON trips (business_unit);
CREATE INDEX IF NOT EXISTS idx_trips_trip_date_vendor ON trips (trip_date, vendor_id);
CREATE INDEX IF NOT EXISTS idx_trips_trip_date_office ON trips (trip_date, office);

CREATE INDEX IF NOT EXISTS idx_alerts_trip_id ON alerts (trip_id);
CREATE INDEX IF NOT EXISTS idx_alerts_start_time ON alerts (start_time);
CREATE INDEX IF NOT EXISTS idx_alerts_event_type ON alerts (event_type);
CREATE INDEX IF NOT EXISTS idx_alerts_severity ON alerts (severity);
CREATE INDEX IF NOT EXISTS idx_alerts_trip_start ON alerts (trip_id, start_time);

CREATE INDEX IF NOT EXISTS idx_bills_trip_id ON bills (trip_id);
CREATE INDEX IF NOT EXISTS idx_bills_cycle_start ON bills (cycle_start);
CREATE INDEX IF NOT EXISTS idx_bills_vendor ON bills (vendor);
CREATE INDEX IF NOT EXISTS idx_bills_office ON bills (office);
CREATE INDEX IF NOT EXISTS idx_bills_cycle_vendor ON bills (cycle_start, vendor);

COMMIT;
