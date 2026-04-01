/* ============================================================
   CodyFlow — Settings Page Component
   ============================================================ */

const SettingsPage = {
  props: ['config', 'envStatus'],
  emits: ['saveConfig', 'checkEnv'],

  data() {
    return {
      saving: false,
      checking: false,
      showApiKey: false,
      models: [
        { value: 'claude-sonnet-4-6', label: 'Claude Sonnet 4.6' },
        { value: 'claude-opus-4-6', label: 'Claude Opus 4.6' },
        { value: 'claude-haiku-4-5-20251001', label: 'Claude Haiku 4.5' },
        { value: 'gpt-4o', label: 'GPT-4o' },
        { value: 'deepseek-chat', label: 'DeepSeek' },
        { value: 'qwen3.5', label: '通义千问 Qwen' },
        { value: 'glm-4', label: '智谱 GLM-4' },
      ],
    };
  },

  methods: {
    async save() {
      this.saving = true;
      try {
        await this.$emit('saveConfig', this.config);
      } finally {
        setTimeout(() => this.saving = false, 500);
      }
    },
    async checkEnv() {
      this.checking = true;
      try {
        await this.$emit('checkEnv');
      } finally {
        setTimeout(() => this.checking = false, 1000);
      }
    },
    envIcon(status) {
      return status.ok ? '✅' : '❌';
    },
  },

  template: `
    <div class="settings-page">
      <h2>设置</h2>

      <!-- Environment Check -->
      <div class="settings-section">
        <h3>环境检测</h3>
        <p style="font-size:13px;color:var(--text2);margin-bottom:12px">
          检查运行 CodyFlow 所需的环境依赖是否就绪。
        </p>
        <button class="btn btn-outline btn-sm" @click="checkEnv" :disabled="checking">
          {{ checking ? '检测中...' : '运行检测' }}
        </button>
        <div class="env-check">
          <div class="env-item">
            <span class="status-icon">{{ envIcon(envStatus.python) }}</span>
            <span class="env-name">Python ≥ 3.10</span>
            <span class="env-detail">{{ envStatus.python.detail || '未检测' }}</span>
          </div>
          <div class="env-item">
            <span class="status-icon">{{ envIcon(envStatus.langgraph) }}</span>
            <span class="env-name">LangGraph</span>
            <span class="env-detail">{{ envStatus.langgraph.detail || '未检测' }}</span>
          </div>
          <div class="env-item">
            <span class="status-icon">{{ envIcon(envStatus.cody_sdk) }}</span>
            <span class="env-name">Cody SDK</span>
            <span class="env-detail">{{ envStatus.cody_sdk.detail || '未检测' }}</span>
          </div>
          <div class="env-item">
            <span class="status-icon">{{ envIcon(envStatus.claude_code) }}</span>
            <span class="env-name">Claude Code SDK</span>
            <span class="env-detail">{{ envStatus.claude_code.detail || '未检测' }}</span>
          </div>
          <div class="env-item">
            <span class="status-icon">{{ envIcon(envStatus.api_key) }}</span>
            <span class="env-name">API Key</span>
            <span class="env-detail">{{ envStatus.api_key.detail || '未检测' }}</span>
          </div>
        </div>
      </div>

      <!-- Cody Runner Config -->
      <div class="settings-section">
        <h3>Cody Runner 配置</h3>
        <div class="form-group">
          <label>API Key</label>
          <div style="display:flex;gap:6px">
            <input
              :type="showApiKey ? 'text' : 'password'"
              v-model="config.cody.api_key"
              placeholder="sk-ant-..."
              style="flex:1"
            >
            <button class="btn btn-outline btn-sm" @click="showApiKey = !showApiKey">
              {{ showApiKey ? '隐藏' : '显示' }}
            </button>
          </div>
        </div>
        <div class="form-group">
          <label>模型</label>
          <select v-model="config.cody.model">
            <option v-for="m in models" :key="m.value" :value="m.value">{{ m.label }}</option>
          </select>
        </div>
        <div class="form-group">
          <label>Base URL (可选，用于自定义 API 端点)</label>
          <input v-model="config.cody.base_url" placeholder="https://api.anthropic.com">
        </div>
      </div>

      <!-- Claude Code Runner Config -->
      <div class="settings-section">
        <h3>Claude Code Runner 配置</h3>
        <div class="form-group">
          <label>Claude Code 路径</label>
          <input v-model="config.claude_code.path" placeholder="claude (默认使用 PATH 中的)">
        </div>
        <div class="form-group">
          <label>模型</label>
          <select v-model="config.claude_code.model">
            <option v-for="m in models.filter(m => m.value.startsWith('claude'))" :key="m.value" :value="m.value">
              {{ m.label }}
            </option>
          </select>
        </div>
      </div>

      <!-- General Config -->
      <div class="settings-section">
        <h3>通用配置</h3>
        <div class="form-group">
          <label>默认 Runner</label>
          <select v-model="config.general.default_runner">
            <option value="cody">Cody</option>
            <option value="claude">Claude Code</option>
          </select>
        </div>
        <div class="form-group">
          <label>默认工作目录</label>
          <input v-model="config.general.workdir" placeholder=".">
          <span style="font-size:11px;color:var(--text2)">运行 Flow 时 AI 操作的项目目录路径</span>
        </div>
      </div>

      <div style="display:flex;gap:8px;justify-content:flex-end">
        <button class="btn btn-primary" @click="save">
          {{ saving ? '保存中...' : '保存配置' }}
        </button>
      </div>
    </div>
  `,
};
