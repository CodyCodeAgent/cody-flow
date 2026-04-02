/* ============================================================
   CodyFlow — Header Component
   ============================================================ */

const AppHeader = {
  props: ['currentPage', 'currentFlowId', 'flowName'],
  emits: ['navigate', 'newFlow', 'save', 'exportYaml', 'importYaml', 'loadTemplate'],
  template: `
    <div class="header">
      <div style="display:flex;align-items:center">
        <span class="logo">CodyFlow</span>
        <span class="subtitle">AI 工作流编排</span>
        <div class="header-nav">
          <button :class="{active: currentPage==='editor'}" @click="$emit('navigate','editor')">编辑器</button>
          <button :class="{active: currentPage==='tasks' || currentPage==='task-detail'}" @click="$emit('navigate','tasks')">任务</button>
          <button :class="{active: currentPage==='settings'}" @click="$emit('navigate','settings')">设置</button>
        </div>
      </div>
      <div class="header-actions" v-show="currentPage==='editor'">
        <button class="btn btn-outline btn-sm" @click="$emit('newFlow')">新建</button>
        <button class="btn btn-outline btn-sm" @click="$emit('save')">保存</button>
        <button class="btn btn-outline btn-sm" @click="$emit('loadTemplate')">模板</button>
        <span class="header-divider"></span>
        <button class="btn btn-outline btn-sm" @click="$emit('importYaml')">导入</button>
        <button class="btn btn-outline btn-sm" @click="$emit('exportYaml')">导出</button>
      </div>
    </div>
  `,
};
