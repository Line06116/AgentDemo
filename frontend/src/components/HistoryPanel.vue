<script setup lang="ts">
import { ref, onMounted } from 'vue'
import { useChatStore } from '../stores/chat'

const store = useChatStore()
const deletingId = ref('')

async function loadList() {
  await store.fetchSessions()
}

async function handleSwitch(sessionId: string) {
  await store.switchSession(sessionId)
}

async function handleDelete(sessionId: string) {
  if (deletingId.value === sessionId) {
    await store.deleteSession(sessionId)
    deletingId.value = ''
    await loadList()
  } else {
    deletingId.value = sessionId
    setTimeout(() => { deletingId.value = '' }, 3000)
  }
}

onMounted(loadList)
</script>

<template>
  <div class="history-panel">
    <button class="new-chat-btn" @click="store.startNewSession">
      + 新建对话
    </button>

    <div v-if="store.sessions.length === 0" class="empty-hint">
      暂无历史对话
    </div>

    <div class="session-list">
      <div
        v-for="s in store.sessions"
        :key="s.session_id"
        class="session-item"
        :class="{ active: s.session_id === store.sessionId }"
        @click="handleSwitch(s.session_id)"
      >
        <div class="session-content">
          <div class="session-title">{{ s.title }}</div>
          <div class="session-meta">{{ s.created_at }} · {{ s.message_count }} 条消息</div>
        </div>
        <button
          class="delete-btn"
          @click.stop="handleDelete(s.session_id)"
          :title="deletingId === s.session_id ? '确认删除' : '删除'"
        >
          {{ deletingId === s.session_id ? '⚠' : '✕' }}
        </button>
      </div>
    </div>
  </div>
</template>

<style scoped>
.history-panel {
  display: flex;
  flex-direction: column;
  height: 100%;
}
.new-chat-btn {
  width: 100%;
  padding: 8px 12px;
  background: var(--accent);
  color: white;
  border: none;
  border-radius: var(--radius);
  font-size: 13px;
  cursor: pointer;
  margin-bottom: 10px;
  flex-shrink: 0;
}
.new-chat-btn:hover {
  background: var(--accent-hover);
}
.empty-hint {
  text-align: center;
  color: var(--text-muted);
  font-size: 13px;
  padding: 20px 0;
}
.session-list {
  flex: 1;
  overflow-y: auto;
}
.session-item {
  display: flex;
  align-items: center;
  padding: 10px 12px;
  border-radius: var(--radius);
  cursor: pointer;
  transition: background 0.15s;
}
.session-item:hover {
  background: var(--bg-light);
}
.session-item.active {
  background: var(--accent-light);
  border-left: 3px solid var(--accent);
}
.session-content {
  flex: 1;
  min-width: 0;
}
.session-title {
  font-size: 13px;
  font-weight: 500;
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
}
.session-meta {
  font-size: 11px;
  color: var(--text-muted);
  margin-top: 2px;
}
.delete-btn {
  flex-shrink: 0;
  width: 24px;
  height: 24px;
  border: none;
  background: transparent;
  color: var(--text-muted);
  cursor: pointer;
  border-radius: 4px;
  font-size: 12px;
  display: flex;
  align-items: center;
  justify-content: center;
  opacity: 0;
  transition: opacity 0.15s, color 0.15s;
}
.session-item:hover .delete-btn {
  opacity: 1;
}
.delete-btn:hover {
  color: var(--danger);
  background: var(--danger-light, #fce4e4);
}
</style>
