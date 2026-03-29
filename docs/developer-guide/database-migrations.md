# Database Migrations Guide

This guide covers how to create, apply, and manage database migrations for ShellGuard.

## Overview

ShellGuard uses PostgreSQL 16 via Supabase. Database schema changes are managed through SQL migration files in the `supabase/migrations/` directory. All tables use Row-Level Security (RLS) for access control.

## Migration Workflow

### 1. Create a Migration File

Migration files are plain SQL files placed in `supabase/migrations/`. Each file contains the SQL statements needed to evolve the schema.

```bash
# Create a new migration file with a timestamp prefix
touch supabase/migrations/$(date +%Y%m%d%H%M%S)_add_reports_table.sql
```

### 2. Write the Migration SQL

Edit the new file with your schema changes (see examples below).

### 3. Apply the Migration

Apply using the Supabase CLI or directly via `psql`.

### 4. Update Application Code

Update the ORM model, Pydantic schema, and TypeScript types to match the new schema.

## Naming Convention

Migration files follow this naming pattern:

```
<timestamp>_<description>.sql
```

- **Timestamp**: `YYYYMMDDHHMMSS` format (e.g., `20260326203442`)
- **Description**: Short, lowercase, underscore-separated description of the change

Examples:

```
20260326203442_create_shellguard_schema.sql
20260327145200_add_sandbox_metrics_table.sql
20260328091500_add_index_on_audit_log_created_at.sql
20260329110000_add_reports_table.sql
```

Migrations are applied in alphabetical order, which the timestamp prefix guarantees is chronological.

## Writing Migrations

### Creating a New Table

```sql
-- supabase/migrations/20260329110000_add_reports_table.sql

CREATE TABLE IF NOT EXISTS reports (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    name TEXT NOT NULL,
    description TEXT,
    schedule TEXT NOT NULL,
    last_run_at TIMESTAMPTZ,
    created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
    updated_at TIMESTAMPTZ NOT NULL DEFAULT now()
);

-- Enable Row-Level Security
ALTER TABLE reports ENABLE ROW LEVEL SECURITY;

-- Admin-only access policy
CREATE POLICY "Admin access only" ON reports
    FOR ALL
    USING (auth.role() = 'service_role');

-- Create indexes for common queries
CREATE INDEX IF NOT EXISTS idx_reports_created_at ON reports (created_at DESC);
```

### Altering an Existing Table

```sql
-- supabase/migrations/20260330080000_add_priority_to_reports.sql

ALTER TABLE reports
    ADD COLUMN IF NOT EXISTS priority INTEGER NOT NULL DEFAULT 0;

-- Add an index if the new column will be queried frequently
CREATE INDEX IF NOT EXISTS idx_reports_priority ON reports (priority);
```

### Adding Indexes

```sql
-- supabase/migrations/20260330090000_add_indexes_for_performance.sql

-- Index for filtering sandboxes by state
CREATE INDEX IF NOT EXISTS idx_sandboxes_state ON sandboxes (state);

-- Composite index for user + state lookups
CREATE INDEX IF NOT EXISTS idx_sandboxes_user_state ON sandboxes (user_id, state);

-- Index for audit log time-range queries
CREATE INDEX IF NOT EXISTS idx_audit_log_created_at ON audit_log (created_at DESC);
```

## Row-Level Security

All tables in ShellGuard must have RLS enabled. This is a security requirement enforced at the database level.

### RLS Pattern for Admin-Only Access

Most ShellGuard tables use admin-only access since the dashboard is an admin tool:

```sql
-- Enable RLS on the table
ALTER TABLE <table_name> ENABLE ROW LEVEL SECURITY;

-- Allow full access for the service role (backend API)
CREATE POLICY "Service role has full access" ON <table_name>
    FOR ALL
    USING (auth.role() = 'service_role');

-- Optionally allow authenticated users to read
CREATE POLICY "Authenticated users can read" ON <table_name>
    FOR SELECT
    USING (auth.role() = 'authenticated');
```

### RLS for User-Scoped Data

For tables where users should only see their own data:

```sql
CREATE POLICY "Users can view own sandboxes" ON sandboxes
    FOR SELECT
    USING (auth.uid() = user_id);

CREATE POLICY "Service role has full access" ON sandboxes
    FOR ALL
    USING (auth.role() = 'service_role');
```

### Important RLS Notes

- RLS is enforced for all roles except the `postgres` superuser role.
- The backend API uses the `service_role` key, which bypasses RLS by default in Supabase. However, RLS policies are still defined for defense in depth.
- The frontend Supabase client uses the `anon` key, so RLS policies control what data is accessible from the browser.
- Always test RLS policies to ensure they do not accidentally expose data.

## Applying Migrations

### Using the Supabase CLI

```bash
# Push all pending migrations to the database
supabase db push

# Check migration status
supabase db status

# Reset the database (destroys all data)
supabase db reset
```

### Using psql Directly

```bash
# Apply a specific migration
psql "$DATABASE_URL" -f supabase/migrations/20260329110000_add_reports_table.sql

# Apply all migrations in order
for f in supabase/migrations/*.sql; do
    echo "Applying $f..."
    psql "$DATABASE_URL" -f "$f"
done
```

### In Docker Compose

If using the Docker Compose setup, migrations can be applied against the local database:

```bash
psql "postgresql://postgres:postgres@localhost:5432/shellguard" \
    -f supabase/migrations/<migration_file>.sql
```

## Rollback Considerations

Supabase migrations do not have a built-in rollback mechanism. Plan your migrations carefully:

### Best Practices

- **Make migrations additive.** Prefer `ADD COLUMN` over `DROP COLUMN`. Prefer `CREATE TABLE IF NOT EXISTS` over `CREATE TABLE`.
- **Use `IF NOT EXISTS` / `IF EXISTS` guards.** This makes migrations idempotent and safe to re-run.
- **Avoid destructive changes in production.** Do not drop columns or tables that contain data without a migration plan.
- **Create a rollback script alongside the migration.** For significant changes, write a corresponding undo script (not applied automatically, but available if needed).

### Manual Rollback

If a migration needs to be reversed, create a new migration that undoes the changes:

```sql
-- supabase/migrations/20260329120000_rollback_reports_table.sql

-- Remove the table added in 20260329110000
DROP TABLE IF EXISTS reports;
```

### Partial Failures

If a migration partially applies (e.g., a statement fails mid-file), you may need to:

1. Identify which statements succeeded by inspecting the current schema.
2. Manually fix the schema to a consistent state.
3. Either re-run the migration or mark it as applied.

To reduce partial failure risk, keep individual migration files focused on a single logical change.

## Adding New Fields End-to-End

When adding a new field to an existing entity, update all layers:

### 1. Database Migration

```sql
-- supabase/migrations/20260330100000_add_sandbox_label.sql
ALTER TABLE sandboxes ADD COLUMN IF NOT EXISTS label TEXT;
```

### 2. SQLAlchemy Model (backend)

```python
# backend/app/models.py
class Sandbox(Base):
    __tablename__ = "sandboxes"
    # ... existing columns ...
    label: Mapped[str | None] = mapped_column(Text)
```

### 3. Pydantic Schema (backend)

```python
# backend/app/schemas.py
class SandboxResponse(BaseModel):
    # ... existing fields ...
    label: str | None = None
```

### 4. TypeScript Type (frontend)

```typescript
// src/types/index.ts
export interface Sandbox {
  // ... existing fields ...
  label?: string;
}
```

### 5. Apply and Verify

```bash
# Apply the migration
psql "$DATABASE_URL" -f supabase/migrations/20260330100000_add_sandbox_label.sql

# Run backend tests
cd backend && python -m pytest -v

# Run frontend checks
npm run lint && npm run typecheck
```

## Existing Tables

The current ShellGuard schema includes these tables:

| Table | Description |
|-------|-------------|
| `policies` | Security policy definitions |
| `policy_versions` | Versioned snapshots of policy YAML |
| `groups` | User groups with optional policy assignment |
| `users` | Open WebUI users synced into ShellGuard |
| `sandboxes` | Per-user terminal sandbox instances |
| `policy_assignments` | Maps policies to users, groups, or roles with priority |
| `audit_log` | Enforcement, lifecycle, and admin event records |
| `system_config` | Key-value system configuration settings |

All tables have RLS enabled with admin-only access policies.
