import { apiService } from './index';

const billingApi = {
  getPlans: signal => apiService.get('/billing/plans', { signal }),
  getMine: signal => apiService.get('/billing/me', { signal }),
  checkout: plan => apiService.post('/billing/checkout', { plan }),
  confirm: (id, clientTransactionId) =>
    apiService.post('/billing/confirm', {
      id: Number(id),
      client_transaction_id: clientTransactionId,
    }),
  listAll: signal => apiService.get('/billing/admin/subscriptions', { signal }),
};

export default billingApi;
