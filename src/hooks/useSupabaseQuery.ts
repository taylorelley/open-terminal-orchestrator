import { useEffect, useState, useCallback, useMemo } from 'react';
import { supabase } from '../lib/supabase';

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

    setLoading(false);
  }, [table, select, stableOrder, limit, stableFilters]);

  useEffect(() => {
    fetchData();
  }, [fetchData]);

  return { data, loading, error, refetch: fetchData };
}

export function useSupabaseRealtime<T>(
  table: string,
  callback: (payload: T) => void
): { status: string } {
  const [status, setStatus] = useState<string>('CONNECTING');

  useEffect(() => {
    const channel = supabase
      .channel(`realtime-${table}`)
      .on(
        'postgres_changes',
        { event: '*', schema: 'public', table },
        (payload) => {
          callback(payload.new as T);
        }
      )
      .subscribe((s) => {
        setStatus(s);
      });

    return () => {
      supabase.removeChannel(channel);
    };
  }, [table, callback]);

  return { status };
}
