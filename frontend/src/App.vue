<script setup lang="ts">
import { onMounted } from 'vue'
import { useChatStore } from './stores/chat'
import KnowledgePanel from './components/KnowledgePanel.vue'
import ChatPanel from './components/ChatPanel.vue'

const store = useChatStore()

onMounted(() => {
  store.initSession()
})
</script>

<template>
  <div class="app-layout">
    <header class="app-header">
      <h1>企业知识问答 · 智能 Agent</h1>
      <span v-if="store.sessionId" class="session-info">
        会话: {{ store.sessionId.slice(0, 8) }}...
      </span>
    </header>
    <main class="app-main">
      <KnowledgePanel />
      <section class="chat-area">
        <ChatPanel />
      </section>
    </main>
  </div>
</template>

<style scoped>
.app-layout {
  display: flex;
  flex-direction: column;
  height: 100vh;
}
.app-header {
  height: var(--header-height);
  background: var(--bg-white);
  border-bottom: 1px solid var(--border-color);
  display: flex;
  align-items: center;
  justify-content: space-between;
  padding: 0 20px;
  flex-shrink: 0;
}
.app-header h1 {
  font-size: 16px;
  font-weight: 600;
}
.session-info {
  font-size: 12px;
  color: var(--text-muted);
}
.app-main {
  flex: 1;
  display: flex;
  overflow: hidden;
}
.chat-area {
  flex: 1;
  display: flex;
  flex-direction: column;
  overflow: hidden;
}
</style>
