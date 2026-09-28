/**
 * Approvals API service — list, get, approve, reject.
 */

import api from './api';

const approvalsService = {
  async list(status = null) {
    const params = status ? `?status=${status}` : '';
    const response = await api.get(`/approvals${params}`);
    return response.data;
  },

  async get(approvalId) {
    const response = await api.get(`/approvals/${approvalId}`);
    return response.data;
  },

  async decide(approvalId, decision, comments = '') {
    const response = await api.post(`/approvals/${approvalId}/decide`, {
      decision,
      comments,
    });
    return response.data;
  },
};

export default approvalsService;
