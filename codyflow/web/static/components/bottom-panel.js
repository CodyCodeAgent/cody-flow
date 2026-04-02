/* ============================================================
   CodyFlow — Bottom Panel (output / log / chat)
   ============================================================ */

const BottomPanel = {
  data() {
    return {
      store,
      resizing: false,
      resizeStartY: 0,
      resizeStartH: 0,
    };
  },

  mounted() {
    document.addEventListener('mousemove', this.onResizeMove);
    document.addEventListener('mouseup', this.onResizeEnd);
  },

  beforeUnmount() {
    document.removeEventListener('mousemove', this.onResizeMove);
    document.removeEventListener('mouseup', this.onResizeEnd);
  },

  methods: {
    onResizeStart(e) {
      this.resizing = true;
      this.resizeStartY = e.clientY;
      this.resizeStartH = store.bottomPanelHeight;
      e.preventDefault();
    },
    onResizeMove(e) {
      if (!this.resizing) return;
      const delta = this.resizeStartY - e.clientY;
      store.bottomPanelHeight = Math.max(80, Math.min(600, this.resizeStartH + delta));
    },
    onResizeEnd() {
      this.resizing = false;
    },

    toggle() {
      store.bottomPanelOpen = !store.bottomPanelOpen;
    },

    switchTab(tab) {
      store.bottomPanelTab = tab;
      store.bottomPanelOpen = true;
    },

    outputLineStyle(line) {
      if (line.type === 'tool_call') return 'color:var(--cyan)';
      if (line.type === 'tool_result') return 'color:var(--text2)';
      if (line.type === 'thinking') return 'color:var(--node-discuss);font-style:italic';
      if (line.type === 'node_start') return 'color:var(--yellow);font-weight:600';
      if (line.type === 'node_done') return 'color:var(--green)';
      return 'color:var(--text)';
    },

    formatOutputLine(line) {
      if (line.type === 'node_start') return `▶ ${line.nodeId} (${line.nodeType})`;
      if (line.type === 'node_done') return `✓ ${line.nodeId} 完成 (${line.duration}s)`;
      if (line.type === 'tool_call') {
        const args = line.args ? JSON.stringify(line.args).slice(0, 80) : '';
        return `🔧 ${line.tool}  ${args}`;
      }
      if (line.type === 'tool_result') return `   └ ${(line.content || '').slice(0, 120)}`;
      if (line.type === 'thinking') return `💭 ${line.content}`;
      return line.content || '';
    },
  },

  watch: {
    'store.taskState.outputLines'() {
      this.$nextTick(() => {
        const el = this.$refs.outputLog;
        if (el) el.scrollTop = el.scrollHeight;
      });
    },
    'store.taskState.runEvents'() {
      this.$nextTick(() => {
        const el = this.$refs.eventLog;
        if (el) el.scrollTop = el.scrollHeight;
      });
    },
    'store.taskState.interactiveOutput'() {
      this.$nextTick(() => {
        const el = this.$refs.chatOutput;
        if (el) el.scrollTop = el.scrollHeight;
      });
    },
    'store.taskState.interactiveWaiting'(val) {
      if (val) {
        store.bottomPanelTab = 'chat';
        store.bottomPanelOpen = true;
      }
    },
  },

  template: `
    <div class="bottom-panel" :style="{height: store.bottomPanelOpen ? store.bottomPanelHeight + 'px' : '32px'}">

      <!-- Resize handle -->
      <div class="bp-resize-handle" @mousedown="onResizeStart" v-show="store.bottomPanelOpen"></div>

      <!-- Tab bar -->
      <div class="bp-tabs">
        <button :class="{active: store.bottomPanelTab==='output'}" @click="switchTab('output')">输出</button>
        <button :class="{active: store.bottomPanelTab==='log'}" @click="switchTab('log')">
          日志
          <span v-if="store.taskState.runEvents.length" class="bp-badge">{{ store.taskState.runEvents.length }}</span>
        </button>
        <button :class="{active: store.bottomPanelTab==='chat', attention: store.taskState.interactiveWaiting && store.bottomPanelTab!=='chat'}"
          @click="switchTab('chat')">
          对话
          <span v-if="store.taskState.interactiveWaiting" class="bp-dot-pulse"></span>
        </button>
        <div style="flex:1"></div>
        <button class="bp-toggle" @click="toggle">{{ store.bottomPanelOpen ? '▼' : '▲' }}</button>
      </div>

      <!-- Content -->
      <div class="bp-content" v-show="store.bottomPanelOpen">

        <!-- Output tab -->
        <div v-show="store.bottomPanelTab==='output'" class="bp-log" ref="outputLog">
          <div v-if="store.taskState.outputLines.length === 0" class="bp-empty">等待运行...</div>
          <div
            v-for="(line, i) in store.taskState.outputLines" :key="i"
            class="bp-line"
            :class="line.type"
            :style="outputLineStyle(line)"
          >{{ formatOutputLine(line) }}</div>
        </div>

        <!-- Log tab -->
        <div v-show="store.bottomPanelTab==='log'" class="bp-log" ref="eventLog">
          <div v-if="store.taskState.runEvents.length === 0" class="bp-empty">等待执行...</div>
          <div
            v-for="(ev, i) in store.taskState.runEvents" :key="i"
            class="bp-line"
            :class="ev.type"
          >
            <span class="bp-time" v-if="ev.time">{{ ev.time }}</span>
            {{ ev.text }}
            <div v-if="ev.detail" class="bp-detail">{{ ev.detail }}</div>
          </div>
        </div>

        <!-- Chat tab -->
        <div v-show="store.bottomPanelTab==='chat'" class="bp-chat">
          <div class="bp-chat-output" ref="chatOutput">
            <div v-if="!store.taskState.interactiveOutput && !store.taskState.interactiveWaiting" class="bp-empty">
              discuss 节点运行时，对话会出现在这里。
            </div>
            <pre v-if="store.taskState.interactiveOutput">{{ store.taskState.interactiveOutput }}</pre>
          </div>
          <div v-if="store.taskState.interactiveWaiting" class="bp-chat-input-row">
            <div class="bp-chat-node-label">💬 {{ store.taskState.interactiveNodeId }} 等待回复</div>
            <div style="display:flex;gap:6px;padding:8px">
              <textarea
                class="bp-chat-textarea"
                v-model="store.taskState.interactiveInput"
                placeholder="输入回复... (Ctrl+Enter 发送)"
                rows="2"
                @keydown.ctrl.enter="$root.sendInteractiveMessage()"
                @keydown.meta.enter="$root.sendInteractiveMessage()"
              ></textarea>
              <div style="display:flex;flex-direction:column;gap:4px">
                <button class="btn btn-primary btn-sm" @click="$root.sendInteractiveMessage()">发送</button>
                <button class="btn btn-outline btn-sm" @click="$root.sendInteractiveMessage('done')">结束</button>
              </div>
            </div>
          </div>
        </div>

      </div>
    </div>
  `,
};
