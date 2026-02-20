import { useNavigate } from 'react-router-dom';
import DeviceCard from '@/components/DeviceCard';
import EmptyState from '@/components/EmptyState';
import ErrorState from '@/components/ErrorState';
import LoadingState from '@/components/LoadingState';
import { useDevices } from '@/hooks/useDevices';
import { getErrorMessage } from '@/utils/errors';

function DashboardPage() {
  const navigate = useNavigate();
  const { data: devices, isLoading, isError, error, refetch } = useDevices();

  if (isLoading) {
    return <LoadingState message="Loading IoT devices..." />;
  }

  if (isError) {
    const message = getErrorMessage(error, 'Unable to load devices.');
    return <ErrorState message={message} onRetry={() => void refetch()} />;
  }

  const totalDevices = devices?.length ?? 0;
  const activeDevices = devices?.filter((device) => device.status === 'active').length ?? 0;
  const maintenanceDevices = devices?.filter((device) => device.status === 'maintenance').length ?? 0;

  return (
    <div className="space-y-6">
      <section className="grid gap-4 md:grid-cols-3">
        <article className="panel-soft p-4">
          <p className="text-xs uppercase tracking-[0.14em] text-slate-400">Total Devices</p>
          <p className="mt-2 text-2xl font-semibold text-slate-100">{totalDevices}</p>
        </article>
        <article className="panel-soft p-4">
          <p className="text-xs uppercase tracking-[0.14em] text-slate-400">Active</p>
          <p className="mt-2 text-2xl font-semibold text-status-green">{activeDevices}</p>
        </article>
        <article className="panel-soft p-4">
          <p className="text-xs uppercase tracking-[0.14em] text-slate-400">Maintenance</p>
          <p className="mt-2 text-2xl font-semibold text-status-yellow">{maintenanceDevices}</p>
        </article>
      </section>

      <section className="space-y-4">
        <div>
          <h2 className="text-xl font-semibold text-slate-100">Device Fleet</h2>
          <p className="text-sm text-slate-400">Select a device to inspect linked shipments.</p>
        </div>

        {totalDevices === 0 ? (
          <EmptyState
            title="No devices found"
            description="No registered IoT devices are available for your account yet."
          />
        ) : (
          <div className="grid gap-4 xl:grid-cols-2">
            {devices?.map((device) => (
              <DeviceCard key={device.id} device={device} onOpen={(id) => navigate(`/device/${id}`)} />
            ))}
          </div>
        )}
      </section>
    </div>
  );
}

export default DashboardPage;
