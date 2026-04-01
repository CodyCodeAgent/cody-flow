/* ============================================================
   CodyFlow — Node Properties Panel (right sidebar)
   ============================================================ */

const PropsPanel = {
  props: ['node', 'edges'],
  emits: ['update', 'rename', 'remove'],

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
      <h3>节点属性</h3>

      <div v-if="!node" style="color:var(--text2);font-size:13px;margin-top:16px">
        点击画布上的节点查看属性
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
    </div>
  `,

  setup() {
    // Expose NODE_LABELS as object for template
    const NODE_LABELS_OBJ = { ...NODE_LABELS };
    return { NODE_LABELS_OBJ };
  },
};
