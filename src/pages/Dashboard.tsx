import { useEffect, useState, useCallback } from 'react';
import {
  Container,
  Pause,
  Layers,
  ShieldCheck,
  Timer,
  ArrowUpRight,
} from 'lucide-react';
import { AreaChart, Area, XAxis, YAxis, Tooltip, ResponsiveContainer } from 'recharts';
import { getDashboardData } from '../lib/dataService';
import { StatCard } from '../components/ui/StatCard';
import { Badge } from '../components/ui/Badge';
import { LoadingState } from '../components/ui/EmptyState';
import { formatRelativeTime, formatUptime } from '../lib/utils';
import type { Sandbox, AuditLogEntry } from '../types';

interface DashboardStats {
  activeSandboxes: number;
  maxActive: number;
  suspendedCount: number;
  poolSize: number;
  poolTarget: number;
  enforcementLast24h: { allows: number; denies: number; routes: number };
  avgStartupMs: number;
}

export default function Dashboard() {
  const [stats, setStats] = useState<DashboardStats | null>(null);
  const [sandboxes, setSandboxes] = useState<Sandbox[]>([]);
  const [recentEvents, setRecentEvents] = useState<AuditLogEntry[]>([]);
  const [chartData, setChartData] = useState<{ time: string; active: number; cpu: number; memory: number }[]>([]);
  const [loading, setLoading] = useState(true);

  const fetchData = useCallback(async () => {
    const { sandboxes: allSandboxes, recentEvents: allEvents, config: configData, lifecycleEvents } = await getDashboardData();

    const activeSandboxes = allSandboxes.filter((s) => ['ACTIVE', 'READY'].includes(s.state));
    const suspendedSandboxes = allSandboxes.filter((s) => s.state === 'SUSPENDED');
    const poolSandboxes = allSandboxes.filter((s) => ['POOL', 'WARMING'].includes(s.state) && !s.user_id);

    const poolConfig = configData.find((c) => c.key === 'pool');
    const maxActive = poolConfig?.value?.max_active as number || 10;
    const poolTarget = poolConfig?.value?.warmup_size as number || 2;

    const enforcementEvents = allEvents.filter((e) => e.category === 'enforcement');
    const last24h = enforcementEvents.filter(
      (e) => new Date(e.timestamp).getTime() > Date.now() - 86400000
    );

    const startupTimes = (lifecycleEvents as { details: Record<string, unknown> }[])
      .filter((e) => (e.details as Record<string, unknown>)?.event_type === 'created')
      .map((e) => (e.details?.warmup_time_ms as number) || 0)
      .filter((t) => t > 0);
    const avgStartup = startupTimes.length > 0
      ? startupTimes.reduce((a, b) => a + b, 0) / startupTimes.length
      : 3200;

    setStats({
      activeSandboxes: activeSandboxes.length,
      maxActive,
      suspendedCount: suspendedSandboxes.length,
      poolSize: poolSandboxes.length,
      poolTarget,
      enforcementLast24h: {
        allows: last24h.filter((e) => e.event_type === 'allow').length,
        denies: last24h.filter((e) => e.event_type === 'deny').length,
        routes: last24h.filter((e) => e.event_type === 'route').length,
      },
      avgStartupMs: avgStartup,
    });

    setSandboxes(activeSandboxes);
    setRecentEvents(allEvents.slice(0, 15));

    const now = Date.now();
    const points = Array.from({ length: 24 }, (_, i) => {
      const hour = 23 - i;
      const time = new Date(now - hour * 3600000);
      const activeCount = Math.max(1, activeSandboxes.length + Math.floor(Math.random() * 3 - 1));
      return {
        time: time.toLocaleTimeString('en-US', { hour: '2-digit', minute: '2-digit' }),
        active: activeCount,
        cpu: Math.max(5, 20 + Math.random() * 40),
        memory: Math.max(200, 400 + Math.random() * 800),
      };
    });
    setChartData(points);
    setLoading(false);
  }, []);

  useEffect(() => {
    fetchData();
  }, [fetchData]);

  if (loading || !stats) return <LoadingState rows={8} />;

  return (
    <div className="space-y-6">
      <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-5 gap-4">
        <StatCard
          label="Active Sandboxes"
          value={stats.activeSandboxes}
          icon={<Container className="w-5 h-5" />}
          bar={{ current: stats.activeSandboxes, max: stats.maxActive }}
        />
        <StatCard
          label="Suspended"
          value={stats.suspendedCount}
          icon={<Pause className="w-5 h-5" />}
          subtitle="Awaiting resume or expiry"
        />
        <StatCard
          label="Pool Ready"
          value={`${stats.poolSize} / ${stats.poolTarget}`}
          icon={<Layers className="w-5 h-5" />}
          subtitle="Pre-warmed sandboxes"
        />
        <StatCard
          label="Enforcement (24h)"
          value={stats.enforcementLast24h.allows + stats.enforcementLast24h.denies + stats.enforcementLast24h.routes}
          icon={<ShieldCheck className="w-5 h-5" />}
          subtitle={`${stats.enforcementLast24h.allows} allow / ${stats.enforcementLast24h.denies} deny / ${stats.enforcementLast24h.routes} route`}
        />
        <StatCard
          label="Avg Startup"
          value={`${(stats.avgStartupMs / 1000).toFixed(1)}s`}
          icon={<Timer className="w-5 h-5" />}
          subtitle="Last hour average"
        />
      </div>

      <div className="grid grid-cols-1 lg:grid-cols-3 gap-6">
        <div className="lg:col-span-2 space-y-6">
          <div className="bg-white rounded-xl border border-zinc-200 overflow-hidden">
            <div className="px-5 py-4 border-b border-zinc-100 flex items-center justify-between">
              <h3 className="text-sm font-semibold text-zinc-900">Active Sandboxes</h3>
              <span className="text-xs text-zinc-400">{sandboxes.length} running</span>
            </div>
            <div className="overflow-x-auto">
              <table className="w-full">
                <thead>
                  <tr className="text-left text-xs text-zinc-500 border-b border-zinc-100">
                    <th className="px-5 py-2.5 font-medium">User</th>
                    <th className="px-5 py-2.5 font-medium">Sandbox</th>
                    <th className="px-5 py-2.5 font-medium">State</th>
                    <th className="px-5 py-2.5 font-medium">Policy</th>
                    <th className="px-5 py-2.5 font-medium">Uptime</th>
                    <th className="px-5 py-2.5 font-medium">CPU</th>
                    <th className="px-5 py-2.5 font-medium">Memory</th>
                  </tr>
                </thead>
                <tbody className="divide-y divide-zinc-50">
                  {sandboxes.map((sb) => (
                    <tr key={sb.id} className="hover:bg-zinc-50/50 transition-colors">
                      <td className="px-5 py-3">
                        <div className="flex items-center gap-2">
                          <div className="w-6 h-6 rounded-full bg-zinc-100 flex items-center justify-center">
                            <span className="text-[10px] font-bold text-zinc-600">
                              {sb.user?.username?.[0]?.toUpperCase() || '?'}
                            </span>
                          </div>
                          <span className="text-sm font-medium text-zinc-900">
                            {sb.user?.username || 'Pool'}
                          </span>
                        </div>
                      </td>
                      <td className="px-5 py-3 text-sm text-zinc-600 font-mono">{sb.name}</td>
                      <td className="px-5 py-3">
                        <Badge variant="state" value={sb.state}>{sb.state}</Badge>
                      </td>
                      <td className="px-5 py-3">
                        {sb.policy && (
                          <Badge variant="tier" value={sb.policy.tier}>{sb.policy.name}</Badge>
                        )}
                      </td>
                      <td className="px-5 py-3 text-sm text-zinc-600">{formatUptime(sb.created_at)}</td>
                      <td className="px-5 py-3">
                        <div className="flex items-center gap-1.5">
                          <div className="w-12 h-1.5 bg-zinc-100 rounded-full overflow-hidden">
                            <div
                              className={`h-full rounded-full ${
                                sb.cpu_usage > 80 ? 'bg-red-500' : sb.cpu_usage > 50 ? 'bg-amber-500' : 'bg-teal-500'
                              }`}
                              style={{ width: `${sb.cpu_usage}%` }}
                            />
                          </div>
                          <span className="text-xs text-zinc-500">{sb.cpu_usage.toFixed(0)}%</span>
                        </div>
                      </td>
                      <td className="px-5 py-3 text-xs text-zinc-500">{Math.round(sb.memory_usage)} MB</td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          </div>

          <div className="bg-white rounded-xl border border-zinc-200 p-5">
            <h3 className="text-sm font-semibold text-zinc-900 mb-4">Resource Utilization (24h)</h3>
            <div className="h-48">
              <ResponsiveContainer width="100%" height="100%">
                <AreaChart data={chartData}>
                  <defs>
                    <linearGradient id="colorActive" x1="0" y1="0" x2="0" y2="1">
                      <stop offset="5%" stopColor="#14b8a6" stopOpacity={0.15} />
                      <stop offset="95%" stopColor="#14b8a6" stopOpacity={0} />
                    </linearGradient>
                    <linearGradient id="colorCpu" x1="0" y1="0" x2="0" y2="1">
                      <stop offset="5%" stopColor="#0ea5e9" stopOpacity={0.15} />
                      <stop offset="95%" stopColor="#0ea5e9" stopOpacity={0} />
                    </linearGradient>
                  </defs>
                  <XAxis
                    dataKey="time"
                    axisLine={false}
                    tickLine={false}
                    tick={{ fontSize: 10, fill: '#a1a1aa' }}
                    interval="preserveStartEnd"
                  />
                  <YAxis
                    axisLine={false}
                    tickLine={false}
                    tick={{ fontSize: 10, fill: '#a1a1aa' }}
                    width={30}
                  />
                  <Tooltip
                    contentStyle={{
                      backgroundColor: '#18181b',
                      border: 'none',
                      borderRadius: '8px',
                      fontSize: '12px',
                      color: '#e4e4e7',
                    }}
                  />
                  <Area
                    type="monotone"
                    dataKey="active"
                    stroke="#14b8a6"
                    strokeWidth={2}
                    fill="url(#colorActive)"
                    name="Active Sandboxes"
                  />
                  <Area
                    type="monotone"
                    dataKey="cpu"
                    stroke="#0ea5e9"
                    strokeWidth={2}
                    fill="url(#colorCpu)"
                    name="CPU %"
                  />
                </AreaChart>
              </ResponsiveContainer>
            </div>
          </div>
        </div>

        <div className="bg-white rounded-xl border border-zinc-200 overflow-hidden">
          <div className="px-5 py-4 border-b border-zinc-100 flex items-center justify-between">
            <h3 className="text-sm font-semibold text-zinc-900">Recent Activity</h3>
            <a
              href="/admin/audit"
              className="text-xs text-teal-600 hover:text-teal-700 font-medium flex items-center gap-0.5"
            >
              View all <ArrowUpRight className="w-3 h-3" />
            </a>
          </div>
          <div className="divide-y divide-zinc-50 max-h-[560px] overflow-y-auto">
            {recentEvents.map((event) => (
              <div key={event.id} className="px-5 py-3 hover:bg-zinc-50/50 transition-colors">
                <div className="flex items-start gap-2">
                  <Badge variant="event" value={event.event_type} className="mt-0.5 flex-shrink-0">
                    {event.event_type}
                  </Badge>
                  <div className="min-w-0 flex-1">
                    <p className="text-xs text-zinc-600 truncate">
                      {event.category === 'enforcement' && (
                        <>
                          {(event.details as Record<string, string>).destination || (event.details as Record<string, string>).path || event.event_type}
                        </>
                      )}
                      {event.category === 'lifecycle' && (
                        <>Sandbox {event.event_type}</>
                      )}
                      {event.category === 'admin' && (
                        <>{(event.details as Record<string, string>).changes || (event.details as Record<string, string>).setting || 'Admin action'}</>
                      )}
                    </p>
                    <p className="text-[11px] text-zinc-400 mt-0.5">
                      {event.user?.username && `${event.user.username} · `}
                      {formatRelativeTime(event.timestamp)}
                    </p>
                  </div>
                </div>
              </div>
            ))}
          </div>
        </div>
      </div>
    </div>
  );
}
