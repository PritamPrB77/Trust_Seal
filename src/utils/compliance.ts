import type { SensorLog, ShipmentStatus } from '@/types';
import { TEMPERATURE_THRESHOLD_C } from '@/utils/constants';

export interface SensorStats {
  averageTemperature: number | null;
  maxShock: number | null;
  lastUpdate: string | null;
  hasTemperatureBreach: boolean;
  complianceStatus: 'Valid' | 'Compromised';
}

export function sortLogsByRecordedAt(logs: SensorLog[]): SensorLog[] {
  return [...logs].sort(
    (left, right) => new Date(left.recorded_at).getTime() - new Date(right.recorded_at).getTime(),
  );
}

export function calculateSensorStats(
  logs: SensorLog[],
  shipmentStatus?: ShipmentStatus,
): SensorStats {
  const sortedLogs = sortLogsByRecordedAt(logs);
  const latest = sortedLogs.at(-1) ?? null;

  const temperatureValues = sortedLogs
    .map((entry) => entry.temperature)
    .filter((value): value is number => typeof value === 'number');

  const shockValues = sortedLogs
    .map((entry) => entry.shock)
    .filter((value): value is number => typeof value === 'number');

  const averageTemperature =
    temperatureValues.length > 0
      ? temperatureValues.reduce((sum, value) => sum + value, 0) / temperatureValues.length
      : null;

  const maxShock =
    shockValues.length > 0 ? shockValues.reduce((max, value) => Math.max(max, value), shockValues[0]) : null;

  const hasTemperatureBreach = temperatureValues.some((value) => value > TEMPERATURE_THRESHOLD_C);
  const shipmentCompromised = shipmentStatus === 'compromised';
  const complianceStatus = hasTemperatureBreach || shipmentCompromised ? 'Compromised' : 'Valid';

  return {
    averageTemperature,
    maxShock,
    lastUpdate: latest?.recorded_at ?? null,
    hasTemperatureBreach,
    complianceStatus,
  };
}

