/* ============================================================
   CodyFlow — Task Detail Page
   ============================================================ */

const TaskDetail = {
  emits: ['back', 'sendInteractive'],
  data() {
    return { store };
  },

  computed: {
    task() { return store.currentTaskInfo; },
    ts() { return store.taskState; },
    isRunning() { return store.taskState.status === 'running'; },
    nodeColors() { return NODE_COLORS; },
    nodeLabels() { return NODE_LABELS; },
  },

  methods: {
    statusLabel(status) {
      return { running: '运行中', completed: '已完成', failed: '失败', stopped: '已停止', idle: '就绪' }[status] || status;
    },
    statusDotClass(status) {
      return { running: 'running', completed: '', failed: 'error', stopped: 'error' }[status] || 'idle';
    },
    formatTime(ts) {
      if (!ts) return '';
      return new Date(ts * 1000).toLocaleString();
    },
    nodeStateClass(nodeId) {
      if (store.taskState.runningNodes.includes(nodeId)) return 'task-node-running';
      if (store.taskState.completedNodes.includes(nodeId)) return 'task-node-done';
      return '';
    },
    async stop() {
      try {
        await API.stopTask(store.currentTaskId);
      } catch (e) { alert('停止失败: ' + e.message); }
    },
  },

  template: `
    <div class="task-detail-page">
      <!-- Top bar -->
      <div class="task-detail-topbar">
        <button class="btn btn-outline btn-sm" @click="$emit('back')">← 返回</button>
        <div class="task-detail-title">
          <span>{{ task ? task.flow_name : '' }}</span>
          <span class="task-detail-workdir" :title="task ? task.workdir : ''">{{ task ? task.workdir : '' }}</span>
        </div>
        <div style="display:flex;align-items:center;gap:10px">
          <div class="status-dot" :class="statusDotClass(ts.status)"></div>
          <span style="font-size:12px;color:var(--text2)">{{ statusLabel(ts.status) }}</span>
          <button v-if="isRunning" class="btn btn-danger btn-sm" @click="stop">停止</button>
        </div>
      </div>

      <!-- Main area: flow nodes + bottom panel -->
      <div class="task-detail-body">

        <!-- Flow node status list -->
        <div class="task-node-list" v-if="task && task.flow_snapshot">
          <div style="font-size:11px;text-transform:uppercase;color:var(--text2);margin-bottom:10px;letter-spacing:1px">流程节点</div>
          <div
            v-for="node in task.flow_snapshot.nodes" :key="node.id"
            class="task-node-item"
            :class="nodeStateClass(node.id)"
          >
            <span class="task-node-dot" :style="{background: nodeColors[node.type] || 'var(--node-custom)'}"></span>
            <span class="task-node-label">{{ nodeLabels[node.type] || node.type }}</span>
            <span class="task-node-id">{{ node.id }}</span>
            <span v-if="ts.runningNodes.includes(node.id)" class="task-node-badge running">运行中</span>
            <span v-else-if="ts.completedNodes.includes(node.id)" class="task-node-badge done">✓</span>
          </div>

          <div v-if="task.user_input" class="task-user-input-box">
            <div style="font-size:10px;color:var(--text2);margin-bottom:4px;text-transform:uppercase;letter-spacing:.5px">任务需求</div>
            <div style="font-size:12px;color:var(--text);line-height:1.5;white-space:pre-wrap">{{ task.user_input }}</div>
          </div>
        </div>

        <!-- Bottom panel takes the rest -->
        <div class="task-detail-main">
          <bottom-panel></bottom-panel>
        </div>
      </div>
    </div>
  `,
};
