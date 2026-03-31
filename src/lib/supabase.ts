import { createClient, SupabaseClient } from '@supabase/supabase-js';
import { SUPABASE_URL, SUPABASE_ANON_KEY, BACKEND_MODE } from './config';

/**
 * When running in local mode (no Supabase env vars) we create a dummy client
 * pointed at a non-routable URL.  It is never actually used — all data access
 * goes through the backend API client instead.
 */
export const supabase: SupabaseClient = createClient(
  SUPABASE_URL || 'http://localhost:0',
  SUPABASE_ANON_KEY || 'unused',
);

export const isLocalMode = BACKEND_MODE === 'local';
