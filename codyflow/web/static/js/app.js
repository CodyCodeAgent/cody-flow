/* ============================================================
   CodyFlow — Main Application (Vue 3 instance)
   ============================================================ */

const { createApp } = Vue;

const app = createApp({
  data() {
    return {
      currentPage: 'editor',
      store,
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

    removeEdge(idx) {
      store.flow.edges.splice(idx, 1);
    },

    editEdge(idx) {
      const edge = store.flow.edges[idx];
      if (!edge) return;
      const cond = prompt(
        '设置条件 (如 needs_fix, passed，留空取消条件):',
        edge.condition || ''
      );
      if (cond !== null) {
        edge.condition = cond || null;
      }
    },

    // ---- Template ----
    loadTemplate() {
      store.flow.nodes = [
        { id:'discuss', type:'discuss', x:220, y:40, prompt:'', outputs:['discuss_output.md'], runner:null, interactive:true, error_strategy:'retry', max_retries:3 },
        { id:'learn', type:'learn', x:220, y:160, prompt:'', outputs:['learn_output.md'], runner:null, interactive:false, error_strategy:'retry', max_retries:3 },
        { id:'code', type:'code', x:220, y:280, prompt:'', outputs:['code_output.md'], runner:null, interactive:false, error_strategy:'retry', max_retries:3 },
        { id:'reflect', type:'reflect', x:220, y:400, prompt:'', outputs:['reflect_output.md'], runner:null, interactive:false, error_strategy:'retry', max_retries:3 },
        { id:'judge', type:'judge', x:220, y:520, prompt:'', outputs:['judge_output.md'], runner:null, interactive:false, error_strategy:'retry', max_retries:3 },
      ];
      store.flow.edges = [
        { from_node:'discuss', to_node:'learn', condition:null },
        { from_node:'learn', to_node:'code', condition:null },
        { from_node:'code', to_node:'reflect', condition:null },
        { from_node:'reflect', to_node:'judge', condition:null },
        { from_node:'judge', to_node:'code', condition:'needs_fix' },
      ];
      store.selectedNode = null;
      store.nodeIdCounter = 5;
    },

    // ---- Export YAML ----
    exportYAML() {
      let y = `name: "${store.flow.name}"\n`;
      y += `description: "${store.flow.description}"\n`;
      y += `runner: ${store.flow.runner}\n`;
      y += `max_iterations: ${store.flow.max_iterations}\n\nnodes:\n`;

      store.flow.nodes.forEach(n => {
        y += `  - id: ${n.id}\n    type: ${n.type}\n`;
        if (n.prompt) y += `    prompt: "${n.prompt.replace(/"/g, '\\"')}"\n`;
        if (n.interactive) y += `    interactive: true\n`;
        if (n.runner) y += `    runner: ${n.runner}\n`;
        if (n.error_strategy !== 'retry') y += `    error_strategy: ${n.error_strategy}\n`;
        if (n.max_retries !== 3) y += `    max_retries: ${n.max_retries}\n`;
        if (n.outputs.length) y += `    outputs:\n${n.outputs.map(o => '      - ' + o).join('\n')}\n`;
      });

      y += `\nedges:\n`;
      store.flow.edges.forEach(e => {
        y += `  - from: ${e.from_node}\n    to: ${e.to_node}\n`;
        if (e.condition) y += `    condition: ${e.condition}\n`;
      });

      this.yamlContent = y;
      this.showYamlModal = true;
    },

    copyYaml() {
      navigator.clipboard.writeText(this.yamlContent);
    },

    // ---- Run flow ----
    async runFlow() {
      store.runEvents = [];
      store.runStatus = 'running';

      try {
        const payload = {
          name: store.flow.name,
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

        await API.post('/api/flow/run', payload);
        this.startPolling();
      } catch (e) {
        store.runStatus = 'failed';
        store.runEvents.push({ type: 'error', text: '启动失败: ' + e.message });
      }
    },

    startPolling() {
      this.pollTimer = setInterval(async () => {
        try {
          const data = await API.get('/api/flow/status');
          store.runEvents = data.events.map(ev => {
            if (ev.type === 'node_start') return { type: 'node_start', text: `▶ ${ev.node_id} (${ev.node_type})` };
            if (ev.type === 'node_complete') return { type: 'node_complete', text: `✓ ${ev.node_id}` };
            if (ev.type === 'flow_complete') return { type: 'node_complete', text: `✓ Flow 完成 (${ev.completed.length} 节点)` };
            return { type: 'error', text: JSON.stringify(ev) };
          });

          if (data.status !== 'running') {
            clearInterval(this.pollTimer);
            store.runStatus = data.status === 'completed' ? 'completed' : 'failed';
          }
        } catch (e) { /* ignore poll errors */ }
      }, 1000);
    },

    // ---- Settings ----
    async saveConfig(config) {
      try {
        await API.post('/api/config/save', config);
        store.runEvents.push({ type: 'node_complete', text: '✓ 配置已保存' });
      } catch (e) {
        alert('保存失败: ' + e.message);
      }
    },

    async checkEnvironment() {
      try {
        const data = await API.get('/api/config/check-env');
        Object.assign(store.envStatus, data);
      } catch (e) {
        alert('检测失败: ' + e.message);
      }
    },
  },

  beforeUnmount() {
    if (this.pollTimer) clearInterval(this.pollTimer);
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
