BEGIN;

CREATE TABLE IF NOT EXISTS employee_trip_legs (
    id BIGINT GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
    business_unit VARCHAR,
    office VARCHAR,
    product_type VARCHAR,
    trip_date DATE,
    shift_type VARCHAR,
    trip_id BIGINT NOT NULL,
    planned_pickup_epoch BIGINT,
    planned_drop_epoch BIGINT,
    actual_pickup_epoch BIGINT,
    actual_drop_epoch BIGINT,
    planned_km DOUBLE PRECISION,
    traveled_km DOUBLE PRECISION,
    stwid BIGINT,
    signin_type VARCHAR,
    gender VARCHAR,
    employee_role VARCHAR,
    boarding_status VARCHAR,
    not_boarding_reason VARCHAR NULL,
    is_no_show BOOLEAN,
    distance_quality_issue VARCHAR NULL
);

CREATE TABLE IF NOT EXISTS trip_feedback (
    id BIGINT GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
    business_unit VARCHAR,
    trip_id BIGINT NOT NULL,
    trip_type VARCHAR,
    trip_at TIMESTAMP,
    stwid BIGINT,
    route_rating SMALLINT CHECK (route_rating BETWEEN 0 AND 5),
    driver_rating SMALLINT CHECK (driver_rating BETWEEN 0 AND 5),
    cab_rating SMALLINT CHECK (cab_rating BETWEEN 0 AND 5),
    safety_rating SMALLINT CHECK (safety_rating BETWEEN 0 AND 5),
    marshal_rating SMALLINT CHECK (marshal_rating BETWEEN 0 AND 5),
    creation_time TIMESTAMP
);

CREATE INDEX IF NOT EXISTS idx_employee_legs_trip_id ON employee_trip_legs (trip_id);
CREATE INDEX IF NOT EXISTS idx_employee_legs_stwid ON employee_trip_legs (stwid);
CREATE INDEX IF NOT EXISTS idx_employee_legs_trip_date ON employee_trip_legs (trip_date);
CREATE INDEX IF NOT EXISTS idx_employee_legs_office ON employee_trip_legs (office);
CREATE INDEX IF NOT EXISTS idx_employee_legs_trip_employee ON employee_trip_legs (trip_id, stwid);
CREATE INDEX IF NOT EXISTS idx_employee_legs_date_office ON employee_trip_legs (trip_date, office);

CREATE INDEX IF NOT EXISTS idx_trip_feedback_trip_id ON trip_feedback (trip_id);
CREATE INDEX IF NOT EXISTS idx_trip_feedback_stwid ON trip_feedback (stwid);
CREATE INDEX IF NOT EXISTS idx_trip_feedback_trip_at ON trip_feedback (trip_at);
CREATE INDEX IF NOT EXISTS idx_trip_feedback_trip_employee ON trip_feedback (trip_id, stwid);

COMMIT;
