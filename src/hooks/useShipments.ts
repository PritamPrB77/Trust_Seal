import { useQuery } from '@tanstack/react-query';
import {
  getShipmentById,
  getShipmentCustody,
  getShipmentLegs,
  getShipmentLogs,
  getShipmentsByDevice,
} from '@/api/shipments';

export function useDeviceShipments(deviceId: string | undefined) {
  return useQuery({
    queryKey: ['shipments', 'device', deviceId],
    queryFn: () => getShipmentsByDevice(deviceId as string),
    enabled: Boolean(deviceId),
  });
}

export function useShipment(shipmentId: string | undefined) {
  return useQuery({
    queryKey: ['shipment', shipmentId],
    queryFn: () => getShipmentById(shipmentId as string),
    enabled: Boolean(shipmentId),
  });
}

export function useShipmentLogs(shipmentId: string | undefined) {
  return useQuery({
    queryKey: ['shipment', shipmentId, 'logs'],
    queryFn: () => getShipmentLogs(shipmentId as string),
    enabled: Boolean(shipmentId),
  });
}

export function useShipmentLegs(shipmentId: string | undefined) {
  return useQuery({
    queryKey: ['shipment', shipmentId, 'legs'],
    queryFn: () => getShipmentLegs(shipmentId as string),
    enabled: Boolean(shipmentId),
  });
}

export function useShipmentCustody(shipmentId: string | undefined) {
  return useQuery({
    queryKey: ['shipment', shipmentId, 'custody'],
    queryFn: () => getShipmentCustody(shipmentId as string),
    enabled: Boolean(shipmentId),
  });
}

