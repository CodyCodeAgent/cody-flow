/* ============================================================
   CodyFlow — Main Application (Vue 3 instance)
   ============================================================ */

const { createApp } = Vue;

const app = createApp({
  data() {
    return {
      currentPage: 'editor',
      store,
      sseSource: null,
      wsConn: null,
      pollTimer: null,
      showYamlModal: false,
      yamlContent: '',
    };
  },

  computed: {
    selectedNodeData() {
      if (!store.selectedNode) return null;
      return store.flow.nodes.find(n => n.id === store.selectedNode) || null;
    },
  },

  methods: {
    // ---- Flow management (SQLite) ----
    newFlow() {
      if (store.flow.nodes.length > 0 && !confirm('当前编辑内容未保存，确定要新建吗？')) return;
      store.flow = { name: '', description: '', runner: 'cody', max_iterations: 3, nodes: [], edges: [] };
      store.currentFlowId = null;
      store.selectedNode = null;
      store.nodeIdCounter = 0;
    },

    async openFlows() {
      try {
        const data = await API.listFlows();
        store.savedFlows = data.flows;
        store.showFlowList = true;
      } catch (e) {
        alert('加载 Flow 列表失败: ' + e.message);
      }
    },

    async loadFlow(flowId) {
      try {
        const data = await API.getFlow(flowId);
        const def = data.definition;
        store.flow = {
          name: def.name || data.name,
          description: def.description || data.description,
          runner: def.runner || 'cody',
          max_iterations: def.max_iterations || 3,
          nodes: def.nodes || [],
          edges: def.edges || [],
        };
        store.currentFlowId = data.id;
        store.selectedNode = null;
        store.showFlowList = false;
        // Restore nodeIdCounter from existing nodes
        store.nodeIdCounter = store.flow.nodes.length;
      } catch (e) {
        alert('加载 Flow 失败: ' + e.message);
      }
    },

    async saveFlow() {
      if (!store.flow.name) {
        const name = prompt('请输入 Flow 名称:', 'my-flow');
        if (!name) return;
        store.flow.name = name;
      }

      try {
        const payload = this._buildFlowPayload();
        const result = await API.saveFlow(payload, store.currentFlowId);
        store.currentFlowId = result.id;
        store.runEvents.push({ type: 'node_complete', text: '✓ Flow 已保存 (ID: ' + result.id + ')' });
      } catch (e) {
        alert('保存失败: ' + e.message);
      }
    },

    async deleteFlow(flowId) {
      if (!confirm('确定要删除这个 Flow 吗？')) return;
      try {
        await API.deleteFlow(flowId);
        store.savedFlows = store.savedFlows.filter(f => f.id !== flowId);
        if (store.currentFlowId === flowId) {
          store.currentFlowId = null;
        }
      } catch (e) {
        alert('删除失败: ' + e.message);
      }
    },

    // ---- Node operations ----
    addNodeAtCenter(type) {
      const x = 200 + Math.random() * 100;
      const y = 60 + store.flow.nodes.length * 120;
      this.createNode(type, x, y);
    },

    handleDropNode(type, x, y) {
      this.createNode(type, x, y);
    },

    createNode(type, x, y) {
      store.nodeIdCounter++;
      const id = type + '_' + store.nodeIdCounter;
      store.flow.nodes.push({
        id, type, x, y,
        prompt: '',
        outputs: [id + '_output.md'],
        runner: null,
        interactive: type === 'discuss',
        error_strategy: 'retry',
        max_retries: 3,
      });
    },

    updateNodePos(id, x, y) {
      const node = store.flow.nodes.find(n => n.id === id);
      if (node) { node.x = x; node.y = y; }
    },

    updateNodeProp(id, prop, value) {
      const node = store.flow.nodes.find(n => n.id === id);
      if (node) node[prop] = value;
    },

    renameNode(oldId, newId) {
      if (store.flow.nodes.some(n => n.id === newId)) {
        alert('节点 ID 已存在: ' + newId);
        return;
      }
      const node = store.flow.nodes.find(n => n.id === oldId);
      if (!node) return;
      node.id = newId;
      store.flow.edges.forEach(e => {
        if (e.from_node === oldId) e.from_node = newId;
        if (e.to_node === oldId) e.to_node = newId;
      });
      store.selectedNode = newId;
    },

    removeNode(id) {
      store.flow.nodes = store.flow.nodes.filter(n => n.id !== id);
      store.flow.edges = store.flow.edges.filter(
        e => e.from_node !== id && e.to_node !== id
      );
      if (store.selectedNode === id) store.selectedNode = null;
    },

    // ---- Edge operations ----
    addEdge(fromId, toId) {
      const exists = store.flow.edges.some(
        e => e.from_node === fromId && e.to_node === toId
      );
      if (!exists) {
        store.flow.edges.push({ from_node: fromId, to_node: toId, condition: null });
      }
    },

    removeEdge(idx) { store.flow.edges.splice(idx, 1); },

    editEdge(idx) {
      const edge = store.flow.edges[idx];
      if (!edge) return;
      const cond = prompt('设置条件 (如 needs_fix, passed，留空取消条件):', edge.condition || '');
      if (cond !== null) edge.condition = cond || null;
    },

    // ---- Canvas transform ----
    updateTransform(delta) {
      if (delta.scale !== undefined) store.canvasScale = delta.scale;
      if (delta.offsetX !== undefined) store.canvasOffsetX = delta.offsetX;
      if (delta.offsetY !== undefined) store.canvasOffsetY = delta.offsetY;
    },

    // ---- Template ----
    async loadTemplate() {
      try {
        const data = await API.listTemplates();
        store.templates = data.templates || [];
        store.showTemplateDialog = true;
      } catch (e) {
        alert('加载模板失败: ' + e.message);
      }
    },

    async doLoadTemplate(filename) {
      if (store.flow.nodes.length > 0 && !confirm('加载模板将覆盖当前编辑内容，继续吗？')) return;
      try {
        const tpl = await API.getTemplate(filename);
        store.flow = {
          name: tpl.name,
          description: tpl.description,
          runner: tpl.runner,
          max_iterations: tpl.max_iterations,
          nodes: tpl.nodes,
          edges: tpl.edges,
        };
        store.selectedNode = null;
        store.currentFlowId = null;
        store.nodeIdCounter = tpl.nodes.length;
        store.showTemplateDialog = false;
      } catch (e) {
        alert('加载模板失败: ' + e.message);
      }
    },

    // ---- Export YAML ----
    async exportYAML() {
      try {
        const payload = this._buildFlowPayload();
        const data = await API.exportYaml(payload);
        this.yamlContent = data.yaml;
        this.showYamlModal = true;
      } catch (e) {
        alert('导出失败: ' + e.message);
      }
    },

    copyYaml() { navigator.clipboard.writeText(this.yamlContent); },

    // ---- Import YAML ----
    showImportYamlDialog() {
      store.importYamlContent = '';
      store.showImportDialog = true;
    },

    async doImportYaml() {
      if (!store.importYamlContent.trim()) return;
      try {
        const data = await API.importYaml(store.importYamlContent);
        store.flow = {
          name: data.name,
          description: data.description,
          runner: data.runner,
          max_iterations: data.max_iterations,
          nodes: data.nodes,
          edges: data.edges,
        };
        store.currentFlowId = null; // imported as unsaved
        store.selectedNode = null;
        store.nodeIdCounter = data.nodes.length;
        store.showImportDialog = false;
        store.runEvents.push({ type: 'node_complete', text: '✓ YAML 导入成功 (' + data.nodes.length + ' 个节点)' });
      } catch (e) {
        alert('导入失败: ' + e.message);
      }
    },

    // ---- Run dialog ----
    showRunFlowDialog() {
      if (store.flow.nodes.length === 0) {
        alert('请先添加节点');
        return;
      }
      store.runWorkdir = store.config.general.workdir || '.';
      store.runUserInput = '';
      store.showRunDialog = true;
    },

    closeRunDialog() { store.showRunDialog = false; },

    // ---- Run flow ----
    async runFlow() {
      store.showRunDialog = false;
      store.runEvents = [];
      store.runStatus = 'running';
      store.runningNodes = [];
      store.completedNodes = [];

      try {
        const payload = this._buildFlowPayload();
        await API.runFlow(payload, store.runWorkdir, store.runUserInput);
        this.connectWS();
      } catch (e) {
        store.runStatus = 'failed';
        store.runEvents.push({ type: 'error', text: '启动失败: ' + e.message });
      }
    },

    _buildFlowPayload() {
      return {
        name: store.flow.name || 'unnamed',
        description: store.flow.description,
        runner: store.flow.runner,
        max_iterations: store.flow.max_iterations,
        nodes: store.flow.nodes.map(n => ({
          id: n.id, type: n.type, prompt: n.prompt,
          outputs: n.outputs, runner: n.runner,
          interactive: n.interactive,
          error_strategy: n.error_strategy,
          max_retries: n.max_retries, x: n.x, y: n.y,
        })),
        edges: store.flow.edges,
      };
    },

    // ---- WebSocket connection ----
    connectWS() {
      this.disconnectSSE();
      const proto = location.protocol === 'https:' ? 'wss:' : 'ws:';
      this.wsConn = new WebSocket(`${proto}//${location.host}/ws/flow`);

      this.wsConn.onmessage = (event) => {
        try {
          const data = JSON.parse(event.data);
          if (data.type !== 'keepalive') this.handleFlowEvent(data);
        } catch (e) {}
      };

      this.wsConn.onerror = () => {
        if (store.runStatus === 'running') this.startPolling();
      };

      this.wsConn.onclose = () => {
        this.wsConn = null;
      };
    },

    handleFlowEvent(ev) {
      const time = ev.timestamp ? new Date(ev.timestamp * 1000).toLocaleTimeString() : '';

      if (ev.type === 'node_start') {
        store.runningNodes = [...store.runningNodes.filter(id => id !== ev.node_id), ev.node_id];
        store.runEvents.push({
          type: 'node_start', time,
          text: `▶ ${ev.node_id} (${ev.node_type})`,
          detail: ev.iteration > 0 ? `迭代 ${ev.iteration}/${ev.max_iterations}` : '',
        });
      } else if (ev.type === 'node_complete') {
        store.runningNodes = store.runningNodes.filter(id => id !== ev.node_id);
        if (!store.completedNodes.includes(ev.node_id)) store.completedNodes.push(ev.node_id);
        let text = `✓ ${ev.node_id}`;
        if (ev.duration) text += ` (${ev.duration}s)`;
        let detail = '';
        if (ev.route) {
          detail = `路由: ${ev.route}`;
          if (ev.reasoning) detail += ` — ${ev.reasoning.substring(0, 100)}`;
        }
        store.runEvents.push({ type: 'node_complete', time, text, detail });
      } else if (ev.type === 'node_error') {
        store.runEvents.push({ type: 'error', time, text: `✗ ${ev.node_id} 错误 (尝试 ${ev.attempt})`, detail: ev.error });
      } else if (ev.type === 'flow_complete') {
        store.runStatus = 'completed';
        store.runningNodes = [];
        store.runEvents.push({ type: 'node_complete', time, text: `✓ Flow 完成 (${ev.completed_nodes.length} 节点, ${ev.iteration} 迭代, ${ev.total_duration}s)` });
        this.disconnectSSE();
        this.refreshContextFiles();
      } else if (ev.type === 'flow_stopped') {
        store.runStatus = 'idle';
        store.runningNodes = [];
        store.runEvents.push({ type: 'error', time, text: 'Flow 已停止' });
        this.disconnectSSE();
      } else if (ev.type === 'interactive_turn') {
        store.runEvents.push({ type: 'node_start', time, text: `💬 ${ev.node_id} 轮次 ${ev.turn} (${ev.role})` });
      } else if (ev.type === 'node_skipped') {
        store.runEvents.push({ type: 'error', time, text: `⊘ ${ev.node_id} 已跳过`, detail: ev.error });
      } else if (ev.type === 'interactive_wait') {
        // Interactive node is waiting for user input — show chat UI
        store.interactiveWaiting = true;
        store.interactiveNodeId = ev.node_id;
        store.interactiveOutput = ev.output || '';
        store.interactiveInput = '';
        store.runEvents.push({ type: 'node_start', time, text: `💬 ${ev.node_id} 等待你的回复...` });
      }

      this.$nextTick(() => {
        const log = document.querySelector('.events-log');
        if (log) log.scrollTop = log.scrollHeight;
      });
    },

    // ---- Interactive chat ----
    sendInteractiveMessage(forceMsg) {
      const msg = forceMsg || store.interactiveInput.trim();
      if (!msg) return;

      if (this.wsConn && this.wsConn.readyState === WebSocket.OPEN) {
        this.wsConn.send(JSON.stringify({ type: 'interactive_input', message: msg }));
      }

      const time = new Date().toLocaleTimeString();
      if (msg === 'done') {
        store.runEvents.push({ type: 'node_complete', time, text: `💬 ${store.interactiveNodeId} 对话结束` });
      } else {
        store.runEvents.push({ type: 'node_start', time, text: `💬 你: ${msg.substring(0, 80)}${msg.length > 80 ? '...' : ''}` });
      }

      store.interactiveWaiting = false;
      store.interactiveInput = '';
    },

    disconnectSSE() {
      if (this.sseSource) { this.sseSource.close(); this.sseSource = null; }
      if (this.wsConn) { this.wsConn.close(); this.wsConn = null; }
      if (this.pollTimer) { clearInterval(this.pollTimer); this.pollTimer = null; }
    },

    startPolling() {
      this.pollTimer = setInterval(async () => {
        try {
          const data = await API.getFlowStatus();
          if (data.status !== 'running') {
            clearInterval(this.pollTimer);
            this.pollTimer = null;
            store.runStatus = data.status === 'completed' ? 'completed' : 'failed';
            this.refreshContextFiles();
          }
        } catch (e) {}
      }, 2000);
    },

    async stopFlow() {
      try {
        await API.stopFlow();
        store.runStatus = 'idle';
        store.runningNodes = [];
        this.disconnectSSE();
      } catch (e) { alert('停止失败: ' + e.message); }
    },

    // ---- Context file browser ----
    async refreshContextFiles() {
      try {
        const data = await API.listContextFiles(store.runWorkdir || '.');
        store.contextFiles = data.files;
      } catch (e) {}
    },

    async loadContextFile(filename) {
      try {
        const data = await API.readContextFile(filename, store.runWorkdir || '.');
        store.selectedContextFile = filename;
        store.contextFileContent = data.content;
      } catch (e) { alert('读取失败: ' + e.message); }
    },

    // ---- Settings ----
    async saveConfig(config) {
      try {
        await API.saveConfig(config);
        store.runEvents.push({ type: 'node_complete', text: '✓ 配置已保存' });
      } catch (e) { alert('保存失败: ' + e.message); }
    },

    async checkEnvironment() {
      try {
        const data = await API.checkEnvironment();
        Object.assign(store.envStatus, data);
      } catch (e) { alert('检测失败: ' + e.message); }
    },

    // ---- Helpers ----
    formatTime(ts) {
      if (!ts) return '';
      return new Date(ts * 1000).toLocaleString();
    },

    // ---- Init ----
    async loadSavedConfig() {
      try {
        const cfg = await API.loadConfig();
        if (cfg && Object.keys(cfg).length > 0) {
          if (cfg.cody) Object.assign(store.config.cody, cfg.cody);
          if (cfg.claude_code) Object.assign(store.config.claude_code, cfg.claude_code);
          if (cfg.general) Object.assign(store.config.general, cfg.general);
        }
      } catch (e) {}
    },
  },

  mounted() {
    this.loadSavedConfig();
  },

  beforeUnmount() {
    this.disconnectSSE();
  },
});

// Register components
app.component('app-header', AppHeader);
app.component('node-palette', NodePalette);
app.component('flow-canvas', FlowCanvas);
app.component('props-panel', PropsPanel);
app.component('settings-page', SettingsPage);

// Mount
app.mount('#app');
