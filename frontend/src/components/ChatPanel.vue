<script setup lang="ts">
import { ref, nextTick, watch } from 'vue'
import { useChatStore } from '../stores/chat'
import MessageBubble from './MessageBubble.vue'
import ProcessPanel from './ProcessPanel.vue'

const store = useChatStore()
const inputText = ref('')
const showProcess = ref(false)
const chatContainer = ref<HTMLElement | null>(null)

async function handleSend() {
  const text = inputText.value.trim()
  if (!text) return
  inputText.value = ''
  showProcess.value = true
  await store.sendMessage(text)
  await nextTick()
  if (chatContainer.value) {
    chatContainer.value.scrollTop = chatContainer.value.scrollHeight
  }
}

function handleKeydown(e: KeyboardEvent) {
  if (e.key === 'Enter' && !e.shiftKey) {
    e.preventDefault()
    handleSend()
  }
}

watch(() => store.messages.length, async () => {
  await nextTick()
  if (chatContainer.value) {
    chatContainer.value.scrollTop = chatContainer.value.scrollHeight
  }
})
</script>

<template>
  <div class="chat-panel">
    <div class="messages" ref="chatContainer">
      <div v-if="store.messages.length === 0" class="welcome">
        <h2>👋 欢迎使用企业知识问答助手</h2>
        <p>上传企业文档后，即可基于知识库进行问答</p>
      </div>
      <MessageBubble
        v-for="(msg, i) in store.messages"
        :key="i"
        :role="msg.role"
        :content="msg.content"
      />
    </div>
    <ProcessPanel v-model:visible="showProcess" :steps="store.steps" />
    <div class="input-area">
      <textarea
        v-model="inputText"
        placeholder="输入您的问题... (Enter 发送，Shift+Enter 换行)"
        @keydown="handleKeydown"
        :disabled="store.isStreaming"
        rows="2"
      ></textarea>
      <button
        class="send-btn"
        @click="handleSend"
        :disabled="store.isStreaming || !inputText.trim()"
      >
        {{ store.isStreaming ? '等待中...' : '发送' }}
      </button>
    </div>
  </div>
</template>

<style scoped>
.chat-panel {
  display: flex;
  flex-direction: column;
  height: 100%;
  background: var(--bg-white);
}
.messages {
  flex: 1;
  overflow-y: auto;
  padding: 8px 0;
}
.welcome {
  text-align: center;
  padding: 60px 20px;
  color: var(--text-secondary);
}
.welcome h2 {
  margin-bottom: 8px;
}
.input-area {
  display: flex;
  gap: 10px;
  padding: 12px 16px;
  border-top: 1px solid var(--border-color);
  background: var(--bg-white);
}
.input-area textarea {
  flex: 1;
  resize: none;
  min-height: 40px;
  max-height: 120px;
  font-size: 14px;
  font-family: inherit;
}
.send-btn {
  align-self: flex-end;
  background: var(--accent);
  color: white;
  padding: 8px 20px;
  border-radius: var(--radius);
  font-weight: 500;
}
.send-btn:hover:not(:disabled) {
  background: var(--accent-hover);
}
.send-btn:disabled {
  opacity: 0.6;
  cursor: not-allowed;
}
</style>
