<script setup lang="ts">
import { ref, onMounted } from 'vue'
import { useChatStore } from './stores/chat'
import KnowledgePanel from './components/KnowledgePanel.vue'
import HistoryPanel from './components/HistoryPanel.vue'
import ChatPanel from './components/ChatPanel.vue'

const store = useChatStore()
const leftTab = ref<'knowledge' | 'history'>('knowledge')

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
      <aside class="sidebar">
        <div class="sidebar-tabs">
          <button
            :class="['sidebar-tab', { active: leftTab === 'knowledge' }]"
            @click="leftTab = 'knowledge'"
          >知识库</button>
          <button
            :class="['sidebar-tab', { active: leftTab === 'history' }]"
            @click="leftTab = 'history'"
          >历史对话</button>
        </div>
        <KnowledgePanel v-show="leftTab === 'knowledge'" />
        <HistoryPanel v-show="leftTab === 'history'" />
      </aside>
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
.sidebar {
  width: var(--sidebar-width);
  height: 100%;
  display: flex;
  flex-direction: column;
  background: var(--bg-white);
  border-right: 1px solid var(--border-color);
  overflow: hidden;
}
.sidebar-tabs {
  display: flex;
  border-bottom: 1px solid var(--border-color);
  flex-shrink: 0;
}
.sidebar-tab {
  flex: 1;
  padding: 10px 0;
  font-size: 13px;
  background: none;
  border-radius: 0;
  color: var(--text-secondary);
  border-bottom: 2px solid transparent;
}
.sidebar-tab.active {
  color: var(--accent);
  border-bottom-color: var(--accent);
}
.sidebar-tab:hover {
  background: var(--bg-hover);
}
.chat-area {
  flex: 1;
  display: flex;
  flex-direction: column;
  overflow: hidden;
}
</style>
