/*
  # ShellGuard Management Schema

  1. New Tables
    - `policies` - Security policy definitions (restricted, standard, elevated)
      - `id` (uuid, primary key)
      - `name` (text, unique) - Policy name
      - `tier` (text) - restricted/standard/elevated
      - `description` (text) - Human-readable description
      - `current_version` (text) - Current version string
      - `yaml` (text) - Full YAML policy content
      - `created_at` (timestamptz)
      - `updated_at` (timestamptz)

    - `policy_versions` - Version history for policies
      - `id` (uuid, primary key)
      - `policy_id` (uuid, FK -> policies)
      - `version` (text) - Semantic version string
      - `yaml` (text) - YAML content at this version
      - `changelog` (text) - Description of changes
      - `created_by` (uuid, FK -> auth.users)
      - `created_at` (timestamptz)

    - `groups` - ShellGuard user groups for policy assignment
      - `id` (uuid, primary key)
      - `name` (text, unique)
      - `description` (text)
      - `policy_id` (uuid, FK -> policies)
      - `created_at` (timestamptz)
      - `updated_at` (timestamptz)

    - `users` - Open WebUI user records synced into ShellGuard
      - `id` (uuid, primary key)
      - `owui_id` (text, unique) - Open WebUI user identifier
      - `username` (text)
      - `email` (text)
      - `owui_role` (text) - admin/user/pending
      - `group_id` (uuid, FK -> groups)
      - `synced_at` (timestamptz)

    - `sandboxes` - Per-user sandbox container records
      - `id` (uuid, primary key)
      - `name` (text, unique)
      - `user_id` (uuid, FK -> users)
      - `state` (text) - POOL/WARMING/READY/ACTIVE/SUSPENDED/DESTROYED
      - `policy_id` (uuid, FK -> policies)
      - `internal_ip` (text)
      - `image_tag` (text)
      - `gpu_enabled` (boolean)
      - `cpu_usage` (real) - Current CPU percentage
      - `memory_usage` (real) - Current memory in MB
      - `disk_usage` (real) - Current disk in MB
      - `network_io` (real) - Current network I/O in KB/s
      - `created_at` (timestamptz)
      - `last_active_at` (timestamptz)
      - `suspended_at` (timestamptz)
      - `destroyed_at` (timestamptz)

    - `policy_assignments` - Maps policies to users/groups/roles
      - `id` (uuid, primary key)
      - `entity_type` (text) - user/group/role
      - `entity_id` (text) - user ID, group ID, or role name
      - `policy_id` (uuid, FK -> policies)
      - `priority` (integer) - Resolution precedence
      - `created_by` (uuid, FK -> auth.users)
      - `created_at` (timestamptz)

    - `audit_log` - All enforcement, lifecycle, and admin events
      - `id` (uuid, primary key)
      - `timestamp` (timestamptz)
      - `event_type` (text) - allow/deny/route/created/assigned/suspended/resumed/destroyed/policy_change/config_change
      - `category` (text) - enforcement/lifecycle/admin
      - `user_id` (uuid, FK -> users)
      - `sandbox_id` (uuid, FK -> sandboxes)
      - `details` (jsonb) - Full event metadata
      - `source_ip` (text)

    - `system_config` - Key-value configuration store
      - `key` (text, primary key)
      - `value` (jsonb)
      - `updated_at` (timestamptz)
      - `updated_by` (uuid, FK -> auth.users)

  2. Security
    - RLS enabled on ALL tables
    - Policies restrict access to authenticated users only
    - All tables are admin-only access
*/

-- Policies table
CREATE TABLE IF NOT EXISTS policies (
  id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
  name text UNIQUE NOT NULL,
  tier text NOT NULL DEFAULT 'restricted' CHECK (tier IN ('restricted', 'standard', 'elevated')),
  description text NOT NULL DEFAULT '',
  current_version text NOT NULL DEFAULT '1.0.0',
  yaml text NOT NULL DEFAULT '',
  created_at timestamptz NOT NULL DEFAULT now(),
  updated_at timestamptz NOT NULL DEFAULT now()
);

ALTER TABLE policies ENABLE ROW LEVEL SECURITY;

CREATE POLICY "Authenticated users can read policies"
  ON policies FOR SELECT
  TO authenticated
  USING (auth.uid() IS NOT NULL);

CREATE POLICY "Authenticated users can insert policies"
  ON policies FOR INSERT
  TO authenticated
  WITH CHECK (auth.uid() IS NOT NULL);

CREATE POLICY "Authenticated users can update policies"
  ON policies FOR UPDATE
  TO authenticated
  USING (auth.uid() IS NOT NULL)
  WITH CHECK (auth.uid() IS NOT NULL);

CREATE POLICY "Authenticated users can delete policies"
  ON policies FOR DELETE
  TO authenticated
  USING (auth.uid() IS NOT NULL);

-- Policy versions table
CREATE TABLE IF NOT EXISTS policy_versions (
  id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
  policy_id uuid NOT NULL REFERENCES policies(id) ON DELETE CASCADE,
  version text NOT NULL,
  yaml text NOT NULL DEFAULT '',
  changelog text NOT NULL DEFAULT '',
  created_by uuid REFERENCES auth.users(id),
  created_at timestamptz NOT NULL DEFAULT now()
);

ALTER TABLE policy_versions ENABLE ROW LEVEL SECURITY;

CREATE POLICY "Authenticated users can read policy versions"
  ON policy_versions FOR SELECT
  TO authenticated
  USING (auth.uid() IS NOT NULL);

CREATE POLICY "Authenticated users can insert policy versions"
  ON policy_versions FOR INSERT
  TO authenticated
  WITH CHECK (auth.uid() IS NOT NULL);

-- Groups table
CREATE TABLE IF NOT EXISTS groups (
  id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
  name text UNIQUE NOT NULL,
  description text NOT NULL DEFAULT '',
  policy_id uuid REFERENCES policies(id) ON DELETE SET NULL,
  created_at timestamptz NOT NULL DEFAULT now(),
  updated_at timestamptz NOT NULL DEFAULT now()
);

ALTER TABLE groups ENABLE ROW LEVEL SECURITY;

CREATE POLICY "Authenticated users can read groups"
  ON groups FOR SELECT
  TO authenticated
  USING (auth.uid() IS NOT NULL);

CREATE POLICY "Authenticated users can insert groups"
  ON groups FOR INSERT
  TO authenticated
  WITH CHECK (auth.uid() IS NOT NULL);

CREATE POLICY "Authenticated users can update groups"
  ON groups FOR UPDATE
  TO authenticated
  USING (auth.uid() IS NOT NULL)
  WITH CHECK (auth.uid() IS NOT NULL);

CREATE POLICY "Authenticated users can delete groups"
  ON groups FOR DELETE
  TO authenticated
  USING (auth.uid() IS NOT NULL);

-- Users table (synced from Open WebUI)
CREATE TABLE IF NOT EXISTS users (
  id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
  owui_id text UNIQUE NOT NULL,
  username text NOT NULL,
  email text NOT NULL DEFAULT '',
  owui_role text NOT NULL DEFAULT 'user' CHECK (owui_role IN ('admin', 'user', 'pending')),
  group_id uuid REFERENCES groups(id) ON DELETE SET NULL,
  synced_at timestamptz NOT NULL DEFAULT now()
);

ALTER TABLE users ENABLE ROW LEVEL SECURITY;

CREATE POLICY "Authenticated users can read users"
  ON users FOR SELECT
  TO authenticated
  USING (auth.uid() IS NOT NULL);

CREATE POLICY "Authenticated users can insert users"
  ON users FOR INSERT
  TO authenticated
  WITH CHECK (auth.uid() IS NOT NULL);

CREATE POLICY "Authenticated users can update users"
  ON users FOR UPDATE
  TO authenticated
  USING (auth.uid() IS NOT NULL)
  WITH CHECK (auth.uid() IS NOT NULL);

CREATE POLICY "Authenticated users can delete users"
  ON users FOR DELETE
  TO authenticated
  USING (auth.uid() IS NOT NULL);

-- Sandboxes table
CREATE TABLE IF NOT EXISTS sandboxes (
  id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
  name text UNIQUE NOT NULL,
  user_id uuid REFERENCES users(id) ON DELETE SET NULL,
  state text NOT NULL DEFAULT 'POOL' CHECK (state IN ('POOL', 'WARMING', 'READY', 'ACTIVE', 'SUSPENDED', 'DESTROYED')),
  policy_id uuid REFERENCES policies(id) ON DELETE SET NULL,
  internal_ip text NOT NULL DEFAULT '',
  image_tag text NOT NULL DEFAULT 'shellguard-sandbox:slim',
  gpu_enabled boolean NOT NULL DEFAULT false,
  cpu_usage real NOT NULL DEFAULT 0,
  memory_usage real NOT NULL DEFAULT 0,
  disk_usage real NOT NULL DEFAULT 0,
  network_io real NOT NULL DEFAULT 0,
  created_at timestamptz NOT NULL DEFAULT now(),
  last_active_at timestamptz NOT NULL DEFAULT now(),
  suspended_at timestamptz,
  destroyed_at timestamptz
);

CREATE INDEX IF NOT EXISTS idx_sandboxes_state ON sandboxes(state);
CREATE INDEX IF NOT EXISTS idx_sandboxes_user_id ON sandboxes(user_id);

ALTER TABLE sandboxes ENABLE ROW LEVEL SECURITY;

CREATE POLICY "Authenticated users can read sandboxes"
  ON sandboxes FOR SELECT
  TO authenticated
  USING (auth.uid() IS NOT NULL);

CREATE POLICY "Authenticated users can insert sandboxes"
  ON sandboxes FOR INSERT
  TO authenticated
  WITH CHECK (auth.uid() IS NOT NULL);

CREATE POLICY "Authenticated users can update sandboxes"
  ON sandboxes FOR UPDATE
  TO authenticated
  USING (auth.uid() IS NOT NULL)
  WITH CHECK (auth.uid() IS NOT NULL);

CREATE POLICY "Authenticated users can delete sandboxes"
  ON sandboxes FOR DELETE
  TO authenticated
  USING (auth.uid() IS NOT NULL);

-- Policy assignments table
CREATE TABLE IF NOT EXISTS policy_assignments (
  id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
  entity_type text NOT NULL CHECK (entity_type IN ('user', 'group', 'role')),
  entity_id text NOT NULL,
  policy_id uuid NOT NULL REFERENCES policies(id) ON DELETE CASCADE,
  priority integer NOT NULL DEFAULT 0,
  created_by uuid REFERENCES auth.users(id),
  created_at timestamptz NOT NULL DEFAULT now()
);

CREATE INDEX IF NOT EXISTS idx_policy_assignments_entity ON policy_assignments(entity_type, entity_id);

ALTER TABLE policy_assignments ENABLE ROW LEVEL SECURITY;

CREATE POLICY "Authenticated users can read policy assignments"
  ON policy_assignments FOR SELECT
  TO authenticated
  USING (auth.uid() IS NOT NULL);

CREATE POLICY "Authenticated users can insert policy assignments"
  ON policy_assignments FOR INSERT
  TO authenticated
  WITH CHECK (auth.uid() IS NOT NULL);

CREATE POLICY "Authenticated users can update policy assignments"
  ON policy_assignments FOR UPDATE
  TO authenticated
  USING (auth.uid() IS NOT NULL)
  WITH CHECK (auth.uid() IS NOT NULL);

CREATE POLICY "Authenticated users can delete policy assignments"
  ON policy_assignments FOR DELETE
  TO authenticated
  USING (auth.uid() IS NOT NULL);

-- Audit log table
CREATE TABLE IF NOT EXISTS audit_log (
  id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
  timestamp timestamptz NOT NULL DEFAULT now(),
  event_type text NOT NULL,
  category text NOT NULL CHECK (category IN ('enforcement', 'lifecycle', 'admin')),
  user_id uuid REFERENCES users(id) ON DELETE SET NULL,
  sandbox_id uuid REFERENCES sandboxes(id) ON DELETE SET NULL,
  details jsonb NOT NULL DEFAULT '{}',
  source_ip text NOT NULL DEFAULT ''
);

CREATE INDEX IF NOT EXISTS idx_audit_log_timestamp ON audit_log(timestamp DESC);
CREATE INDEX IF NOT EXISTS idx_audit_log_category ON audit_log(category);
CREATE INDEX IF NOT EXISTS idx_audit_log_user_id ON audit_log(user_id);

ALTER TABLE audit_log ENABLE ROW LEVEL SECURITY;

CREATE POLICY "Authenticated users can read audit log"
  ON audit_log FOR SELECT
  TO authenticated
  USING (auth.uid() IS NOT NULL);

CREATE POLICY "Authenticated users can insert audit log"
  ON audit_log FOR INSERT
  TO authenticated
  WITH CHECK (auth.uid() IS NOT NULL);

-- System config table
CREATE TABLE IF NOT EXISTS system_config (
  key text PRIMARY KEY,
  value jsonb NOT NULL DEFAULT '{}',
  updated_at timestamptz NOT NULL DEFAULT now(),
  updated_by uuid REFERENCES auth.users(id)
);

ALTER TABLE system_config ENABLE ROW LEVEL SECURITY;

CREATE POLICY "Authenticated users can read system config"
  ON system_config FOR SELECT
  TO authenticated
  USING (auth.uid() IS NOT NULL);

CREATE POLICY "Authenticated users can insert system config"
  ON system_config FOR INSERT
  TO authenticated
  WITH CHECK (auth.uid() IS NOT NULL);

CREATE POLICY "Authenticated users can update system config"
  ON system_config FOR UPDATE
  TO authenticated
  USING (auth.uid() IS NOT NULL)
  WITH CHECK (auth.uid() IS NOT NULL);
