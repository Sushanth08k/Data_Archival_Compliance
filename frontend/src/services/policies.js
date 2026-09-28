/**
 * Policy API service — upload, list, analyze, get rules.
 */

import api from './api';

const policyService = {
  async upload(file) {
    const formData = new FormData();
    formData.append('file', file);
    const response = await api.post('/policies/upload', formData, {
      headers: { 'Content-Type': 'multipart/form-data' },
    });
    return response.data;
  },

  async list() {
    const response = await api.get('/policies');
    return response.data;
  },

  async get(policyId) {
    const response = await api.get(`/policies/${policyId}`);
    return response.data;
  },

  async getVersions(policyId) {
    const response = await api.get(`/policies/${policyId}/versions`);
    return response.data;
  },

  async analyze(policyId) {
    const response = await api.post(`/policies/${policyId}/analyze`);
    return response.data;
  },

  async getRules(policyId) {
    const response = await api.get(`/policies/${policyId}/rules`);
    return response.data;
  },
};

export default policyService;
