/**
 * Runtime configuration derived from environment variables.
 *
 * When VITE_SUPABASE_URL is set the app operates in "supabase" mode and talks
 * directly to Supabase for data + auth.  Otherwise it falls back to "local"
 * mode where all data flows through the backend REST API and authentication
 * uses simple JWT tokens stored in localStorage.
 */

export const SUPABASE_URL = import.meta.env.VITE_SUPABASE_URL as string | undefined;
export const SUPABASE_ANON_KEY = import.meta.env.VITE_SUPABASE_ANON_KEY as string | undefined;

export const BACKEND_MODE: 'supabase' | 'local' = SUPABASE_URL ? 'supabase' : 'local';

export const API_BASE = '/admin/api';
