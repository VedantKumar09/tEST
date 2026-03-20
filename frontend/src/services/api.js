import axios from 'axios';

// Use relative URLs — Vite proxy forwards /api/* to http://localhost:8000
// This works for both PC (https://localhost:5173) and phone (https://<LAN-IP>:5173)
// Avoids mixed-content block: phone is HTTPS, backend is HTTP
const api = axios.create({ baseURL: '/' });

// Attach JWT to every request if present
api.interceptors.request.use((config) => {
  const token = localStorage.getItem('mm_token');
  if (token) config.headers.Authorization = `Bearer ${token}`;
  return config;
});

// ── Auth ─────────────────────────────────────────────────────────────────────
export const authAPI = {
  login: (email, password, role) =>
    api.post('/api/auth/login', { email, password, role }).then(r => r.data),
  me: () => api.get('/api/auth/me').then(r => r.data),
};

// ── Exam ─────────────────────────────────────────────────────────────────────
export const examAPI = {
  getQuestions: () => api.get('/api/exam/questions').then(r => r.data),
  submitExam: (payload) => api.post('/api/exam/submit', payload).then(r => r.data),
};

// ── Proctoring ───────────────────────────────────────────────────────────────
export const proctoringAPI = {
  startSession: (student_id) =>
    api.post('/api/proctor/start-session', { student_id }).then(r => r.data),
  endSession: (student_id) =>
    api.post('/api/proctor/end-session', { student_id }).then(r => r.data),
  analyzeFrame: (image, student_id) =>
    api.post('/api/proctor/analyze', { image, student_id }).then(r => r.data),
  sendBrowserEvent: (student_id, event_type) =>
    api.post('/api/proctor/browser-event', { student_id, event_type }).then(r => r.data),
  getProctorScore: (student_id) =>
    api.get(`/api/proctor/score/${student_id}`).then(r => r.data),
  getProctorLogs: (student_id) =>
    api.get(`/api/proctor/logs/${student_id}`).then(r => r.data),
  sendSecondFrame: (image, student_id) =>
    api.post('/api/proctor/second-frame', { image, student_id }).then(r => r.data),
  getSecondCamFrame: (student_id) =>
    api.get(`/api/proctor/second-cam/${student_id}`).then(r => r.data),
  verifyIdentity: (student_id, image) =>
    api.post('/api/proctor/verify-identity', { student_id, image }).then(r => r.data),
};

// ── Admin ─────────────────────────────────────────────────────────────────────
export const adminAPI = {
  getSubmissions: () => api.get('/api/admin/submissions').then(r => r.data),
  getSubmission: (id) => api.get(`/api/admin/submissions/${id}`).then(r => r.data),
  getProctorLogs: () => api.get('/api/admin/proctor-logs').then(r => r.data),
  getRiskTimeline: (studentId) => api.get(`/api/admin/risk-timeline/${studentId}`).then(r => r.data),
  getEvidence: (studentId) => api.get(`/api/admin/evidence/${studentId}`).then(r => r.data),
  flagSubmission: (id) => api.post(`/api/admin/flag/${id}`).then(r => r.data),
  markSubmission: (id, status) => api.post(`/api/admin/mark/${id}`, { status }).then(r => r.data),
};

// ── Code Execution ───────────────────────────────────────────────────────────
export const codeAPI = {
  getLanguages: () => api.get('/api/code/languages').then(r => r.data),
  getQuestions: () => api.get('/api/code/questions').then(r => r.data),
  getQuestion: (id) => api.get(`/api/code/questions/${id}`).then(r => r.data),
  execute: (language, code, stdin = '') =>
    api.post('/api/code/execute', { language, code, stdin }).then(r => r.data),
  submit: (language, code, question_id) =>
    api.post('/api/code/submit', { language, code, question_id }).then(r => r.data),
};
