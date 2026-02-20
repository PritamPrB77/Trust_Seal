import type { Device } from '@/types';
import StatusBadge from '@/components/StatusBadge';

interface DeviceCardProps {
  device: Device;
  onOpen: (id: string) => void;
}

function DeviceCard({ device, onOpen }: DeviceCardProps) {
  return (
    <article className="panel animate-fade-up p-5">
      <div className="flex items-start justify-between gap-3">
        <div>
          <p className="text-xs uppercase tracking-[0.18em] text-slate-400">Device UID</p>
          <h3 className="mt-1 text-lg font-semibold text-slate-100">{device.device_uid}</h3>
        </div>
        <StatusBadge kind="device" status={device.status} />
      </div>

      <dl className="mt-5 grid grid-cols-2 gap-4 text-sm">
        <div>
          <dt className="text-slate-400">Model</dt>
          <dd className="mt-1 text-slate-100">{device.model}</dd>
        </div>
        <div>
          <dt className="text-slate-400">Firmware</dt>
          <dd className="mt-1 font-mono text-slate-100">{device.firmware_version}</dd>
        </div>
        <div className="col-span-2">
          <dt className="text-slate-400">Battery Capacity</dt>
          <dd className="mt-1 text-slate-100">
            {device.battery_capacity_mAh ? `${device.battery_capacity_mAh} mAh` : 'N/A'}
          </dd>
        </div>
      </dl>

      <button type="button" className="btn-primary mt-6 w-full" onClick={() => onOpen(device.id)}>
        View Shipments
      </button>
    </article>
  );
}

export default DeviceCard;

