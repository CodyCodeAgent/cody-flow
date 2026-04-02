/* ============================================================
   CodyFlow — Task List Page
   ============================================================ */

const TaskList = {
  emits: ['openTask'],
  data() {
    return {
      store,
      // New task dialog
      showNewTask: false,
      newTaskSelection: null,  // { type: 'flow'|'template', id, name, description, node_count }
      newTaskWorkdir: '',
      newTaskInput: '',
      creating: false,
      // Flows / templates for selection
      savedFlows: [],
      templates: [],
      loadingFlows: false,
    };
  },

  mounted() {
    this.refresh();
  },

  methods: {
    async refresh() {
      try {
        const data = await API.listTasks();
        store.taskList = data.tasks;
      } catch (e) {
        console.error('listTasks failed', e);
      }
    },

    async openNewTaskDialog() {
      this.showNewTask = true;
      this.newTaskSelection = null;
      this.newTaskWorkdir = '';
      this.newTaskInput = '';
      this.loadingFlows = true;
      try {
        const [flowsData, tplData] = await Promise.all([API.listFlows(), API.listTemplates()]);
        this.savedFlows = (flowsData.flows || []).map(f => ({
          type: 'flow', id: f.id,
          name: f.name || '未命名', description: f.description || '',
          node_count: f.node_count,
        }));
        this.templates = (tplData.templates || []).map(t => ({
          type: 'template', id: t.filename,
          name: t.name, description: t.description || '',
          node_count: t.node_count,
        }));
      } finally {
        this.loadingFlows = false;
      }
    },

    async createTask() {
      if (!this.newTaskSelection) { alert('请选择一个 Flow 或模板'); return; }
      if (!this.newTaskWorkdir.trim()) { alert('请填写工作目录'); return; }
      this.creating = true;
      try {
        let flow, flowId;
        const sel = this.newTaskSelection;
        if (sel.type === 'flow') {
          const flowData = await API.getFlow(sel.id);
          const def = flowData.definition;
          flow = {
            name: def.name || flowData.name,
            description: def.description || '',
            runner: def.runner || 'cody',
            max_iterations: def.max_iterations || 3,
            nodes: def.nodes || [],
            edges: def.edges || [],
          };
          flowId = sel.id;
        } else {
          // Template
          const tpl = await API.getTemplate(sel.id);
          flow = {
            name: tpl.name, description: tpl.description || '',
            runner: tpl.runner || 'cody',
            max_iterations: tpl.max_iterations || 3,
            nodes: tpl.nodes || [],
            edges: tpl.edges || [],
          };
          flowId = null;
        }
        const result = await API.createTask(flow, flowId, this.newTaskWorkdir, this.newTaskInput);
        this.showNewTask = false;
        await this.refresh();
        this.$emit('openTask', result.task_id);
      } catch (e) {
        alert('创建失败: ' + e.message);
      } finally {
        this.creating = false;
      }
    },

    async deleteTask(taskId) {
      if (!confirm('确定删除此任务记录？')) return;
      try {
        await API.deleteTask(taskId);
        store.taskList = store.taskList.filter(t => t.id !== taskId);
      } catch (e) {
        alert('删除失败: ' + e.message);
      }
    },

    statusLabel(status) {
      return { running: '运行中', completed: '已完成', failed: '失败', stopped: '已停止' }[status] || status;
    },
    statusClass(status) {
      return { running: 'task-status-running', completed: 'task-status-done', failed: 'task-status-failed', stopped: 'task-status-stopped' }[status] || '';
    },
    formatTime(ts) {
      if (!ts) return '';
      return new Date(ts * 1000).toLocaleString();
    },
    elapsed(t) {
      if (!t.created_at) return '';
      const sec = Math.round((t.updated_at || Date.now() / 1000) - t.created_at);
      if (sec < 60) return sec + 's';
      return Math.floor(sec / 60) + 'm ' + (sec % 60) + 's';
    },
  },

  template: `
    <div class="task-list-page">
      <div class="task-list-header">
        <h2>任务</h2>
        <div style="display:flex;gap:8px">
          <button class="btn btn-outline btn-sm" @click="refresh">刷新</button>
          <button class="btn btn-primary btn-sm" @click="openNewTaskDialog">+ 新建任务</button>
        </div>
      </div>

      <!-- Empty state -->
      <div v-if="store.taskList.length === 0" class="task-empty">
        <div style="font-size:40px;margin-bottom:12px;opacity:.3">📋</div>
        <div>还没有任务</div>
        <div style="font-size:12px;color:var(--text2);margin-top:6px">新建任务来运行一个 Flow</div>
      </div>

      <!-- Task cards -->
      <div class="task-cards" v-else>
        <div
          v-for="task in store.taskList" :key="task.id"
          class="task-card"
          @click="$emit('openTask', task.id)"
        >
          <div class="task-card-top">
            <div class="task-card-name">{{ task.flow_name || '未命名' }}</div>
            <span class="task-status-badge" :class="statusClass(task.status)">
              <span v-if="task.status === 'running'" class="bp-dot-pulse" style="margin-right:4px"></span>
              {{ statusLabel(task.status) }}
            </span>
          </div>
          <div class="task-card-workdir" :title="task.workdir">{{ task.workdir }}</div>
          <div v-if="task.user_input" class="task-card-input">{{ task.user_input.slice(0, 80) }}{{ task.user_input.length > 80 ? '...' : '' }}</div>
          <div class="task-card-meta">
            <span>{{ formatTime(task.created_at) }}</span>
            <span style="margin-left:auto">{{ elapsed(task) }}</span>
            <button class="btn btn-danger btn-sm" style="margin-left:8px;padding:2px 7px" @click.stop="deleteTask(task.id)">删除</button>
          </div>
        </div>
      </div>

      <!-- New Task Dialog -->
      <div class="modal-overlay" v-if="showNewTask" @click.self="showNewTask=false">
        <div class="modal" style="width:560px">
          <h3>新建任务</h3>

          <div class="form-group">
            <label>选择 Flow</label>
            <div v-if="loadingFlows" style="color:var(--text2);font-size:12px">加载中...</div>
            <div v-else class="flow-select-list">
              <!-- Saved flows -->
              <div v-if="savedFlows.length > 0">
                <div class="flow-select-section-label">已保存的 Flow</div>
                <div
                  v-for="f in savedFlows" :key="'flow-'+f.id"
                  class="flow-select-item"
                  :class="{selected: newTaskSelection && newTaskSelection.type==='flow' && newTaskSelection.id===f.id}"
                  @click="newTaskSelection = f"
                >
                  <div class="flow-select-name">{{ f.name }}</div>
                  <div class="flow-select-meta">{{ f.node_count }} 个节点 · {{ f.description || '无描述' }}</div>
                </div>
              </div>
              <!-- Templates -->
              <div v-if="templates.length > 0">
                <div class="flow-select-section-label">内置模板</div>
                <div
                  v-for="t in templates" :key="'tpl-'+t.id"
                  class="flow-select-item"
                  :class="{selected: newTaskSelection && newTaskSelection.type==='template' && newTaskSelection.id===t.id}"
                  @click="newTaskSelection = t"
                >
                  <div class="flow-select-name">{{ t.name }}</div>
                  <div class="flow-select-meta">{{ t.node_count }} 个节点 · {{ t.description || '无描述' }}</div>
                </div>
              </div>
              <div v-if="savedFlows.length === 0 && templates.length === 0" style="color:var(--text2);font-size:12px;padding:8px 0">
                暂无可用 Flow
              </div>
            </div>
          </div>

          <div class="form-group">
            <label>工作目录</label>
            <input v-model="newTaskWorkdir" placeholder="/path/to/your/project">
            <span style="font-size:11px;color:var(--text2)">AI 将在此目录读写代码</span>
          </div>

          <div class="form-group">
            <label>任务需求描述</label>
            <textarea rows="4" v-model="newTaskInput" placeholder="描述你希望 AI 完成的任务...&#10;&#10;例如：实现用户登录功能，包含邮箱验证和 JWT token"></textarea>
          </div>

          <div style="display:flex;gap:8px;justify-content:flex-end;margin-top:16px">
            <button class="btn btn-outline btn-sm" @click="showNewTask=false">取消</button>
            <button class="btn btn-primary btn-sm" @click="createTask" :disabled="creating || !newTaskSelection">
              {{ creating ? '创建中...' : '开始运行' }}
            </button>
          </div>
        </div>
      </div>
    </div>
  `,
};
