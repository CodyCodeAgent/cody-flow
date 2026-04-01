/* ============================================================
   CodyFlow — Node Palette (left sidebar)
   ============================================================ */

const NodePalette = {
  emits: ['addNode', 'loadContextFile'],
  data() {
    return {
      nodeTypes: ['discuss', 'learn', 'code', 'reflect', 'judge', 'custom'],
      activeTab: 'nodes', // nodes | context | log
    };
  },
  methods: {
    dragStart(e, type) {
      e.dataTransfer.setData('nodeType', type);
    },
    formatSize(bytes) {
      if (bytes < 1024) return bytes + ' B';
      if (bytes < 1024 * 1024) return (bytes / 1024).toFixed(1) + ' KB';
      return (bytes / (1024 * 1024)).toFixed(1) + ' MB';
    },
    formatTime(ts) {
      if (!ts) return '';
      return new Date(ts * 1000).toLocaleTimeString();
    },
  },
  template: `
    <div class="sidebar">
      <!-- Tab switcher -->
      <div class="sidebar-tabs">
        <button :class="{active: activeTab==='nodes'}" @click="activeTab='nodes'">节点</button>
        <button :class="{active: activeTab==='context'}" @click="activeTab='context'">上下文</button>
        <button :class="{active: activeTab==='log'}" @click="activeTab='log'">日志</button>
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
        <div style="margin-bottom:16px;padding-bottom:16px;border-bottom:1px solid var(--border)">
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

      <!-- Context Files Tab -->
      <div v-show="activeTab==='context'">
        <h3>上下文文件</h3>
        <p v-if="store.contextFiles.length === 0" style="font-size:11px;color:var(--text2);padding:8px 0">
          运行 Flow 后，节点产出的上下文文件会显示在这里。
        </p>
        <div class="context-list">
          <div
            v-for="f in store.contextFiles" :key="f.name"
            class="context-item"
            :class="{active: store.selectedContextFile === f.name}"
            @click="$emit('loadContextFile', f.name)"
          >
            <div class="context-name">{{ f.name }}</div>
            <div class="context-meta">{{ formatSize(f.size) }} · {{ formatTime(f.modified) }}</div>
          </div>
        </div>
        <div v-if="store.contextFileContent" class="context-preview">
          <h4>{{ store.selectedContextFile }}</h4>
          <pre>{{ store.contextFileContent }}</pre>
        </div>
      </div>

      <!-- Log Tab -->
      <div v-show="activeTab==='log'">
        <h3>执行日志</h3>
        <div class="events-log" ref="log">
          <div v-if="store.runEvents.length === 0" class="event">等待执行...</div>
          <div
            v-for="(ev, i) in store.runEvents" :key="i"
            class="event"
            :class="{start: ev.type==='node_start', complete: ev.type==='node_complete', error: ev.type==='error', route: ev.type==='route'}"
          >
            <span class="event-time" v-if="ev.time">{{ ev.time }}</span>
            {{ ev.text }}
            <div v-if="ev.detail" class="event-detail">{{ ev.detail }}</div>
          </div>
        </div>
      </div>
    </div>
  `,
};
