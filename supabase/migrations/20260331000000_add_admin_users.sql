-- Admin users table for local (non-Supabase) authentication.
CREATE TABLE IF NOT EXISTS admin_users (
    id UUID PRIMARY KEY,
    email TEXT UNIQUE NOT NULL,
    password_hash TEXT NOT NULL,
    created_at TIMESTAMPTZ NOT NULL DEFAULT now()
);
