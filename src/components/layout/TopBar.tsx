import { useLocation } from 'react-router-dom';
import { LogOut, User, Circle } from 'lucide-react';
import { useState, useRef, useEffect } from 'react';
import { useAuth } from '../../contexts/AuthContext';

const routeTitles: Record<string, string> = {
  '/admin': 'Dashboard',
  '/admin/sandboxes': 'Sandboxes',
  '/admin/policies': 'Policies',
  '/admin/users': 'Users & Groups',
  '/admin/audit': 'Audit Log',
  '/admin/monitoring': 'Monitoring',
  '/admin/settings': 'Settings',
};

export function TopBar() {
  const { pathname } = useLocation();
  const { user, oidcSession, signOut } = useAuth();
  const [menuOpen, setMenuOpen] = useState(false);
  const menuRef = useRef<HTMLDivElement>(null);

  const title = routeTitles[pathname] || 'ShellGuard';

  useEffect(() => {
    const handleClick = (e: MouseEvent) => {
      if (menuRef.current && !menuRef.current.contains(e.target as Node)) {
        setMenuOpen(false);
      }
    };
    document.addEventListener('mousedown', handleClick);
    return () => document.removeEventListener('mousedown', handleClick);
  }, []);

  return (
    <header className="h-16 bg-white border-b border-zinc-200 flex items-center justify-between px-6">
      <div className="flex items-center gap-3">
        <h2 className="text-lg font-semibold text-zinc-900">{title}</h2>
      </div>

      <div className="flex items-center gap-4">
        <div className="flex items-center gap-2 text-xs text-zinc-500">
          <Circle className="w-2.5 h-2.5 fill-emerald-400 text-emerald-400" />
          <span>Gateway Connected</span>
        </div>

        <div className="relative" ref={menuRef}>
          <button
            onClick={() => setMenuOpen(!menuOpen)}
            className="flex items-center gap-2 px-2 py-1.5 rounded-lg hover:bg-zinc-50 transition-colors"
          >
            <div className="w-7 h-7 rounded-full bg-zinc-200 flex items-center justify-center">
              <User className="w-3.5 h-3.5 text-zinc-600" />
            </div>
            <span className="text-sm font-medium text-zinc-700 hidden sm:block">
              {oidcSession?.name || user?.email?.split('@')[0] || 'Admin'}
            </span>
          </button>

          {menuOpen && (
            <div className="absolute right-0 top-full mt-1 w-48 bg-white rounded-xl shadow-lg border border-zinc-200 py-1 z-50">
              <div className="px-3 py-2 border-b border-zinc-100">
                <p className="text-xs text-zinc-500 truncate">{oidcSession?.email || user?.email}</p>
              </div>
              <button
                onClick={() => { signOut(); setMenuOpen(false); }}
                className="w-full flex items-center gap-2 px-3 py-2 text-sm text-zinc-600 hover:bg-zinc-50 transition-colors"
              >
                <LogOut className="w-3.5 h-3.5" />
                Sign Out
              </button>
            </div>
          )}
        </div>
      </div>
    </header>
  );
}
