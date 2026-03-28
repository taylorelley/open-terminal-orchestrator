import { useState, useEffect, useCallback } from 'react';
import {
  Save,
  Download,
  Upload,
  Key,
  Plus,
  Trash2,
  Copy,
  Check,
  Archive,
} from 'lucide-react';
import { supabase } from '../lib/supabase';
import { Tabs } from '../components/ui/Tabs';
import { LoadingState } from '../components/ui/EmptyState';
import type { SystemConfig } from '../types';

interface ConfigState {
  general: {
    instance_name: string;
    base_url: string;
    openshell_gateway: string;
    owui_endpoint: string;
    byoc_image: string;
  };
  pool: {
    warmup_size: number;
    max_sandboxes: number;
    max_active: number;
  };
  lifecycle: {
    idle_timeout: string;
    suspend_timeout: string;
    startup_timeout: string;
    resume_timeout: string;
  };
  auth: {
    method: string;
    oidc_issuer: string;
    oidc_client_id: string;
    oidc_redirect_uri: string;
  };
  integrations: {
    litellm_url: string;
    prometheus_enabled: boolean;
    webhook_url: string;
    syslog_enabled: boolean;
  };
}

const defaultConfig: ConfigState = {
  general: { instance_name: '', base_url: '', openshell_gateway: '', owui_endpoint: '', byoc_image: '' },
  pool: { warmup_size: 2, max_sandboxes: 20, max_active: 10 },
  lifecycle: { idle_timeout: '30m', suspend_timeout: '24h', startup_timeout: '120s', resume_timeout: '30s' },
  auth: { method: 'local', oidc_issuer: '', oidc_client_id: '', oidc_redirect_uri: '' },
  integrations: { litellm_url: '', prometheus_enabled: true, webhook_url: '', syslog_enabled: false },
};

export default function Settings() {
  const [activeTab, setActiveTab] = useState('general');
  const [config, setConfig] = useState<ConfigState>(defaultConfig);
  const [loading, setLoading] = useState(true);
  const [saving, setSaving] = useState(false);
  const [saved, setSaved] = useState(false);
  const [apiKeys, setApiKeys] = useState<{ id: string; name: string; key: string; created_at: string }[]>([
    { id: '1', name: 'Management API Key', key: 'sg-key-a1b2c3d4e5f6', created_at: new Date(Date.now() - 86400000 * 10).toISOString() },
  ]);
  const [copiedKey, setCopiedKey] = useState<string | null>(null);
  const [backingUp, setBackingUp] = useState(false);

  const fetchConfig = useCallback(async () => {
    const { data } = await supabase.from('system_config').select('*');
    if (data) {
      const configMap: Record<string, unknown> = {};
      (data as SystemConfig[]).forEach((c) => {
        configMap[c.key] = c.value;
      });
      setConfig({
        general: (configMap.general as ConfigState['general']) || defaultConfig.general,
        pool: (configMap.pool as ConfigState['pool']) || defaultConfig.pool,
        lifecycle: (configMap.lifecycle as ConfigState['lifecycle']) || defaultConfig.lifecycle,
        auth: (configMap.auth as ConfigState['auth']) || defaultConfig.auth,
        integrations: (configMap.integrations as ConfigState['integrations']) || defaultConfig.integrations,
      });
    }
    setLoading(false);
  }, []);

  useEffect(() => { fetchConfig(); }, [fetchConfig]);

  const handleSave = async (section: string) => {
    setSaving(true);
    await supabase.from('system_config').upsert({
      key: section,
      value: config[section as keyof ConfigState],
      updated_at: new Date().toISOString(),
    });
    setSaving(false);
    setSaved(true);
    setTimeout(() => setSaved(false), 2000);
  };

  const updateConfig = <K extends keyof ConfigState>(
    section: K,
    field: string,
    value: unknown
  ) => {
    setConfig((prev) => ({
      ...prev,
      [section]: { ...prev[section], [field]: value },
    }));
  };

  const handleExportPolicies = async () => {
    const { data } = await supabase.from('policies').select('*');
    const blob = new Blob([JSON.stringify(data, null, 2)], { type: 'application/json' });
    const url = URL.createObjectURL(blob);
    const a = document.createElement('a');
    a.href = url;
    a.download = `shellguard-policies-${Date.now()}.json`;
    a.click();
    URL.revokeObjectURL(url);
  };

  const handleExportConfig = () => {
    const blob = new Blob([JSON.stringify(config, null, 2)], { type: 'application/json' });
    const url = URL.createObjectURL(blob);
    const a = document.createElement('a');
    a.href = url;
    a.download = `shellguard-config-${Date.now()}.json`;
    a.click();
    URL.revokeObjectURL(url);
  };

  const handleFullBackup = async () => {
    setBackingUp(true);
    try {
      const res = await fetch('/admin/api/backup', { method: 'POST' });
      const blob = await res.blob();
      const disposition = res.headers.get('Content-Disposition') || '';
      const match = disposition.match(/filename=(.+)/);
      const filename = match ? match[1] : `shellguard-backup-${Date.now()}.json`;
      const url = URL.createObjectURL(blob);
      const a = document.createElement('a');
      a.href = url;
      a.download = filename;
      a.click();
      URL.revokeObjectURL(url);
    } finally {
      setBackingUp(false);
    }
  };

  const copyToClipboard = (text: string, id: string) => {
    navigator.clipboard.writeText(text);
    setCopiedKey(id);
    setTimeout(() => setCopiedKey(null), 2000);
  };

  const tabs = [
    { id: 'general', label: 'General' },
    { id: 'pool', label: 'Pool & Lifecycle' },
    { id: 'auth', label: 'Authentication' },
    { id: 'integrations', label: 'Integrations' },
    { id: 'backup', label: 'Backup & Export' },
  ];

  if (loading) return <LoadingState rows={6} />;

  return (
    <div className="space-y-4">
      <Tabs tabs={tabs} activeTab={activeTab} onChange={setActiveTab} />

      {activeTab === 'general' && (
        <div className="max-w-2xl space-y-6">
          <div className="bg-white rounded-xl border border-zinc-200 p-6 space-y-4">
            <h3 className="text-sm font-semibold text-zinc-900">Instance Configuration</h3>
            {[
              { label: 'Instance Name', field: 'instance_name', placeholder: 'ShellGuard Production' },
              { label: 'Base URL', field: 'base_url', placeholder: 'http://shellguard:8080' },
              { label: 'OpenShell Gateway', field: 'openshell_gateway', placeholder: 'http://openshell-gateway:6443' },
              { label: 'Open WebUI Endpoint', field: 'owui_endpoint', placeholder: 'http://open-webui:3000' },
              { label: 'BYOC Image', field: 'byoc_image', placeholder: 'shellguard-sandbox:slim' },
            ].map((item) => (
              <div key={item.field}>
                <label className="block text-xs font-medium text-zinc-500 mb-1.5">{item.label}</label>
                <input
                  type="text"
                  value={(config.general as Record<string, string>)[item.field] || ''}
                  onChange={(e) => updateConfig('general', item.field, e.target.value)}
                  placeholder={item.placeholder}
                  className="w-full px-3 py-2 border border-zinc-200 rounded-lg text-sm focus:outline-none focus:ring-2 focus:ring-teal-500/20 focus:border-teal-400 font-mono"
                />
              </div>
            ))}
            <div className="pt-2">
              <button
                onClick={() => handleSave('general')}
                disabled={saving}
                className="px-4 py-2 text-sm font-medium text-white bg-teal-600 hover:bg-teal-500 rounded-lg transition-colors flex items-center gap-1.5 disabled:opacity-50"
              >
                {saved ? <Check className="w-3.5 h-3.5" /> : <Save className="w-3.5 h-3.5" />}
                {saved ? 'Saved' : saving ? 'Saving...' : 'Save Changes'}
              </button>
            </div>
          </div>
        </div>
      )}

      {activeTab === 'pool' && (
        <div className="max-w-2xl space-y-6">
          <div className="bg-white rounded-xl border border-zinc-200 p-6 space-y-4">
            <h3 className="text-sm font-semibold text-zinc-900">Pool Settings</h3>
            {[
              { label: 'Warmup Pool Size', field: 'warmup_size', description: 'Number of pre-warmed sandboxes to maintain', type: 'number' },
              { label: 'Max Sandboxes', field: 'max_sandboxes', description: 'Maximum total sandboxes (active + suspended)', type: 'number' },
              { label: 'Max Active', field: 'max_active', description: 'Maximum concurrently running sandboxes', type: 'number' },
            ].map((item) => (
              <div key={item.field}>
                <label className="block text-xs font-medium text-zinc-500 mb-1">{item.label}</label>
                <p className="text-[11px] text-zinc-400 mb-1.5">{item.description}</p>
                <input
                  type="number"
                  value={(config.pool as Record<string, number>)[item.field] || 0}
                  onChange={(e) => updateConfig('pool', item.field, parseInt(e.target.value) || 0)}
                  className="w-full max-w-[120px] px-3 py-2 border border-zinc-200 rounded-lg text-sm focus:outline-none focus:ring-2 focus:ring-teal-500/20 focus:border-teal-400"
                  min={0}
                />
              </div>
            ))}
          </div>

          <div className="bg-white rounded-xl border border-zinc-200 p-6 space-y-4">
            <h3 className="text-sm font-semibold text-zinc-900">Lifecycle Timeouts</h3>
            {[
              { label: 'Idle Timeout', field: 'idle_timeout', description: 'Time after last activity before sandbox is suspended' },
              { label: 'Suspend Timeout', field: 'suspend_timeout', description: 'Time a suspended sandbox is retained before destruction' },
              { label: 'Startup Timeout', field: 'startup_timeout', description: 'Maximum wait for sandbox to reach READY state' },
              { label: 'Resume Timeout', field: 'resume_timeout', description: 'Maximum wait for suspended sandbox to resume' },
            ].map((item) => (
              <div key={item.field}>
                <label className="block text-xs font-medium text-zinc-500 mb-1">{item.label}</label>
                <p className="text-[11px] text-zinc-400 mb-1.5">{item.description}</p>
                <input
                  type="text"
                  value={(config.lifecycle as Record<string, string>)[item.field] || ''}
                  onChange={(e) => updateConfig('lifecycle', item.field, e.target.value)}
                  className="w-full max-w-[120px] px-3 py-2 border border-zinc-200 rounded-lg text-sm focus:outline-none focus:ring-2 focus:ring-teal-500/20 focus:border-teal-400 font-mono"
                />
              </div>
            ))}
            <div className="pt-2 flex gap-2">
              <button
                onClick={() => { handleSave('pool'); handleSave('lifecycle'); }}
                disabled={saving}
                className="px-4 py-2 text-sm font-medium text-white bg-teal-600 hover:bg-teal-500 rounded-lg transition-colors flex items-center gap-1.5 disabled:opacity-50"
              >
                {saved ? <Check className="w-3.5 h-3.5" /> : <Save className="w-3.5 h-3.5" />}
                {saved ? 'Saved' : 'Apply Changes'}
              </button>
            </div>
          </div>
        </div>
      )}

      {activeTab === 'auth' && (
        <div className="max-w-2xl space-y-6">
          <div className="bg-white rounded-xl border border-zinc-200 p-6 space-y-4">
            <h3 className="text-sm font-semibold text-zinc-900">Authentication Method</h3>
            <div className="flex gap-3">
              {['local', 'oidc'].map((method) => (
                <button
                  key={method}
                  onClick={() => updateConfig('auth', 'method', method)}
                  className={`px-4 py-2 text-sm font-medium rounded-lg border transition-colors ${
                    config.auth.method === method
                      ? 'border-teal-500 bg-teal-50 text-teal-700'
                      : 'border-zinc-200 text-zinc-600 hover:bg-zinc-50'
                  }`}
                >
                  {method === 'local' ? 'Local Credentials' : 'OIDC / SSO'}
                </button>
              ))}
            </div>
          </div>

          {config.auth.method === 'oidc' && (
            <div className="bg-white rounded-xl border border-zinc-200 p-6 space-y-4">
              <h3 className="text-sm font-semibold text-zinc-900">OIDC Configuration</h3>
              {[
                { label: 'Issuer URL', field: 'oidc_issuer', placeholder: 'https://auth.example.com/application/o/shellguard/' },
                { label: 'Client ID', field: 'oidc_client_id', placeholder: 'shellguard-client' },
                { label: 'Redirect URI', field: 'oidc_redirect_uri', placeholder: 'http://shellguard:8080/admin/callback' },
              ].map((item) => (
                <div key={item.field}>
                  <label className="block text-xs font-medium text-zinc-500 mb-1.5">{item.label}</label>
                  <input
                    type="text"
                    value={(config.auth as Record<string, string>)[item.field] || ''}
                    onChange={(e) => updateConfig('auth', item.field, e.target.value)}
                    placeholder={item.placeholder}
                    className="w-full px-3 py-2 border border-zinc-200 rounded-lg text-sm focus:outline-none focus:ring-2 focus:ring-teal-500/20 focus:border-teal-400 font-mono"
                  />
                </div>
              ))}
            </div>
          )}

          <div className="bg-white rounded-xl border border-zinc-200 p-6 space-y-4">
            <div className="flex items-center justify-between">
              <div>
                <h3 className="text-sm font-semibold text-zinc-900">API Keys</h3>
                <p className="text-xs text-zinc-400 mt-0.5">Keys for programmatic access to the management API</p>
              </div>
              <button
                onClick={() => {
                  const key = `sg-key-${Math.random().toString(36).slice(2, 14)}`;
                  setApiKeys([...apiKeys, {
                    id: Math.random().toString(),
                    name: `API Key ${apiKeys.length + 1}`,
                    key,
                    created_at: new Date().toISOString(),
                  }]);
                }}
                className="px-3 py-1.5 text-xs font-medium text-teal-700 bg-teal-50 hover:bg-teal-100 rounded-lg transition-colors flex items-center gap-1"
              >
                <Plus className="w-3 h-3" /> Generate Key
              </button>
            </div>

            <div className="space-y-2">
              {apiKeys.map((key) => (
                <div key={key.id} className="flex items-center gap-3 p-3 bg-zinc-50 rounded-lg">
                  <Key className="w-4 h-4 text-zinc-400 flex-shrink-0" />
                  <div className="flex-1 min-w-0">
                    <p className="text-sm font-medium text-zinc-700">{key.name}</p>
                    <p className="text-xs font-mono text-zinc-400 truncate">{key.key}</p>
                  </div>
                  <button
                    onClick={() => copyToClipboard(key.key, key.id)}
                    className="p-1.5 rounded-lg hover:bg-zinc-200 text-zinc-400 transition-colors"
                  >
                    {copiedKey === key.id ? <Check className="w-3.5 h-3.5 text-emerald-500" /> : <Copy className="w-3.5 h-3.5" />}
                  </button>
                  <button
                    onClick={() => setApiKeys(apiKeys.filter((k) => k.id !== key.id))}
                    className="p-1.5 rounded-lg hover:bg-red-100 text-zinc-400 hover:text-red-500 transition-colors"
                  >
                    <Trash2 className="w-3.5 h-3.5" />
                  </button>
                </div>
              ))}
            </div>
          </div>

          <div className="pt-2">
            <button
              onClick={() => handleSave('auth')}
              disabled={saving}
              className="px-4 py-2 text-sm font-medium text-white bg-teal-600 hover:bg-teal-500 rounded-lg transition-colors flex items-center gap-1.5 disabled:opacity-50"
            >
              {saved ? <Check className="w-3.5 h-3.5" /> : <Save className="w-3.5 h-3.5" />}
              {saved ? 'Saved' : 'Save Changes'}
            </button>
          </div>
        </div>
      )}

      {activeTab === 'integrations' && (
        <div className="max-w-2xl space-y-6">
          <div className="bg-white rounded-xl border border-zinc-200 p-6 space-y-4">
            <h3 className="text-sm font-semibold text-zinc-900">LiteLLM Proxy</h3>
            <div>
              <label className="block text-xs font-medium text-zinc-500 mb-1.5">Proxy URL</label>
              <input
                type="text"
                value={config.integrations.litellm_url}
                onChange={(e) => updateConfig('integrations', 'litellm_url', e.target.value)}
                placeholder="http://litellm-proxy:4000"
                className="w-full px-3 py-2 border border-zinc-200 rounded-lg text-sm focus:outline-none focus:ring-2 focus:ring-teal-500/20 focus:border-teal-400 font-mono"
              />
            </div>
          </div>

          <div className="bg-white rounded-xl border border-zinc-200 p-6 space-y-4">
            <h3 className="text-sm font-semibold text-zinc-900">Observability</h3>
            <label className="flex items-center justify-between py-2">
              <div>
                <p className="text-sm text-zinc-700">Prometheus Metrics</p>
                <p className="text-xs text-zinc-400">Expose /admin/api/system/metrics endpoint</p>
              </div>
              <button
                onClick={() => updateConfig('integrations', 'prometheus_enabled', !config.integrations.prometheus_enabled)}
                className={`relative w-11 h-6 rounded-full transition-colors ${
                  config.integrations.prometheus_enabled ? 'bg-teal-500' : 'bg-zinc-300'
                }`}
              >
                <span
                  className={`absolute top-0.5 left-0.5 w-5 h-5 rounded-full bg-white shadow transition-transform ${
                    config.integrations.prometheus_enabled ? 'translate-x-5' : ''
                  }`}
                />
              </button>
            </label>
            <label className="flex items-center justify-between py-2">
              <div>
                <p className="text-sm text-zinc-700">Syslog Forwarding</p>
                <p className="text-xs text-zinc-400">Forward audit events to syslog/SIEM</p>
              </div>
              <button
                onClick={() => updateConfig('integrations', 'syslog_enabled', !config.integrations.syslog_enabled)}
                className={`relative w-11 h-6 rounded-full transition-colors ${
                  config.integrations.syslog_enabled ? 'bg-teal-500' : 'bg-zinc-300'
                }`}
              >
                <span
                  className={`absolute top-0.5 left-0.5 w-5 h-5 rounded-full bg-white shadow transition-transform ${
                    config.integrations.syslog_enabled ? 'translate-x-5' : ''
                  }`}
                />
              </button>
            </label>
          </div>

          <div className="bg-white rounded-xl border border-zinc-200 p-6 space-y-4">
            <h3 className="text-sm font-semibold text-zinc-900">Webhooks</h3>
            <div>
              <label className="block text-xs font-medium text-zinc-500 mb-1.5">Webhook URL</label>
              <input
                type="text"
                value={config.integrations.webhook_url}
                onChange={(e) => updateConfig('integrations', 'webhook_url', e.target.value)}
                placeholder="https://hooks.example.com/shellguard"
                className="w-full px-3 py-2 border border-zinc-200 rounded-lg text-sm focus:outline-none focus:ring-2 focus:ring-teal-500/20 focus:border-teal-400 font-mono"
              />
              <p className="text-[11px] text-zinc-400 mt-1">Lifecycle event notifications will be sent to this URL</p>
            </div>
          </div>

          <button
            onClick={() => handleSave('integrations')}
            disabled={saving}
            className="px-4 py-2 text-sm font-medium text-white bg-teal-600 hover:bg-teal-500 rounded-lg transition-colors flex items-center gap-1.5 disabled:opacity-50"
          >
            {saved ? <Check className="w-3.5 h-3.5" /> : <Save className="w-3.5 h-3.5" />}
            {saved ? 'Saved' : 'Save Changes'}
          </button>
        </div>
      )}

      {activeTab === 'backup' && (
        <div className="max-w-2xl space-y-6">
          <div className="bg-white rounded-xl border border-zinc-200 p-6 space-y-4">
            <h3 className="text-sm font-semibold text-zinc-900">Full Backup</h3>
            <button
              onClick={handleFullBackup}
              disabled={backingUp}
              className="flex items-center gap-3 p-4 w-full border border-teal-200 bg-teal-50 rounded-lg hover:bg-teal-100 transition-colors text-left disabled:opacity-50"
            >
              <Archive className="w-5 h-5 text-teal-600" />
              <div>
                <p className="text-sm font-medium text-teal-800">{backingUp ? 'Creating Backup...' : 'Download Full Backup'}</p>
                <p className="text-xs text-teal-600">Policies, versions, assignments, groups, and configuration</p>
              </div>
            </button>
          </div>

          <div className="bg-white rounded-xl border border-zinc-200 p-6 space-y-4">
            <h3 className="text-sm font-semibold text-zinc-900">Export Individual</h3>
            <div className="grid grid-cols-1 sm:grid-cols-2 gap-3">
              <button
                onClick={handleExportPolicies}
                className="flex items-center gap-3 p-4 border border-zinc-200 rounded-lg hover:bg-zinc-50 transition-colors text-left"
              >
                <Download className="w-5 h-5 text-zinc-400" />
                <div>
                  <p className="text-sm font-medium text-zinc-700">Export Policies</p>
                  <p className="text-xs text-zinc-400">All policies as JSON</p>
                </div>
              </button>
              <button
                onClick={handleExportConfig}
                className="flex items-center gap-3 p-4 border border-zinc-200 rounded-lg hover:bg-zinc-50 transition-colors text-left"
              >
                <Download className="w-5 h-5 text-zinc-400" />
                <div>
                  <p className="text-sm font-medium text-zinc-700">Export Configuration</p>
                  <p className="text-xs text-zinc-400">All settings as JSON</p>
                </div>
              </button>
            </div>
          </div>

          <div className="bg-white rounded-xl border border-zinc-200 p-6 space-y-4">
            <h3 className="text-sm font-semibold text-zinc-900">Import</h3>
            <div className="border-2 border-dashed border-zinc-200 rounded-xl p-8 text-center hover:border-teal-400 transition-colors">
              <Upload className="w-8 h-8 text-zinc-300 mx-auto mb-3" />
              <p className="text-sm text-zinc-500 mb-1">Drop a JSON file or click to upload</p>
              <p className="text-xs text-zinc-400">Supports policy bundles and configuration files</p>
              <input
                type="file"
                accept=".json,.yaml,.yml"
                className="hidden"
                id="import-file"
                onChange={async (e) => {
                  const file = e.target.files?.[0];
                  if (!file) return;
                  const text = await file.text();
                  try {
                    const data = JSON.parse(text);
                    if (Array.isArray(data)) {
                      for (const policy of data) {
                        await supabase.from('policies').upsert({
                          name: policy.name,
                          tier: policy.tier,
                          description: policy.description,
                          current_version: policy.current_version,
                          yaml: policy.yaml,
                        });
                      }
                    }
                  } catch {
                    // invalid file
                  }
                }}
              />
              <label
                htmlFor="import-file"
                className="inline-block mt-3 px-4 py-2 text-sm font-medium text-teal-700 bg-teal-50 hover:bg-teal-100 rounded-lg cursor-pointer transition-colors"
              >
                Choose File
              </label>
            </div>
          </div>
        </div>
      )}
    </div>
  );
}
