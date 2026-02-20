import { apiClient } from '@/api/axios';
import { API_PREFIX } from '@/utils/constants';
import type { Device, DeviceStatus } from '@/types';

interface DeviceQueryParams {
  skip?: number;
  limit?: number;
  status?: DeviceStatus;
}

export async function getDevices(params?: DeviceQueryParams): Promise<Device[]> {
  const { data } = await apiClient.get<Device[]>(`${API_PREFIX}/devices/`, { params });
  return data;
}

export async function getDeviceById(deviceId: string): Promise<Device> {
  const { data } = await apiClient.get<Device>(`${API_PREFIX}/devices/${deviceId}`);
  return data;
}
