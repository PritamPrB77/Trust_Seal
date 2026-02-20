import { apiClient } from '@/api/axios';
import { API_PREFIX } from '@/utils/constants';
import type {
  CustodyCheckpoint,
  SensorLog,
  Shipment,
  ShipmentLeg,
  ShipmentStatus,
  ShipmentWithDetails,
} from '@/types';

interface ShipmentQueryParams {
  skip?: number;
  limit?: number;
  status?: ShipmentStatus;
  device_id?: string;
}

export async function getShipments(params?: ShipmentQueryParams): Promise<Shipment[]> {
  const { data } = await apiClient.get<Shipment[]>(`${API_PREFIX}/shipments/`, { params });
  return data;
}

export async function getShipmentsByDevice(deviceId: string): Promise<Shipment[]> {
  return getShipments({ device_id: deviceId });
}

export async function getShipmentById(shipmentId: string): Promise<ShipmentWithDetails> {
  const { data } = await apiClient.get<ShipmentWithDetails>(`${API_PREFIX}/shipments/${shipmentId}`);
  return data;
}

export async function getShipmentLogs(shipmentId: string): Promise<SensorLog[]> {
  const { data } = await apiClient.get<SensorLog[]>(`${API_PREFIX}/shipments/${shipmentId}/logs`);
  return data;
}

export async function getShipmentLegs(shipmentId: string): Promise<ShipmentLeg[]> {
  const { data } = await apiClient.get<ShipmentLeg[]>(`${API_PREFIX}/legs/`, {
    params: { shipment_id: shipmentId },
  });
  return data;
}

export async function getShipmentCustody(shipmentId: string): Promise<CustodyCheckpoint[]> {
  const { data } = await apiClient.get<CustodyCheckpoint[]>(`${API_PREFIX}/custody/`, {
    params: { shipment_id: shipmentId },
  });
  return data;
}
