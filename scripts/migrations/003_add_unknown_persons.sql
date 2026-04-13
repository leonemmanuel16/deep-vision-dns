-- Migration 003: Add is_unknown flag to known_persons
-- Allows auto-registering unknown faces detected by cameras

ALTER TABLE known_persons ADD COLUMN IF NOT EXISTS is_unknown BOOLEAN DEFAULT false;
ALTER TABLE known_persons ADD COLUMN IF NOT EXISTS first_seen_camera_id UUID;
ALTER TABLE known_persons ADD COLUMN IF NOT EXISTS first_seen_at TIMESTAMPTZ;
ALTER TABLE known_persons ADD COLUMN IF NOT EXISTS times_seen INTEGER DEFAULT 1;
ALTER TABLE known_persons ADD COLUMN IF NOT EXISTS last_seen_at TIMESTAMPTZ;
ALTER TABLE known_persons ADD COLUMN IF NOT EXISTS merged_into_id UUID;

-- Index for quick filtering of unknowns
CREATE INDEX IF NOT EXISTS idx_known_persons_unknown ON known_persons(is_unknown) WHERE is_unknown = true;
CREATE INDEX IF NOT EXISTS idx_known_persons_active ON known_persons(is_active) WHERE is_active = true;
