import { useState, useEffect, useCallback } from 'react';
import {
  Container,
  Pause,
  Trash2,
  RotateCcw,
  Clock,
  Cpu,
  HardDrive,
  Wifi,
  MemoryStick,
  Play,
  Search,
} from 'lucide-react';
import { supabase } from '../lib/supabase';
import { Tabs } from '../components/ui/Tabs';
import { Badge } from '../components/ui/Badge';
import { SlidePanel } from '../components/ui/SlidePanel';
import { LoadingState, EmptyState } from '../components/ui/EmptyState';
import { Modal } from '../components/ui/Modal';
import { formatRelativeTime, formatUptime, formatBytes } from '../lib/utils';
import type { Sandbox, AuditLogEntry } from '../types';

export default function Sandboxes() {
  const [activeTab, setActiveTab] = useState('active');
  const [sandboxes, setSandboxes] = useState<Sandbox[]>([]);
  const [loading, setLoading] = useState(true);
  const [selectedSandbox, setSelectedSandbox] = useState<Sandbox | null>(null);
  const [sandboxLogs, setSandboxLogs] = useState<AuditLogEntry[]>([]);
  const [confirmAction, setConfirmAction] = useState<{ sandbox: Sandbox; action: string } | null>(null);
  const [search, setSearch] = useState('');

  const fetchSandboxes = useCallback(async () => {
    const { data } = await supabase
      .from('sandboxes')
      .select('*, user:users(*), policy:policies(*)')
      .neq('state', 'DESTROYED')
      .order('last_active_at', { ascending: false });
    setSandboxes((data || []) as Sandbox[]);
    setLoading(false);
  }, []);

  useEffect(() => {
    fetchSandboxes();
  }, [fetchSandboxes]);

  const fetchSandboxLogs = async (sandboxId: string) => {
    const { data } = await supabase
      .from('audit_log')
      .select('*, user:users(*)')
      .eq('sandbox_id', sandboxId)
      .order('timestamp', { ascending: false })
      .limit(20);
    setSandboxLogs((data || []) as AuditLogEntry[]);
  };

  const handleSelectSandbox = (sb: Sandbox) => {
    setSelectedSandbox(sb);
    fetchSandboxLogs(sb.id);
  };

  const handleAction = async (sandbox: Sandbox, action: string) => {
    if (action === 'suspend') {
      await supabase
        .from('sandboxes')
        .update({ state: 'SUSPENDED', suspended_at: new Date().toISOString(), cpu_usage: 0, memory_usage: 0, network_io: 0 })
        .eq('id', sandbox.id);
    } else if (action === 'resume') {
      await supabase
        .from('sandboxes')
        .update({ state: 'ACTIVE', suspended_at: null, last_active_at: new Date().toISOString() })
        .eq('id', sandbox.id);
    } else if (action === 'destroy') {
      await supabase
        .from('sandboxes')
        .update({ state: 'DESTROYED', destroyed_at: new Date().toISOString() })
        .eq('id', sandbox.id);
    }
    setConfirmAction(null);
    setSelectedSandbox(null);
    fetchSandboxes();
  };

  const activeSandboxes = sandboxes.filter((s) => ['ACTIVE', 'READY'].includes(s.state));
  const suspendedSandboxes = sandboxes.filter((s) => s.state === 'SUSPENDED');
  const poolSandboxes = sandboxes.filter((s) => ['POOL', 'WARMING'].includes(s.state) && !s.user_id);

  const tabs = [
    { id: 'active', label: 'Active', count: activeSandboxes.length },
    { id: 'suspended', label: 'Suspended', count: suspendedSandboxes.length },
    { id: 'pool', label: 'Pre-warmed Pool', count: poolSandboxes.length },
  ];

  const currentSandboxes =
    activeTab === 'active' ? activeSandboxes :
    activeTab === 'suspended' ? suspendedSandboxes :
    poolSandboxes;

  const filtered = currentSandboxes.filter((sb) =>
    !search || sb.name.toLowerCase().includes(search.toLowerCase()) ||
    sb.user?.username?.toLowerCase().includes(search.toLowerCase())
  );

  if (loading) return <LoadingState rows={8} />;

  return (
    <div className="space-y-4">
      <Tabs tabs={tabs} activeTab={activeTab} onChange={setActiveTab} />

      <div className="flex items-center gap-3">
        <div className="relative flex-1 max-w-sm">
          <Search className="absolute left-3 top-1/2 -translate-y-1/2 w-4 h-4 text-zinc-400" />
          <input
            type="text"
            value={search}
            onChange={(e) => setSearch(e.target.value)}
            placeholder="Search sandboxes..."
            className="w-full pl-9 pr-3 py-2 bg-white border border-zinc-200 rounded-lg text-sm focus:outline-none focus:ring-2 focus:ring-teal-500/20 focus:border-teal-400"
          />
        </div>
      </div>

      <div className="bg-white rounded-xl border border-zinc-200 overflow-hidden">
        {filtered.length === 0 ? (
          <EmptyState
            icon={<Container className="w-8 h-8" />}
            title={`No ${activeTab} sandboxes`}
            description={
              activeTab === 'pool'
                ? 'The pre-warmed pool is empty. New sandboxes will be provisioned on demand.'
                : `There are currently no ${activeTab} sandboxes.`
            }
          />
        ) : (
          <div className="overflow-x-auto">
            <table className="w-full">
              <thead>
                <tr className="text-left text-xs text-zinc-500 border-b border-zinc-100">
                  <th className="px-5 py-3 font-medium">
                    {activeTab === 'pool' ? 'Sandbox' : 'User'}
                  </th>
                  <th className="px-5 py-3 font-medium">Name</th>
                  <th className="px-5 py-3 font-medium">State</th>
                  <th className="px-5 py-3 font-medium">Policy</th>
                  {activeTab === 'active' && (
                    <>
                      <th className="px-5 py-3 font-medium">Uptime</th>
                      <th className="px-5 py-3 font-medium">Last Active</th>
                      <th className="px-5 py-3 font-medium">CPU</th>
                      <th className="px-5 py-3 font-medium">Memory</th>
                    </>
                  )}
                  {activeTab === 'suspended' && (
                    <>
                      <th className="px-5 py-3 font-medium">Suspended</th>
                      <th className="px-5 py-3 font-medium">Expires</th>
                    </>
                  )}
                  {activeTab === 'pool' && (
                    <th className="px-5 py-3 font-medium">Created</th>
                  )}
                  <th className="px-5 py-3 font-medium">Actions</th>
                </tr>
              </thead>
              <tbody className="divide-y divide-zinc-50">
                {filtered.map((sb) => (
                  <tr
                    key={sb.id}
                    className="hover:bg-zinc-50/50 transition-colors cursor-pointer"
                    onClick={() => handleSelectSandbox(sb)}
                  >
                    <td className="px-5 py-3">
                      {sb.user ? (
                        <div className="flex items-center gap-2">
                          <div className="w-6 h-6 rounded-full bg-zinc-100 flex items-center justify-center">
                            <span className="text-[10px] font-bold text-zinc-600">
                              {sb.user.username[0].toUpperCase()}
                            </span>
                          </div>
                          <span className="text-sm font-medium text-zinc-900">{sb.user.username}</span>
                        </div>
                      ) : (
                        <span className="text-sm text-zinc-400">Unassigned</span>
                      )}
                    </td>
                    <td className="px-5 py-3 text-sm text-zinc-600 font-mono">{sb.name}</td>
                    <td className="px-5 py-3">
                      <Badge variant="state" value={sb.state}>{sb.state}</Badge>
                    </td>
                    <td className="px-5 py-3">
                      {sb.policy && <Badge variant="tier" value={sb.policy.tier}>{sb.policy.name}</Badge>}
                    </td>
                    {activeTab === 'active' && (
                      <>
                        <td className="px-5 py-3 text-sm text-zinc-600">{formatUptime(sb.created_at)}</td>
                        <td className="px-5 py-3 text-sm text-zinc-500">{formatRelativeTime(sb.last_active_at)}</td>
                        <td className="px-5 py-3">
                          <div className="flex items-center gap-1.5">
                            <div className="w-10 h-1.5 bg-zinc-100 rounded-full overflow-hidden">
                              <div
                                className={`h-full rounded-full ${
                                  sb.cpu_usage > 80 ? 'bg-red-500' : sb.cpu_usage > 50 ? 'bg-amber-500' : 'bg-teal-500'
                                }`}
                                style={{ width: `${sb.cpu_usage}%` }}
                              />
                            </div>
                            <span className="text-xs text-zinc-500 w-8">{sb.cpu_usage.toFixed(0)}%</span>
                          </div>
                        </td>
                        <td className="px-5 py-3 text-xs text-zinc-500">{formatBytes(sb.memory_usage)}</td>
                      </>
                    )}
                    {activeTab === 'suspended' && (
                      <>
                        <td className="px-5 py-3 text-sm text-zinc-500">
                          {sb.suspended_at ? formatRelativeTime(sb.suspended_at) : '-'}
                        </td>
                        <td className="px-5 py-3 text-sm text-zinc-500">
                          {sb.suspended_at
                            ? formatRelativeTime(new Date(new Date(sb.suspended_at).getTime() + 86400000).toISOString())
                            : '-'}
                        </td>
                      </>
                    )}
                    {activeTab === 'pool' && (
                      <td className="px-5 py-3 text-sm text-zinc-500">{formatRelativeTime(sb.created_at)}</td>
                    )}
                    <td className="px-5 py-3">
                      <div className="flex items-center gap-1" onClick={(e) => e.stopPropagation()}>
                        {activeTab === 'active' && (
                          <button
                            onClick={() => setConfirmAction({ sandbox: sb, action: 'suspend' })}
                            className="p-1.5 rounded-lg hover:bg-orange-50 text-zinc-400 hover:text-orange-600 transition-colors"
                            title="Suspend"
                          >
                            <Pause className="w-3.5 h-3.5" />
                          </button>
                        )}
                        {activeTab === 'suspended' && (
                          <button
                            onClick={() => handleAction(sb, 'resume')}
                            className="p-1.5 rounded-lg hover:bg-teal-50 text-zinc-400 hover:text-teal-600 transition-colors"
                            title="Resume"
                          >
                            <Play className="w-3.5 h-3.5" />
                          </button>
                        )}
                        <button
                          onClick={() => setConfirmAction({ sandbox: sb, action: 'destroy' })}
                          className="p-1.5 rounded-lg hover:bg-red-50 text-zinc-400 hover:text-red-600 transition-colors"
                          title="Destroy"
                        >
                          <Trash2 className="w-3.5 h-3.5" />
                        </button>
                      </div>
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        )}
      </div>

      <SlidePanel
        open={!!selectedSandbox}
        onClose={() => setSelectedSandbox(null)}
        title={selectedSandbox?.name || ''}
        subtitle={selectedSandbox?.user?.username ? `Assigned to ${selectedSandbox.user.username}` : 'Unassigned'}
      >
        {selectedSandbox && (
          <div className="space-y-6">
            <div className="grid grid-cols-2 gap-4">
              <div className="bg-zinc-50 rounded-lg p-3">
                <p className="text-xs text-zinc-500 mb-1">State</p>
                <Badge variant="state" value={selectedSandbox.state}>{selectedSandbox.state}</Badge>
              </div>
              <div className="bg-zinc-50 rounded-lg p-3">
                <p className="text-xs text-zinc-500 mb-1">Policy</p>
                {selectedSandbox.policy && (
                  <Badge variant="tier" value={selectedSandbox.policy.tier}>
                    {selectedSandbox.policy.name}
                  </Badge>
                )}
              </div>
              <div className="bg-zinc-50 rounded-lg p-3">
                <p className="text-xs text-zinc-500 mb-1">Image</p>
                <p className="text-sm font-mono text-zinc-700">{selectedSandbox.image_tag}</p>
              </div>
              <div className="bg-zinc-50 rounded-lg p-3">
                <p className="text-xs text-zinc-500 mb-1">Internal IP</p>
                <p className="text-sm font-mono text-zinc-700">{selectedSandbox.internal_ip}</p>
              </div>
            </div>

            {['ACTIVE', 'READY'].includes(selectedSandbox.state) && (
              <div>
                <h4 className="text-xs font-semibold text-zinc-500 uppercase tracking-wider mb-3">Resources</h4>
                <div className="space-y-3">
                  {[
                    { icon: Cpu, label: 'CPU', value: `${selectedSandbox.cpu_usage.toFixed(1)}%`, pct: selectedSandbox.cpu_usage },
                    { icon: MemoryStick, label: 'Memory', value: formatBytes(selectedSandbox.memory_usage), pct: (selectedSandbox.memory_usage / 2048) * 100 },
                    { icon: HardDrive, label: 'Disk', value: formatBytes(selectedSandbox.disk_usage), pct: (selectedSandbox.disk_usage / 5120) * 100 },
                    { icon: Wifi, label: 'Network I/O', value: `${selectedSandbox.network_io.toFixed(1)} KB/s`, pct: (selectedSandbox.network_io / 200) * 100 },
                  ].map((r) => (
                    <div key={r.label} className="flex items-center gap-3">
                      <r.icon className="w-4 h-4 text-zinc-400 flex-shrink-0" />
                      <div className="flex-1">
                        <div className="flex justify-between text-xs mb-1">
                          <span className="text-zinc-600">{r.label}</span>
                          <span className="text-zinc-500">{r.value}</span>
                        </div>
                        <div className="h-1.5 bg-zinc-100 rounded-full overflow-hidden">
                          <div
                            className={`h-full rounded-full transition-all ${
                              r.pct > 80 ? 'bg-red-500' : r.pct > 50 ? 'bg-amber-500' : 'bg-teal-500'
                            }`}
                            style={{ width: `${Math.min(r.pct, 100)}%` }}
                          />
                        </div>
                      </div>
                    </div>
                  ))}
                </div>
              </div>
            )}

            <div>
              <h4 className="text-xs font-semibold text-zinc-500 uppercase tracking-wider mb-3">Timestamps</h4>
              <div className="space-y-2 text-sm">
                <div className="flex justify-between">
                  <span className="text-zinc-500 flex items-center gap-1.5"><Clock className="w-3.5 h-3.5" /> Created</span>
                  <span className="text-zinc-700">{formatRelativeTime(selectedSandbox.created_at)}</span>
                </div>
                <div className="flex justify-between">
                  <span className="text-zinc-500 flex items-center gap-1.5"><RotateCcw className="w-3.5 h-3.5" /> Last Active</span>
                  <span className="text-zinc-700">{formatRelativeTime(selectedSandbox.last_active_at)}</span>
                </div>
                {selectedSandbox.gpu_enabled && (
                  <div className="flex justify-between">
                    <span className="text-zinc-500">GPU</span>
                    <Badge variant="tier" value="elevated">Enabled</Badge>
                  </div>
                )}
              </div>
            </div>

            <div>
              <h4 className="text-xs font-semibold text-zinc-500 uppercase tracking-wider mb-3">Recent Enforcement</h4>
              {sandboxLogs.length === 0 ? (
                <p className="text-sm text-zinc-400">No enforcement events</p>
              ) : (
                <div className="space-y-2">
                  {sandboxLogs.slice(0, 8).map((log) => (
                    <div key={log.id} className="flex items-center gap-2 text-xs">
                      <Badge variant="event" value={log.event_type}>{log.event_type}</Badge>
                      <span className="text-zinc-600 truncate flex-1">
                        {(log.details as Record<string, string>).destination || (log.details as Record<string, string>).action || log.event_type}
                      </span>
                      <span className="text-zinc-400 flex-shrink-0">{formatRelativeTime(log.timestamp)}</span>
                    </div>
                  ))}
                </div>
              )}
            </div>

            <div className="flex gap-2 pt-2 border-t border-zinc-100">
              {selectedSandbox.state === 'SUSPENDED' && (
                <button
                  onClick={() => handleAction(selectedSandbox, 'resume')}
                  className="flex-1 py-2 bg-teal-600 hover:bg-teal-500 text-white text-sm font-medium rounded-lg transition-colors"
                >
                  Resume
                </button>
              )}
              {['ACTIVE', 'READY'].includes(selectedSandbox.state) && (
                <button
                  onClick={() => setConfirmAction({ sandbox: selectedSandbox, action: 'suspend' })}
                  className="flex-1 py-2 bg-orange-50 hover:bg-orange-100 text-orange-700 text-sm font-medium rounded-lg transition-colors"
                >
                  Suspend
                </button>
              )}
              <button
                onClick={() => setConfirmAction({ sandbox: selectedSandbox, action: 'destroy' })}
                className="flex-1 py-2 bg-red-50 hover:bg-red-100 text-red-700 text-sm font-medium rounded-lg transition-colors"
              >
                Destroy
              </button>
            </div>
          </div>
        )}
      </SlidePanel>

      <Modal
        open={!!confirmAction}
        onClose={() => setConfirmAction(null)}
        title={`Confirm ${confirmAction?.action}`}
        actions={
          <>
            <button
              onClick={() => setConfirmAction(null)}
              className="px-4 py-2 text-sm text-zinc-600 hover:bg-zinc-100 rounded-lg transition-colors"
            >
              Cancel
            </button>
            <button
              onClick={() => confirmAction && handleAction(confirmAction.sandbox, confirmAction.action)}
              className={`px-4 py-2 text-sm font-medium text-white rounded-lg transition-colors ${
                confirmAction?.action === 'destroy' ? 'bg-red-600 hover:bg-red-500' : 'bg-orange-600 hover:bg-orange-500'
              }`}
            >
              {confirmAction?.action === 'destroy' ? 'Destroy' : 'Suspend'}
            </button>
          </>
        }
      >
        <p className="text-sm text-zinc-600">
          Are you sure you want to {confirmAction?.action} sandbox{' '}
          <span className="font-mono font-medium">{confirmAction?.sandbox.name}</span>?
          {confirmAction?.action === 'destroy' && (
            <span className="block mt-2 text-red-600">
              This will permanently remove the sandbox and its resources.
            </span>
          )}
        </p>
      </Modal>
    </div>
  );
}
