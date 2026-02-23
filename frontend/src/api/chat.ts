import { apiClient } from '@/api/axios';
import { API_PREFIX } from '@/utils/constants';
import type { ChatResponse } from '@/types';

interface ChatRequestBody {
  message: string;
  shipment_id?: string;
}

export async function sendAdminChat(message: string, shipmentId?: string): Promise<ChatResponse> {
  const payload: ChatRequestBody = { message };
  if (shipmentId) {
    payload.shipment_id = shipmentId;
  }
  const { data } = await apiClient.post<ChatResponse>(`${API_PREFIX}/chat`, payload);
  return data;
}
