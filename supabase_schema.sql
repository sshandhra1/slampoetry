-- ============================================================
-- SlamPoetryFabric — Supabase Schema
-- Run this in your Supabase project: SQL Editor → New query
-- ============================================================

CREATE TABLE IF NOT EXISTS events (
    id              BIGINT GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
    external_id     TEXT UNIQUE,          -- deduplication key (e.g. "eventbrite-123456")
    name            TEXT NOT NULL,
    venue           TEXT,
    city            TEXT,
    state           TEXT DEFAULT 'CA',
    region          TEXT DEFAULT 'west',
    lat             FLOAT,
    lng             FLOAT,
    type            TEXT,                 -- slam | open_mic | reading | workshop | festival
    date            DATE,
    time            TEXT,
    price           TEXT,
    url             TEXT,
    source          TEXT,                 -- eventbrite | meetup | manual
    created_at      TIMESTAMPTZ DEFAULT NOW(),
    updated_at      TIMESTAMPTZ DEFAULT NOW()
);

-- Index for fast filtering
CREATE INDEX IF NOT EXISTS idx_events_city   ON events(city);
CREATE INDEX IF NOT EXISTS idx_events_type   ON events(type);
CREATE INDEX IF NOT EXISTS idx_events_date   ON events(date);
CREATE INDEX IF NOT EXISTS idx_events_source ON events(source);

-- Auto-update updated_at on row change
CREATE OR REPLACE FUNCTION update_updated_at()
RETURNS TRIGGER AS $$
BEGIN
    NEW.updated_at = NOW();
    RETURN NEW;
END;
$$ LANGUAGE plpgsql;

CREATE OR REPLACE TRIGGER set_updated_at
    BEFORE UPDATE ON events
    FOR EACH ROW EXECUTE FUNCTION update_updated_at();

-- Row Level Security: allow anyone to read, only service role can write
ALTER TABLE events ENABLE ROW LEVEL SECURITY;

CREATE POLICY "Public read access"
    ON events FOR SELECT
    USING (true);

-- Enable Supabase Realtime for live browser updates
ALTER PUBLICATION supabase_realtime ADD TABLE events;
