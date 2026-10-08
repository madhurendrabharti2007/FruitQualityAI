import axios from 'axios';
const TOKEN_KEY = 'fruit_ai_access_token';
const API_BASE_URL = import.meta.env.VITE_API_BASE_URL || import.meta.env.VITE_API_URL || 'http://localhost:8000/api';
export const api = axios.create({ baseURL: API_BASE_URL, withCredentials: true });
api.interceptors.request.use(config => {
  try {
    const token = localStorage.getItem(TOKEN_KEY);
    if (token) {
      config.headers = config.headers || {};
      config.headers.Authorization = `Bearer ${token}`;
    }
  } catch {}
  return config;
}, error => Promise.reject(error));
export async function predictFruit(file) { const form = new FormData(); form.append('file', file); return (await api.post('/predict', form, { withCredentials: true })).data; }
export async function getFruits() { return (await api.get('/fruits')).data; }
export async function signUp(data) { return (await api.post('/auth/signup', data)).data; }
export async function signIn(data) { return (await api.post('/auth/login', data)).data; }
export async function signOut() { return (await api.post('/auth/logout')).data; }
export async function getMe() { return (await api.get('/auth/me')).data; }
function unwrapList(data) {
  if (Array.isArray(data)) return data;
  if (data && Array.isArray(data.items)) return data.items;
  if (data && Array.isArray(data.history)) return data.history;
  if (data && Array.isArray(data.results)) return data.results;
  if (data && Array.isArray(data.data)) return data.data;
  return [];
}
export async function getHistory() { return unwrapList((await api.get('/auth/history')).data); }
export async function getNotebook() { return unwrapList((await api.get('/notebook')).data); }
export async function getReports() { return unwrapList((await api.get('/reports')).data); }
export async function getNotebookEntry(fruitId) { return (await api.get(`/notebook/${encodeURIComponent(fruitId)}`)).data; }
export async function askFruitAssistant(data) { return (await api.post('/chat', data)).data; }
export async function requestVendorAccess() { return (await api.post('/auth/request-vendor')).data; }
export async function batchPredict(files, onUploadProgress) { const form = new FormData(); files.forEach(file => form.append('files', file)); return (await api.post('/batch-predict', form, { withCredentials: true, onUploadProgress })).data; }
export function reportExportUrl(batchId, format) { return `${api.defaults.baseURL}/reports/${encodeURIComponent(batchId)}/${format}`; }
export async function getAdminAnalytics() { return (await api.get('/admin/analytics')).data; }
export async function forgotPassword(data) { return (await api.post('/auth/forgot-password', data)).data; }
export async function resetPassword(data) { return (await api.post('/auth/reset-password', data)).data; }
