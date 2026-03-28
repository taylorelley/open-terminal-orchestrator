import { useState, useEffect, useCallback, useRef } from 'react';
import {
  FileText,
  Search,
  Download,
  ChevronDown,
  ChevronUp,
  Calendar,
} from 'lucide-react';
import { supabase } from '../lib/supabase';
import { useSupabaseRealtime } from '../hooks/useSupabaseQuery';
import { Tabs } from '../components/ui/Tabs';
import { Badge } from '../components/ui/Badge';
import { LoadingState, EmptyState } from '../components/ui/EmptyState';
import { formatTimestamp } from '../lib/utils';
import type { AuditLogEntry, AuditCategory } from '../types';

const DATE_PRESETS = [
  { label: 'Last hour', ms: 3600000 },
  { label: 'Last 24h', ms: 86400000 },
  { label: 'Last 7d', ms: 604800000 },
  { label: 'Last 30d', ms: 2592000000 },
];

export default function AuditLog() {
  const [activeTab, setActiveTab] = useState<AuditCategory>('enforcement');
  const [entries, setEntries] = useState<AuditLogEntry[]>([]);
  const [loading, setLoading] = useState(true);
  const [search, setSearch] = useState('');
  const [datePreset, setDatePreset] = useState(1);
  const [expandedId, setExpandedId] = useState<string | null>(null);
  const [counts, setCounts] = useState({ enforcement: 0, lifecycle: 0, admin: 0 });

  const fetchEntries = useCallback(async () => {
    setLoading(true);
    const since = new Date(Date.now() - DATE_PRESETS[datePreset].ms).toISOString();

    const { data } = await supabase
      .from('audit_log')
      .select('*, user:users(*), sandbox:sandboxes(*)')
      .eq('category', activeTab)
      .gte('timestamp', since)
      .order('timestamp', { ascending: false })
      .limit(200);

    setEntries((data || []) as AuditLogEntry[]);
    setLoading(false);
  }, [activeTab, datePreset]);

  const fetchCounts = useCallback(async () => {
    const since = new Date(Date.now() - DATE_PRESETS[datePreset].ms).toISOString();
    const categories: AuditCategory[] = ['enforcement', 'lifecycle', 'admin'];

    const results = await Promise.all(
      categories.map((cat) =>
        supabase
          .from('audit_log')
          .select('id', { count: 'exact', head: true })
          .eq('category', cat)
          .gte('timestamp', since)
      )
    );

    setCounts({
      enforcement: results[0].count || 0,
      lifecycle: results[1].count || 0,
      admin: results[2].count || 0,
    });
  }, [datePreset]);

  useEffect(() => { fetchEntries(); }, [fetchEntries]);
  useEffect(() => { fetchCounts(); }, [fetchCounts]);

  // Keep refs for realtime callback so it always sees current filter state
  const activeTabRef = useRef(activeTab);
  const datePresetRef = useRef(datePreset);
  useEffect(() => { activeTabRef.current = activeTab; }, [activeTab]);
  useEffect(() => { datePresetRef.current = datePreset; }, [datePreset]);

  const handleRealtimeInsert = useCallback((entry: AuditLogEntry) => {
    if (!entry || !entry.id) return;

    // Only prepend if the entry matches the active category
    if (entry.category !== activeTabRef.current) {
      // Still update counts for other categories
      setCounts((prev) => ({
        ...prev,
        [entry.category]: (prev[entry.category] || 0) + 1,
      }));
      return;
    }

    // Check if entry falls within the current date range
    const since = Date.now() - DATE_PRESETS[datePresetRef.current].ms;
    if (new Date(entry.timestamp).getTime() < since) return;

    // Prepend, deduplicating by id
    setEntries((prev) => {
      if (prev.some((e) => e.id === entry.id)) return prev;
      return [entry, ...prev].slice(0, 200);
    });

    // Update count for active category
    setCounts((prev) => ({
      ...prev,
      [entry.category]: (prev[entry.category] || 0) + 1,
    }));
  }, []);

  useSupabaseRealtime<AuditLogEntry>('audit_log', handleRealtimeInsert);

  const filtered = entries.filter((e) => {
    if (!search) return true;
    const s = search.toLowerCase();
    return (
      e.event_type.toLowerCase().includes(s) ||
      e.user?.username?.toLowerCase().includes(s) ||
      e.sandbox?.name?.toLowerCase().includes(s) ||
      JSON.stringify(e.details).toLowerCase().includes(s)
    );
  });

  const handleExport = (format: 'csv' | 'json') => {
    let content: string;
    let filename: string;
    let mime: string;

    if (format === 'json') {
      content = JSON.stringify(filtered, null, 2);
      filename = `audit-${activeTab}-${Date.now()}.json`;
      mime = 'application/json';
    } else {
      const headers = ['timestamp', 'event_type', 'category', 'user', 'sandbox', 'details', 'source_ip'];
      const rows = filtered.map((e) => [
        e.timestamp,
        e.event_type,
        e.category,
        e.user?.username || '',
        e.sandbox?.name || '',
        JSON.stringify(e.details),
        e.source_ip,
      ]);
      content = [headers.join(','), ...rows.map((r) => r.map((v) => `"${v}"`).join(','))].join('\n');
      filename = `audit-${activeTab}-${Date.now()}.csv`;
      mime = 'text/csv';
    }

    const blob = new Blob([content], { type: mime });
    const url = URL.createObjectURL(blob);
    const a = document.createElement('a');
    a.href = url;
    a.download = filename;
    a.click();
    URL.revokeObjectURL(url);
  };

  const tabs = [
    { id: 'enforcement', label: 'Enforcement Events', count: counts.enforcement },
    { id: 'lifecycle', label: 'Lifecycle Events', count: counts.lifecycle },
    { id: 'admin', label: 'Admin Actions', count: counts.admin },
  ];

  return (
    <div className="space-y-4">
      <Tabs
        tabs={tabs}
        activeTab={activeTab}
        onChange={(id) => setActiveTab(id as AuditCategory)}
      />

      <div className="flex items-center gap-3 flex-wrap">
        <div className="relative flex-1 max-w-sm">
          <Search className="absolute left-3 top-1/2 -translate-y-1/2 w-4 h-4 text-zinc-400" />
          <input
            type="text"
            value={search}
            onChange={(e) => setSearch(e.target.value)}
            placeholder="Search events..."
            className="w-full pl-9 pr-3 py-2 bg-white border border-zinc-200 rounded-lg text-sm focus:outline-none focus:ring-2 focus:ring-teal-500/20 focus:border-teal-400"
          />
        </div>

        <div className="flex items-center gap-1 bg-white border border-zinc-200 rounded-lg p-0.5">
          {DATE_PRESETS.map((preset, i) => (
            <button
              key={i}
              onClick={() => setDatePreset(i)}
              className={`px-3 py-1.5 text-xs font-medium rounded-md transition-colors ${
                datePreset === i ? 'bg-zinc-900 text-white' : 'text-zinc-500 hover:text-zinc-700'
              }`}
            >
              {preset.label}
            </button>
          ))}
        </div>

        <div className="flex gap-1 ml-auto">
          <button
            onClick={() => handleExport('csv')}
            className="px-3 py-2 text-xs text-zinc-600 bg-white border border-zinc-200 rounded-lg hover:bg-zinc-50 transition-colors flex items-center gap-1"
          >
            <Download className="w-3 h-3" /> CSV
          </button>
          <button
            onClick={() => handleExport('json')}
            className="px-3 py-2 text-xs text-zinc-600 bg-white border border-zinc-200 rounded-lg hover:bg-zinc-50 transition-colors flex items-center gap-1"
          >
            <Download className="w-3 h-3" /> JSON
          </button>
        </div>
      </div>

      <div className="bg-white rounded-xl border border-zinc-200 overflow-hidden">
        {loading ? (
          <LoadingState rows={10} />
        ) : filtered.length === 0 ? (
          <EmptyState
            icon={<FileText className="w-8 h-8" />}
            title="No events found"
            description="Try adjusting your date range or search query."
          />
        ) : (
          <div className="overflow-x-auto">
            <table className="w-full">
              <thead>
                <tr className="text-left text-xs text-zinc-500 border-b border-zinc-100">
                  <th className="px-5 py-3 font-medium w-8" />
                  <th className="px-5 py-3 font-medium">Timestamp</th>
                  <th className="px-5 py-3 font-medium">Event</th>
                  {activeTab === 'enforcement' && (
                    <>
                      <th className="px-5 py-3 font-medium">User</th>
                      <th className="px-5 py-3 font-medium">Destination</th>
                      <th className="px-5 py-3 font-medium">Method</th>
                      <th className="px-5 py-3 font-medium">Rule</th>
                    </>
                  )}
                  {activeTab === 'lifecycle' && (
                    <>
                      <th className="px-5 py-3 font-medium">Sandbox</th>
                      <th className="px-5 py-3 font-medium">User</th>
                      <th className="px-5 py-3 font-medium">Trigger</th>
                    </>
                  )}
                  {activeTab === 'admin' && (
                    <>
                      <th className="px-5 py-3 font-medium">Admin</th>
                      <th className="px-5 py-3 font-medium">Details</th>
                      <th className="px-5 py-3 font-medium">Source IP</th>
                    </>
                  )}
                </tr>
              </thead>
              <tbody className="divide-y divide-zinc-50">
                {filtered.map((entry) => {
                  const details = entry.details as Record<string, string>;
                  const isExpanded = expandedId === entry.id;
                  return (
                    <>
                      <tr
                        key={entry.id}
                        className="hover:bg-zinc-50/50 transition-colors cursor-pointer"
                        onClick={() => setExpandedId(isExpanded ? null : entry.id)}
                      >
                        <td className="pl-5 py-3">
                          {isExpanded ? (
                            <ChevronUp className="w-3.5 h-3.5 text-zinc-400" />
                          ) : (
                            <ChevronDown className="w-3.5 h-3.5 text-zinc-400" />
                          )}
                        </td>
                        <td className="px-5 py-3">
                          <div className="flex items-center gap-1.5">
                            <Calendar className="w-3 h-3 text-zinc-400" />
                            <span className="text-xs text-zinc-600 whitespace-nowrap">{formatTimestamp(entry.timestamp)}</span>
                          </div>
                        </td>
                        <td className="px-5 py-3">
                          <Badge variant="event" value={entry.event_type}>{entry.event_type}</Badge>
                        </td>
                        {activeTab === 'enforcement' && (
                          <>
                            <td className="px-5 py-3 text-sm text-zinc-600">{entry.user?.username || '-'}</td>
                            <td className="px-5 py-3 text-xs text-zinc-600 font-mono">{details.destination || details.path || '-'}</td>
                            <td className="px-5 py-3">
                              {details.method && (
                                <span className="px-1.5 py-0.5 bg-zinc-100 text-zinc-600 text-[11px] rounded font-mono">
                                  {details.method}
                                </span>
                              )}
                            </td>
                            <td className="px-5 py-3 text-xs text-zinc-500 truncate max-w-[200px]">{details.rule || '-'}</td>
                          </>
                        )}
                        {activeTab === 'lifecycle' && (
                          <>
                            <td className="px-5 py-3 text-xs text-zinc-600 font-mono">{entry.sandbox?.name || '-'}</td>
                            <td className="px-5 py-3 text-sm text-zinc-600">{entry.user?.username || '-'}</td>
                            <td className="px-5 py-3 text-xs text-zinc-500">{details.trigger || '-'}</td>
                          </>
                        )}
                        {activeTab === 'admin' && (
                          <>
                            <td className="px-5 py-3 text-sm text-zinc-600">{details.admin || '-'}</td>
                            <td className="px-5 py-3 text-xs text-zinc-500 truncate max-w-[240px]">
                              {details.changes || details.setting || details.action || '-'}
                            </td>
                            <td className="px-5 py-3 text-xs text-zinc-400 font-mono">{entry.source_ip || '-'}</td>
                          </>
                        )}
                      </tr>
                      {isExpanded && (
                        <tr key={`${entry.id}-detail`}>
                          <td colSpan={8} className="px-5 py-3 bg-zinc-50">
                            <div className="rounded-lg bg-zinc-900 p-4 overflow-x-auto">
                              <pre className="text-xs text-zinc-300 font-mono whitespace-pre-wrap">
                                {JSON.stringify(entry.details, null, 2)}
                              </pre>
                            </div>
                            <div className="flex gap-4 mt-2 text-[11px] text-zinc-400">
                              <span>ID: {entry.id}</span>
                              <span>Source: {entry.source_ip || 'N/A'}</span>
                              <span>Time: {new Date(entry.timestamp).toISOString()}</span>
                            </div>
                          </td>
                        </tr>
                      )}
                    </>
                  );
                })}
              </tbody>
            </table>
          </div>
        )}
      </div>

      <div className="flex items-center justify-between text-xs text-zinc-400">
        <span>Showing {filtered.length} events</span>
        <span>{DATE_PRESETS[datePreset].label} window</span>
      </div>
    </div>
  );
}
