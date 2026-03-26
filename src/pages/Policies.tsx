import { useState, useEffect, useCallback } from 'react';
import {
  Shield,
  Plus,
  History,
  Users,
  Pencil,
  Copy,
  Trash2,
  Save,
  X,
  ChevronRight,
  Search,
  ArrowLeft,
} from 'lucide-react';
import { supabase } from '../lib/supabase';
import { Tabs } from '../components/ui/Tabs';
import { Badge } from '../components/ui/Badge';
import { Modal } from '../components/ui/Modal';
import { LoadingState } from '../components/ui/EmptyState';
import { formatRelativeTime } from '../lib/utils';
import type { Policy, PolicyVersion, PolicyAssignment, User, Group } from '../types';

export default function Policies() {
  const [activeTab, setActiveTab] = useState('library');
  const [policies, setPolicies] = useState<Policy[]>([]);
  const [versions, setVersions] = useState<PolicyVersion[]>([]);
  const [assignments, setAssignments] = useState<PolicyAssignment[]>([]);
  const [users, setUsers] = useState<User[]>([]);
  const [groups, setGroups] = useState<Group[]>([]);
  const [loading, setLoading] = useState(true);
  const [editingPolicy, setEditingPolicy] = useState<Policy | null>(null);
  const [editorYaml, setEditorYaml] = useState('');
  const [editorChangelog, setEditorChangelog] = useState('');
  const [selectedVersionPolicy, setSelectedVersionPolicy] = useState<Policy | null>(null);
  const [deleteConfirm, setDeleteConfirm] = useState<Policy | null>(null);
  const [search, setSearch] = useState('');

  const fetchData = useCallback(async () => {
    const [polRes, assignRes, usersRes, groupsRes] = await Promise.all([
      supabase.from('policies').select('*').order('created_at', { ascending: true }),
      supabase.from('policy_assignments').select('*, policy:policies(*)').order('priority', { ascending: false }),
      supabase.from('users').select('*, group:groups(*)').order('username'),
      supabase.from('groups').select('*, policy:policies(*)').order('name'),
    ]);
    setPolicies((polRes.data || []) as Policy[]);
    setAssignments((assignRes.data || []) as PolicyAssignment[]);
    setUsers((usersRes.data || []) as User[]);
    setGroups((groupsRes.data || []) as Group[]);
    setLoading(false);
  }, []);

  useEffect(() => { fetchData(); }, [fetchData]);

  const fetchVersions = async (policyId: string) => {
    const { data } = await supabase
      .from('policy_versions')
      .select('*')
      .eq('policy_id', policyId)
      .order('created_at', { ascending: false });
    setVersions((data || []) as PolicyVersion[]);
  };

  const handleEdit = (policy: Policy) => {
    setEditingPolicy(policy);
    setEditorYaml(policy.yaml);
    setEditorChangelog('');
    setActiveTab('editor');
  };

  const handleSave = async () => {
    if (!editingPolicy) return;

    const parts = editingPolicy.current_version.split('.');
    const newVersion = `${parts[0]}.${parseInt(parts[1]) + 1}.${parts[2]}`;

    await supabase.from('policy_versions').insert({
      policy_id: editingPolicy.id,
      version: editingPolicy.current_version,
      yaml: editingPolicy.yaml,
      changelog: editorChangelog || 'No changelog provided',
    });

    await supabase.from('policies').update({
      yaml: editorYaml,
      current_version: newVersion,
      updated_at: new Date().toISOString(),
    }).eq('id', editingPolicy.id);

    setEditingPolicy(null);
    setActiveTab('library');
    fetchData();
  };

  const handleClone = async (policy: Policy) => {
    const newName = `${policy.name}-copy`;
    await supabase.from('policies').insert({
      name: newName,
      tier: policy.tier,
      description: `Copy of ${policy.name}`,
      current_version: '1.0.0',
      yaml: policy.yaml,
    });
    fetchData();
  };

  const handleDelete = async (policy: Policy) => {
    const usedBy = assignments.filter((a) => a.policy_id === policy.id);
    if (usedBy.length > 0) return;
    await supabase.from('policies').delete().eq('id', policy.id);
    setDeleteConfirm(null);
    fetchData();
  };

  const handleAssignmentChange = async (entityType: string, entityId: string, policyId: string) => {
    const existing = assignments.find((a) => a.entity_type === entityType && a.entity_id === entityId);
    if (existing) {
      await supabase.from('policy_assignments').update({ policy_id: policyId }).eq('id', existing.id);
    } else {
      await supabase.from('policy_assignments').insert({
        entity_type: entityType,
        entity_id: entityId,
        policy_id: policyId,
        priority: entityType === 'user' ? 30 : entityType === 'group' ? 20 : 10,
      });
    }
    fetchData();
  };

  const getAssignmentCount = (policyId: string) =>
    assignments.filter((a) => a.policy_id === policyId).length;

  const tabs = [
    { id: 'library', label: 'Policy Library' },
    { id: 'editor', label: 'Editor' },
    { id: 'assignments', label: 'Assignments' },
  ];

  if (loading) return <LoadingState rows={6} />;

  const filteredPolicies = policies.filter((p) =>
    !search || p.name.toLowerCase().includes(search.toLowerCase()) || p.description.toLowerCase().includes(search.toLowerCase())
  );

  return (
    <div className="space-y-4">
      <Tabs tabs={tabs} activeTab={activeTab} onChange={setActiveTab} />

      {activeTab === 'library' && (
        <div className="space-y-4">
          <div className="flex items-center gap-3">
            <div className="relative flex-1 max-w-sm">
              <Search className="absolute left-3 top-1/2 -translate-y-1/2 w-4 h-4 text-zinc-400" />
              <input
                type="text"
                value={search}
                onChange={(e) => setSearch(e.target.value)}
                placeholder="Search policies..."
                className="w-full pl-9 pr-3 py-2 bg-white border border-zinc-200 rounded-lg text-sm focus:outline-none focus:ring-2 focus:ring-teal-500/20 focus:border-teal-400"
              />
            </div>
          </div>

          <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-4">
            {filteredPolicies.map((policy) => (
              <div
                key={policy.id}
                className="bg-white rounded-xl border border-zinc-200 p-5 hover:shadow-md transition-all group"
              >
                <div className="flex items-start justify-between mb-3">
                  <div className="flex items-center gap-2">
                    <div className="w-8 h-8 rounded-lg bg-zinc-50 flex items-center justify-center">
                      <Shield className="w-4 h-4 text-zinc-500" />
                    </div>
                    <div>
                      <h3 className="text-sm font-semibold text-zinc-900">{policy.name}</h3>
                      <p className="text-[11px] text-zinc-400">v{policy.current_version}</p>
                    </div>
                  </div>
                  <Badge variant="tier" value={policy.tier}>{policy.tier}</Badge>
                </div>

                <p className="text-xs text-zinc-500 mb-4 line-clamp-2">{policy.description}</p>

                <div className="flex items-center justify-between text-xs text-zinc-400 mb-4">
                  <span className="flex items-center gap-1">
                    <Users className="w-3 h-3" /> {getAssignmentCount(policy.id)} assignments
                  </span>
                  <span>Updated {formatRelativeTime(policy.updated_at)}</span>
                </div>

                <div className="flex items-center gap-1 pt-3 border-t border-zinc-100">
                  <button
                    onClick={() => handleEdit(policy)}
                    className="flex items-center gap-1 px-2.5 py-1.5 text-xs font-medium text-zinc-600 hover:bg-zinc-100 rounded-lg transition-colors"
                  >
                    <Pencil className="w-3 h-3" /> Edit
                  </button>
                  <button
                    onClick={() => handleClone(policy)}
                    className="flex items-center gap-1 px-2.5 py-1.5 text-xs font-medium text-zinc-600 hover:bg-zinc-100 rounded-lg transition-colors"
                  >
                    <Copy className="w-3 h-3" /> Clone
                  </button>
                  <button
                    onClick={() => { setSelectedVersionPolicy(policy); fetchVersions(policy.id); }}
                    className="flex items-center gap-1 px-2.5 py-1.5 text-xs font-medium text-zinc-600 hover:bg-zinc-100 rounded-lg transition-colors"
                  >
                    <History className="w-3 h-3" /> History
                  </button>
                  {getAssignmentCount(policy.id) === 0 && (
                    <button
                      onClick={() => setDeleteConfirm(policy)}
                      className="flex items-center gap-1 px-2.5 py-1.5 text-xs font-medium text-red-500 hover:bg-red-50 rounded-lg transition-colors ml-auto"
                    >
                      <Trash2 className="w-3 h-3" />
                    </button>
                  )}
                </div>
              </div>
            ))}

            <button
              onClick={() => {
                setEditingPolicy({
                  id: '',
                  name: 'new-policy',
                  tier: 'restricted',
                  description: 'New policy',
                  current_version: '1.0.0',
                  yaml: 'metadata:\n  name: new-policy\n  tier: restricted\n  version: "1.0.0"\n\nnetwork:\n  egress: []\n  default: deny\n\nfilesystem:\n  writable:\n    - /home/user\n    - /tmp\n  readable:\n    - /home/user\n    - /tmp\n    - /usr\n    - /lib\n  default: deny\n\nprocess:\n  allow_sudo: false\n  allow_ptrace: false',
                  created_at: '',
                  updated_at: '',
                });
                setEditorYaml('metadata:\n  name: new-policy\n  tier: restricted\n  version: "1.0.0"\n\nnetwork:\n  egress: []\n  default: deny\n\nfilesystem:\n  writable:\n    - /home/user\n    - /tmp\n  readable:\n    - /home/user\n    - /tmp\n    - /usr\n    - /lib\n  default: deny\n\nprocess:\n  allow_sudo: false\n  allow_ptrace: false');
                setEditorChangelog('');
                setActiveTab('editor');
              }}
              className="border-2 border-dashed border-zinc-200 rounded-xl p-5 flex flex-col items-center justify-center gap-2 hover:border-teal-400 hover:bg-teal-50/30 transition-all text-zinc-400 hover:text-teal-600"
            >
              <Plus className="w-6 h-6" />
              <span className="text-sm font-medium">New Policy</span>
            </button>
          </div>
        </div>
      )}

      {activeTab === 'editor' && editingPolicy && (
        <div className="space-y-4">
          <div className="flex items-center gap-3">
            <button
              onClick={() => { setActiveTab('library'); setEditingPolicy(null); }}
              className="p-1.5 rounded-lg hover:bg-zinc-100 text-zinc-400 hover:text-zinc-600"
            >
              <ArrowLeft className="w-4 h-4" />
            </button>
            <div className="flex-1">
              <h3 className="text-sm font-semibold text-zinc-900">
                {editingPolicy.id ? `Editing: ${editingPolicy.name}` : 'New Policy'}
              </h3>
              <p className="text-xs text-zinc-400">
                {editingPolicy.id ? `Current version: ${editingPolicy.current_version}` : 'Creating new policy'}
              </p>
            </div>
            <div className="flex gap-2">
              <button
                onClick={() => { setActiveTab('library'); setEditingPolicy(null); }}
                className="px-3 py-1.5 text-sm text-zinc-600 hover:bg-zinc-100 rounded-lg transition-colors flex items-center gap-1"
              >
                <X className="w-3.5 h-3.5" /> Cancel
              </button>
              <button
                onClick={editingPolicy.id ? handleSave : async () => {
                  const nameMatch = editorYaml.match(/name:\s*(\S+)/);
                  const tierMatch = editorYaml.match(/tier:\s*(\S+)/);
                  const descMatch = editorYaml.match(/description:\s*"?([^"\n]+)"?/);
                  await supabase.from('policies').insert({
                    name: nameMatch?.[1] || 'new-policy',
                    tier: tierMatch?.[1] || 'restricted',
                    description: descMatch?.[1] || '',
                    current_version: '1.0.0',
                    yaml: editorYaml,
                  });
                  setEditingPolicy(null);
                  setActiveTab('library');
                  fetchData();
                }}
                className="px-3 py-1.5 text-sm font-medium text-white bg-teal-600 hover:bg-teal-500 rounded-lg transition-colors flex items-center gap-1"
              >
                <Save className="w-3.5 h-3.5" /> Save
              </button>
            </div>
          </div>

          <div className="grid grid-cols-1 lg:grid-cols-2 gap-4">
            <div className="bg-white rounded-xl border border-zinc-200 overflow-hidden">
              <div className="px-4 py-2.5 bg-zinc-50 border-b border-zinc-200 flex items-center justify-between">
                <span className="text-xs font-medium text-zinc-500">YAML Source</span>
              </div>
              <textarea
                value={editorYaml}
                onChange={(e) => setEditorYaml(e.target.value)}
                className="w-full h-[500px] p-4 font-mono text-sm text-zinc-800 bg-white resize-none focus:outline-none leading-relaxed"
                spellCheck={false}
              />
            </div>

            <div className="space-y-4">
              <div className="bg-white rounded-xl border border-zinc-200 overflow-hidden">
                <div className="px-4 py-2.5 bg-zinc-50 border-b border-zinc-200">
                  <span className="text-xs font-medium text-zinc-500">Policy Summary</span>
                </div>
                <div className="p-4 space-y-4 max-h-[400px] overflow-y-auto">
                  <PolicySummarySection yaml={editorYaml} />
                </div>
              </div>

              {editingPolicy.id && (
                <div className="bg-white rounded-xl border border-zinc-200 p-4">
                  <label className="block text-xs font-medium text-zinc-500 mb-1.5">Changelog</label>
                  <textarea
                    value={editorChangelog}
                    onChange={(e) => setEditorChangelog(e.target.value)}
                    placeholder="Describe what changed in this version..."
                    className="w-full h-20 px-3 py-2 border border-zinc-200 rounded-lg text-sm resize-none focus:outline-none focus:ring-2 focus:ring-teal-500/20 focus:border-teal-400"
                  />
                </div>
              )}
            </div>
          </div>
        </div>
      )}

      {activeTab === 'assignments' && (
        <div className="grid grid-cols-1 lg:grid-cols-3 gap-6">
          <div className="bg-white rounded-xl border border-zinc-200 overflow-hidden">
            <div className="px-5 py-3 border-b border-zinc-100">
              <h3 className="text-sm font-semibold text-zinc-900">User Overrides</h3>
              <p className="text-xs text-zinc-400">Highest priority</p>
            </div>
            <div className="divide-y divide-zinc-50">
              {users.map((user) => {
                const userAssignment = assignments.find(
                  (a) => a.entity_type === 'user' && a.entity_id === user.id
                );
                return (
                  <div key={user.id} className="px-5 py-3 flex items-center justify-between gap-2">
                    <div className="min-w-0">
                      <p className="text-sm font-medium text-zinc-900 truncate">{user.username}</p>
                      <p className="text-[11px] text-zinc-400">{user.owui_role}</p>
                    </div>
                    <select
                      value={userAssignment?.policy_id || ''}
                      onChange={(e) => {
                        if (e.target.value) {
                          handleAssignmentChange('user', user.id, e.target.value);
                        }
                      }}
                      className="text-xs border border-zinc-200 rounded-lg px-2 py-1.5 bg-white focus:outline-none focus:ring-2 focus:ring-teal-500/20 max-w-[140px]"
                    >
                      <option value="">Inherit</option>
                      {policies.map((p) => (
                        <option key={p.id} value={p.id}>{p.name}</option>
                      ))}
                    </select>
                  </div>
                );
              })}
            </div>
          </div>

          <div className="bg-white rounded-xl border border-zinc-200 overflow-hidden">
            <div className="px-5 py-3 border-b border-zinc-100">
              <h3 className="text-sm font-semibold text-zinc-900">Group Assignments</h3>
              <p className="text-xs text-zinc-400">Medium priority</p>
            </div>
            <div className="divide-y divide-zinc-50">
              {groups.map((group) => {
                const groupAssignment = assignments.find(
                  (a) => a.entity_type === 'group' && a.entity_id === group.id
                );
                return (
                  <div key={group.id} className="px-5 py-3 flex items-center justify-between gap-2">
                    <div className="min-w-0">
                      <p className="text-sm font-medium text-zinc-900 truncate">{group.name}</p>
                      <p className="text-[11px] text-zinc-400">{group.description}</p>
                    </div>
                    <select
                      value={groupAssignment?.policy_id || group.policy_id || ''}
                      onChange={(e) => handleAssignmentChange('group', group.id, e.target.value)}
                      className="text-xs border border-zinc-200 rounded-lg px-2 py-1.5 bg-white focus:outline-none focus:ring-2 focus:ring-teal-500/20 max-w-[140px]"
                    >
                      <option value="">None</option>
                      {policies.map((p) => (
                        <option key={p.id} value={p.id}>{p.name}</option>
                      ))}
                    </select>
                  </div>
                );
              })}
            </div>
          </div>

          <div className="bg-white rounded-xl border border-zinc-200 overflow-hidden">
            <div className="px-5 py-3 border-b border-zinc-100">
              <h3 className="text-sm font-semibold text-zinc-900">Role Defaults</h3>
              <p className="text-xs text-zinc-400">Lowest priority</p>
            </div>
            <div className="divide-y divide-zinc-50">
              {['admin', 'user', 'pending'].map((role) => {
                const roleAssignment = assignments.find(
                  (a) => a.entity_type === 'role' && a.entity_id === role
                );
                return (
                  <div key={role} className="px-5 py-3 flex items-center justify-between gap-2">
                    <div>
                      <p className="text-sm font-medium text-zinc-900 capitalize">{role}</p>
                      <p className="text-[11px] text-zinc-400">Open WebUI role</p>
                    </div>
                    <select
                      value={roleAssignment?.policy_id || ''}
                      onChange={(e) => handleAssignmentChange('role', role, e.target.value)}
                      className="text-xs border border-zinc-200 rounded-lg px-2 py-1.5 bg-white focus:outline-none focus:ring-2 focus:ring-teal-500/20 max-w-[140px]"
                    >
                      <option value="">None</option>
                      {policies.map((p) => (
                        <option key={p.id} value={p.id}>{p.name}</option>
                      ))}
                    </select>
                  </div>
                );
              })}
            </div>
          </div>
        </div>
      )}

      <Modal
        open={!!selectedVersionPolicy}
        onClose={() => setSelectedVersionPolicy(null)}
        title={`Version History: ${selectedVersionPolicy?.name || ''}`}
      >
        <div className="space-y-3 max-h-64 overflow-y-auto">
          {versions.length === 0 ? (
            <p className="text-sm text-zinc-500">No previous versions</p>
          ) : (
            versions.map((v) => (
              <div key={v.id} className="flex items-start gap-3 p-3 bg-zinc-50 rounded-lg">
                <div className="flex-shrink-0 w-16">
                  <span className="text-sm font-mono font-medium text-zinc-700">v{v.version}</span>
                </div>
                <div className="flex-1 min-w-0">
                  <p className="text-xs text-zinc-600">{v.changelog}</p>
                  <p className="text-[11px] text-zinc-400 mt-1">{formatRelativeTime(v.created_at)}</p>
                </div>
                <ChevronRight className="w-4 h-4 text-zinc-300 flex-shrink-0" />
              </div>
            ))
          )}
        </div>
      </Modal>

      <Modal
        open={!!deleteConfirm}
        onClose={() => setDeleteConfirm(null)}
        title="Delete Policy"
        actions={
          <>
            <button
              onClick={() => setDeleteConfirm(null)}
              className="px-4 py-2 text-sm text-zinc-600 hover:bg-zinc-100 rounded-lg transition-colors"
            >
              Cancel
            </button>
            <button
              onClick={() => deleteConfirm && handleDelete(deleteConfirm)}
              className="px-4 py-2 text-sm font-medium text-white bg-red-600 hover:bg-red-500 rounded-lg transition-colors"
            >
              Delete
            </button>
          </>
        }
      >
        <p className="text-sm text-zinc-600">
          Are you sure you want to delete the policy <strong>{deleteConfirm?.name}</strong>?
        </p>
      </Modal>
    </div>
  );
}

function PolicySummarySection({ yaml }: { yaml: string }) {
  const lines = yaml.split('\n');

  const getSection = (name: string): string[] => {
    const startIdx = lines.findIndex((l) => l.trim().startsWith(`${name}:`));
    if (startIdx === -1) return [];
    const result: string[] = [];
    for (let i = startIdx + 1; i < lines.length; i++) {
      const line = lines[i];
      if (line.trim() === '' || (!line.startsWith(' ') && !line.startsWith('\t') && line.trim() !== '')) break;
      result.push(line);
    }
    return result;
  };

  const networkLines = getSection('network');
  const fsLines = getSection('filesystem');
  const processLines = getSection('process');

  const egressRules = networkLines
    .filter((l) => l.includes('destination:'))
    .map((l) => l.split(':').slice(1).join(':').trim().replace(/"/g, ''));

  const writablePaths = fsLines
    .filter((l) => l.trim().startsWith('- /'))
    .map((l) => l.trim().replace('- ', ''));

  const allowSudo = processLines.some((l) => l.includes('allow_sudo: true'));

  return (
    <>
      <div>
        <h4 className="text-xs font-semibold text-zinc-500 uppercase tracking-wider mb-2">Network Egress</h4>
        {egressRules.length > 0 ? (
          <div className="flex flex-wrap gap-1">
            {egressRules.map((r, i) => (
              <span key={i} className="px-2 py-1 bg-teal-50 text-teal-700 text-xs rounded-md">{r}</span>
            ))}
          </div>
        ) : (
          <p className="text-xs text-zinc-400">No egress rules defined</p>
        )}
      </div>
      <div>
        <h4 className="text-xs font-semibold text-zinc-500 uppercase tracking-wider mb-2">Filesystem</h4>
        {writablePaths.length > 0 ? (
          <div className="flex flex-wrap gap-1">
            {writablePaths.map((p, i) => (
              <span key={i} className="px-2 py-1 bg-zinc-100 text-zinc-600 text-xs rounded-md font-mono">{p}</span>
            ))}
          </div>
        ) : (
          <p className="text-xs text-zinc-400">No writable paths</p>
        )}
      </div>
      <div>
        <h4 className="text-xs font-semibold text-zinc-500 uppercase tracking-wider mb-2">Process</h4>
        <div className="flex gap-2">
          <span className={`px-2 py-1 text-xs rounded-md ${allowSudo ? 'bg-red-50 text-red-600' : 'bg-emerald-50 text-emerald-600'}`}>
            sudo: {allowSudo ? 'allowed' : 'blocked'}
          </span>
        </div>
      </div>
    </>
  );
}
