import { useState, useEffect, useCallback } from 'react';
import {
  Users as UsersIcon,
  Plus,
  Search,
  Pencil,
  Trash2,
  Circle,
  RefreshCw,
} from 'lucide-react';
import * as ds from '../lib/dataService';
import { Tabs } from '../components/ui/Tabs';
import { Badge } from '../components/ui/Badge';
import { SlidePanel } from '../components/ui/SlidePanel';
import { Modal } from '../components/ui/Modal';
import { LoadingState } from '../components/ui/EmptyState';
import { formatRelativeTime } from '../lib/utils';
import type { User, Group, Policy, Sandbox, PolicyAssignment } from '../types';

export default function UsersGroups() {
  const [activeTab, setActiveTab] = useState('users');
  const [users, setUsers] = useState<User[]>([]);
  const [groups, setGroups] = useState<Group[]>([]);
  const [policies, setPolicies] = useState<Policy[]>([]);
  const [sandboxes, setSandboxes] = useState<Sandbox[]>([]);
  const [assignments, setAssignments] = useState<PolicyAssignment[]>([]);
  const [loading, setLoading] = useState(true);
  const [selectedUser, setSelectedUser] = useState<User | null>(null);
  const [editGroup, setEditGroup] = useState<{ id?: string; name: string; description: string; policy_id: string } | null>(null);
  const [deleteGroup, setDeleteGroup] = useState<Group | null>(null);
  const [search, setSearch] = useState('');
  const [syncing, setSyncing] = useState(false);

  const fetchData = useCallback(async () => {
    const [usersRes, groupsRes, polRes, sbRes, assignRes] = await Promise.all([
      ds.getUsers(),
      ds.getGroups(),
      ds.getPolicies(),
      ds.getSandboxes({ excludeState: 'DESTROYED' }),
      ds.getPolicyAssignments(),
    ]);
    setUsers(usersRes.data || []);
    setGroups(groupsRes.data || []);
    setPolicies(polRes.data || []);
    setSandboxes(sbRes.data || []);
    setAssignments(assignRes.data || []);
    setLoading(false);
  }, []);

  useEffect(() => { fetchData(); }, [fetchData]);

  const handleSync = async () => {
    setSyncing(true);
    try {
      const res = await fetch('/admin/api/users/sync', { method: 'POST' });
      if (!res.ok) {
        const err = await res.json().catch(() => ({ detail: 'Sync failed' }));
        alert(err.detail || 'User sync failed');
        return;
      }
      await fetchData();
    } catch {
      alert('Failed to connect to the server');
    } finally {
      setSyncing(false);
    }
  };

  const getUserSandbox = (userId: string) =>
    sandboxes.find((s) => s.user_id === userId && ['ACTIVE', 'READY'].includes(s.state));

  const getEffectivePolicy = (user: User): string => {
    const userAssign = assignments.find((a) => a.entity_type === 'user' && a.entity_id === user.id);
    if (userAssign?.policy) return (userAssign.policy as Policy).name;

    if (user.group_id) {
      const groupAssign = assignments.find((a) => a.entity_type === 'group' && a.entity_id === user.group_id);
      if (groupAssign?.policy) return (groupAssign.policy as Policy).name;
      const group = groups.find((g) => g.id === user.group_id);
      if (group?.policy) return (group.policy as Policy).name;
    }

    const roleAssign = assignments.find((a) => a.entity_type === 'role' && a.entity_id === user.owui_role);
    if (roleAssign?.policy) return (roleAssign.policy as Policy).name;

    return 'restricted';
  };

  const getGroupMemberCount = (groupId: string) =>
    users.filter((u) => u.group_id === groupId).length;

  const handleSaveGroup = async () => {
    if (!editGroup) return;
    if (editGroup.id) {
      await ds.updateGroup(editGroup.id, {
        name: editGroup.name,
        description: editGroup.description,
        policy_id: editGroup.policy_id || null,
        updated_at: new Date().toISOString(),
      } as Partial<Group>);
    } else {
      await ds.createGroup({
        name: editGroup.name,
        description: editGroup.description,
        policy_id: editGroup.policy_id || null,
      } as Partial<Group>);
    }
    setEditGroup(null);
    fetchData();
  };

  const handleDeleteGroup = async () => {
    if (!deleteGroup) return;
    await ds.deleteGroup(deleteGroup.id);
    setDeleteGroup(null);
    fetchData();
  };

  const handleUserGroupChange = async (userId: string, groupId: string) => {
    await ds.assignUserGroup(userId, groupId || null);
    fetchData();
  };

  const handleUserPolicyOverride = async (userId: string, policyId: string) => {
    const existing = assignments.find((a) => a.entity_type === 'user' && a.entity_id === userId);
    if (policyId) {
      if (existing) {
        await ds.upsertPolicyAssignment({ id: existing.id, policy_id: policyId });
      } else {
        await ds.upsertPolicyAssignment({
          entity_type: 'user',
          entity_id: userId,
          policy_id: policyId,
          priority: 30,
        });
      }
    } else if (existing) {
      await ds.deletePolicyAssignment(existing.id);
    }
    fetchData();
  };

  const tabs = [
    { id: 'users', label: 'User Directory', count: users.length },
    { id: 'groups', label: 'Groups', count: groups.length },
    { id: 'roles', label: 'Role Mappings' },
  ];

  const filteredUsers = users.filter((u) =>
    !search || u.username.toLowerCase().includes(search.toLowerCase()) || u.email.toLowerCase().includes(search.toLowerCase())
  );

  if (loading) return <LoadingState rows={8} />;

  return (
    <div className="space-y-4">
      <Tabs tabs={tabs} activeTab={activeTab} onChange={setActiveTab} />

      {activeTab === 'users' && (
        <div className="space-y-4">
          <div className="flex items-center gap-3">
            <div className="relative flex-1 max-w-sm">
              <Search className="absolute left-3 top-1/2 -translate-y-1/2 w-4 h-4 text-zinc-400" />
              <input
                type="text"
                value={search}
                onChange={(e) => setSearch(e.target.value)}
                placeholder="Search users..."
                className="w-full pl-9 pr-3 py-2 bg-white border border-zinc-200 rounded-lg text-sm focus:outline-none focus:ring-2 focus:ring-teal-500/20 focus:border-teal-400"
              />
            </div>
            <button
              onClick={handleSync}
              disabled={syncing}
              className="px-3 py-2 text-sm text-zinc-600 bg-white border border-zinc-200 rounded-lg hover:bg-zinc-50 transition-colors flex items-center gap-1.5 disabled:opacity-50"
            >
              <RefreshCw className={`w-3.5 h-3.5${syncing ? ' animate-spin' : ''}`} /> Sync Users
            </button>
          </div>

          <div className="bg-white rounded-xl border border-zinc-200 overflow-hidden">
            <div className="overflow-x-auto">
              <table className="w-full">
                <thead>
                  <tr className="text-left text-xs text-zinc-500 border-b border-zinc-100">
                    <th className="px-5 py-3 font-medium">User</th>
                    <th className="px-5 py-3 font-medium">Email</th>
                    <th className="px-5 py-3 font-medium">Role</th>
                    <th className="px-5 py-3 font-medium">Group</th>
                    <th className="px-5 py-3 font-medium">Effective Policy</th>
                    <th className="px-5 py-3 font-medium">Sandbox</th>
                    <th className="px-5 py-3 font-medium">Synced</th>
                  </tr>
                </thead>
                <tbody className="divide-y divide-zinc-50">
                  {filteredUsers.map((user) => {
                    const sb = getUserSandbox(user.id);
                    const effectivePolicy = getEffectivePolicy(user);
                    return (
                      <tr
                        key={user.id}
                        className="hover:bg-zinc-50/50 transition-colors cursor-pointer"
                        onClick={() => setSelectedUser(user)}
                      >
                        <td className="px-5 py-3">
                          <div className="flex items-center gap-2">
                            <div className="w-7 h-7 rounded-full bg-zinc-100 flex items-center justify-center">
                              <span className="text-xs font-bold text-zinc-600">
                                {user.username[0].toUpperCase()}
                              </span>
                            </div>
                            <span className="text-sm font-medium text-zinc-900">{user.username}</span>
                          </div>
                        </td>
                        <td className="px-5 py-3 text-sm text-zinc-500">{user.email}</td>
                        <td className="px-5 py-3">
                          <Badge variant="role" value={user.owui_role}>{user.owui_role}</Badge>
                        </td>
                        <td className="px-5 py-3 text-sm text-zinc-600">
                          {(user.group as Group | null)?.name || <span className="text-zinc-400">None</span>}
                        </td>
                        <td className="px-5 py-3">
                          <span className="text-sm text-zinc-700">{effectivePolicy}</span>
                        </td>
                        <td className="px-5 py-3">
                          {sb ? (
                            <span className="flex items-center gap-1.5 text-xs text-emerald-600">
                              <Circle className="w-2 h-2 fill-emerald-400" /> Active
                            </span>
                          ) : (
                            <span className="text-xs text-zinc-400">None</span>
                          )}
                        </td>
                        <td className="px-5 py-3 text-xs text-zinc-400">{formatRelativeTime(user.synced_at)}</td>
                      </tr>
                    );
                  })}
                </tbody>
              </table>
            </div>
          </div>
        </div>
      )}

      {activeTab === 'groups' && (
        <div className="space-y-4">
          <div className="flex justify-end">
            <button
              onClick={() => setEditGroup({ name: '', description: '', policy_id: '' })}
              className="px-3 py-2 text-sm font-medium text-white bg-teal-600 hover:bg-teal-500 rounded-lg transition-colors flex items-center gap-1.5"
            >
              <Plus className="w-3.5 h-3.5" /> New Group
            </button>
          </div>

          <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-4">
            {groups.map((group) => (
              <div key={group.id} className="bg-white rounded-xl border border-zinc-200 p-5">
                <div className="flex items-start justify-between mb-3">
                  <div>
                    <h3 className="text-sm font-semibold text-zinc-900">{group.name}</h3>
                    <p className="text-xs text-zinc-400 mt-0.5">{group.description}</p>
                  </div>
                  <div className="flex gap-1">
                    <button
                      onClick={() => setEditGroup({
                        id: group.id,
                        name: group.name,
                        description: group.description,
                        policy_id: group.policy_id || '',
                      })}
                      className="p-1.5 rounded-lg hover:bg-zinc-100 text-zinc-400 hover:text-zinc-600 transition-colors"
                    >
                      <Pencil className="w-3.5 h-3.5" />
                    </button>
                    <button
                      onClick={() => setDeleteGroup(group)}
                      className="p-1.5 rounded-lg hover:bg-red-50 text-zinc-400 hover:text-red-600 transition-colors"
                    >
                      <Trash2 className="w-3.5 h-3.5" />
                    </button>
                  </div>
                </div>

                <div className="flex items-center gap-4 text-xs text-zinc-500 mb-3">
                  <span className="flex items-center gap-1">
                    <UsersIcon className="w-3 h-3" /> {getGroupMemberCount(group.id)} members
                  </span>
                  {group.policy && (
                    <Badge variant="tier" value={(group.policy as Policy).tier}>
                      {(group.policy as Policy).name}
                    </Badge>
                  )}
                </div>

                <div className="pt-3 border-t border-zinc-100">
                  <p className="text-[11px] text-zinc-400 mb-1.5">Members</p>
                  <div className="flex flex-wrap gap-1">
                    {users.filter((u) => u.group_id === group.id).map((u) => (
                      <span key={u.id} className="px-1.5 py-0.5 bg-zinc-100 text-zinc-600 text-[11px] rounded">
                        {u.username}
                      </span>
                    ))}
                    {getGroupMemberCount(group.id) === 0 && (
                      <span className="text-[11px] text-zinc-400">No members</span>
                    )}
                  </div>
                </div>
              </div>
            ))}
          </div>
        </div>
      )}

      {activeTab === 'roles' && (
        <div className="bg-white rounded-xl border border-zinc-200 overflow-hidden max-w-lg">
          <div className="px-5 py-3 border-b border-zinc-100">
            <h3 className="text-sm font-semibold text-zinc-900">Role to Policy Mappings</h3>
            <p className="text-xs text-zinc-400 mt-0.5">Default policy applied when no user or group override exists</p>
          </div>
          <div className="divide-y divide-zinc-50">
            {['admin', 'user', 'pending'].map((role) => {
              const roleAssign = assignments.find((a) => a.entity_type === 'role' && a.entity_id === role);
              return (
                <div key={role} className="px-5 py-4 flex items-center justify-between">
                  <div className="flex items-center gap-3">
                    <Badge variant="role" value={role}>{role}</Badge>
                    <span className="text-sm text-zinc-600">Open WebUI role</span>
                  </div>
                  <select
                    value={roleAssign?.policy_id || ''}
                    onChange={async (e) => {
                      const policyId = e.target.value;
                      if (roleAssign) {
                        await ds.upsertPolicyAssignment({ id: roleAssign.id, policy_id: policyId });
                      } else {
                        await ds.upsertPolicyAssignment({
                          entity_type: 'role',
                          entity_id: role,
                          policy_id: policyId,
                          priority: 10,
                        });
                      }
                      fetchData();
                    }}
                    className="text-sm border border-zinc-200 rounded-lg px-3 py-1.5 bg-white focus:outline-none focus:ring-2 focus:ring-teal-500/20"
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
      )}

      <SlidePanel
        open={!!selectedUser}
        onClose={() => setSelectedUser(null)}
        title={selectedUser?.username || ''}
        subtitle={selectedUser?.email}
      >
        {selectedUser && (
          <div className="space-y-6">
            <div className="grid grid-cols-2 gap-4">
              <div className="bg-zinc-50 rounded-lg p-3">
                <p className="text-xs text-zinc-500 mb-1">Role</p>
                <Badge variant="role" value={selectedUser.owui_role}>{selectedUser.owui_role}</Badge>
              </div>
              <div className="bg-zinc-50 rounded-lg p-3">
                <p className="text-xs text-zinc-500 mb-1">Effective Policy</p>
                <span className="text-sm font-medium text-zinc-700">{getEffectivePolicy(selectedUser)}</span>
              </div>
            </div>

            <div>
              <h4 className="text-xs font-semibold text-zinc-500 uppercase tracking-wider mb-3">Group</h4>
              <select
                value={selectedUser.group_id || ''}
                onChange={(e) => handleUserGroupChange(selectedUser.id, e.target.value)}
                className="w-full px-3 py-2 border border-zinc-200 rounded-lg text-sm focus:outline-none focus:ring-2 focus:ring-teal-500/20"
              >
                <option value="">No group</option>
                {groups.map((g) => (
                  <option key={g.id} value={g.id}>{g.name}</option>
                ))}
              </select>
            </div>

            <div>
              <h4 className="text-xs font-semibold text-zinc-500 uppercase tracking-wider mb-3">Policy Override</h4>
              <select
                value={assignments.find((a) => a.entity_type === 'user' && a.entity_id === selectedUser.id)?.policy_id || ''}
                onChange={(e) => handleUserPolicyOverride(selectedUser.id, e.target.value)}
                className="w-full px-3 py-2 border border-zinc-200 rounded-lg text-sm focus:outline-none focus:ring-2 focus:ring-teal-500/20"
              >
                <option value="">Inherit from group/role</option>
                {policies.map((p) => (
                  <option key={p.id} value={p.id}>{p.name} ({p.tier})</option>
                ))}
              </select>
              {assignments.find((a) => a.entity_type === 'user' && a.entity_id === selectedUser.id) && (
                <p className="text-[11px] text-amber-600 mt-1">This user has a direct policy override</p>
              )}
            </div>

            <div>
              <h4 className="text-xs font-semibold text-zinc-500 uppercase tracking-wider mb-3">Policy Resolution</h4>
              <div className="space-y-2">
                {[
                  {
                    level: 'User Override',
                    value: assignments.find((a) => a.entity_type === 'user' && a.entity_id === selectedUser.id)?.policy,
                  },
                  {
                    level: 'Group',
                    value: selectedUser.group_id
                      ? (groups.find((g) => g.id === selectedUser.group_id)?.policy || null)
                      : null,
                  },
                  {
                    level: 'Role Default',
                    value: assignments.find((a) => a.entity_type === 'role' && a.entity_id === selectedUser.owui_role)?.policy,
                  },
                ].map((item, i) => (
                  <div key={i} className="flex items-center justify-between py-1.5">
                    <span className="text-xs text-zinc-500">{item.level}</span>
                    {item.value ? (
                      <Badge variant="tier" value={(item.value as Policy).tier}>
                        {(item.value as Policy).name}
                      </Badge>
                    ) : (
                      <span className="text-xs text-zinc-300">Not set</span>
                    )}
                  </div>
                ))}
              </div>
            </div>
          </div>
        )}
      </SlidePanel>

      <Modal
        open={!!editGroup}
        onClose={() => setEditGroup(null)}
        title={editGroup?.id ? 'Edit Group' : 'New Group'}
        actions={
          <>
            <button
              onClick={() => setEditGroup(null)}
              className="px-4 py-2 text-sm text-zinc-600 hover:bg-zinc-100 rounded-lg transition-colors"
            >
              Cancel
            </button>
            <button
              onClick={handleSaveGroup}
              className="px-4 py-2 text-sm font-medium text-white bg-teal-600 hover:bg-teal-500 rounded-lg transition-colors"
            >
              {editGroup?.id ? 'Save' : 'Create'}
            </button>
          </>
        }
      >
        {editGroup && (
          <div className="space-y-3">
            <div>
              <label className="block text-xs font-medium text-zinc-500 mb-1">Name</label>
              <input
                type="text"
                value={editGroup.name}
                onChange={(e) => setEditGroup({ ...editGroup, name: e.target.value })}
                className="w-full px-3 py-2 border border-zinc-200 rounded-lg text-sm focus:outline-none focus:ring-2 focus:ring-teal-500/20"
                placeholder="Group name"
              />
            </div>
            <div>
              <label className="block text-xs font-medium text-zinc-500 mb-1">Description</label>
              <input
                type="text"
                value={editGroup.description}
                onChange={(e) => setEditGroup({ ...editGroup, description: e.target.value })}
                className="w-full px-3 py-2 border border-zinc-200 rounded-lg text-sm focus:outline-none focus:ring-2 focus:ring-teal-500/20"
                placeholder="Brief description"
              />
            </div>
            <div>
              <label className="block text-xs font-medium text-zinc-500 mb-1">Default Policy</label>
              <select
                value={editGroup.policy_id}
                onChange={(e) => setEditGroup({ ...editGroup, policy_id: e.target.value })}
                className="w-full px-3 py-2 border border-zinc-200 rounded-lg text-sm focus:outline-none focus:ring-2 focus:ring-teal-500/20"
              >
                <option value="">None</option>
                {policies.map((p) => (
                  <option key={p.id} value={p.id}>{p.name}</option>
                ))}
              </select>
            </div>
          </div>
        )}
      </Modal>

      <Modal
        open={!!deleteGroup}
        onClose={() => setDeleteGroup(null)}
        title="Delete Group"
        actions={
          <>
            <button
              onClick={() => setDeleteGroup(null)}
              className="px-4 py-2 text-sm text-zinc-600 hover:bg-zinc-100 rounded-lg transition-colors"
            >
              Cancel
            </button>
            <button
              onClick={handleDeleteGroup}
              className="px-4 py-2 text-sm font-medium text-white bg-red-600 hover:bg-red-500 rounded-lg transition-colors"
            >
              Delete
            </button>
          </>
        }
      >
        <p className="text-sm text-zinc-600">
          Are you sure you want to delete <strong>{deleteGroup?.name}</strong>?
          Members will be unassigned from this group.
        </p>
      </Modal>
    </div>
  );
}
