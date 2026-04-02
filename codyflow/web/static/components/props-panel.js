/* ============================================================
   CodyFlow — Node Properties Panel (right sidebar)
   ============================================================ */

const PropsPanel = {
  props: ['node', 'selectedEdge', 'edges'],
  emits: ['update', 'rename', 'remove', 'updateEdge', 'removeEdge'],

  computed: {
    outputsStr() {
      return this.node ? this.node.outputs.join(', ') : '';
    },
    connectedEdges() {
      if (!this.node) return [];
      return this.edges.filter(
        e => e.from_node === this.node.id || e.to_node === this.node.id
      );
    },
    edgeIdx() {
      if (!this.selectedEdge) return -1;
      return this.edges.indexOf(this.selectedEdge);
    },
  },

  methods: {
    emitUpdate(prop, value) {
      this.$emit('update', this.node.id, prop, value);
    },
    updateOutputs(val) {
      const outputs = val.split(',').map(s => s.trim()).filter(Boolean);
      this.$emit('update', this.node.id, 'outputs', outputs);
    },
    handleRename(newId) {
      if (newId && newId !== this.node.id) {
        this.$emit('rename', this.node.id, newId);
      }
    },
  },

  template: `
    <div class="panel">

      <!-- Edge selected -->
      <template v-if="selectedEdge">
        <h3>连线属性</h3>
        <div class="form-group">
          <label>从</label>
          <div style="font-size:13px;color:var(--text);padding:4px 0">{{ selectedEdge.from_node }}</div>
        </div>
        <div class="form-group">
          <label>到</label>
          <div style="font-size:13px;color:var(--text);padding:4px 0">{{ selectedEdge.to_node }}</div>
        </div>
        <div class="form-group">
          <label>条件 (留空为无条件)</label>
          <input
            :value="selectedEdge.condition || ''"
            @input="$emit('updateEdge', edgeIdx, 'condition', $event.target.value)"
            placeholder="如: needs_fix / passed"
          >
          <span style="font-size:11px;color:var(--text2)">judge 节点路由时匹配此条件</span>
        </div>
        <div style="margin-top:20px">
          <button class="btn btn-danger btn-sm" @click="$emit('removeEdge', edgeIdx)">删除连线</button>
        </div>
      </template>

      <!-- Node selected or nothing -->
      <template v-else>
      <h3>节点属性</h3>

      <div v-if="!node" style="color:var(--text2);font-size:13px;margin-top:16px">
        点击节点或连线查看属性
      </div>

      <div v-else>
        <div class="form-group">
          <label>节点 ID</label>
          <input :value="node.id" @change="handleRename($event.target.value)">
        </div>

        <div class="form-group">
          <label>类型</label>
          <select :value="node.type" @change="emitUpdate('type', $event.target.value)">
            <option v-for="(label, type) in NODE_LABELS_OBJ" :key="type" :value="type">{{ label }}</option>
          </select>
        </div>

        <template v-if="node.type !== 'start' && node.type !== 'end'">
          <div class="form-group">
            <label>Prompt (留空使用默认)</label>
            <textarea rows="4" :value="node.prompt" @input="emitUpdate('prompt', $event.target.value)"></textarea>
          </div>

          <div class="form-group">
            <label>输出文件 (逗号分隔)</label>
            <input :value="outputsStr" @input="updateOutputs($event.target.value)">
          </div>

          <div class="form-group">
            <label>Runner</label>
            <select :value="node.runner || ''" @change="emitUpdate('runner', $event.target.value || null)">
              <option value="">全局默认</option>
              <option value="cody">Cody</option>
              <option value="claude">Claude</option>
            </select>
          </div>

          <div class="form-group">
            <label class="toggle">
              <input type="checkbox" :checked="node.interactive" @change="emitUpdate('interactive', $event.target.checked)">
              交互模式 (多轮对话)
            </label>
          </div>

          <div class="form-group">
            <label>错误策略</label>
            <select :value="node.error_strategy" @change="emitUpdate('error_strategy', $event.target.value)">
              <option value="retry">重试 (retry)</option>
              <option value="skip">跳过 (skip)</option>
              <option value="fail">失败停止 (fail)</option>
            </select>
          </div>

          <div class="form-group">
            <label>最大重试次数</label>
            <input type="number" :value="node.max_retries" min="0" max="10"
              @input="emitUpdate('max_retries', +$event.target.value)">
          </div>
        </template>
        <div v-else style="color:var(--text2);font-size:12px;margin-top:8px;padding:10px;background:var(--surface2);border-radius:6px">
          {{ node.type === 'start' ? '开始节点：流程入口，无需配置' : '结束节点：流程出口，无需配置' }}
        </div>

        <!-- Connected edges info -->
        <div v-if="connectedEdges.length" style="margin-top:12px">
          <label style="font-size:10px;color:var(--text2);text-transform:uppercase;letter-spacing:.5px">连线</label>
          <div v-for="e in connectedEdges" :key="e.from_node+e.to_node"
            style="font-size:11px;color:var(--text2);padding:3px 0">
            {{ e.from_node }} → {{ e.to_node }}
            <span v-if="e.condition" style="color:var(--yellow)">  [{{ e.condition }}]</span>
          </div>
        </div>

        <div style="margin-top:20px">
          <button class="btn btn-danger btn-sm" @click="$emit('remove', node.id)">删除节点</button>
        </div>
      </div>
      </template>
    </div>
  `,

  setup() {
    // Expose NODE_LABELS as object for template
    const NODE_LABELS_OBJ = { ...NODE_LABELS };
    return { NODE_LABELS_OBJ };
  },
};
