import { defineStore } from 'pinia'
import { ref } from 'vue'

export interface Message {
  role: 'user' | 'assistant'
  content: string
}

export interface ProcessStep {
  step: number
  tool: string
  args: Record<string, string>
  reasoning: string
  result: string
  duration_ms: number
  status: 'running' | 'done'
}

export const useChatStore = defineStore('chat', () => {
  const sessionId = ref('')
  const userId = ref('')
  const messages = ref<Message[]>([])
  const steps = ref<ProcessStep[]>([])
  const isStreaming = ref(false)
  const extractResult = ref('')

  async function initSession() {
    const resp = await fetch('/api/session', { method: 'POST' })
    const data = await resp.json()
    sessionId.value = data.session_id
    userId.value = data.user_id
  }

  async function sendMessage(content: string) {
    if (!sessionId.value || isStreaming.value) return

    messages.value.push({ role: 'user', content })
    steps.value = []
    isStreaming.value = true

    const assistantMsg: Message = { role: 'assistant', content: '' }
    messages.value.push(assistantMsg)

    const resp = await fetch('/api/chat', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ session_id: sessionId.value, message: content }),
    })

    const reader = resp.body!.getReader()
    const decoder = new TextDecoder()
    let buffer = ''

    while (true) {
      const { done, value } = await reader.read()
      if (done) break

      buffer += decoder.decode(value, { stream: true })
      const lines = buffer.split('\n')
      buffer = lines.pop() || ''

      let eventType = ''
      for (const line of lines) {
        if (line.startsWith('event: ')) {
          eventType = line.slice(7).trim()
        } else if (line.startsWith('data: ')) {
          const data = JSON.parse(line.slice(6))
          handleSSEEvent(eventType, data, assistantMsg)
        }
      }
    }

    isStreaming.value = false
  }

  function handleSSEEvent(type: string, data: any, msg: Message) {
    switch (type) {
      case 'thinking':
        steps.value.push({
          step: data.step,
          tool: data.tool,
          args: data.args,
          reasoning: data.reasoning,
          result: '',
          duration_ms: 0,
          status: 'running',
        })
        break
      case 'tool_result':
        const step = steps.value.find(s => s.step === data.step)
        if (step) {
          step.result = data.result
          step.duration_ms = data.duration_ms
          step.status = 'done'
        }
        break
      case 'token':
        msg.content += data.content
        break
      case 'error':
        msg.content += `\n[错误: ${data.message}]`
        break
    }
  }

  async function doExtract() {
    const resp = await fetch('/api/extract', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ session_id: sessionId.value }),
    })
    const data = await resp.json()
    extractResult.value = data.result
  }

  function downloadTxt() {
    window.open(`/api/extract/download?session_id=${sessionId.value}`, '_blank')
  }

  return {
    sessionId, userId, messages, steps, isStreaming, extractResult,
    initSession, sendMessage, doExtract, downloadTxt,
  }
})
