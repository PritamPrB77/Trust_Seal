import type { AxiosError } from 'axios';
import type { ApiErrorPayload } from '@/types';

export function getErrorMessage(error: unknown, fallback = 'Something went wrong'): string {
  const axiosError = error as AxiosError<ApiErrorPayload> | undefined;
  const detail = axiosError?.response?.data?.detail;
  const message = axiosError?.response?.data?.message;

  if (typeof detail === 'string' && detail.trim().length > 0) {
    return detail;
  }

  if (typeof message === 'string' && message.trim().length > 0) {
    return message;
  }

  if (error instanceof Error && error.message.trim().length > 0) {
    return error.message;
  }

  return fallback;
}

