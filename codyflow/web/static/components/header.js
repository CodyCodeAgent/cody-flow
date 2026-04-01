/* ============================================================
   CodyFlow — Header Component
   ============================================================ */

const AppHeader = {
  props: ['currentPage', 'runStatus'],
  emits: ['navigate', 'run', 'stop', 'export', 'loadTemplate'],
  template: `
    <div class="header">
      <div style="display:flex;align-items:center">
        <span class="logo">CodyFlow</span>
        <span class="subtitle">AI 工作流编排</span>
        <div class="header-nav">
          <button :class="{active: currentPage==='editor'}" @click="$emit('navigate','editor')">编辑器</button>
          <button :class="{active: currentPage==='settings'}" @click="$emit('navigate','settings')">设置</button>
        </div>
      </div>
      <div class="header-actions" v-show="currentPage==='editor'">
        <button class="btn btn-outline btn-sm" @click="$emit('loadTemplate')">加载模板</button>
        <button class="btn btn-outline btn-sm" @click="$emit('export')">导出 YAML</button>
        <button v-if="runStatus==='running'" class="btn btn-danger btn-sm" @click="$emit('stop')">停止</button>
        <button v-else class="btn btn-primary btn-sm" @click="$emit('run')">运行</button>
      </div>
    </div>
  `,
};
