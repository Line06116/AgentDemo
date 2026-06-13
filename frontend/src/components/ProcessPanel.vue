<script setup lang="ts">
import type { ProcessStep } from '../stores/chat'

defineProps<{
  steps: ProcessStep[]
}>()

const visible = defineModel<boolean>('visible', { default: false })

const toolLabels: Record<string, string> = {
  rag_search: 'RAG 知识库检索',
  knowledge_extract: '知识萃取',
  get_knowledge_stats: '知识库统计',
  get_current_time: '获取当前时间',
  web_search: '网络搜索',
}

function toolLabel(tool: string) {
  return toolLabels[tool] || tool
}

function formatDuration(ms: number) {
  if (ms < 1000) return `${ms}ms`
  return `${(ms / 1000).toFixed(1)}s`
}
</script>

<template>
  <div class="process-panel">
    <button class="toggle-btn" @click="visible = !visible">
      {{ visible ? '▾' : '▸' }} Agent 思考过程 ({{ steps.length }} 步)
    </button>
    <div v-if="visible" class="steps">
      <div v-if="steps.length === 0" class="empty">暂无步骤</div>
      <div v-for="s in steps" :key="s.step" :class="['step', s.status]">
        <div class="step-header">
          <span class="step-icon">{{ s.status === 'running' ? '🔄' : '✅' }}</span>
          <span class="step-tool">{{ toolLabel(s.tool) }}</span>
          <span v-if="s.duration_ms" class="step-duration">{{ formatDuration(s.duration_ms) }}</span>
        </div>
        <div class="step-args" v-if="s.args && Object.keys(s.args).length">
          参数: {{ JSON.stringify(s.args) }}
        </div>
        <div class="step-result" v-if="s.result">
          {{ s.result.length > 300 ? s.result.slice(0, 300) + '...' : s.result }}
        </div>
      </div>
    </div>
  </div>
</template>

<style scoped>
.process-panel {
  border-top: 1px solid var(--border-color);
  background: var(--bg-white);
}
.toggle-btn {
  width: 100%;
  padding: 8px 16px;
  background: none;
  border: none;
  border-radius: 0;
  text-align: left;
  font-size: 13px;
  color: var(--text-secondary);
  cursor: pointer;
}
.toggle-btn:hover {
  background: var(--bg-hover);
}
.steps {
  padding: 0 16px 12px;
}
.empty {
  color: var(--text-muted);
  font-size: 13px;
}
.step {
  padding: 8px 0;
  border-bottom: 1px solid var(--border-color);
}
.step:last-child {
  border-bottom: none;
}
.step-header {
  display: flex;
  align-items: center;
  gap: 6px;
  font-size: 13px;
  font-weight: 500;
}
.step-icon {
  font-size: 14px;
}
.step-duration {
  margin-left: auto;
  color: var(--text-muted);
  font-size: 12px;
}
.step-args {
  font-size: 12px;
  color: var(--text-secondary);
  margin-top: 4px;
  padding-left: 20px;
}
.step-result {
  font-size: 12px;
  color: var(--text-primary);
  margin-top: 4px;
  padding: 6px 8px;
  background: var(--bg-primary);
  border-radius: 4px;
  white-space: pre-wrap;
  word-break: break-word;
}
.step.running .step-header {
  color: var(--accent);
}
</style>
