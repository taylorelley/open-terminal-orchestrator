import { NavLink } from 'react-router-dom';
import {
  LayoutDashboard,
  Container,
  Shield,
  Users,
  FileText,
  Activity,
  Settings,
  Terminal,
  ChevronLeft,
  ChevronRight,
  BookOpen,
} from 'lucide-react';
import { useState } from 'react';

const navItems = [
  { to: '/admin', icon: LayoutDashboard, label: 'Dashboard', end: true },
  { to: '/admin/sandboxes', icon: Container, label: 'Sandboxes' },
  { to: '/admin/policies', icon: Shield, label: 'Policies' },
  { to: '/admin/users', icon: Users, label: 'Users & Groups' },
  { to: '/admin/audit', icon: FileText, label: 'Audit Log' },
  { to: '/admin/monitoring', icon: Activity, label: 'Monitoring' },
  { to: '/admin/settings', icon: Settings, label: 'Settings' },
];

export function Sidebar() {
  const [collapsed, setCollapsed] = useState(false);

  return (
    <aside
      className={`fixed inset-y-0 left-0 z-30 flex flex-col bg-zinc-950 text-white transition-all duration-300 ${
        collapsed ? 'w-16' : 'w-60'
      }`}
    >
      <div className={`flex items-center h-16 px-4 border-b border-zinc-800 ${collapsed ? 'justify-center' : 'gap-3'}`}>
        <div className="flex-shrink-0 w-8 h-8 bg-teal-500 rounded-lg flex items-center justify-center">
          <Terminal className="w-4 h-4 text-white" />
        </div>
        {!collapsed && (
          <div className="min-w-0">
            <h1 className="text-sm font-bold tracking-tight truncate">Open Terminal Orchestrator</h1>
            <p className="text-[10px] text-zinc-500 font-medium">Sandbox Management</p>
          </div>
        )}
      </div>

      <nav className="flex-1 py-3 px-2 space-y-0.5 overflow-y-auto">
        {navItems.map((item) => (
          <NavLink
            key={item.to}
            to={item.to}
            end={item.end}
            className={({ isActive }) =>
              `flex items-center gap-3 px-3 py-2 rounded-lg text-sm font-medium transition-colors ${
                isActive
                  ? 'bg-teal-500/10 text-teal-400'
                  : 'text-zinc-400 hover:text-zinc-200 hover:bg-zinc-800/50'
              } ${collapsed ? 'justify-center' : ''}`
            }
          >
            <item.icon className="w-[18px] h-[18px] flex-shrink-0" />
            {!collapsed && <span className="truncate">{item.label}</span>}
          </NavLink>
        ))}
      </nav>

      <div className="px-2 pb-2">
        <a
          href="/docs/"
          target="_blank"
          rel="noopener noreferrer"
          className={`flex items-center gap-3 px-3 py-2 rounded-lg text-sm font-medium transition-colors text-zinc-400 hover:text-zinc-200 hover:bg-zinc-800/50 ${collapsed ? 'justify-center' : ''}`}
        >
          <BookOpen className="w-[18px] h-[18px] flex-shrink-0" />
          {!collapsed && <span className="truncate">Documentation</span>}
        </a>
      </div>

      <button
        onClick={() => setCollapsed(!collapsed)}
        className="flex items-center justify-center h-10 border-t border-zinc-800 text-zinc-500 hover:text-zinc-300 transition-colors"
      >
        {collapsed ? <ChevronRight className="w-4 h-4" /> : <ChevronLeft className="w-4 h-4" />}
      </button>
    </aside>
  );
}
