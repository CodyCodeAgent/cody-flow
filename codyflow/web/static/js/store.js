/* ============================================================
   CodyFlow — Reactive Store (shared state)
   ============================================================ */

const NODE_COLORS = {
  discuss: 'var(--node-discuss)',
  learn:   'var(--node-learn)',
  code:    'var(--node-code)',
  reflect: 'var(--node-reflect)',
  judge:   'var(--node-judge)',
  custom:  'var(--node-custom)',
};

const NODE_LABELS = {
  discuss: '讨论',
  learn:   '学习',
  code:    '写代码',
  reflect: '反思',
  judge:   '判断',
  custom:  '自定义',
};

const NODE_DESCS = {
  discuss: '多轮对话分析需求',
  learn:   '学习项目代码和结构',
  code:    '编写或修改代码',
  reflect: '检查代码质量和问题',
  judge:   '决定流程走向',
  custom:  '自定义节点行为',
};

// Store object — wrapped with Vue.reactive() for proper reactivity
const store = Vue.reactive({
  // Current flow being edited
  flow: {
    name: '',
    description: '',
    runner: 'cody',
    max_iterations: 3,
    nodes: [],
    edges: [],
  },

  // Current flow's DB ID (null = unsaved new flow)
  currentFlowId: null,

  // Saved flows list
  savedFlows: [],

  // UI state
  selectedNode: null,
  nodeIdCounter: 0,

  // Flow list panel
  showFlowList: false,

  // Import YAML modal
  showImportDialog: false,
  importYamlContent: '',

  // Run state
  runStatus: 'idle',
  runEvents: [],
  runningNodes: [],
  completedNodes: [],

  // Run dialog
  showRunDialog: false,
  runWorkdir: '.',
  runUserInput: '',

  // Context file browser
  contextFiles: [],
  selectedContextFile: null,
  contextFileContent: '',

  // Template dialog
  showTemplateDialog: false,
  templates: [],

  // Interactive node chat
  interactiveWaiting: false,
  interactiveNodeId: '',
  interactiveOutput: '',
  interactiveInput: '',

  // Canvas zoom/pan
  canvasScale: 1,
  canvasOffsetX: 0,
  canvasOffsetY: 0,

  // Configuration
  config: {
    cody: {
      api_key: '',
      model: 'claude-sonnet-4-6',
      base_url: '',
    },
    claude_code: {
      installed: false,
      path: '',
      model: 'claude-sonnet-4-6',
    },
    general: {
      default_runner: 'cody',
      workdir: '.',
    },
  },

  // Environment check results
  envStatus: {
    python: { ok: false, detail: '' },
    cody_sdk: { ok: false, detail: '' },
    claude_code: { ok: false, detail: '' },
    api_key: { ok: false, detail: '' },
    langgraph: { ok: false, detail: '' },
  },
});
