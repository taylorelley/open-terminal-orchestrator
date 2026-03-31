import { useEffect, useState, useCallback, useMemo, useRef } from 'react';
import { supabase, isLocalMode } from '../lib/supabase';
import { API_BASE } from '../lib/config';
import { getLocalToken } from '../lib/api';

interface QueryResult<T> {
  data: T[];
  loading: boolean;
  error: string | null;
  refetch: () => void;
}

interface QueryOptions {
  table: string;
  select?: string;
  order?: { column: string; ascending?: boolean };
  filters?: Array<{ column: string; operator: string; value: unknown }>;
  limit?: number;
}

/**
 * Map a QueryOptions object to backend REST API query params and fetch.
 *
 * The backend route naming convention is `/admin/api/{table}` for the main
 * resources.  This is a best-effort mapper — pages that need precise control
 * should use `dataService.ts` helpers directly.
 */
async function fetchViaApi<T>(opts: QueryOptions): Promise<T[]> {
  // Map table names to API paths.
  const tablePathMap: Record<string, string> = {
    sandboxes: '/sandboxes',
    policies: '/policies',
    policy_assignments: '/policies/assignments',
    policy_versions: '/policies/versions',
    users: '/users',
    groups: '/groups',
    audit_log: '/audit',
    system_config: '/config',
    metric_snapshots: '/metrics/history',
  };

  const path = tablePathMap[opts.table];
  if (!path) throw new Error(`No API mapping for table "${opts.table}"`);

  const q = new URLSearchParams();
  if (opts.filters) {
    for (const f of opts.filters) {
      if (f.operator === 'eq') q.set(f.column, String(f.value));
      else if (f.operator === 'neq') q.set(`${f.column}_ne`, String(f.value));
      else if (f.operator === 'in') q.set(`${f.column}_in`, (f.value as unknown[]).join(','));
      else if (f.operator === 'gte') q.set(`${f.column}_gte`, String(f.value));
      else if (f.operator === 'lte') q.set(`${f.column}_lte`, String(f.value));
    }
  }
  if (opts.order) q.set('order', `${opts.order.column}:${opts.order.ascending ? 'asc' : 'desc'}`);
  if (opts.limit) q.set('limit', String(opts.limit));

  const qs = q.toString();
  const headers: Record<string, string> = { 'Content-Type': 'application/json' };
  const token = getLocalToken();
  if (token) headers['Authorization'] = `Bearer ${token}`;

  const res = await fetch(`${API_BASE}${path}${qs ? `?${qs}` : ''}`, { headers });
  if (!res.ok) throw new Error(`API ${res.status}: ${res.statusText}`);
  const body = await res.json();

  // Backend may return { items: [...], total: N } or a plain array.
  if (Array.isArray(body)) return body as T[];
  if (body && Array.isArray(body.items)) return body.items as T[];
  return [];
}

export function useSupabaseQuery<T>({
  table,
  select = '*',
  order,
  filters,
  limit,
}: QueryOptions): QueryResult<T> {
  const [data, setData] = useState<T[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  const filtersKey = useMemo(() => JSON.stringify(filters), [filters]);
  const stableFilters = useMemo(
    () => filters,
    // eslint-disable-next-line react-hooks/exhaustive-deps
    [filtersKey],
  );
  const stableOrder = useMemo(
    () => order,
    // eslint-disable-next-line react-hooks/exhaustive-deps
    [order?.column, order?.ascending],
  );

  const fetchData = useCallback(async () => {
    setLoading(true);
    setError(null);

    try {
      if (isLocalMode) {
        const result = await fetchViaApi<T>({
          table,
          select,
          order: stableOrder,
          filters: stableFilters,
          limit,
        });
        setData(result);
      } else {
        let query = supabase.from(table).select(select);

        if (stableFilters) {
          for (const f of stableFilters) {
            if (f.operator === 'eq') query = query.eq(f.column, f.value);
            else if (f.operator === 'neq') query = query.neq(f.column, f.value);
            else if (f.operator === 'in') query = query.in(f.column, f.value as unknown[]);
            else if (f.operator === 'gte') query = query.gte(f.column, f.value);
            else if (f.operator === 'lte') query = query.lte(f.column, f.value);
          }
        }

        if (stableOrder) {
          query = query.order(stableOrder.column, { ascending: stableOrder.ascending ?? false });
        }

        if (limit) {
          query = query.limit(limit);
        }

        const { data: result, error: err } = await query;

        if (err) {
          setError(err.message);
        } else {
          setData((result as T[]) || []);
        }
      }
    } catch (e) {
      setError((e as Error).message);
    }

    setLoading(false);
  }, [table, select, stableOrder, limit, stableFilters]);

  useEffect(() => {
    fetchData();
  }, [fetchData]);

  return { data, loading, error, refetch: fetchData };
}

/**
 * In Supabase mode, subscribe to Postgres changes via Supabase Realtime.
 * In local mode, fall back to polling the backend API every 30 seconds.
 */
export function useSupabaseRealtime<T>(
  table: string,
  callback: (payload: T) => void
): { status: string } {
  const [status, setStatus] = useState<string>(isLocalMode ? 'POLLING' : 'CONNECTING');
  const callbackRef = useRef(callback);
  callbackRef.current = callback;

  useEffect(() => {
    if (isLocalMode) {
      // Polling fallback: call the API every 30 seconds and invoke callback
      // with the latest record.
      let active = true;
      const poll = async () => {
        try {
          const result = await fetchViaApi<T>({
            table,
            order: { column: 'timestamp', ascending: false },
            limit: 1,
          });
          if (active && result.length > 0) {
            callbackRef.current(result[0]);
          }
        } catch {
          // Silently ignore polling errors.
        }
      };

      const interval = setInterval(poll, 30_000);
      // Initial poll.
      poll();

      return () => {
        active = false;
        clearInterval(interval);
      };
    }

    // Supabase Realtime.
    const channel = supabase
      .channel(`realtime-${table}`)
      .on(
        'postgres_changes',
        { event: '*', schema: 'public', table },
        (payload) => {
          callbackRef.current(payload.new as T);
        }
      )
      .subscribe((s) => {
        setStatus(s);
      });

    return () => {
      supabase.removeChannel(channel);
    };
  }, [table]);

  return { status };
}
