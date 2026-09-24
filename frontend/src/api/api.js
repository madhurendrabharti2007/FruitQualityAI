import axios from 'axios';
export const api = axios.create({ baseURL: import.meta.env.VITE_API_URL || 'http://127.0.0.1:8000/api', withCredentials: true });
export async function predictFruit(file) { const form = new FormData(); form.append('file', file); return (await api.post('/predict', form)).data; }
export async function getFruits() { return (await api.get('/fruits')).data; }
export async function signUp(data) { return (await api.post('/auth/signup', data)).data; }
export async function signIn(data) { return (await api.post('/auth/login', data)).data; }
export async function signOut() { return (await api.post('/auth/logout')).data; }
export async function getMe() { return (await api.get('/auth/me')).data; }
export async function getHistory() { return (await api.get('/auth/history')).data; }
export async function getNotebook() { return (await api.get('/notebook')).data; }
export async function getNotebookEntry(fruitId) { return (await api.get(`/notebook/${encodeURIComponent(fruitId)}`)).data; }
export async function askFruitAssistant(data) { return (await api.post('/chat', data)).data; }
export async function requestVendorAccess() { return (await api.post('/auth/request-vendor')).data; }
export async function batchPredict(files, onUploadProgress) { const form = new FormData(); files.forEach(file => form.append('files', file)); return (await api.post('/batch-predict', form, { onUploadProgress })).data; }
export async function getReports() { return (await api.get('/reports')).data; }
export function reportExportUrl(batchId, format) { return `${api.defaults.baseURL}/reports/${encodeURIComponent(batchId)}/${format}`; }
export async function getAdminAnalytics() { return (await api.get('/admin/analytics')).data; }
export async function forgotPassword(data) { return (await api.post('/auth/forgot-password', data)).data; }
export async function resetPassword(data) { return (await api.post('/auth/reset-password', data)).data; }
