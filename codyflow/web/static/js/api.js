/* ============================================================
   CodyFlow — API Client
   ============================================================ */

const API = {
  async post(url, body) {
    const res = await fetch(url, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify(body),
    });
    if (!res.ok) {
      const err = await res.json().catch(() => ({ detail: res.statusText }));
      throw new Error(err.detail || 'Request failed');
    }
    return res.json();
  },

  async get(url) {
    const res = await fetch(url);
    if (!res.ok) throw new Error(res.statusText);
    return res.json();
  },

  // Flow operations
  async runFlow(flow, workdir, userInput) {
    return this.post('/api/flow/run', {
      flow,
      req: { workdir, user_input: userInput },
    });
  },

  async getFlowStatus() {
    return this.get('/api/flow/status');
  },

  async stopFlow() {
    return this.post('/api/flow/stop');
  },

  async validateFlow(flow) {
    return this.post('/api/flow/validate', flow);
  },

  // Config operations
  async saveConfig(config) {
    return this.post('/api/config/save', config);
  },

  async loadConfig() {
    return this.get('/api/config/load');
  },

  async checkEnvironment() {
    return this.get('/api/config/check-env');
  },
};
