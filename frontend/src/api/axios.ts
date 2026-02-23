import axios from 'axios';
import { clearStoredToken, getStoredToken, isTokenExpired } from '@/utils/token';

const fallbackApiBase = 'https://trust-seal.onrender.com';
const fallbackTimeoutMs = 120_000;

function normalizeLocalApiBase(value: string): string {
  let output = value.trim();
  output = output.replace('http://localhost:8000', 'http://127.0.0.1:8001');
  output = output.replace('http://127.0.0.1:8000', 'http://127.0.0.1:8001');
  return output;
}

function isLocal8000(value: string): boolean {
  return value.includes('localhost:8000') || value.includes('127.0.0.1:8000');
}

export const apiClient = axios.create({
  baseURL: normalizeLocalApiBase(String(import.meta.env.VITE_API_BASE_URL || fallbackApiBase)),
  timeout: Number(import.meta.env.VITE_API_TIMEOUT_MS || fallbackTimeoutMs),
});

apiClient.interceptors.request.use((config) => {
  const token = getStoredToken();
  if (!token) {
    // No token found — request will be sent without Authorization header
    console.debug('[api] no token in localStorage, sending request without Authorization');
    return config;
  }

  if (isTokenExpired(token)) {
    // Token expired: clear and notify app
    console.debug('[api] token expired, clearing token and dispatching unauthorized');
    clearStoredToken();
    window.dispatchEvent(new CustomEvent('trustseal:unauthorized'));
    return config;
  }

  config.headers = config.headers ?? {};
  config.headers.Authorization = `Bearer ${token}`;
  console.debug('[api] attaching Authorization header to request');
  return config;
});

apiClient.interceptors.response.use(
  (response) => response,
  (error) => {
    // Local dev safety net: if stale port 8000 instance returns DB-unavailable, retry once on 8001.
    const originalConfig = error?.config as ({ _retryOnLocalFailover?: boolean; baseURL?: string } | undefined);
    const currentBase = String(originalConfig?.baseURL || apiClient.defaults.baseURL || '');
    const detail = String(error?.response?.data?.detail || '');
    if (
      error?.response?.status === 503 &&
      detail.includes('Database unavailable') &&
      originalConfig &&
      !originalConfig._retryOnLocalFailover &&
      isLocal8000(currentBase)
    ) {
      const failoverBase = normalizeLocalApiBase(currentBase);
      originalConfig._retryOnLocalFailover = true;
      originalConfig.baseURL = failoverBase;
      apiClient.defaults.baseURL = failoverBase;
      return apiClient.request(originalConfig);
    }

    if (error.response?.status === 401) {
      clearStoredToken();
      window.dispatchEvent(new CustomEvent('trustseal:unauthorized'));
    }

    if (error.response?.status === 403) {
      const detail = error?.response?.data?.detail;
      const message =
        typeof detail === 'string' && detail.trim().length > 0
          ? detail
          : 'Insufficient permissions for this operation.';
      window.dispatchEvent(new CustomEvent('trustseal:forbidden', { detail: message }));
    }
    return Promise.reject(error);
  },
);
