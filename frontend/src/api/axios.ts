import axios from 'axios';
import { clearStoredToken, getStoredToken, isTokenExpired } from '@/utils/token';

const fallbackApiBase = 'http://localhost:8000';

export const apiClient = axios.create({
  baseURL: import.meta.env.VITE_API_BASE_URL || fallbackApiBase,
  timeout: 20_000,
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
    return Promise.reject(error);
  },
);

