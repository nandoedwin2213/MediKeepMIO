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
  getFunctional: (patientId, signal) =>
    apiService.get(`/metabolic/patients/${patientId}/functional`, { signal }),
  createFunctional: (patientId, data) =>
    apiService.post(`/metabolic/patients/${patientId}/functional`, data),
  deleteFunctional: (patientId, id) =>
    apiService.delete(`/metabolic/patients/${patientId}/functional/${id}`),
  getNutritionPlans: (patientId, signal) =>
    apiService.get(`/metabolic/patients/${patientId}/nutrition-plans`, {
      signal,
    }),
  generateNutritionPlan: patientId =>
    apiService.post(
      `/metabolic/patients/${patientId}/nutrition-plans/generate`
    ),
  createNutritionPlan: (patientId, body) =>
    apiService.post(`/metabolic/patients/${patientId}/nutrition-plans`, body),
  updateNutritionPlan: (patientId, planId, body) =>
    apiService.put(
      `/metabolic/patients/${patientId}/nutrition-plans/${planId}`,
      body
    ),
  approveNutritionPlan: (patientId, planId) =>
    apiService.post(
      `/metabolic/patients/${patientId}/nutrition-plans/${planId}/approve`
    ),
  deleteNutritionPlan: (patientId, planId) =>
    apiService.delete(
      `/metabolic/patients/${patientId}/nutrition-plans/${planId}`
    ),
  getExercisePlans: (patientId, signal) =>
    apiService.get(`/metabolic/patients/${patientId}/exercise-plans`, {
      signal,
    }),
  generateExercisePlan: patientId =>
    apiService.post(`/metabolic/patients/${patientId}/exercise-plans/generate`),
  createExercisePlan: (patientId, body) =>
    apiService.post(`/metabolic/patients/${patientId}/exercise-plans`, body),
  updateExercisePlan: (patientId, planId, body) =>
    apiService.put(
      `/metabolic/patients/${patientId}/exercise-plans/${planId}`,
      body
    ),
  approveExercisePlan: (patientId, planId) =>
    apiService.post(
      `/metabolic/patients/${patientId}/exercise-plans/${planId}/approve`
    ),
  deleteExercisePlan: (patientId, planId) =>
    apiService.delete(
      `/metabolic/patients/${patientId}/exercise-plans/${planId}`
    ),
  getProfessionalDashboard: signal =>
    apiService.get('/metabolic/professional/dashboard', { signal }),
};

export default metabolicApi;
