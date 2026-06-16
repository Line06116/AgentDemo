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

export interface SessionItem {
  session_id: string
  title: string
  created_at: string
  message_count: number
}

export const useChatStore = defineStore('chat', () => {
  const sessionId = ref('')
  const userId = ref('')
  const messages = ref<Message[]>([])
  const steps = ref<ProcessStep[]>([])
  const isStreaming = ref(false)
  const extractResult = ref('')
  const sessions = ref<SessionItem[]>([])

  async function initSession() {
    const lastId = localStorage.getItem('last_session_id')
    if (lastId) {
      try {
        const resp = await fetch(`/api/session/${lastId}`)
        if (resp.ok) {
          const data = await resp.json()
          sessionId.value = data.session_id
          userId.value = data.user_id
          messages.value = data.messages
          extractResult.value = data.extract_result
          await fetchSessions()
          return
        }
      } catch {}
    }
    const resp = await fetch('/api/session', { method: 'POST' })
    const data = await resp.json()
    sessionId.value = data.session_id
    userId.value = data.user_id
    localStorage.setItem('last_session_id', data.session_id)
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

  async function fetchSessions() {
    try {
      const resp = await fetch('/api/sessions')
      sessions.value = await resp.json()
    } catch (err: any) {
      console.error('加载历史会话失败:', err.message)
    }
  }

  async function switchSession(id: string) {
    if (id === sessionId.value) return
    if (isStreaming.value) return
    try {
      const resp = await fetch(`/api/session/${id}`)
      if (!resp.ok) throw new Error('会话不存在')
      const data = await resp.json()
      sessionId.value = data.session_id
      userId.value = data.user_id
      messages.value = data.messages
      extractResult.value = data.extract_result
      steps.value = []
      localStorage.setItem('last_session_id', id)
    } catch (err: any) {
      console.error('切换会话失败:', err.message)
    }
  }

  async function startNewSession() {
    if (isStreaming.value) return
    try {
      const resp = await fetch('/api/session', { method: 'POST' })
      const data = await resp.json()
      sessionId.value = data.session_id
      userId.value = data.user_id
      messages.value = []
      steps.value = []
      extractResult.value = ''
      localStorage.setItem('last_session_id', data.session_id)
      await fetchSessions()
    } catch (err: any) {
      console.error('新建会话失败:', err.message)
    }
  }

  async function deleteSession(id: string) {
    try {
      const resp = await fetch(`/api/session/${id}`, { method: 'DELETE' })
      if (!resp.ok) throw new Error('删除失败')
      if (id === sessionId.value) {
        await startNewSession()
      }
    } catch (err: any) {
      console.error('删除会话失败:', err.message)
    }
  }

  return {
    sessionId, userId, messages, steps, isStreaming, extractResult, sessions,
    initSession, sendMessage, doExtract, downloadTxt,
    fetchSessions, switchSession, startNewSession, deleteSession,
  }
})
