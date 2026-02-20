import { Outlet } from 'react-router-dom';
import AdminChatWidget from '@/components/AdminChatWidget';
import Sidebar from '@/components/Sidebar';
import { useAuth } from '@/hooks/useAuth';

function AppLayout() {
  const { user } = useAuth();

  return (
    <div className="min-h-screen md:grid md:grid-cols-[260px_1fr]">
      <Sidebar />
      <div className="md:pl-2">
        <header className="sticky top-0 z-30 border-b border-slate-700/60 bg-surface-900/90 px-4 py-4 backdrop-blur md:px-8">
          <div className="mx-auto flex max-w-7xl items-center justify-between gap-3">
            <div>
              <p className="text-xs uppercase tracking-[0.14em] text-slate-400">Monitoring</p>
              <p className="text-sm font-semibold text-slate-100">
                {user ? `${user.name} (${user.role})` : 'Session'}
              </p>
            </div>
            <p className="text-xs text-slate-500">Traceability | Compliance | Integrity</p>
          </div>
        </header>
        <main className="mx-auto max-w-7xl px-4 py-6 md:px-8">
          <Outlet />
        </main>
        <AdminChatWidget />
      </div>
    </div>
  );
}

export default AppLayout;
