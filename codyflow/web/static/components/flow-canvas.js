/* ============================================================
   CodyFlow — Flow Canvas Component (with zoom/pan + node state)
   ============================================================ */

const FlowCanvas = {
  props: ['nodes', 'edges', 'selectedNode', 'runStatus', 'runningNodes', 'completedNodes', 'scale', 'offsetX', 'offsetY'],
  emits: ['selectNode', 'updateNodePos', 'addEdge', 'removeEdge', 'editEdge', 'dropNode', 'updateTransform'],

  data() {
    return {
      dragging: null,     // { id, offsetX, offsetY }
      connecting: null,   // { fromId }
      connectLine: null,  // { x1, y1, x2, y2 }
      panning: false,
      panStart: null,
    };
  },

  computed: {
    canvasTransform() {
      const s = this.scale || 1;
      const ox = this.offsetX || 0;
      const oy = this.offsetY || 0;
      return `translate(${ox}px, ${oy}px) scale(${s})`;
    },

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
      if (this.runningNodes && this.runningNodes.includes(node.id)) classes.push('running');
      if (this.completedNodes && this.completedNodes.includes(node.id)) classes.push('completed');
      return classes.join(' ');
    },

    onNodeMouseDown(e, node) {
      if (e.target.classList.contains('port')) return;
      this.$emit('selectNode', node.id);
      const s = this.scale || 1;
      this.dragging = {
        id: node.id,
        offsetX: e.clientX / s - node.x,
        offsetY: e.clientY / s - node.y,
      };
      e.stopPropagation();
    },

    onMouseMove(e) {
      if (this.dragging) {
        const s = this.scale || 1;
        const x = e.clientX / s - this.dragging.offsetX;
        const y = e.clientY / s - this.dragging.offsetY;
        this.$emit('updateNodePos', this.dragging.id, x, y);
      }
      if (this.connecting) {
        const rect = this.$refs.canvasEl.getBoundingClientRect();
        const s = this.scale || 1;
        this.connectLine = {
          ...this.connectLine,
          x2: (e.clientX - rect.left - (this.offsetX || 0)) / s,
          y2: (e.clientY - rect.top - (this.offsetY || 0)) / s,
        };
      }
      if (this.panning && this.panStart) {
        const dx = e.clientX - this.panStart.x;
        const dy = e.clientY - this.panStart.y;
        this.$emit('updateTransform', {
          offsetX: this.panStart.ox + dx,
          offsetY: this.panStart.oy + dy,
        });
      }
    },

    onMouseUp() {
      this.dragging = null;
      this.connecting = null;
      this.connectLine = null;
      this.panning = false;
      this.panStart = null;
    },

    onCanvasClick(e) {
      if (e.target === this.$refs.canvasEl || e.target.closest('.grid-bg')) {
        this.$emit('selectNode', null);
      }
    },

    onCanvasMouseDown(e) {
      // Middle mouse button or ctrl+left for pan
      if (e.button === 1 || (e.button === 0 && e.ctrlKey)) {
        e.preventDefault();
        this.panning = true;
        this.panStart = {
          x: e.clientX,
          y: e.clientY,
          ox: this.offsetX || 0,
          oy: this.offsetY || 0,
        };
      }
    },

    onWheel(e) {
      e.preventDefault();
      const delta = e.deltaY > 0 ? -0.1 : 0.1;
      const newScale = Math.max(0.3, Math.min(2, (this.scale || 1) + delta));
      this.$emit('updateTransform', { scale: newScale });
    },

    resetZoom() {
      this.$emit('updateTransform', { scale: 1, offsetX: 0, offsetY: 0 });
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
      const s = this.scale || 1;
      const x = (e.clientX - rect.left - (this.offsetX || 0)) / s - 75;
      const y = (e.clientY - rect.top - (this.offsetY || 0)) / s - 30;
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
      @mousedown="onCanvasMouseDown"
      @wheel.prevent="onWheel"
    >
      <div class="grid-bg"></div>
      <div class="canvas" ref="canvasEl" :style="{transform: canvasTransform, transformOrigin: '0 0'}" @mousedown="onCanvasClick">
        <svg :style="{transform: canvasTransform, transformOrigin: '0 0'}">
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
        <div class="icon">&#x2B21;</div>
        <p>从左侧拖拽节点到画布，或双击添加</p>
      </div>

      <!-- Zoom controls -->
      <div class="zoom-controls">
        <button class="btn btn-outline btn-sm" @click="$emit('updateTransform', {scale: Math.min(2, (scale||1)+0.1)})">+</button>
        <span class="zoom-label">{{ Math.round((scale||1)*100) }}%</span>
        <button class="btn btn-outline btn-sm" @click="$emit('updateTransform', {scale: Math.max(0.3, (scale||1)-0.1)})">-</button>
        <button class="btn btn-outline btn-sm" @click="resetZoom" title="重置">R</button>
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
