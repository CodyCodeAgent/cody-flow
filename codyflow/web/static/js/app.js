/* ============================================================
   CodyFlow — Main Application (Vue 3 instance)
   ============================================================ */

const { createApp } = Vue;

const app = createApp({
  data() {
    return {
      currentPage: 'editor',
      store,
      wsConn: null,
      showYamlModal: false,
      yamlContent: '',
    };
  },

  computed: {
    selectedNodeData() {
      if (!store.selectedNode) return null;
      return store.flow.nodes.find(n => n.id === store.selectedNode) || null;
    },
    selectedEdgeData() {
      if (store.selectedEdgeIdx === null || store.selectedEdgeIdx === undefined) return null;
      return store.flow.edges[store.selectedEdgeIdx] || null;
    },
  },

  methods: {
    // ---- Navigation ----
    navigate(page) {
      this.currentPage = page;
    },

    // ---- Flow management ----
    newFlow() {
      if (store.flow.nodes.length > 0 && !confirm('当前编辑内容未保存，确定要新建吗？')) return;
      store.flow = { name: '', description: '', runner: 'cody', workdir: '', max_iterations: 3, nodes: [], edges: [] };
      store.currentFlowId = null;
      store.selectedNode = null;
      store.nodeIdCounter = 0;
    },

    async loadFlow(flowId) {
      try {
        const data = await API.getFlow(flowId);
        const def = data.definition;
        store.flow = {
          name: def.name || data.name,
          description: def.description || data.description,
          runner: def.runner || 'cody',
          workdir: def.workdir || '',
          max_iterations: def.max_iterations || 3,
          nodes: def.nodes || [],
          edges: def.edges || [],
        };
        store.currentFlowId = data.id;
        store.selectedNode = null;
        store.selectedEdgeIdx = null;
        store.nodeIdCounter = store.flow.nodes.length;
      } catch (e) {
        alert('加载失败: ' + e.message);
      }
    },

    async saveFlow() {
      try {
        const payload = this._buildFlowPayload();
        const result = await API.saveFlow(payload, store.currentFlowId);
        store.currentFlowId = result.id;
      } catch (e) {
        alert('保存失败: ' + e.message);
      }
    },

    // Called from sidebar Flow tab delete button (passes a refresh callback)
    async deleteSidebarFlow(flowId, refreshCallback) {
      if (!confirm('确定删除此 Flow？')) return;
      try {
        await API.deleteFlow(flowId);
        if (store.currentFlowId === flowId) {
          store.flow = { name: '', description: '', runner: 'cody', workdir: '', max_iterations: 3, nodes: [], edges: [] };
          store.currentFlowId = null;
          store.selectedNode = null;
          store.nodeIdCounter = 0;
        }
        if (refreshCallback) refreshCallback();
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

    handleDropNode(type, x, y) { this.createNode(type, x, y); },

    createNode(type, x, y) {
      store.nodeIdCounter++;
      const id = type + '_' + store.nodeIdCounter;
      store.flow.nodes.push({
        id, type, x, y,
        prompt: '',
        outputs: (type === 'start' || type === 'end') ? [] : [id + '_output.md'],
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
      if (store.flow.nodes.some(n => n.id === newId)) { alert('节点 ID 已存在: ' + newId); return; }
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
      store.flow.edges = store.flow.edges.filter(e => e.from_node !== id && e.to_node !== id);
      if (store.selectedNode === id) store.selectedNode = null;
    },

    // ---- Edge operations ----
    addEdge(fromId, toId) {
      const exists = store.flow.edges.some(e => e.from_node === fromId && e.to_node === toId);
      if (!exists) store.flow.edges.push({ from_node: fromId, to_node: toId, condition: null });
    },

    removeEdge(idx) { store.flow.edges.splice(idx, 1); },

    updateEdge(idx, prop, value) {
      const edge = store.flow.edges[idx];
      if (edge) edge[prop] = value || null;
    },

    removeEdgeByIdx(idx) {
      store.flow.edges.splice(idx, 1);
      store.selectedEdgeIdx = null;
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
      } catch (e) { alert('加载模板失败: ' + e.message); }
    },

    async doLoadTemplate(filename) {
      if (store.flow.nodes.length > 0 && !confirm('加载模板将覆盖当前编辑内容，继续吗？')) return;
      try {
        const tpl = await API.getTemplate(filename);
        store.flow = {
          name: tpl.name, description: tpl.description, runner: tpl.runner,
          workdir: tpl.workdir || '', max_iterations: tpl.max_iterations,
          nodes: tpl.nodes, edges: tpl.edges,
        };
        store.selectedNode = null;
        store.currentFlowId = null;
        store.nodeIdCounter = tpl.nodes.length;
        store.showTemplateDialog = false;
      } catch (e) { alert('加载模板失败: ' + e.message); }
    },

    // ---- Export/Import YAML ----
    async exportYAML() {
      try {
        const data = await API.exportYaml(this._buildFlowPayload());
        this.yamlContent = data.yaml;
        this.showYamlModal = true;
      } catch (e) { alert('导出失败: ' + e.message); }
    },

    copyYaml() { navigator.clipboard.writeText(this.yamlContent); },

    showImportYamlDialog() { store.importYamlContent = ''; store.showImportDialog = true; },

    async doImportYaml() {
      if (!store.importYamlContent.trim()) return;
      try {
        const data = await API.importYaml(store.importYamlContent);
        store.flow = {
          name: data.name, description: data.description, runner: data.runner,
          workdir: data.workdir || '', max_iterations: data.max_iterations,
          nodes: data.nodes, edges: data.edges,
        };
        store.currentFlowId = null;
        store.selectedNode = null;
        store.nodeIdCounter = data.nodes.length;
        store.showImportDialog = false;
      } catch (e) { alert('导入失败: ' + e.message); }
    },

    // ---- Task navigation ----
    async openTask(taskId) {
      this.disconnectWS();
      store.currentTaskId = taskId;
      store.currentTaskInfo = null;
      store.taskState = {
        status: 'running',
        outputLines: [],
        runEvents: [],
        runningNodes: [],
        completedNodes: [],
        interactiveWaiting: false,
        interactiveNodeId: '',
        interactiveOutput: '',
        interactiveInput: '',
      };
      store.bottomPanelOpen = true;
      store.bottomPanelTab = 'output';
      this.currentPage = 'task-detail';

      // Load task info (includes historical events)
      try {
        const data = await API.getTask(taskId);
        store.currentTaskInfo = data;
        store.taskState.status = data.status;
        // Replay historical events to rebuild output/log/node state
        for (const ev of data.events) {
          this.handleTaskEvent(ev, false);
        }
      } catch (e) {
        alert('加载任务失败: ' + e.message);
        return;
      }

      // Connect live WebSocket if task is running
      if (store.taskState.status === 'running') {
        this.connectTaskWS(taskId);
      }
    },

    backToTasks() {
      this.disconnectWS();
      store.currentTaskId = null;
      store.currentTaskInfo = null;
      this.currentPage = 'tasks';
    },

    // ---- Task WebSocket ----
    connectTaskWS(taskId) {
      this.disconnectWS();
      const proto = location.protocol === 'https:' ? 'wss:' : 'ws:';
      this.wsConn = new WebSocket(`${proto}//${location.host}/ws/task/${taskId}`);

      this.wsConn.onmessage = (event) => {
        try {
          const data = JSON.parse(event.data);
          if (data.type !== 'keepalive') this.handleTaskEvent(data, true);
        } catch (e) {}
      };

      this.wsConn.onerror = () => { console.warn('WS error for task', taskId); };
      this.wsConn.onclose = () => { this.wsConn = null; };
    },

    disconnectWS() {
      if (this.wsConn) { this.wsConn.close(); this.wsConn = null; }
    },

    // ---- Task event handler ----
    handleTaskEvent(ev, live = true) {
      const ts = store.taskState;
      const time = ev.timestamp ? new Date(ev.timestamp * 1000).toLocaleTimeString() : '';

      if (ev.type === 'output_chunk') {
        const last = ts.outputLines[ts.outputLines.length - 1];
        if (ev.chunk_type === 'text_delta') {
          if (live && last && last.type === 'text' && last.nodeId === ev.node_id) {
            last.content += ev.content;
          } else {
            ts.outputLines.push({ type: 'text', nodeId: ev.node_id, content: ev.content });
          }
        } else if (ev.chunk_type === 'tool_call') {
          ts.outputLines.push({ type: 'tool_call', nodeId: ev.node_id, tool: ev.content, args: ev.extra?.args });
        } else if (ev.chunk_type === 'tool_result') {
          ts.outputLines.push({ type: 'tool_result', nodeId: ev.node_id, content: ev.content });
        } else if (ev.chunk_type === 'thinking') {
          ts.outputLines.push({ type: 'thinking', nodeId: ev.node_id, content: ev.content });
        }
        if (live && store.bottomPanelTab !== 'chat') store.bottomPanelTab = 'output';
        if (live) store.bottomPanelOpen = true;

      } else if (ev.type === 'node_start') {
        ts.interactiveWaiting = false;  // a new node starting means any prior interactive wait is over
        ts.runningNodes = [...ts.runningNodes.filter(id => id !== ev.node_id), ev.node_id];
        ts.outputLines.push({ type: 'node_start', nodeId: ev.node_id, nodeType: ev.node_type });
        ts.runEvents.push({
          type: 'node_start', time,
          text: `▶ ${ev.node_id} (${ev.node_type})`,
          detail: ev.iteration > 0 ? `迭代 ${ev.iteration}/${ev.max_iterations}` : '',
        });

      } else if (ev.type === 'node_complete') {
        ts.runningNodes = ts.runningNodes.filter(id => id !== ev.node_id);
        if (!ts.completedNodes.includes(ev.node_id)) ts.completedNodes.push(ev.node_id);
        ts.outputLines.push({ type: 'node_done', nodeId: ev.node_id, duration: ev.duration });
        let text = `✓ ${ev.node_id}`;
        if (ev.duration) text += ` (${ev.duration}s)`;
        let detail = '';
        if (ev.route) {
          detail = `路由: ${ev.route}`;
          if (ev.reasoning) detail += ` — ${ev.reasoning.substring(0, 100)}`;
        }
        ts.runEvents.push({ type: 'node_complete', time, text, detail });

      } else if (ev.type === 'node_error') {
        ts.runEvents.push({ type: 'error', time, text: `✗ ${ev.node_id} 错误 (尝试 ${ev.attempt})`, detail: ev.error });

      } else if (ev.type === 'flow_start') {
        ts.outputLines = [];

      } else if (ev.type === 'flow_complete') {
        ts.status = 'completed';
        ts.runningNodes = [];
        ts.interactiveWaiting = false;
        ts.runEvents.push({ type: 'node_complete', time, text: `✓ 完成 (${ev.completed_nodes?.length} 节点, ${ev.iteration} 迭代, ${ev.total_duration}s)` });
        this.disconnectWS();
        if (store.currentTaskInfo) store.currentTaskInfo.status = 'completed';

      } else if (ev.type === 'flow_stopped') {
        ts.status = 'stopped';
        ts.runningNodes = [];
        ts.interactiveWaiting = false;
        ts.runEvents.push({ type: 'error', time, text: 'Flow 已停止' });
        this.disconnectWS();
        if (store.currentTaskInfo) store.currentTaskInfo.status = 'stopped';

      } else if (ev.type === 'flow_error') {
        ts.status = 'failed';
        ts.runningNodes = [];
        ts.interactiveWaiting = false;
        ts.runEvents.push({ type: 'error', time, text: `Flow 失败: ${ev.error}` });
        this.disconnectWS();
        if (store.currentTaskInfo) store.currentTaskInfo.status = 'failed';

      } else if (ev.type === 'interactive_turn') {
        ts.runEvents.push({ type: 'node_start', time, text: `💬 ${ev.node_id} 轮次 ${ev.turn} (${ev.role})` });

      } else if (ev.type === 'node_skipped') {
        ts.runEvents.push({ type: 'error', time, text: `⊘ ${ev.node_id} 已跳过`, detail: ev.error });

      } else if (ev.type === 'interactive_wait') {
        ts.interactiveWaiting = true;
        ts.interactiveNodeId = ev.node_id;
        ts.interactiveOutput = ev.output || '';
        ts.interactiveInput = '';
        ts.runEvents.push({ type: 'node_start', time, text: `💬 ${ev.node_id} 等待你的回复...` });
      }
    },

    // ---- Interactive chat ----
    sendInteractiveMessage(forceMsg) {
      const ts = store.taskState;
      const msg = forceMsg || ts.interactiveInput.trim();
      if (!msg) return;

      if (this.wsConn && this.wsConn.readyState === WebSocket.OPEN) {
        this.wsConn.send(JSON.stringify({ type: 'interactive_input', message: msg }));
      }

      const time = new Date().toLocaleTimeString();
      if (msg === 'done') {
        ts.runEvents.push({ type: 'node_complete', time, text: `💬 ${ts.interactiveNodeId} 对话结束` });
      } else {
        ts.runEvents.push({ type: 'node_start', time, text: `💬 你: ${msg.substring(0, 80)}` });
      }
      ts.interactiveWaiting = false;
      ts.interactiveInput = '';
    },

    // ---- Settings ----
    async saveConfig(config) {
      try {
        await API.saveConfig(config);
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

    _buildFlowPayload() {
      return {
        name: store.flow.name || 'unnamed',
        description: store.flow.description,
        runner: store.flow.runner,
        workdir: store.flow.workdir,
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
    this.disconnectWS();
  },
});

// Register components
app.component('app-header', AppHeader);
app.component('node-palette', NodePalette);
app.component('flow-canvas', FlowCanvas);
app.component('props-panel', PropsPanel);
app.component('settings-page', SettingsPage);
app.component('bottom-panel', BottomPanel);
app.component('task-list', TaskList);
app.component('task-detail', TaskDetail);

// Mount
app.mount('#app');
