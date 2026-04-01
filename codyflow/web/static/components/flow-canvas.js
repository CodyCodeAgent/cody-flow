/* ============================================================
   CodyFlow — Flow Canvas Component
   ============================================================ */

const FlowCanvas = {
  props: ['nodes', 'edges', 'selectedNode', 'runStatus'],
  emits: ['selectNode', 'updateNodePos', 'addEdge', 'removeEdge', 'editEdge', 'dropNode'],

  data() {
    return {
      dragging: null,     // { id, offsetX, offsetY }
      connecting: null,   // { fromId }
      connectLine: null,  // { x1, y1, x2, y2 }
    };
  },

  computed: {
    edgePaths() {
      return this.edges.map((edge, idx) => {
        const fromNode = this.nodes.find(n => n.id === edge.from_node);
        const toNode = this.nodes.find(n => n.id === edge.to_node);
        if (!fromNode || !toNode) return null;

        const x1 = fromNode.x + 75;
        const y1 = fromNode.y + 68;
        const x2 = toNode.x + 75;
        const y2 = toNode.y;
        const midY = (y1 + y2) / 2;

        return {
          idx,
          d: `M ${x1} ${y1} C ${x1} ${midY}, ${x2} ${midY}, ${x2} ${y2}`,
          color: edge.condition ? 'var(--yellow)' : '#3a3a5e',
          dashed: !!edge.condition,
          condition: edge.condition,
          labelX: (x1 + x2) / 2 - 25,
          labelY: midY - 8,
          arrowPoints: `${x2},${y2} ${x2-5},${y2-8} ${x2+5},${y2-8}`,
        };
      }).filter(Boolean);
    },
  },

  methods: {
    getNodeColor(type) { return NODE_COLORS[type] || 'var(--node-custom)'; },
    getNodeLabel(type) { return NODE_LABELS[type] || type; },

    nodeClass(node) {
      const classes = ['flow-node'];
      if (this.selectedNode === node.id) classes.push('active');
      // Run status classes are managed externally
      return classes.join(' ');
    },

    onNodeMouseDown(e, node) {
      if (e.target.classList.contains('port')) return;
      this.$emit('selectNode', node.id);
      this.dragging = {
        id: node.id,
        offsetX: e.clientX - node.x,
        offsetY: e.clientY - node.y,
      };
      e.stopPropagation();
    },

    onMouseMove(e) {
      if (this.dragging) {
        const rect = this.$refs.canvasEl.getBoundingClientRect();
        const x = e.clientX - this.dragging.offsetX;
        const y = e.clientY - this.dragging.offsetY;
        this.$emit('updateNodePos', this.dragging.id, x, y);
      }
      if (this.connecting) {
        const rect = this.$refs.canvasEl.getBoundingClientRect();
        this.connectLine = {
          ...this.connectLine,
          x2: e.clientX - rect.left,
          y2: e.clientY - rect.top,
        };
      }
    },

    onMouseUp() {
      this.dragging = null;
      this.connecting = null;
      this.connectLine = null;
    },

    onCanvasClick(e) {
      if (e.target === this.$refs.canvasEl || e.target.closest('.grid-bg')) {
        this.$emit('selectNode', null);
      }
    },

    startConnect(e, fromId) {
      e.stopPropagation();
      e.preventDefault();
      const node = this.nodes.find(n => n.id === fromId);
      if (!node) return;
      this.connecting = { fromId };
      this.connectLine = {
        x1: node.x + 75, y1: node.y + 68,
        x2: node.x + 75, y2: node.y + 68,
      };
    },

    endConnect(toId) {
      if (!this.connecting || this.connecting.fromId === toId) return;
      this.$emit('addEdge', this.connecting.fromId, toId);
      this.connecting = null;
      this.connectLine = null;
    },

    onEdgeClick(idx) {
      this.$emit('editEdge', idx);
    },

    onEdgeDblClick(idx) {
      this.$emit('removeEdge', idx);
    },

    onDrop(e) {
      e.preventDefault();
      const type = e.dataTransfer.getData('nodeType');
      if (!type) return;
      const rect = this.$refs.canvasEl.getBoundingClientRect();
      const x = e.clientX - rect.left - 75;
      const y = e.clientY - rect.top - 30;
      this.$emit('dropNode', type, x, y);
    },
  },

  template: `
    <div
      class="canvas-wrap"
      @dragover.prevent
      @drop="onDrop"
      @mousemove="onMouseMove"
      @mouseup="onMouseUp"
    >
      <div class="grid-bg"></div>
      <div class="canvas" ref="canvasEl" @mousedown="onCanvasClick">
        <svg>
          <!-- Edges -->
          <g v-for="ep in edgePaths" :key="'e'+ep.idx">
            <path
              :d="ep.d" :stroke="ep.color" stroke-width="2" fill="none"
              :stroke-dasharray="ep.dashed ? '6 3' : 'none'"
              style="pointer-events:stroke;cursor:pointer"
              @click.stop="onEdgeClick(ep.idx)"
              @dblclick.stop="onEdgeDblClick(ep.idx)"
            />
            <polygon :points="ep.arrowPoints" :fill="ep.color"/>
            <foreignObject
              v-if="ep.condition"
              :x="ep.labelX" :y="ep.labelY" width="60" height="18"
            >
              <div xmlns="http://www.w3.org/1999/xhtml"
                style="background:var(--surface2);border:1px solid var(--border);border-radius:3px;padding:1px 5px;font-size:9px;color:var(--yellow);text-align:center;white-space:nowrap"
              >{{ ep.condition }}</div>
            </foreignObject>
          </g>

          <!-- Connecting line (while dragging) -->
          <path v-if="connectLine"
            :d="'M '+connectLine.x1+' '+connectLine.y1+' L '+connectLine.x2+' '+connectLine.y2"
            stroke="var(--accent)" stroke-width="2" fill="none" stroke-dasharray="4 4"
          />
        </svg>

        <!-- Nodes -->
        <div
          v-for="node in nodes" :key="node.id"
          :class="nodeClass(node)"
          :id="'node-'+node.id"
          :style="{left: node.x+'px', top: node.y+'px'}"
          @mousedown="onNodeMouseDown($event, node)"
        >
          <div class="port port-in" @mouseup="endConnect(node.id)"></div>
          <div class="flow-node-header"
            :style="{background: getNodeColor(node.type)+'22', color: getNodeColor(node.type)}"
          >
            <span :style="{width:'8px',height:'8px',borderRadius:'50%',background:getNodeColor(node.type)}"></span>
            {{ getNodeLabel(node.type) }}
          </div>
          <div class="flow-node-body">
            <div class="node-id">{{ node.id }}</div>
          </div>
          <div class="port port-out" @mousedown="startConnect($event, node.id)"></div>
        </div>
      </div>

      <!-- Empty state -->
      <div class="empty-state" v-show="nodes.length === 0">
        <div class="icon">⬡</div>
        <p>从左侧拖拽节点到画布，或双击添加</p>
      </div>

      <!-- Status bar -->
      <div class="status-bar">
        <div class="status-dot" :class="runStatus"></div>
        <span>{{ {idle:'就绪',running:'运行中',completed:'完成',failed:'失败'}[runStatus] || '就绪' }}</span>
        <span style="margin-left:auto">{{ nodes.length }} 个节点 · {{ edges.length }} 条连线</span>
      </div>
    </div>
  `,
};
