import { Link, useNavigate, useParams } from 'react-router-dom';
import EmptyState from '@/components/EmptyState';
import ErrorState from '@/components/ErrorState';
import LoadingState from '@/components/LoadingState';
import StatusBadge from '@/components/StatusBadge';
import { useDevice } from '@/hooks/useDevices';
import { useDeviceShipments } from '@/hooks/useShipments';
import { formatDate } from '@/utils/format';

function DeviceDetailsPage() {
  const navigate = useNavigate();
  const { deviceId } = useParams<{ deviceId: string }>();
  const {
    data: device,
    isLoading: deviceLoading,
    isError: deviceError,
    error: deviceErrorObj,
    refetch: refetchDevice,
  } = useDevice(deviceId);
  const {
    data: shipments,
    isLoading: shipmentsLoading,
    isError: shipmentsError,
    error: shipmentsErrorObj,
    refetch: refetchShipments,
  } = useDeviceShipments(deviceId);

  if (!deviceId) {
    return <ErrorState message="Device ID is missing." />;
  }

  if (deviceLoading || shipmentsLoading) {
    return <LoadingState message="Loading device and shipment data..." />;
  }

  if (deviceError || shipmentsError) {
    const message = deviceError
      ? deviceErrorObj instanceof Error
        ? deviceErrorObj.message
        : 'Failed to load device.'
      : shipmentsErrorObj instanceof Error
        ? shipmentsErrorObj.message
        : 'Failed to load shipments.';

    return (
      <ErrorState
        message={message}
        onRetry={() => {
          void refetchDevice();
          void refetchShipments();
        }}
      />
    );
  }

  if (!device) {
    return (
      <EmptyState
        title="Device not found"
        description="This device does not exist or you do not have access to it."
        action={
          <Link className="btn-secondary" to="/dashboard">
            Back to Dashboard
          </Link>
        }
      />
    );
  }

  return (
    <div className="space-y-6">
      <header className="space-y-3">
        <Link to="/dashboard" className="text-sm font-medium text-brand-300 transition hover:text-brand-400">
          &larr; Back to dashboard
        </Link>
        <div className="panel p-5">
          <div className="flex flex-wrap items-start justify-between gap-4">
            <div>
              <p className="text-xs uppercase tracking-[0.14em] text-slate-400">Device UID</p>
              <h1 className="mt-1 text-2xl font-semibold text-slate-100">{device.device_uid}</h1>
              <p className="mt-2 text-sm text-slate-300">
                Model: {device.model} | Firmware: <span className="font-mono">{device.firmware_version}</span>
              </p>
            </div>
            <StatusBadge kind="device" status={device.status} />
          </div>

          <div className="mt-4 grid gap-3 text-sm text-slate-300 md:grid-cols-3">
            <p>Battery: {device.battery_capacity_mAh ? `${device.battery_capacity_mAh} mAh` : 'N/A'}</p>
            <p>Created: {formatDate(device.created_at)}</p>
            <p>Device ID: {device.id}</p>
          </div>
        </div>
      </header>

      <section className="space-y-4">
        <div>
          <h2 className="text-xl font-semibold text-slate-100">Linked Shipments</h2>
          <p className="text-sm text-slate-400">Select a shipment for sensor logs and custody events.</p>
        </div>

        {!shipments || shipments.length === 0 ? (
          <EmptyState
            title="No shipments for this device"
            description="No shipment currently references this device."
          />
        ) : (
          <div className="grid gap-4">
            {shipments.map((shipment) => (
              <article key={shipment.id} className="panel animate-fade-up p-5">
                <div className="flex flex-wrap items-center justify-between gap-3">
                  <div>
                    <p className="text-xs uppercase tracking-[0.14em] text-slate-400">Shipment Code</p>
                    <h3 className="mt-1 text-lg font-semibold text-slate-100">{shipment.shipment_code}</h3>
                    <p className="mt-2 text-sm text-slate-300">
                      {shipment.origin} {'->'} {shipment.destination}
                    </p>
                    <p className="text-xs text-slate-400">Created: {formatDate(shipment.created_at)}</p>
                  </div>
                  <div className="flex items-center gap-2">
                    <StatusBadge kind="shipment" status={shipment.status} />
                    <button
                      type="button"
                      className="btn-primary"
                      onClick={() => navigate(`/shipments/${shipment.id}`)}
                    >
                      Open
                    </button>
                  </div>
                </div>
              </article>
            ))}
          </div>
        )}
      </section>
    </div>
  );
}

export default DeviceDetailsPage;
