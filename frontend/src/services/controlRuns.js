/**
 * Control Runs API service — start, list, lifecycle actions,
 * and live database inspection (Active DB and Archive DB).
 */

import api from './api';

const controlRunService = {
  async getDatabaseProfiles() {
    const response = await api.get('/control-runs/database/profiles');
    return response.data;
  },

  async start(policyId, numRecords = 50, databaseId = 'postgres_core') {
    const response = await api.post(`/control-runs?policy_id=${policyId}&num_records=${numRecords}&database_id=${databaseId}`);
    return response.data;
  },

  async list(policyId = null) {
    const params = policyId ? `?policy_id=${policyId}` : '';
    const response = await api.get(`/control-runs${params}`);
    return response.data;
  },

  async get(runId) {
    const response = await api.get(`/control-runs/${runId}`);
    return response.data;
  },

  async archive(runId) {
    const response = await api.post(`/control-runs/${runId}/archive`);
    return response.data;
  },

  async verify(runId) {
    const response = await api.post(`/control-runs/${runId}/verify`);
    return response.data;
  },

  async cleanup(runId) {
    const response = await api.post(`/control-runs/${runId}/cleanup`);
    return response.data;
  },

  async finalVerify(runId) {
    const response = await api.post(`/control-runs/${runId}/final-verify`);
    return response.data;
  },

  // Live Database View endpoints
  async getSourceDatabase(limit = 100) {
    const response = await api.get(`/control-runs/database/source?limit=${limit}`);
    return response.data;
  },

  async getArchiveDatabase(runId = null, limit = 100) {
    const params = runId ? `?run_id=${runId}&limit=${limit}` : `?limit=${limit}`;
    const response = await api.get(`/control-runs/database/archive${params}`);
    return response.data;
  },

  async seedDatabase(count = 50) {
    const response = await api.post(`/control-runs/database/seed?count=${count}&force=true`);
    return response.data;
  },
};

export default controlRunService;
