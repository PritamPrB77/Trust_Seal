import clsx from 'clsx';
import { NavLink } from 'react-router-dom';
import { useAuth } from '@/hooks/useAuth';
import { getStatusLabel } from '@/utils/status';

const links = [
  { to: '/dashboard', label: 'Dashboard' },
  { to: '/devices', label: 'Devices' },
  { to: '/shipments', label: 'Shipments' },
  { to: '/lookup', label: 'QR Lookup' },
];

function Sidebar() {
  const { user, logout } = useAuth();

  return (
    <aside className="panel mb-4 flex w-full flex-col p-5 md:sticky md:top-0 md:mb-0 md:h-screen md:w-[260px]">
      <div>
        <p className="text-xs uppercase tracking-[0.22em] text-brand-300">TrustSeal IoT</p>
        <h1 className="mt-2 text-xl font-semibold text-slate-100">Supply Chain Console</h1>
      </div>

      <nav className="mt-8 flex flex-1 flex-col gap-2">
        {links.map((link) => (
          <NavLink
            key={link.to}
            to={link.to}
            className={({ isActive }) =>
              clsx(
                'rounded-xl px-3 py-2 text-sm font-medium transition',
                isActive
                  ? 'bg-brand-500/20 text-brand-300'
                  : 'text-slate-300 hover:bg-surface-600 hover:text-slate-100',
              )
            }
          >
            {link.label}
          </NavLink>
        ))}
      </nav>

      <div className="space-y-4 border-t border-slate-700/70 pt-4">
        <div className="space-y-1">
          <p className="text-sm font-semibold text-slate-100">{user?.name ?? 'User'}</p>
          <p className="text-xs uppercase tracking-wide text-slate-400">
            {user ? getStatusLabel(user.role) : 'No Role'}
          </p>
          <p className="truncate text-xs text-slate-500">{user?.email ?? ''}</p>
        </div>

        <button type="button" className="btn-secondary w-full" onClick={logout}>
          Logout
        </button>
      </div>
    </aside>
  );
}

export default Sidebar;
