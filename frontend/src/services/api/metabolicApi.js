import { apiService } from './index';

const metabolicApi = {
  getConfig: signal => apiService.get('/metabolic/config', { signal }),
  getDefaultConfig: signal =>
    apiService.get('/metabolic/config/default', { signal }),
  updateConfig: (config, notes) =>
    apiService.put('/metabolic/config', { config, notes }),
  evaluate: (patientId, signal) =>
    apiService.post(`/metabolic/patients/${patientId}/evaluate`, null, {
      signal,
    }),
  getAssessments: (patientId, signal) =>
    apiService.get(`/metabolic/patients/${patientId}/assessments`, { signal }),
  getProgress: (patientId, signal) =>
    apiService.get(`/metabolic/patients/${patientId}/progress`, { signal }),
  getProfile: (patientId, signal) =>
    apiService.get(`/metabolic/patients/${patientId}/profile`, { signal }),
  updateProfile: (patientId, profile) =>
    apiService.put(`/metabolic/patients/${patientId}/profile`, profile),
  getProfessionalDashboard: signal =>
    apiService.get('/metabolic/professional/dashboard', { signal }),
};

export default metabolicApi;
