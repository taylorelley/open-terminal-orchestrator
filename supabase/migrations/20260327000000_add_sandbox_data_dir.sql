-- Add data_dir column to track the host-side user data volume mounted into each sandbox.
ALTER TABLE sandboxes ADD COLUMN data_dir text NOT NULL DEFAULT '';
