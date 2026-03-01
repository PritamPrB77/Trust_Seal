import axios from 'axios';
import { clearStoredToken, getStoredToken, isTokenExpired } from '@/utils/token';

const prodApiBase = 'https://trust-seal-1.onrender.com';
const fallbackApiBase = import.meta.env.DEV ? 'http://127.0.0.1:8000' : prodApiBase;
const fallbackTimeoutMs = 120_000;

export const apiClient = axios.create({
  baseURL: String(import.meta.env.VITE_API_BASE_URL || fallbackApiBase).trim(),
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
    if (error.response?.status === 401) {
      clearStoredToken();
      window.dispatchEvent(new CustomEvent('trustseal:unauthorized'));
    }

    if (error.response?.status === 403) {
      const forbiddenDetail = error?.response?.data?.detail;
      const message =
        typeof forbiddenDetail === 'string' && forbiddenDetail.trim().length > 0
          ? forbiddenDetail
          : 'Insufficient permissions for this operation.';
      window.dispatchEvent(new CustomEvent('trustseal:forbidden', { detail: message }));
    }

    return Promise.reject(error);
  },
);
