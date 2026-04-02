/* ============================================================
   CodyFlow — Node Palette (left sidebar)
   ============================================================ */

const NodePalette = {
  emits: ['addNode', 'loadFlow', 'newFlow', 'deleteFlow'],
  data() {
    return {
      nodeTypes: ['start', 'discuss', 'learn', 'code', 'reflect', 'judge', 'custom', 'end'],
      activeTab: 'nodes',  // nodes | flows
      NODE_COLORS,
      NODE_LABELS,
      NODE_DESCS,
      store,
      flows: [],
      loadingFlows: false,
    };
  },

  methods: {
    dragStart(e, type) {
      e.dataTransfer.setData('nodeType', type);
    },

    async switchToFlows() {
      this.activeTab = 'flows';
      await this.refreshFlows();
    },

    async refreshFlows() {
      this.loadingFlows = true;
      try {
        const data = await API.listFlows();
        this.flows = data.flows || [];
      } catch (e) {
        console.error('loadFlows failed', e);
      } finally {
        this.loadingFlows = false;
      }
    },

    formatTime(ts) {
      if (!ts) return '';
      const d = new Date(ts * 1000);
      return d.toLocaleDateString() + ' ' + d.toLocaleTimeString([], { hour: '2-digit', minute: '2-digit' });
    },
  },

  template: `
    <div class="sidebar">
      <!-- Tab switcher -->
      <div class="sidebar-tabs">
        <button :class="{active: activeTab==='nodes'}" @click="activeTab='nodes'">节点</button>
        <button :class="{active: activeTab==='flows'}" @click="switchToFlows()">Flow</button>
      </div>

      <!-- Nodes Tab -->
      <div v-show="activeTab==='nodes'">
        <h3>节点类型</h3>
        <div class="node-palette">
          <div
            v-for="type in nodeTypes" :key="type"
            class="palette-item"
            draggable="true"
            @dragstart="dragStart($event, type)"
            @dblclick="$emit('addNode', type)"
          >
            <div class="dot" :style="{background: NODE_COLORS[type]}"></div>
            <div>
              <div class="label">{{ NODE_LABELS[type] }}</div>
              <div class="desc">{{ NODE_DESCS[type] }}</div>
            </div>
          </div>
        </div>

        <h3>Flow 配置</h3>
        <div style="padding-bottom:16px">
          <div class="form-group">
            <label>名称</label>
            <input v-model="store.flow.name">
          </div>
          <div class="form-group">
            <label>描述</label>
            <input v-model="store.flow.description" placeholder="Flow 目标描述">
          </div>
          <div class="form-group">
            <label>默认 Runner</label>
            <select v-model="store.flow.runner">
              <option value="cody">Cody</option>
              <option value="claude">Claude</option>
            </select>
          </div>
          <div class="form-group">
            <label>最大迭代</label>
            <input type="number" v-model.number="store.flow.max_iterations" min="1" max="20">
          </div>
        </div>
      </div>

      <!-- Flows Tab -->
      <div v-show="activeTab==='flows'" style="display:flex;flex-direction:column;height:100%">
        <div style="display:flex;align-items:center;justify-content:space-between;margin-bottom:10px">
          <h3 style="margin:0">已保存的 Flow</h3>
          <div style="display:flex;gap:4px">
            <button class="btn btn-outline btn-sm" @click="refreshFlows" title="刷新">↺</button>
            <button class="btn btn-primary btn-sm" @click="$emit('newFlow')">+ 新建</button>
          </div>
        </div>

        <div v-if="loadingFlows" style="color:var(--text2);font-size:12px;padding:8px 0">加载中...</div>
        <div v-else-if="flows.length === 0" style="color:var(--text2);font-size:12px;padding:12px 0;text-align:center;line-height:1.8">
          还没有保存的 Flow<br>
          <span style="font-size:11px">在"节点"tab 设计后点保存</span>
        </div>
        <div v-else class="flow-sidebar-list">
          <div
            v-for="f in flows" :key="f.id"
            class="flow-sidebar-item"
            :class="{active: store.currentFlowId === f.id}"
            @click="$emit('loadFlow', f.id)"
          >
            <div class="flow-sidebar-name">{{ f.name || '未命名' }}</div>
            <div class="flow-sidebar-meta">
              {{ f.node_count }} 个节点
              <span v-if="f.description" style="margin-left:4px;color:var(--text2)">· {{ f.description.slice(0, 20) }}{{ f.description.length > 20 ? '…' : '' }}</span>
            </div>
            <div class="flow-sidebar-time">{{ formatTime(f.updated_at) }}</div>
            <button
              class="btn btn-danger btn-sm flow-sidebar-del"
              @click.stop="$emit('deleteFlow', f.id, () => refreshFlows())"
              title="删除"
            >✕</button>
          </div>
        </div>
      </div>

    </div>
  `,
};
