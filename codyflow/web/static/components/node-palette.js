/* ============================================================
   CodyFlow — Node Palette (left sidebar)
   ============================================================ */

const NodePalette = {
  emits: ['addNode'],
  data() {
    return {
      nodeTypes: ['discuss', 'learn', 'code', 'reflect', 'judge', 'custom'],
    };
  },
  methods: {
    dragStart(e, type) {
      e.dataTransfer.setData('nodeType', type);
    },
  },
  template: `
    <div class="sidebar">
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

      <h3>执行日志</h3>
      <div class="events-log" ref="log">
        <div v-if="store.runEvents.length === 0" class="event">等待执行...</div>
        <div
          v-for="(ev, i) in store.runEvents" :key="i"
          class="event"
          :class="{start: ev.type==='node_start', complete: ev.type==='node_complete', error: ev.type==='error'}"
        >{{ ev.text }}</div>
      </div>
    </div>
  `,
};
