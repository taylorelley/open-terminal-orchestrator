-- Add metric_snapshots table for historical monitoring data.

CREATE TABLE IF NOT EXISTS metric_snapshots (
    id          uuid PRIMARY KEY DEFAULT gen_random_uuid(),
    timestamp   timestamptz NOT NULL DEFAULT now(),
    metric_type text NOT NULL,
    value       double precision NOT NULL DEFAULT 0,
    metadata    jsonb NOT NULL DEFAULT '{}'::jsonb
);

CREATE INDEX IF NOT EXISTS idx_metric_snapshots_type_ts
    ON metric_snapshots (metric_type, timestamp DESC);

-- Enable RLS
ALTER TABLE metric_snapshots ENABLE ROW LEVEL SECURITY;

CREATE POLICY "Allow authenticated access to metric_snapshots"
    ON metric_snapshots FOR ALL
    TO authenticated
    USING (true)
    WITH CHECK (true);
