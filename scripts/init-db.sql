-- Deep Vision by DNS — Database Schema
-- PostgreSQL 16

CREATE EXTENSION IF NOT EXISTS "uuid-ossp";
CREATE EXTENSION IF NOT EXISTS "pgcrypto";

-- ── Users ────────────────────────────────────────────────────
CREATE TABLE users (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    email VARCHAR(255) UNIQUE NOT NULL,
    username VARCHAR(100) UNIQUE NOT NULL,
    password_hash VARCHAR(255) NOT NULL,
    full_name VARCHAR(255),
    role VARCHAR(20) DEFAULT 'operator' CHECK (role IN ('admin', 'operator', 'viewer')),
    is_active BOOLEAN DEFAULT true,
    created_at TIMESTAMPTZ DEFAULT NOW(),
    updated_at TIMESTAMPTZ DEFAULT NOW()
);

-- Default admin user (password: admin123 — change immediately)
INSERT INTO users (email, username, password_hash, full_name, role) VALUES (
    'admin@deepvision.local',
    'admin',
    crypt('admin123', gen_salt('bf')),
    'Administrador',
    'admin'
);

-- ── Cameras ──────────────────────────────────────────────────
CREATE TABLE cameras (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    name VARCHAR(255) NOT NULL,
    rtsp_url VARCHAR(500) NOT NULL,
    rtsp_sub_url VARCHAR(500),
    brand VARCHAR(100),
    model VARCHAR(100),
    location VARCHAR(255),
    latitude DOUBLE PRECISION,
    longitude DOUBLE PRECISION,
    status VARCHAR(20) DEFAULT 'offline' CHECK (status IN ('online', 'offline', 'error')),
    enabled BOOLEAN DEFAULT true,
    recording_enabled BOOLEAN DEFAULT true,
    config JSONB DEFAULT '{
        "motion_on_threshold": 0.005,
        "motion_off_frames": 30,
        "detection_fps": 10,
        "resolution": "1280x720"
    }'::jsonb,
    created_at TIMESTAMPTZ DEFAULT NOW(),
    updated_at TIMESTAMPTZ DEFAULT NOW()
);

-- ── Zones ────────────────────────────────────────────────────
CREATE TABLE zones (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    camera_id UUID NOT NULL REFERENCES cameras(id) ON DELETE CASCADE,
    name VARCHAR(255) NOT NULL,
    zone_type VARCHAR(30) DEFAULT 'roi' CHECK (zone_type IN ('roi', 'line_crossing', 'exclusion')),
    points JSONB NOT NULL, -- [{x: 0.1, y: 0.2}, ...]
    direction VARCHAR(10), -- for line_crossing: 'A2B', 'B2A', 'both'
    config JSONB DEFAULT '{}'::jsonb,
    enabled BOOLEAN DEFAULT true,
    created_at TIMESTAMPTZ DEFAULT NOW()
);

-- ── Events ───────────────────────────────────────────────────
CREATE TABLE events (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    camera_id UUID NOT NULL REFERENCES cameras(id) ON DELETE CASCADE,
    zone_id UUID REFERENCES zones(id) ON DELETE SET NULL,
    event_type VARCHAR(50) NOT NULL, -- 'person_detected', 'vehicle_detected', 'zone_crossing', 'overcrowding'
    label VARCHAR(100) NOT NULL, -- 'person', 'car', 'truck', etc.
    confidence REAL NOT NULL,
    bbox JSONB, -- {x1, y1, x2, y2} as percentages
    tracker_id INTEGER,
    snapshot_url VARCHAR(500),
    clip_url VARCHAR(500),
    thumbnail_url VARCHAR(500),
    review_pass VARCHAR(20) DEFAULT 'online' CHECK (review_pass IN ('online', 'nightly', 'both')),
    needs_deep_review BOOLEAN DEFAULT true,
    attributes JSONB DEFAULT '{}'::jsonb, -- ropa_sup, ropa_inf, casco, mochila, color_vehiculo, etc.
    person_id UUID, -- FK to known_persons if matched
    metadata JSONB DEFAULT '{}'::jsonb,
    detected_at TIMESTAMPTZ DEFAULT NOW(),
    created_at TIMESTAMPTZ DEFAULT NOW()
);

CREATE INDEX idx_events_camera ON events(camera_id);
CREATE INDEX idx_events_detected_at ON events(detected_at);
CREATE INDEX idx_events_label ON events(label);
CREATE INDEX idx_events_review ON events(needs_deep_review) WHERE needs_deep_review = true;
CREATE INDEX idx_events_attributes ON events USING GIN(attributes);

-- ── Known Persons (Face DB) ──────────────────────────────────
CREATE TABLE known_persons (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    name VARCHAR(255) NOT NULL,
    employee_id VARCHAR(100),
    department VARCHAR(100),
    face_encoding BYTEA, -- face embedding vector
    photo_url VARCHAR(500),
    notes TEXT,
    is_active BOOLEAN DEFAULT true,
    is_unknown BOOLEAN DEFAULT false, -- auto-registered unknown face
    first_seen_camera_id UUID, -- camera where first detected
    first_seen_at TIMESTAMPTZ, -- when first detected
    times_seen INTEGER DEFAULT 1, -- how many times detected
    last_seen_at TIMESTAMPTZ, -- last detection time
    merged_into_id UUID, -- if merged into another person
    created_at TIMESTAMPTZ DEFAULT NOW(),
    updated_at TIMESTAMPTZ DEFAULT NOW()
);

CREATE INDEX idx_known_persons_unknown ON known_persons(is_unknown) WHERE is_unknown = true;
CREATE INDEX idx_known_persons_active ON known_persons(is_active) WHERE is_active = true;

-- ── Alert Rules ──────────────────────────────────────────────
CREATE TABLE alert_rules (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    name VARCHAR(255) NOT NULL,
    event_type VARCHAR(50) NOT NULL,
    camera_ids UUID[], -- null = all cameras
    zone_ids UUID[], -- null = all zones
    conditions JSONB DEFAULT '{}'::jsonb, -- min_confidence, labels, schedule
    actions JSONB NOT NULL, -- [{type: 'email', to: '...'}, {type: 'webhook', url: '...'}]
    cooldown_seconds INTEGER DEFAULT 60,
    enabled BOOLEAN DEFAULT true,
    last_triggered_at TIMESTAMPTZ,
    created_at TIMESTAMPTZ DEFAULT NOW(),
    updated_at TIMESTAMPTZ DEFAULT NOW()
);

-- ── Recordings Metadata ──────────────────────────────────────
CREATE TABLE recordings (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    camera_id UUID NOT NULL REFERENCES cameras(id) ON DELETE CASCADE,
    file_path VARCHAR(500) NOT NULL,
    start_time TIMESTAMPTZ NOT NULL,
    end_time TIMESTAMPTZ,
    duration_seconds INTEGER,
    file_size_bytes BIGINT,
    status VARCHAR(20) DEFAULT 'recording' CHECK (status IN ('recording', 'completed', 'archived', 'deleted')),
    created_at TIMESTAMPTZ DEFAULT NOW()
);

CREATE INDEX idx_recordings_camera_time ON recordings(camera_id, start_time);

-- ── Heatmap Data ─────────────────────────────────────────────
CREATE TABLE heatmap_data (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    camera_id UUID NOT NULL REFERENCES cameras(id) ON DELETE CASCADE,
    hour_bucket TIMESTAMPTZ NOT NULL, -- truncated to hour
    grid_data JSONB NOT NULL, -- 2D grid of counts
    total_detections INTEGER DEFAULT 0,
    created_at TIMESTAMPTZ DEFAULT NOW()
);

CREATE INDEX idx_heatmap_camera_hour ON heatmap_data(camera_id, hour_bucket);

-- ── Traffic / Counting ───────────────────────────────────────
CREATE TABLE traffic_counts (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    zone_id UUID NOT NULL REFERENCES zones(id) ON DELETE CASCADE,
    direction VARCHAR(10), -- 'A2B', 'B2A'
    count_in INTEGER DEFAULT 0,
    count_out INTEGER DEFAULT 0,
    hour_bucket TIMESTAMPTZ NOT NULL,
    created_at TIMESTAMPTZ DEFAULT NOW()
);

CREATE INDEX idx_traffic_zone_hour ON traffic_counts(zone_id, hour_bucket);
