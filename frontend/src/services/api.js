import axios from 'axios';

const api = axios.create({
  baseURL: 'http://localhost:8000',
  headers: { 'Content-Type': 'application/json' }
});

export const appointmentService = {
  getAppointments: (status) => api.get(`/api/appointments${status ? `?status=${status}` : ''}`),
  createAppointment: (data) => api.post('/api/appointments', data),
  cancelAppointment: (id) => api.delete(`/api/appointments/${id}`),
  updateAppointmentStatus: (id, status) => api.put(`/api/appointments/${id}/status?status=${status}`),
  getNotifications: () => api.get('/api/notifications'),
};

// Add token to requests
api.interceptors.request.use(config => {
  const token = localStorage.getItem('mc_token');
  if (token) config.headers.Authorization = `Bearer ${token}`;
  return config;
});

// Handle 401 errors
api.interceptors.response.use(
  response => response,
  error => {
    if (error.response?.status === 401) {
      localStorage.removeItem('mc_token');
      if (window.location.pathname !== '/login') {
        window.location.href = '/login';
      }
    }
    return Promise.reject(error);
  }
);

export default api;
