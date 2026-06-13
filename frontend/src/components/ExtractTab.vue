<script setup lang="ts">
import { useChatStore } from '../stores/chat'

const store = useChatStore()
</script>

<template>
  <div class="extract-tab">
    <button
      class="extract-btn"
      @click="store.doExtract"
      :disabled="store.isStreaming || store.messages.length === 0"
    >
      🔍 从对话中萃取知识
    </button>

    <div v-if="store.extractResult" class="extract-header">
      <h4>萃取结果</h4>
      <button class="download-btn" @click="store.downloadTxt">📥 导出 TXT</button>
    </div>

    <div v-if="store.extractResult" class="extract-content">
      {{ store.extractResult }}
    </div>
    <div v-else class="extract-empty">
      点击按钮将当前对话内容提炼为知识要点
    </div>
  </div>
</template>

<style scoped>
.extract-tab {
  padding: 12px;
}
.extract-btn {
  width: 100%;
  background: var(--accent);
  color: white;
  font-weight: 500;
  padding: 10px;
}
.extract-btn:hover:not(:disabled) {
  background: var(--accent-hover);
}
.extract-btn:disabled {
  opacity: 0.6;
  cursor: not-allowed;
}
.extract-header {
  display: flex;
  justify-content: space-between;
  align-items: center;
  margin-top: 16px;
}
.extract-header h4 {
  font-size: 14px;
}
.download-btn {
  background: var(--success);
  color: white;
  font-size: 12px;
  padding: 4px 12px;
}
.extract-content {
  margin-top: 8px;
  font-size: 13px;
  line-height: 1.8;
  white-space: pre-wrap;
  background: var(--bg-primary);
  border-radius: var(--radius);
  padding: 12px;
  max-height: 400px;
  overflow-y: auto;
}
.extract-empty {
  margin-top: 12px;
  color: var(--text-muted);
  font-size: 13px;
  text-align: center;
}
</style>
