import axios from 'axios';

const API_BASE_URL =
  import.meta.env.VITE_API_URL || import.meta.env.REACT_APP_API_URL || 'http://localhost:8000/api';
const USER_ID_STORAGE_KEY = 'fileVaultUserId';
const DEFAULT_USER_ID = 'user1';
const CALL_LIMIT_MESSAGE = 'Call Limit Reached';
const MAX_RATE_LIMIT_RETRIES = 3;

// --- Current user (sent to the backend as the UserId header) ---------------

export const getUserId = () => {
  try {
    return localStorage.getItem(USER_ID_STORAGE_KEY) || DEFAULT_USER_ID;
  } catch {
    return DEFAULT_USER_ID;
  }
};

export const setUserId = (userId) => {
  try {
    localStorage.setItem(USER_ID_STORAGE_KEY, userId);
  } catch {
    // Storage unavailable (private mode etc.): the value just won't persist.
  }
};

const api = axios.create({ baseURL: API_BASE_URL });

api.interceptors.request.use((config) => {
  config.headers.UserId = getUserId();
  return config;
});

// The backend allows 2 calls per second per user. One UI action can fire several
// requests at once, so on "Call Limit Reached" wait for Retry-After and retry.
// "Storage Quota Exceeded" is also a 429 but is final, so it is not retried.
const sleep = (ms) => new Promise((resolve) => setTimeout(resolve, ms));

const errorMessageOf = async (error) => {
  const data = error.response?.data;
  if (data instanceof Blob) {
    try {
      return JSON.parse(await data.text()).error;
    } catch {
      return undefined;
    }
  }
  return data?.error;
};

api.interceptors.response.use(undefined, async (error) => {
  const { config, response } = error;
  if (!config || response?.status !== 429) throw error;
  if ((await errorMessageOf(error)) !== CALL_LIMIT_MESSAGE) throw error;

  config.__rateLimitRetries = (config.__rateLimitRetries || 0) + 1;
  if (config.__rateLimitRetries > MAX_RATE_LIMIT_RETRIES) throw error;

  const retryAfterSeconds = parseFloat(response.headers['retry-after']) || 1;
  await sleep(retryAfterSeconds * 1000 + Math.random() * 200);
  return api(config);
});

export const getErrorMessage = (error, fallback) =>
  error.response?.data?.error || fallback;

// --- API calls -------------------------------------------------------------

export const uploadFile = async (file) => {
  const formData = new FormData();
  formData.append('file', file);
  const response = await api.post('/files/', formData);
  return response.data;
};

export const getFiles = async (filters = {}) => {
  const params = new URLSearchParams();
  Object.keys(filters).forEach((key) => {
    if (filters[key] !== '' && filters[key] !== false && filters[key] !== null) {
      params.append(key, filters[key]);
    }
  });
  const response = await api.get(`/files/?${params.toString()}`);
  return response.data;
};

export const getStats = async () => {
  const response = await api.get('/files/stats/');
  return response.data;
};

export const deleteFile = async (fileId) => {
  await api.delete(`/files/${fileId}/`);
};

export const downloadFile = async (fileId, fileName) => {
  const response = await api.get(`/files/${fileId}/download/`, { responseType: 'blob' });
  const url = window.URL.createObjectURL(new Blob([response.data]));
  const link = document.createElement('a');
  link.href = url;
  link.setAttribute('download', fileName);
  document.body.appendChild(link);
  link.click();
  link.remove();
  window.URL.revokeObjectURL(url);
};
