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

// Store object — will be made reactive by Vue
const store = {
  // Flow definition
  flow: {
    name: 'my-feature',
    description: '',
    runner: 'cody',
    max_iterations: 3,
    nodes: [],
    edges: [],
  },

  // UI state
  selectedNode: null,
  currentPage: 'editor',
  nodeIdCounter: 0,

  // Run state
  runStatus: 'idle',  // idle | running | completed | failed
  runEvents: [],
  runningNodes: [],   // node IDs currently executing
  completedNodes: [], // node IDs that have completed

  // Run dialog
  showRunDialog: false,
  runWorkdir: '.',
  runUserInput: '',

  // Context file browser
  contextFiles: [],
  selectedContextFile: null,
  contextFileContent: '',

  // Canvas zoom/pan
  canvasScale: 1,
  canvasOffsetX: 0,
  canvasOffsetY: 0,

  // Configuration
  config: {
    cody: {
      api_key: '',
      model: 'claude-sonnet-4-20250514',
      base_url: '',
    },
    claude_code: {
      installed: false,
      path: '',
      model: 'claude-sonnet-4-20250514',
    },
    general: {
      default_runner: 'cody',
      workdir: '.',
      language: 'zh-CN',
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
};
