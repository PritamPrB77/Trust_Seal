import { useQuery } from '@tanstack/react-query';
import { getDeviceById, getDevices } from '@/api/devices';

export function useDevices() {
  return useQuery({
    queryKey: ['devices'],
    queryFn: () => getDevices(),
  });
}

export function useDevice(deviceId: string | undefined) {
  return useQuery({
    queryKey: ['device', deviceId],
    queryFn: () => getDeviceById(deviceId as string),
    enabled: Boolean(deviceId),
  });
}

