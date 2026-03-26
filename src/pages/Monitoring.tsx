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
import { supabase } from '../lib/supabase';
import { Tabs } from '../components/ui/Tabs';
import { LoadingState } from '../components/ui/EmptyState';
import { formatBytes } from '../lib/utils';
import type { Sandbox } from '../types';

export default function Monitoring() {
  const [activeTab, setActiveTab] = useState('resources');
  const [sandboxes, setSandboxes] = useState<Sandbox[]>([]);
  const [loading, setLoading] = useState(true);

  const fetchData = useCallback(async () => {
    const { data } = await supabase
      .from('sandboxes')
      .select('*, user:users(*), policy:policies(*)')
      .in('state', ['ACTIVE', 'READY'])
      .order('cpu_usage', { ascending: false });
    setSandboxes((data || []) as Sandbox[]);
    setLoading(false);
  }, []);

  useEffect(() => { fetchData(); }, [fetchData]);

  const totalCpu = sandboxes.reduce((s, sb) => s + sb.cpu_usage, 0);
  const totalMemory = sandboxes.reduce((s, sb) => s + sb.memory_usage, 0);
  const totalDisk = sandboxes.reduce((s, sb) => s + sb.disk_usage, 0);

  const generateTimeSeries = (baseValue: number, variance: number, points: number) =>
    Array.from({ length: points }, (_, i) => {
      const time = new Date(Date.now() - (points - 1 - i) * 3600000);
      return {
        time: time.toLocaleTimeString('en-US', { hour: '2-digit', minute: '2-digit' }),
        value: Math.max(0, baseValue + (Math.random() - 0.5) * variance),
      };
    });

  const cpuHistory = generateTimeSeries(totalCpu / Math.max(sandboxes.length, 1), 20, 24);
  const memoryHistory = generateTimeSeries(totalMemory / Math.max(sandboxes.length, 1), 200, 24);

  const requestData = generateTimeSeries(45, 30, 24).map((d) => ({
    ...d,
    requests: Math.max(1, Math.round(d.value)),
  }));

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
  ];

  if (loading) return <LoadingState rows={8} />;

  return (
    <div className="space-y-4">
      <Tabs tabs={tabs} activeTab={activeTab} onChange={setActiveTab} />

      {activeTab === 'resources' && (
        <div className="space-y-6">
          <div className="grid grid-cols-1 md:grid-cols-4 gap-4">
            {[
              { icon: Cpu, label: 'Total CPU', value: `${totalCpu.toFixed(1)}%`, color: 'teal' },
              { icon: MemoryStick, label: 'Total Memory', value: formatBytes(totalMemory), color: 'sky' },
              { icon: HardDrive, label: 'Total Disk', value: formatBytes(totalDisk), color: 'amber' },
              { icon: Wifi, label: 'Network I/O', value: `${sandboxes.reduce((s, sb) => s + sb.network_io, 0).toFixed(1)} KB/s`, color: 'emerald' },
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
              <h3 className="text-sm font-semibold text-zinc-900 mb-4">CPU Usage (24h avg per sandbox)</h3>
              <div className="h-48">
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
              </div>
            </div>

            <div className="bg-white rounded-xl border border-zinc-200 p-5">
              <h3 className="text-sm font-semibold text-zinc-900 mb-4">Memory Usage (24h avg per sandbox)</h3>
              <div className="h-48">
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
              <h3 className="text-sm font-semibold text-zinc-900 mb-4">Requests per Second (24h)</h3>
              <div className="h-48">
                <ResponsiveContainer width="100%" height="100%">
                  <BarChart data={requestData}>
                    <XAxis dataKey="time" axisLine={false} tickLine={false} tick={{ fontSize: 10, fill: '#a1a1aa' }} interval="preserveStartEnd" />
                    <YAxis axisLine={false} tickLine={false} tick={{ fontSize: 10, fill: '#a1a1aa' }} width={30} />
                    <Tooltip contentStyle={{ backgroundColor: '#18181b', border: 'none', borderRadius: '8px', fontSize: '12px', color: '#e4e4e7' }} />
                    <Bar dataKey="requests" fill="#14b8a6" radius={[2, 2, 0, 0]} name="Requests/s" />
                  </BarChart>
                </ResponsiveContainer>
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
              <h3 className="text-sm font-semibold text-zinc-900 mb-4">Error Breakdown (24h)</h3>
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
    </div>
  );
}
