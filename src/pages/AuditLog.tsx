import { useState, useEffect, useCallback, useRef } from 'react';
import {
  FileText,
  Search,
  Download,
  ChevronDown,
  ChevronUp,
  Calendar,
  Radio,
  Circle,
  Bookmark,
  Trash2,
  Plus,
} from 'lucide-react';
import * as ds from '../lib/dataService';
import { useSupabaseRealtime } from '../hooks/useSupabaseQuery';
import { useFilterPresets } from '../hooks/useFilterPresets';
import { Tabs } from '../components/ui/Tabs';
import { Badge } from '../components/ui/Badge';
import { Modal } from '../components/ui/Modal';
import { LoadingState, EmptyState } from '../components/ui/EmptyState';
import { formatTimestamp } from '../lib/utils';
import type { AuditLogEntry, AuditCategory, AuditFilterPreset } from '../types';

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
  const [streamingEnabled, setStreamingEnabled] = useState(false);
  const [bufferedCount, setBufferedCount] = useState(0);
  const [realtimeNewIds, setRealtimeNewIds] = useState<Set<string>>(new Set());
  const bufferedEntriesRef = useRef<AuditLogEntry[]>([]);
  const listTopRef = useRef<HTMLDivElement>(null);
  const newIdTimersRef = useRef<Map<string, ReturnType<typeof setTimeout>>>(new Map());
  const isScrolledToTopRef = useRef(true);

  const { presets, savePreset, deletePreset } = useFilterPresets();
  const [presetDropdownOpen, setPresetDropdownOpen] = useState(false);
  const [saveModalOpen, setSaveModalOpen] = useState(false);
  const [presetName, setPresetName] = useState('');
  const [activePresetId, setActivePresetId] = useState<string | null>(null);
  const presetDropdownRef = useRef<HTMLDivElement>(null);
  const applyingPresetRef = useRef(false);

  const isPaused = expandedId !== null || search.length > 0;

  const fetchEntries = useCallback(async () => {
    setLoading(true);
    const since = new Date(Date.now() - DATE_PRESETS[datePreset].ms).toISOString();

    const result = await ds.getAuditLog({ category: activeTab, since, limit: 200 });
    setEntries(result.data?.items || []);
    setLoading(false);
  }, [activeTab, datePreset]);

  const fetchCounts = useCallback(async () => {
    const since = new Date(Date.now() - DATE_PRESETS[datePreset].ms).toISOString();
    const categories: AuditCategory[] = ['enforcement', 'lifecycle', 'admin'];

    const results = await Promise.all(
      categories.map((cat) => ds.getAuditLogCount(cat, since))
    );

    setCounts({
      enforcement: results[0].data || 0,
      lifecycle: results[1].data || 0,
      admin: results[2].data || 0,
    });
  }, [datePreset]);

  useEffect(() => { fetchEntries(); }, [fetchEntries]);
  useEffect(() => { fetchCounts(); }, [fetchCounts]);

  // Keep refs for realtime callback so it always sees current filter state
  const activeTabRef = useRef(activeTab);
  const datePresetRef = useRef(datePreset);
  const streamingEnabledRef = useRef(streamingEnabled);
  const isPausedRef = useRef(isPaused);
  useEffect(() => { activeTabRef.current = activeTab; }, [activeTab]);
  useEffect(() => { datePresetRef.current = datePreset; }, [datePreset]);
  useEffect(() => { streamingEnabledRef.current = streamingEnabled; }, [streamingEnabled]);
  useEffect(() => { isPausedRef.current = isPaused; }, [isPaused]);

  const markNewEntry = useCallback((id: string) => {
    setRealtimeNewIds((prev) => new Set(prev).add(id));
    const timer = setTimeout(() => {
      setRealtimeNewIds((prev) => {
        const next = new Set(prev);
        next.delete(id);
        return next;
      });
      newIdTimersRef.current.delete(id);
    }, 2000);
    newIdTimersRef.current.set(id, timer);
  }, []);

  const flushBuffer = useCallback(() => {
    const buffered = bufferedEntriesRef.current;
    if (buffered.length === 0) return;
    bufferedEntriesRef.current = [];
    setBufferedCount(0);

    setEntries((prev) => {
      const existingIds = new Set(prev.map((e) => e.id));
      const newEntries = buffered.filter((e) => !existingIds.has(e.id));
      return [...newEntries, ...prev].slice(0, 200);
    });

    for (const entry of buffered) {
      markNewEntry(entry.id);
    }
  }, [markNewEntry]);

  const handleRealtimeInsert = useCallback((entry: AuditLogEntry) => {
    if (!entry || !entry.id) return;

    // Always update counts
    setCounts((prev) => ({
      ...prev,
      [entry.category]: (prev[entry.category] || 0) + 1,
    }));

    // Only process entries matching the active category
    if (entry.category !== activeTabRef.current) return;

    // Check if entry falls within the current date range
    const since = Date.now() - DATE_PRESETS[datePresetRef.current].ms;
    if (new Date(entry.timestamp).getTime() < since) return;

    // When streaming is off, prepend immediately (original behavior)
    if (!streamingEnabledRef.current) {
      setEntries((prev) => {
        if (prev.some((e) => e.id === entry.id)) return prev;
        return [entry, ...prev].slice(0, 200);
      });
      return;
    }

    // When streaming is on but paused or scrolled away, buffer
    if (isPausedRef.current || !isScrolledToTopRef.current) {
      bufferedEntriesRef.current.push(entry);
      setBufferedCount((prev) => prev + 1);
      return;
    }

    // Streaming on, not paused, at top — prepend with highlight
    setEntries((prev) => {
      if (prev.some((e) => e.id === entry.id)) return prev;
      return [entry, ...prev].slice(0, 200);
    });
    markNewEntry(entry.id);
  }, [markNewEntry]);

  const { status: realtimeStatus } = useSupabaseRealtime<AuditLogEntry>('audit_log', handleRealtimeInsert);

  // Flush buffer when unpaused
  useEffect(() => {
    if (!isPaused && streamingEnabled) {
      flushBuffer();
    }
  }, [isPaused, streamingEnabled, flushBuffer]);

  // IntersectionObserver for auto-scroll awareness
  useEffect(() => {
    if (!listTopRef.current) return;
    const observer = new IntersectionObserver(
      ([entry]) => { isScrolledToTopRef.current = entry.isIntersecting; },
      { threshold: 0.1 }
    );
    observer.observe(listTopRef.current);
    return () => observer.disconnect();
  }, []);

  // Cleanup highlight timers on unmount
  useEffect(() => {
    const timers = newIdTimersRef.current;
    return () => {
      for (const timer of timers.values()) {
        clearTimeout(timer);
      }
    };
  }, []);

  // Clear activePresetId when filters change manually
  useEffect(() => {
    if (applyingPresetRef.current) {
      applyingPresetRef.current = false;
      return;
    }
    setActivePresetId(null);
  }, [activeTab, datePreset, search]);

  // Close dropdown on outside click
  useEffect(() => {
    if (!presetDropdownOpen) return;
    const handleClick = (e: MouseEvent) => {
      if (presetDropdownRef.current && !presetDropdownRef.current.contains(e.target as Node)) {
        setPresetDropdownOpen(false);
      }
    };
    document.addEventListener('mousedown', handleClick);
    return () => document.removeEventListener('mousedown', handleClick);
  }, [presetDropdownOpen]);

  const handleApplyPreset = (preset: AuditFilterPreset) => {
    applyingPresetRef.current = true;
    const dateIndex = DATE_PRESETS.findIndex((p) => p.ms === preset.datePresetMs);
    setActiveTab(preset.category);
    setDatePreset(dateIndex >= 0 ? dateIndex : 0);
    setSearch(preset.search);
    setActivePresetId(preset.id);
    setPresetDropdownOpen(false);
  };

  const handleSavePreset = () => {
    if (!presetName.trim()) return;
    savePreset({
      name: presetName.trim(),
      category: activeTab,
      datePresetMs: DATE_PRESETS[datePreset].ms,
      search,
    });
    setPresetName('');
    setSaveModalOpen(false);
  };

  const handleDeletePreset = (id: string) => {
    deletePreset(id);
    if (activePresetId === id) setActivePresetId(null);
  };

  const activePresetName = presets.find((p) => p.id === activePresetId)?.name;

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
        <div className="relative" ref={presetDropdownRef}>
          <button
            onClick={() => setPresetDropdownOpen((prev) => !prev)}
            className={`px-3 py-2 text-xs font-medium rounded-lg border transition-colors flex items-center gap-1.5 ${
              activePresetId
                ? 'bg-teal-50 text-teal-700 border-teal-200'
                : 'bg-white text-zinc-600 border-zinc-200 hover:bg-zinc-50'
            }`}
          >
            <Bookmark className="w-3 h-3" />
            {activePresetName || 'Presets'}
            <ChevronDown className="w-3 h-3" />
          </button>
          {presetDropdownOpen && (
            <div className="absolute top-full left-0 mt-1 z-20 w-64 bg-white border border-zinc-200 rounded-lg shadow-lg overflow-hidden">
              {presets.length === 0 ? (
                <div className="px-4 py-3 text-xs text-zinc-400 text-center">No saved presets</div>
              ) : (
                <div className="max-h-48 overflow-y-auto divide-y divide-zinc-50">
                  {presets.map((preset) => (
                    <div
                      key={preset.id}
                      className="flex items-center gap-2 px-3 py-2 hover:bg-zinc-50 cursor-pointer group"
                      onClick={() => handleApplyPreset(preset)}
                    >
                      <div className="flex-1 min-w-0">
                        <div className="text-xs font-medium text-zinc-700 truncate">{preset.name}</div>
                        <div className="text-[11px] text-zinc-400 truncate">
                          {preset.category} / {DATE_PRESETS.find((p) => p.ms === preset.datePresetMs)?.label || 'Custom'}
                          {preset.search && ` / "${preset.search}"`}
                        </div>
                      </div>
                      <button
                        onClick={(e) => {
                          e.stopPropagation();
                          handleDeletePreset(preset.id);
                        }}
                        className="p-1 rounded text-zinc-300 hover:text-red-500 hover:bg-red-50 opacity-0 group-hover:opacity-100 transition-all"
                      >
                        <Trash2 className="w-3 h-3" />
                      </button>
                    </div>
                  ))}
                </div>
              )}
              <div className="border-t border-zinc-100">
                <button
                  onClick={() => {
                    setPresetDropdownOpen(false);
                    setSaveModalOpen(true);
                  }}
                  className="w-full px-3 py-2 text-xs text-teal-600 hover:bg-teal-50 transition-colors flex items-center gap-1.5"
                >
                  <Plus className="w-3 h-3" />
                  Save current filters...
                </button>
              </div>
            </div>
          )}
        </div>

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

        <button
          onClick={() => {
            setStreamingEnabled((prev) => {
              if (prev) {
                // Turning off: clear buffer
                bufferedEntriesRef.current = [];
                setBufferedCount(0);
              } else {
                // Turning on: clear stale highlights
                setRealtimeNewIds(new Set());
              }
              return !prev;
            });
          }}
          className={`px-3 py-2 text-xs font-medium rounded-lg border transition-colors flex items-center gap-1.5 ${
            streamingEnabled
              ? 'bg-teal-600 text-white border-teal-600'
              : 'bg-white text-zinc-600 border-zinc-200 hover:bg-zinc-50'
          }`}
        >
          <Radio className="w-3 h-3" />
          Live
          {streamingEnabled && realtimeStatus === 'SUBSCRIBED' && (
            <Circle className="w-1.5 h-1.5 fill-emerald-300 text-emerald-300 animate-pulse" />
          )}
          {streamingEnabled && realtimeStatus === 'CHANNEL_ERROR' && (
            <Circle className="w-1.5 h-1.5 fill-red-400 text-red-400" />
          )}
          {streamingEnabled && isPaused && (
            <span className="text-[10px] opacity-75">(paused)</span>
          )}
        </button>

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

      <div ref={listTopRef} />
      <div className="bg-white rounded-xl border border-zinc-200 overflow-hidden">
        {bufferedCount > 0 && (
          <button
            onClick={flushBuffer}
            className="w-full py-2 bg-teal-50 border-b border-teal-200 text-teal-700 text-xs font-medium text-center hover:bg-teal-100 transition-colors"
          >
            {bufferedCount} new event{bufferedCount !== 1 ? 's' : ''} — click to show
          </button>
        )}
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
                        className={`hover:bg-zinc-50/50 transition-colors cursor-pointer ${realtimeNewIds.has(entry.id) ? 'audit-row-new' : ''}`}
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

      <Modal
        open={saveModalOpen}
        onClose={() => { setSaveModalOpen(false); setPresetName(''); }}
        title="Save Filter Preset"
        actions={
          <>
            <button
              onClick={() => { setSaveModalOpen(false); setPresetName(''); }}
              className="px-4 py-2 text-sm text-zinc-600 hover:bg-zinc-100 rounded-lg transition-colors"
            >
              Cancel
            </button>
            <button
              onClick={handleSavePreset}
              disabled={!presetName.trim()}
              className="px-4 py-2 text-sm font-medium text-white bg-teal-600 rounded-lg hover:bg-teal-700 transition-colors disabled:opacity-40 disabled:cursor-not-allowed"
            >
              Save
            </button>
          </>
        }
      >
        <div className="space-y-4">
          <div>
            <label className="block text-sm font-medium text-zinc-700 mb-1">Preset name</label>
            <input
              type="text"
              value={presetName}
              onChange={(e) => setPresetName(e.target.value)}
              onKeyDown={(e) => { if (e.key === 'Enter') handleSavePreset(); }}
              placeholder="e.g. Recent denials"
              autoFocus
              className="w-full px-3 py-2 border border-zinc-200 rounded-lg text-sm focus:outline-none focus:ring-2 focus:ring-teal-500/20 focus:border-teal-400"
            />
          </div>
          <div className="bg-zinc-50 rounded-lg px-3 py-2 text-xs text-zinc-500 space-y-1">
            <div><span className="font-medium text-zinc-600">Category:</span> {activeTab}</div>
            <div><span className="font-medium text-zinc-600">Date range:</span> {DATE_PRESETS[datePreset].label}</div>
            <div><span className="font-medium text-zinc-600">Search:</span> {search || '(none)'}</div>
          </div>
        </div>
      </Modal>
    </div>
  );
}
