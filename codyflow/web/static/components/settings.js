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

      <!-- Environment Check: core deps only -->
      <div class="settings-section">
        <h3>环境检测</h3>
        <p style="font-size:13px;color:var(--text2);margin-bottom:12px">
          检查运行 CodyFlow 所需的核心依赖是否就绪。
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
          <input v-model="config.cody.model" placeholder="claude-sonnet-4-6">
        </div>
        <div class="form-group">
          <label>Base URL（可选，用于自定义 API 端点）</label>
          <input v-model="config.cody.base_url" placeholder="https://api.anthropic.com">
        </div>
      </div>

      <!-- Claude Code Runner Config -->
      <div class="settings-section">
        <h3>Claude Code Runner 配置</h3>

        <!-- Not installed: show install guide -->
        <div v-if="!envStatus.claude_code || !envStatus.claude_code.ok"
          style="background:var(--surface2);border:1px solid var(--border);border-radius:8px;padding:14px 16px;margin-bottom:12px">
          <div style="font-size:13px;color:var(--text2);margin-bottom:10px">
            使用 Claude Code Runner 需要先安装 SDK：
          </div>
          <code style="display:block;background:var(--bg);border-radius:4px;padding:8px 12px;font-size:12px;color:var(--accent);margin-bottom:10px;user-select:all">
            pip install codyflow[claude]
          </code>
          <button class="btn btn-outline btn-sm" @click="checkEnv" :disabled="checking">
            {{ checking ? '检测中...' : '安装后点此检测' }}
          </button>
        </div>

        <!-- Installed: show config -->
        <template v-else>
          <div style="font-size:12px;color:var(--text2);margin-bottom:12px">
            {{ envStatus.claude_code.detail }}
          </div>
          <div class="form-group">
            <label>Claude Code 路径</label>
            <input v-model="config.claude_code.path" placeholder="claude（默认使用 PATH 中的）">
          </div>
          <div class="form-group">
            <label>模型</label>
            <input v-model="config.claude_code.model" placeholder="claude-sonnet-4-6">
          </div>
        </template>
      </div>

      <div style="display:flex;gap:8px;justify-content:flex-end">
        <button class="btn btn-primary" @click="save">
          {{ saving ? '保存中...' : '保存配置' }}
        </button>
      </div>
    </div>
  `,
};
