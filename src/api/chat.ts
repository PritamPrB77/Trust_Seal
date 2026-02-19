import { apiClient } from '@/api/axios';
import { API_PREFIX } from '@/utils/constants';
import type { ChatResponse } from '@/types';

interface ChatRequestBody {
  message: string;
}

export async function sendAdminChat(message: string): Promise<ChatResponse> {
  const payload: ChatRequestBody = { message };
  const { data } = await apiClient.post<ChatResponse>(`${API_PREFIX}/chat`, payload);
  return data;
}
