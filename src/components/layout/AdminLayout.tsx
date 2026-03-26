import { Outlet } from 'react-router-dom';
import { Sidebar } from './Sidebar';
import { TopBar } from './TopBar';

export function AdminLayout() {
  return (
    <div className="min-h-screen bg-zinc-50">
      <Sidebar />
      <div className="pl-60 transition-all duration-300">
        <TopBar />
        <main className="p-6">
          <Outlet />
        </main>
      </div>
    </div>
  );
}
