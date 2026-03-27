-- Track when a sandbox enters the WARMING state.
-- Used by the pool manager to enforce resume_timeout (WARMING sandboxes being
-- resumed) separately from startup_timeout (newly created pool sandboxes).

ALTER TABLE sandboxes ADD COLUMN warming_started_at timestamptz;
