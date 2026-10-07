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
  getRecipes: (params, signal) =>
    apiService.get('/metabolic/recipes', { params, signal }),
  createRecipe: body => apiService.post('/metabolic/recipes', body),
  updateRecipe: (recipeId, body) =>
    apiService.put(`/metabolic/recipes/${recipeId}`, body),
  deleteRecipe: recipeId => apiService.delete(`/metabolic/recipes/${recipeId}`),
  getRecommendedRecipes: (patientId, params, signal) =>
    apiService.get(`/metabolic/patients/${patientId}/recipes/recommended`, {
      params,
      signal,
    }),
  getWeek: (patientId, params, signal) =>
    apiService.get(`/metabolic/patients/${patientId}/week`, { params, signal }),
  logAdherence: (patientId, body) =>
    apiService.put(`/metabolic/patients/${patientId}/adherence`, body),
  getAdherenceHistory: (patientId, params, signal) =>
    apiService.get(`/metabolic/patients/${patientId}/adherence/history`, {
      params,
      signal,
    }),
  getInsights: (patientId, signal) =>
    apiService.get(`/metabolic/patients/${patientId}/insights`, { signal }),
  generateInsight: patientId =>
    apiService.post(`/metabolic/patients/${patientId}/insights/generate`),
  updateInsight: (patientId, insightId, body) =>
    apiService.put(
      `/metabolic/patients/${patientId}/insights/${insightId}`,
      body
    ),
  approveInsight: (patientId, insightId) =>
    apiService.post(
      `/metabolic/patients/${patientId}/insights/${insightId}/approve`
    ),
  deleteInsight: (patientId, insightId) =>
    apiService.delete(`/metabolic/patients/${patientId}/insights/${insightId}`),
  simulate: (patientId, body) =>
    apiService.post(`/metabolic/patients/${patientId}/simulate`, body),
  getProfessionalDashboard: signal =>
    apiService.get('/metabolic/professional/dashboard', { signal }),
};

export default metabolicApi;
