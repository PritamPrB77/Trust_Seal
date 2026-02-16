import { useMemo } from 'react';
import { Link, useParams } from 'react-router-dom';
import ComplianceCard from '@/components/ComplianceCard';
import CustodyTable from '@/components/CustodyTable';
import EmptyState from '@/components/EmptyState';
import ErrorState from '@/components/ErrorState';
import JourneyTimeline from '@/components/JourneyTimeline';
import LoadingState from '@/components/LoadingState';
import SensorCharts from '@/components/SensorCharts';
import SensorStatsStrip from '@/components/SensorStatsStrip';
import StatusBadge from '@/components/StatusBadge';
import {
  useShipment,
  useShipmentCustody,
  useShipmentLegs,
  useShipmentLogs,
} from '@/hooks/useShipments';
import { calculateSensorStats } from '@/utils/compliance';
import { formatDate } from '@/utils/format';
import { downloadShipmentReport } from '@/utils/report';

function ShipmentDetailsPage() {
  const { shipmentId } = useParams<{ shipmentId: string }>();

  const {
    data: shipment,
    isLoading: shipmentLoading,
    isError: shipmentError,
    error: shipmentErrorObj,
  } = useShipment(shipmentId);
  const {
    data: logs,
    isLoading: logsLoading,
    isError: logsError,
    error: logsErrorObj,
  } = useShipmentLogs(shipmentId);
  const {
    data: legs,
    isLoading: legsLoading,
    isError: legsError,
    error: legsErrorObj,
  } = useShipmentLegs(shipmentId);
  const {
    data: custody,
    isLoading: custodyLoading,
    isError: custodyError,
    error: custodyErrorObj,
  } = useShipmentCustody(shipmentId);

  const loading = shipmentLoading || logsLoading || legsLoading || custodyLoading;
  const hasError = shipmentError || logsError || legsError || custodyError;

  const stats = useMemo(
    () => calculateSensorStats(logs ?? [], shipment?.status),
    [logs, shipment?.status],
  );

  if (!shipmentId) {
    return <ErrorState message="Shipment ID is missing from route." />;
  }

  if (loading) {
    return <LoadingState message="Loading shipment dashboard..." />;
  }

  if (hasError) {
    const message = shipmentError
      ? shipmentErrorObj instanceof Error
        ? shipmentErrorObj.message
        : 'Failed to load shipment.'
      : logsError
        ? logsErrorObj instanceof Error
          ? logsErrorObj.message
          : 'Failed to load sensor logs.'
        : legsError
          ? legsErrorObj instanceof Error
            ? legsErrorObj.message
            : 'Failed to load legs.'
          : custodyErrorObj instanceof Error
            ? custodyErrorObj.message
            : 'Failed to load custody checkpoints.';

    return <ErrorState message={message} />;
  }

  if (!shipment) {
    return (
      <EmptyState
        title="Shipment not found"
        description="The shipment requested does not exist."
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
        <section className="panel p-5">
          <div className="flex flex-wrap items-start justify-between gap-4">
            <div>
              <p className="text-xs uppercase tracking-[0.14em] text-slate-400">Shipment Code</p>
              <h1 className="mt-1 text-2xl font-semibold text-slate-100">{shipment.shipment_code}</h1>
              <p className="mt-2 text-sm text-slate-300">
                {shipment.origin} {'->'} {shipment.destination}
              </p>
            </div>
            <StatusBadge kind="shipment" status={shipment.status} />
          </div>

          <div className="mt-4 grid gap-3 text-sm text-slate-300 md:grid-cols-3">
            <p>Created: {formatDate(shipment.created_at)}</p>
            <p>Device ID: {shipment.device_id}</p>
            <button
              type="button"
              className="btn-secondary justify-self-start md:justify-self-end"
              onClick={() =>
                downloadShipmentReport(shipment, stats, legs?.length ?? 0, custody?.length ?? 0)
              }
            >
              Download Report
            </button>
          </div>
        </section>
      </header>

      <SensorStatsStrip stats={stats} />

      <div className="grid gap-5 xl:grid-cols-[2fr_1fr]">
        <SensorCharts logs={logs ?? []} />
        <div className="space-y-5">
          <ComplianceCard stats={stats} />
          <section className="panel p-5">
            <h3 className="text-lg font-semibold text-slate-100">Map View</h3>
            <p className="mt-1 text-sm text-slate-400">GPS tracking placeholder for future integration.</p>
            <div className="mt-4 flex h-48 items-center justify-center rounded-xl border border-dashed border-brand-400/40 bg-surface-800/60 text-center text-sm text-slate-400">
              Live route map coming soon
            </div>
          </section>
        </div>
      </div>

      <JourneyTimeline legs={legs ?? []} />
      <CustodyTable checkpoints={custody ?? []} />
    </div>
  );
}

export default ShipmentDetailsPage;
