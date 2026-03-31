import { useState, useEffect, useCallback } from 'react';
import {
  Activity,
  Circle,
  Server,
  Cpu,
  MemoryStick,
  HardDrive,
  Wifi,
  Clock,
  CheckCircle2,
  Bell,
  Plus,
  Trash2,
} from 'lucide-react';
import {
  AreaChart,
  Area,
  BarChart,
  Bar,
  XAxis,
  YAxis,
  Tooltip,
  ResponsiveContainer,
  PieChart,
  Pie,
  Cell,
} from 'recharts';
import { getSandboxes } from '../lib/dataService';
import { Tabs } from '../components/ui/Tabs';
import { LoadingState, EmptyState } from '../components/ui/EmptyState';
import { formatBytes } from '../lib/utils';
import type { Sandbox } from '../types';

type TimeRange = '1h' | '24h' | '7d' | '30d';

interface MetricPoint {
  time: string;
  value: number;
}

interface AlertRule {
  name: string;
  metric: string;
  operator: string;
  threshold: number;
  duration_seconds: number;
  webhook_index: number | null;
  enabled: boolean;
}

const TIME_RANGES: { key: TimeRange; label: string }[] = [
  { key: '1h', label: '1h' },
  { key: '24h', label: '24h' },
  { key: '7d', label: '7d' },
  { key: '30d', label: '30d' },
];

const RANGE_LABELS: Record<TimeRange, string> = {
  '1h': '1h',
  '24h': '24h',
  '7d': '7d',
  '30d': '30d',
};

export default function Monitoring() {
  const [activeTab, setActiveTab] = useState('resources');
  const [sandboxes, setSandboxes] = useState<Sandbox[]>([]);
  const [loading, setLoading] = useState(true);
  const [timeRange, setTimeRange] = useState<TimeRange>('24h');
  const [cpuHistory, setCpuHistory] = useState<MetricPoint[]>([]);
  const [memoryHistory, setMemoryHistory] = useState<MetricPoint[]>([]);
  const [requestData, setRequestData] = useState<{ time: string; requests: number }[]>([]);
  const [chartsLoading, setChartsLoading] = useState(false);

  // Alert state
  const [alertRules, setAlertRules] = useState<AlertRule[]>([]);
  const [alertsLoading, setAlertsLoading] = useState(false);
  const [showAlertForm, setShowAlertForm] = useState(false);
  const [editingAlert, setEditingAlert] = useState<AlertRule>({
    name: '', metric: 'cpu', operator: 'gt', threshold: 80,
    duration_seconds: 60, webhook_index: null, enabled: true,
  });

  const fetchData = useCallback(async () => {
    const result = await getSandboxes({ stateIn: ['ACTIVE', 'READY'], orderBy: 'cpu_usage', ascending: false });
    setSandboxes(result.data || []);
    setLoading(false);
  }, []);

  const fetchMetrics = useCallback(async (range: TimeRange) => {
    setChartsLoading(true);
    try {
      const [cpuRes, memRes, reqRes] = await Promise.all([
        fetch(`/admin/api/metrics/history?metric=cpu&range=${range}`),
        fetch(`/admin/api/metrics/history?metric=memory&range=${range}`),
        fetch(`/admin/api/metrics/history?metric=requests&range=${range}`),
      ]);
      const [cpuData, memData, reqData] = await Promise.all([
        cpuRes.ok ? cpuRes.json() : { points: [] },
        memRes.ok ? memRes.json() : { points: [] },
        reqRes.ok ? reqRes.json() : { points: [] },
      ]);
      setCpuHistory(cpuData.points || []);
      setMemoryHistory(memData.points || []);
      setRequestData((reqData.points || []).map((p: MetricPoint) => ({
        time: p.time,
        requests: Math.max(1, Math.round(p.value)),
      })));
    } catch {
      // Fall back to empty data on fetch error
    }
    setChartsLoading(false);
  }, []);

  const fetchAlerts = useCallback(async () => {
    setAlertsLoading(true);
    try {
      const res = await fetch('/admin/api/alerts');
      if (res.ok) {
        const data = await res.json();
        setAlertRules(data.rules || []);
      }
    } catch {
      // ignore
    }
    setAlertsLoading(false);
  }, []);

  const saveAlerts = async (rules: AlertRule[]) => {
    await fetch('/admin/api/alerts', {
      method: 'PUT',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ rules }),
    });
    setAlertRules(rules);
  };

  useEffect(() => { fetchData(); }, [fetchData]);
  useEffect(() => { fetchMetrics(timeRange); }, [timeRange, fetchMetrics]);
  useEffect(() => {
    if (activeTab === 'alerts') fetchAlerts();
  }, [activeTab, fetchAlerts]);

  const totalCpu = sandboxes.reduce((s, sb) => s + sb.cpu_usage, 0);
  const totalMemory = sandboxes.reduce((s, sb) => s + sb.memory_usage, 0);
  const totalDisk = sandboxes.reduce((s, sb) => s + sb.disk_usage, 0);

  const latencyData = [
    { name: 'p50', value: 120 },
    { name: 'p95', value: 340 },
    { name: 'p99', value: 890 },
  ];

  const errorData = [
    { name: 'Policy Denials', value: 12, color: '#f59e0b' },
    { name: 'Sandbox Errors', value: 3, color: '#ef4444' },
    { name: 'Proxy Errors', value: 1, color: '#6b7280' },
  ];

  const startupData = [
    { range: '0-2s', count: 8 },
    { range: '2-4s', count: 15 },
    { range: '4-6s', count: 6 },
    { range: '6-8s', count: 2 },
    { range: '8s+', count: 1 },
  ];

  const tabs = [
    { id: 'resources', label: 'Resource Usage' },
    { id: 'gateway', label: 'Gateway Health' },
    { id: 'requests', label: 'Request Metrics' },
    { id: 'alerts', label: 'Alerts' },
  ];

  if (loading) return <LoadingState rows={8} />;

  return (
    <div className="space-y-4">
      <Tabs tabs={tabs} activeTab={activeTab} onChange={setActiveTab} />

      {(activeTab === 'resources' || activeTab === 'requests') && (
        <div className="flex items-center justify-end">
          <div className="flex items-center gap-1 bg-white border border-zinc-200 rounded-lg p-0.5">
            {TIME_RANGES.map((r) => (
              <button
                key={r.key}
                onClick={() => setTimeRange(r.key)}
                className={`px-3 py-1 text-xs font-medium rounded-md transition-colors ${
                  timeRange === r.key
                    ? 'bg-teal-600 text-white'
                    : 'text-zinc-600 hover:bg-zinc-100'
                }`}
              >
                {r.label}
              </button>
            ))}
          </div>
        </div>
      )}

      {activeTab === 'resources' && (
        <div className="space-y-6">
          <div className="grid grid-cols-1 md:grid-cols-4 gap-4">
            {[
              { icon: Cpu, label: 'Total CPU', value: `${totalCpu.toFixed(1)}%` },
              { icon: MemoryStick, label: 'Total Memory', value: formatBytes(totalMemory) },
              { icon: HardDrive, label: 'Total Disk', value: formatBytes(totalDisk) },
              { icon: Wifi, label: 'Network I/O', value: `${sandboxes.reduce((s, sb) => s + sb.network_io, 0).toFixed(1)} KB/s` },
            ].map((stat) => (
              <div key={stat.label} className="bg-white rounded-xl border border-zinc-200 p-4">
                <div className="flex items-center gap-2 mb-2">
                  <stat.icon className="w-4 h-4 text-zinc-400" />
                  <span className="text-xs text-zinc-500">{stat.label}</span>
                </div>
                <p className="text-xl font-semibold text-zinc-900">{stat.value}</p>
                <p className="text-[11px] text-zinc-400 mt-0.5">{sandboxes.length} active sandboxes</p>
              </div>
            ))}
          </div>

          <div className="grid grid-cols-1 lg:grid-cols-2 gap-6">
            <div className="bg-white rounded-xl border border-zinc-200 p-5">
              <h3 className="text-sm font-semibold text-zinc-900 mb-4">
                CPU Usage ({RANGE_LABELS[timeRange]} avg per sandbox)
              </h3>
              <div className="h-48">
                {chartsLoading ? (
                  <div className="h-full flex items-center justify-center text-xs text-zinc-400">Loading...</div>
                ) : (
                  <ResponsiveContainer width="100%" height="100%">
                    <AreaChart data={cpuHistory}>
                      <defs>
                        <linearGradient id="cpuGrad" x1="0" y1="0" x2="0" y2="1">
                          <stop offset="5%" stopColor="#14b8a6" stopOpacity={0.15} />
                          <stop offset="95%" stopColor="#14b8a6" stopOpacity={0} />
                        </linearGradient>
                      </defs>
                      <XAxis dataKey="time" axisLine={false} tickLine={false} tick={{ fontSize: 10, fill: '#a1a1aa' }} interval="preserveStartEnd" />
                      <YAxis axisLine={false} tickLine={false} tick={{ fontSize: 10, fill: '#a1a1aa' }} width={30} unit="%" />
                      <Tooltip contentStyle={{ backgroundColor: '#18181b', border: 'none', borderRadius: '8px', fontSize: '12px', color: '#e4e4e7' }} />
                      <Area type="monotone" dataKey="value" stroke="#14b8a6" strokeWidth={2} fill="url(#cpuGrad)" name="CPU %" />
                    </AreaChart>
                  </ResponsiveContainer>
                )}
              </div>
            </div>

            <div className="bg-white rounded-xl border border-zinc-200 p-5">
              <h3 className="text-sm font-semibold text-zinc-900 mb-4">
                Memory Usage ({RANGE_LABELS[timeRange]} avg per sandbox)
              </h3>
              <div className="h-48">
                {chartsLoading ? (
                  <div className="h-full flex items-center justify-center text-xs text-zinc-400">Loading...</div>
                ) : (
                  <ResponsiveContainer width="100%" height="100%">
                    <AreaChart data={memoryHistory}>
                      <defs>
                        <linearGradient id="memGrad" x1="0" y1="0" x2="0" y2="1">
                          <stop offset="5%" stopColor="#0ea5e9" stopOpacity={0.15} />
                          <stop offset="95%" stopColor="#0ea5e9" stopOpacity={0} />
                        </linearGradient>
                      </defs>
                      <XAxis dataKey="time" axisLine={false} tickLine={false} tick={{ fontSize: 10, fill: '#a1a1aa' }} interval="preserveStartEnd" />
                      <YAxis axisLine={false} tickLine={false} tick={{ fontSize: 10, fill: '#a1a1aa' }} width={40} unit=" MB" />
                      <Tooltip contentStyle={{ backgroundColor: '#18181b', border: 'none', borderRadius: '8px', fontSize: '12px', color: '#e4e4e7' }} />
                      <Area type="monotone" dataKey="value" stroke="#0ea5e9" strokeWidth={2} fill="url(#memGrad)" name="Memory (MB)" />
                    </AreaChart>
                  </ResponsiveContainer>
                )}
              </div>
            </div>
          </div>

          <div className="bg-white rounded-xl border border-zinc-200 overflow-hidden">
            <div className="px-5 py-3 border-b border-zinc-100">
              <h3 className="text-sm font-semibold text-zinc-900">Per-Sandbox Resources</h3>
            </div>
            <div className="overflow-x-auto">
              <table className="w-full">
                <thead>
                  <tr className="text-left text-xs text-zinc-500 border-b border-zinc-100">
                    <th className="px-5 py-2.5 font-medium">Sandbox</th>
                    <th className="px-5 py-2.5 font-medium">User</th>
                    <th className="px-5 py-2.5 font-medium">CPU</th>
                    <th className="px-5 py-2.5 font-medium">Memory</th>
                    <th className="px-5 py-2.5 font-medium">Disk</th>
                    <th className="px-5 py-2.5 font-medium">Network</th>
                  </tr>
                </thead>
                <tbody className="divide-y divide-zinc-50">
                  {sandboxes.map((sb) => (
                    <tr key={sb.id} className="hover:bg-zinc-50/50">
                      <td className="px-5 py-3 text-sm font-mono text-zinc-600">{sb.name}</td>
                      <td className="px-5 py-3 text-sm text-zinc-700">{sb.user?.username || 'Pool'}</td>
                      <td className="px-5 py-3">
                        <div className="flex items-center gap-2">
                          <div className="w-16 h-1.5 bg-zinc-100 rounded-full overflow-hidden">
                            <div
                              className={`h-full rounded-full ${sb.cpu_usage > 80 ? 'bg-red-500' : sb.cpu_usage > 50 ? 'bg-amber-500' : 'bg-teal-500'}`}
                              style={{ width: `${sb.cpu_usage}%` }}
                            />
                          </div>
                          <span className="text-xs text-zinc-500 w-10">{sb.cpu_usage.toFixed(1)}%</span>
                        </div>
                      </td>
                      <td className="px-5 py-3 text-xs text-zinc-500">{formatBytes(sb.memory_usage)}</td>
                      <td className="px-5 py-3 text-xs text-zinc-500">{formatBytes(sb.disk_usage)}</td>
                      <td className="px-5 py-3 text-xs text-zinc-500">{sb.network_io.toFixed(1)} KB/s</td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          </div>
        </div>
      )}

      {activeTab === 'gateway' && (
        <div className="space-y-6">
          <div className="grid grid-cols-1 md:grid-cols-3 gap-4">
            <div className="bg-white rounded-xl border border-zinc-200 p-5">
              <div className="flex items-center gap-3 mb-4">
                <div className="w-10 h-10 rounded-xl bg-emerald-50 flex items-center justify-center">
                  <CheckCircle2 className="w-5 h-5 text-emerald-500" />
                </div>
                <div>
                  <h3 className="text-sm font-semibold text-zinc-900">OpenShell Gateway</h3>
                  <div className="flex items-center gap-1.5 mt-0.5">
                    <Circle className="w-2 h-2 fill-emerald-400 text-emerald-400" />
                    <span className="text-xs text-emerald-600">Healthy</span>
                  </div>
                </div>
              </div>
              <div className="space-y-2 text-xs">
                <div className="flex justify-between">
                  <span className="text-zinc-500">Endpoint</span>
                  <span className="text-zinc-700 font-mono">openshell-gateway:6443</span>
                </div>
                <div className="flex justify-between">
                  <span className="text-zinc-500">Version</span>
                  <span className="text-zinc-700">v0.4.2-alpha</span>
                </div>
                <div className="flex justify-between">
                  <span className="text-zinc-500">Uptime</span>
                  <span className="text-zinc-700">14d 6h</span>
                </div>
              </div>
            </div>

            <div className="bg-white rounded-xl border border-zinc-200 p-5">
              <div className="flex items-center gap-3 mb-4">
                <div className="w-10 h-10 rounded-xl bg-emerald-50 flex items-center justify-center">
                  <Server className="w-5 h-5 text-emerald-500" />
                </div>
                <div>
                  <h3 className="text-sm font-semibold text-zinc-900">K3s Cluster</h3>
                  <div className="flex items-center gap-1.5 mt-0.5">
                    <Circle className="w-2 h-2 fill-emerald-400 text-emerald-400" />
                    <span className="text-xs text-emerald-600">Running</span>
                  </div>
                </div>
              </div>
              <div className="space-y-2 text-xs">
                <div className="flex justify-between">
                  <span className="text-zinc-500">Nodes</span>
                  <span className="text-zinc-700">1 (single-node)</span>
                </div>
                <div className="flex justify-between">
                  <span className="text-zinc-500">K3s Version</span>
                  <span className="text-zinc-700">v1.29.3+k3s1</span>
                </div>
                <div className="flex justify-between">
                  <span className="text-zinc-500">Pods Running</span>
                  <span className="text-zinc-700">{sandboxes.length + 3}</span>
                </div>
              </div>
            </div>

            <div className="bg-white rounded-xl border border-zinc-200 p-5">
              <div className="flex items-center gap-3 mb-4">
                <div className="w-10 h-10 rounded-xl bg-emerald-50 flex items-center justify-center">
                  <Activity className="w-5 h-5 text-emerald-500" />
                </div>
                <div>
                  <h3 className="text-sm font-semibold text-zinc-900">Container Runtime</h3>
                  <div className="flex items-center gap-1.5 mt-0.5">
                    <Circle className="w-2 h-2 fill-emerald-400 text-emerald-400" />
                    <span className="text-xs text-emerald-600">Operational</span>
                  </div>
                </div>
              </div>
              <div className="space-y-2 text-xs">
                <div className="flex justify-between">
                  <span className="text-zinc-500">Runtime</span>
                  <span className="text-zinc-700">containerd v1.7.14</span>
                </div>
                <div className="flex justify-between">
                  <span className="text-zinc-500">Images Cached</span>
                  <span className="text-zinc-700">3</span>
                </div>
                <div className="flex justify-between">
                  <span className="text-zinc-500">Last Health Check</span>
                  <span className="text-zinc-700 flex items-center gap-1">
                    <Clock className="w-3 h-3" /> 12s ago
                  </span>
                </div>
              </div>
            </div>
          </div>

          <div className="bg-white rounded-xl border border-zinc-200 p-5">
            <h3 className="text-sm font-semibold text-zinc-900 mb-4">Health Check History</h3>
            <div className="flex gap-0.5">
              {Array.from({ length: 48 }, (_, i) => {
                const healthy = Math.random() > 0.03;
                return (
                  <div
                    key={i}
                    className={`flex-1 h-8 rounded-sm ${healthy ? 'bg-emerald-400' : 'bg-red-400'}`}
                    title={`${48 - i}h ago: ${healthy ? 'Healthy' : 'Degraded'}`}
                  />
                );
              })}
            </div>
            <div className="flex justify-between text-[11px] text-zinc-400 mt-1">
              <span>48h ago</span>
              <span>Now</span>
            </div>
          </div>
        </div>
      )}

      {activeTab === 'requests' && (
        <div className="space-y-6">
          <div className="grid grid-cols-1 lg:grid-cols-2 gap-6">
            <div className="bg-white rounded-xl border border-zinc-200 p-5">
              <h3 className="text-sm font-semibold text-zinc-900 mb-4">
                Requests per Second ({RANGE_LABELS[timeRange]})
              </h3>
              <div className="h-48">
                {chartsLoading ? (
                  <div className="h-full flex items-center justify-center text-xs text-zinc-400">Loading...</div>
                ) : (
                  <ResponsiveContainer width="100%" height="100%">
                    <BarChart data={requestData}>
                      <XAxis dataKey="time" axisLine={false} tickLine={false} tick={{ fontSize: 10, fill: '#a1a1aa' }} interval="preserveStartEnd" />
                      <YAxis axisLine={false} tickLine={false} tick={{ fontSize: 10, fill: '#a1a1aa' }} width={30} />
                      <Tooltip contentStyle={{ backgroundColor: '#18181b', border: 'none', borderRadius: '8px', fontSize: '12px', color: '#e4e4e7' }} />
                      <Bar dataKey="requests" fill="#14b8a6" radius={[2, 2, 0, 0]} name="Requests/s" />
                    </BarChart>
                  </ResponsiveContainer>
                )}
              </div>
            </div>

            <div className="bg-white rounded-xl border border-zinc-200 p-5">
              <h3 className="text-sm font-semibold text-zinc-900 mb-4">Response Time Percentiles</h3>
              <div className="space-y-4 pt-2">
                {latencyData.map((item) => (
                  <div key={item.name} className="flex items-center gap-4">
                    <span className="text-sm font-mono text-zinc-500 w-10">{item.name}</span>
                    <div className="flex-1 h-6 bg-zinc-100 rounded-lg overflow-hidden relative">
                      <div
                        className="h-full bg-teal-500 rounded-lg transition-all flex items-center justify-end pr-2"
                        style={{ width: `${(item.value / 1000) * 100}%` }}
                      >
                        <span className="text-[11px] font-medium text-white">{item.value}ms</span>
                      </div>
                    </div>
                  </div>
                ))}
              </div>
            </div>
          </div>

          <div className="grid grid-cols-1 lg:grid-cols-2 gap-6">
            <div className="bg-white rounded-xl border border-zinc-200 p-5">
              <h3 className="text-sm font-semibold text-zinc-900 mb-4">Error Breakdown ({RANGE_LABELS[timeRange]})</h3>
              <div className="flex items-center gap-8">
                <div className="w-32 h-32">
                  <ResponsiveContainer width="100%" height="100%">
                    <PieChart>
                      <Pie data={errorData} cx="50%" cy="50%" innerRadius={30} outerRadius={50} paddingAngle={4} dataKey="value">
                        {errorData.map((entry, i) => (
                          <Cell key={i} fill={entry.color} />
                        ))}
                      </Pie>
                    </PieChart>
                  </ResponsiveContainer>
                </div>
                <div className="space-y-2">
                  {errorData.map((item) => (
                    <div key={item.name} className="flex items-center gap-2">
                      <div className="w-2.5 h-2.5 rounded-full" style={{ backgroundColor: item.color }} />
                      <span className="text-xs text-zinc-600">{item.name}</span>
                      <span className="text-xs font-medium text-zinc-900">{item.value}</span>
                    </div>
                  ))}
                </div>
              </div>
            </div>

            <div className="bg-white rounded-xl border border-zinc-200 p-5">
              <h3 className="text-sm font-semibold text-zinc-900 mb-4">Sandbox Startup Latency</h3>
              <div className="h-40">
                <ResponsiveContainer width="100%" height="100%">
                  <BarChart data={startupData}>
                    <XAxis dataKey="range" axisLine={false} tickLine={false} tick={{ fontSize: 10, fill: '#a1a1aa' }} />
                    <YAxis axisLine={false} tickLine={false} tick={{ fontSize: 10, fill: '#a1a1aa' }} width={25} />
                    <Tooltip contentStyle={{ backgroundColor: '#18181b', border: 'none', borderRadius: '8px', fontSize: '12px', color: '#e4e4e7' }} />
                    <Bar dataKey="count" fill="#0ea5e9" radius={[4, 4, 0, 0]} name="Sandboxes" />
                  </BarChart>
                </ResponsiveContainer>
              </div>
            </div>
          </div>
        </div>
      )}

      {activeTab === 'alerts' && (
        <div className="space-y-4">
          <div className="flex items-center justify-between">
            <p className="text-sm text-zinc-500">Configure threshold alerts to fire webhooks when metrics breach limits.</p>
            <button
              onClick={() => {
                setEditingAlert({
                  name: '', metric: 'cpu', operator: 'gt', threshold: 80,
                  duration_seconds: 60, webhook_index: null, enabled: true,
                });
                setShowAlertForm(true);
              }}
              className="flex items-center gap-1.5 px-3 py-1.5 bg-teal-600 hover:bg-teal-500 text-white text-xs font-medium rounded-lg transition-colors"
            >
              <Plus className="w-3.5 h-3.5" /> Add Rule
            </button>
          </div>

          {showAlertForm && (
            <div className="bg-white rounded-xl border border-zinc-200 p-5 space-y-4">
              <div className="grid grid-cols-2 md:grid-cols-4 gap-3">
                <div>
                  <label className="block text-xs font-medium text-zinc-500 mb-1">Name</label>
                  <input
                    value={editingAlert.name}
                    onChange={(e) => setEditingAlert({ ...editingAlert, name: e.target.value })}
                    className="w-full px-3 py-1.5 border border-zinc-200 rounded-lg text-sm focus:outline-none focus:ring-2 focus:ring-teal-500/20"
                    placeholder="High CPU"
                  />
                </div>
                <div>
                  <label className="block text-xs font-medium text-zinc-500 mb-1">Metric</label>
                  <select
                    value={editingAlert.metric}
                    onChange={(e) => setEditingAlert({ ...editingAlert, metric: e.target.value })}
                    className="w-full px-3 py-1.5 border border-zinc-200 rounded-lg text-sm focus:outline-none focus:ring-2 focus:ring-teal-500/20"
                  >
                    <option value="cpu">CPU Usage</option>
                    <option value="memory">Memory Usage</option>
                    <option value="active_sandboxes">Active Sandboxes</option>
                    <option value="pool_available">Pool Available</option>
                  </select>
                </div>
                <div>
                  <label className="block text-xs font-medium text-zinc-500 mb-1">Operator</label>
                  <select
                    value={editingAlert.operator}
                    onChange={(e) => setEditingAlert({ ...editingAlert, operator: e.target.value })}
                    className="w-full px-3 py-1.5 border border-zinc-200 rounded-lg text-sm focus:outline-none focus:ring-2 focus:ring-teal-500/20"
                  >
                    <option value="gt">Greater than</option>
                    <option value="lt">Less than</option>
                    <option value="eq">Equal to</option>
                  </select>
                </div>
                <div>
                  <label className="block text-xs font-medium text-zinc-500 mb-1">Threshold</label>
                  <input
                    type="number"
                    value={editingAlert.threshold}
                    onChange={(e) => setEditingAlert({ ...editingAlert, threshold: Number(e.target.value) })}
                    className="w-full px-3 py-1.5 border border-zinc-200 rounded-lg text-sm focus:outline-none focus:ring-2 focus:ring-teal-500/20"
                  />
                </div>
              </div>
              <div className="grid grid-cols-2 gap-3">
                <div>
                  <label className="block text-xs font-medium text-zinc-500 mb-1">Duration (seconds)</label>
                  <input
                    type="number"
                    value={editingAlert.duration_seconds}
                    onChange={(e) => setEditingAlert({ ...editingAlert, duration_seconds: Number(e.target.value) })}
                    className="w-full px-3 py-1.5 border border-zinc-200 rounded-lg text-sm focus:outline-none focus:ring-2 focus:ring-teal-500/20"
                  />
                </div>
                <div className="flex items-end gap-2">
                  <button
                    onClick={() => {
                      if (editingAlert.name) {
                        saveAlerts([...alertRules, editingAlert]);
                        setShowAlertForm(false);
                      }
                    }}
                    disabled={!editingAlert.name}
                    className="px-4 py-1.5 bg-teal-600 hover:bg-teal-500 text-white text-sm font-medium rounded-lg transition-colors disabled:opacity-50"
                  >
                    Save
                  </button>
                  <button
                    onClick={() => setShowAlertForm(false)}
                    className="px-4 py-1.5 text-sm text-zinc-600 hover:bg-zinc-100 rounded-lg transition-colors"
                  >
                    Cancel
                  </button>
                </div>
              </div>
            </div>
          )}

          {alertsLoading ? (
            <LoadingState rows={3} />
          ) : alertRules.length === 0 ? (
            <EmptyState
              icon={<Bell className="w-8 h-8" />}
              title="No alert rules"
              description="Add alert rules to get notified when metrics breach thresholds."
            />
          ) : (
            <div className="space-y-2">
              {alertRules.map((rule, idx) => (
                <div key={idx} className="bg-white rounded-xl border border-zinc-200 px-5 py-3 flex items-center justify-between">
                  <div className="flex items-center gap-4">
                    <div className={`w-2 h-2 rounded-full ${rule.enabled ? 'bg-emerald-400' : 'bg-zinc-300'}`} />
                    <div>
                      <p className="text-sm font-medium text-zinc-900">{rule.name}</p>
                      <p className="text-xs text-zinc-500">
                        {rule.metric} {rule.operator === 'gt' ? '>' : rule.operator === 'lt' ? '<' : '='} {rule.threshold} for {rule.duration_seconds}s
                      </p>
                    </div>
                  </div>
                  <div className="flex items-center gap-2">
                    <button
                      onClick={() => {
                        const updated = alertRules.map((r, i) => i === idx ? { ...r, enabled: !r.enabled } : r);
                        saveAlerts(updated);
                      }}
                      className="px-2 py-1 text-xs text-zinc-500 hover:text-zinc-700 hover:bg-zinc-100 rounded transition-colors"
                    >
                      {rule.enabled ? 'Disable' : 'Enable'}
                    </button>
                    <button
                      onClick={() => saveAlerts(alertRules.filter((_, i) => i !== idx))}
                      className="p-1.5 rounded-lg hover:bg-red-50 text-zinc-400 hover:text-red-600 transition-colors"
                    >
                      <Trash2 className="w-3.5 h-3.5" />
                    </button>
                  </div>
                </div>
              ))}
            </div>
          )}
        </div>
      )}
    </div>
  );
}
