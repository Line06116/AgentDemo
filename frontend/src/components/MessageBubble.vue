<script setup lang="ts">
defineProps<{
  role: 'user' | 'assistant'
  content: string
}>()
</script>

<template>
  <div :class="['bubble', role]">
    <div class="avatar">{{ role === 'user' ? '👤' : '🤖' }}</div>
    <div class="content">{{ content }}</div>
  </div>
</template>

<style scoped>
.bubble {
  display: flex;
  gap: 10px;
  padding: 12px 16px;
  animation: fadeIn 0.3s ease;
}
.bubble.user {
  flex-direction: row-reverse;
}
.bubble.user .content {
  background: var(--user-bubble);
}
.bubble.assistant .content {
  background: var(--assistant-bubble);
}
.avatar {
  flex-shrink: 0;
  width: 32px;
  height: 32px;
  display: flex;
  align-items: center;
  justify-content: center;
  border-radius: 50%;
  background: var(--bg-white);
  font-size: 16px;
}
.content {
  max-width: 70%;
  padding: 10px 14px;
  border-radius: 12px;
  line-height: 1.6;
  white-space: pre-wrap;
  word-break: break-word;
  font-size: 14px;
}
@keyframes fadeIn {
  from { opacity: 0; transform: translateY(8px); }
  to { opacity: 1; transform: translateY(0); }
}
</style>
