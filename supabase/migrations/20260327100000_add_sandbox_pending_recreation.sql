-- Add pending_recreation flag to sandboxes table.
-- When a policy update includes static section changes (filesystem, process),
-- affected sandboxes are marked for recreation on the next user request.

ALTER TABLE sandboxes ADD COLUMN pending_recreation boolean NOT NULL DEFAULT false;
