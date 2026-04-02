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

  async del(url) {
    const res = await fetch(url, { method: 'DELETE' });
    if (!res.ok) throw new Error(res.statusText);
    return res.json();
  },

  // ---- Flow CRUD (SQLite) ----
  async listFlows() {
    return this.get('/api/flows');
  },

  async getFlow(flowId) {
    return this.get('/api/flows/' + flowId);
  },

  async saveFlow(flow, flowId) {
    return this.post('/api/flows/save', { flow, flow_id: flowId || null });
  },

  async deleteFlow(flowId) {
    return this.del('/api/flows/' + flowId);
  },

  // ---- Flow operations ----
  async validateFlow(flow) {
    return this.post('/api/flow/validate', flow);
  },

  async exportYaml(flow) {
    return this.post('/api/flow/export-yaml', flow);
  },

  async importYaml(yamlContent) {
    return this.post('/api/flow/import-yaml', { yaml_content: yamlContent });
  },

  // ---- Context file browser ----
  async listContextFiles(workdir) {
    return this.get('/api/context/list?workdir=' + encodeURIComponent(workdir || '.'));
  },

  async readContextFile(filename, workdir) {
    return this.get(
      '/api/context/read?filename=' + encodeURIComponent(filename) +
      '&workdir=' + encodeURIComponent(workdir || '.')
    );
  },

  // ---- Config ----
  async saveConfig(config) {
    return this.post('/api/config/save', config);
  },

  async loadConfig() {
    return this.get('/api/config/load');
  },

  async checkEnvironment() {
    return this.get('/api/config/check-env');
  },

  // ---- Templates ----
  async listTemplates() {
    return this.get('/api/templates');
  },

  async getTemplate(filename) {
    return this.get('/api/templates/' + encodeURIComponent(filename));
  },

  // ---- Tasks ----
  async createTask(flow, flowId, workdir, userInput) {
    return this.post('/api/tasks', {
      flow,
      flow_id: flowId || null,
      workdir: workdir || '.',
      user_input: userInput || '',
    });
  },

  async listTasks() {
    return this.get('/api/tasks');
  },

  async getTask(taskId) {
    return this.get('/api/tasks/' + taskId);
  },

  async stopTask(taskId) {
    return this.post('/api/tasks/' + taskId + '/stop');
  },

  async deleteTask(taskId) {
    return this.del('/api/tasks/' + taskId);
  },
};
