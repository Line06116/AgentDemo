<script setup lang="ts">
import { ref, onMounted } from 'vue'
import ExtractTab from './ExtractTab.vue'

const activeTab = ref<'upload' | 'files' | 'extract'>('upload')
const files = ref<{ name: string; size_display: string }[]>([])
const uploadStatus = ref('')

async function loadFiles() {
  try {
    const resp = await fetch('/api/documents')
    if (!resp.ok) throw new Error(`HTTP ${resp.status}`)
    const data = await resp.json()
    files.value = data.files || []
  } catch (err: any) {
    console.error('加载文件列表失败:', err.message)
    files.value = []
  }
}

async function handleUpload(e: Event) {
  const input = e.target as HTMLInputElement
  const file = input.files?.[0]
  if (!file) return

  uploadStatus.value = `正在上传 ${file.name}...`
  const formData = new FormData()
  formData.append('file', file)

  try {
    const resp = await fetch('/api/upload', { method: 'POST', body: formData })
    const data = await resp.json()
    uploadStatus.value = data.message
    input.value = ''
    loadFiles()
  } catch (err: any) {
    uploadStatus.value = `上传失败: ${err.message}`
  }
}

async function handleDelete(filename: string) {
  try {
    await fetch(`/api/documents/${encodeURIComponent(filename)}`, { method: 'DELETE' })
  } catch (err: any) {
    console.error('删除文件失败:', err.message)
  }
  loadFiles()
}

onMounted(loadFiles)
</script>

<template>
  <div class="knowledge-panel">
    <div class="tabs">
      <button v-for="tab in [
        { key: 'upload' as const, label: '📤 上传' },
        { key: 'files' as const, label: '📁 文件' },
        { key: 'extract' as const, label: '💡 萃取' },
      ]" :key="tab.key" :class="['tab', { active: activeTab === tab.key }]" @click="activeTab = tab.key">
        {{ tab.label }}
      </button>
    </div>

    <div class="tab-content">
      <div v-if="activeTab === 'upload'" class="upload-area">
        <label class="upload-label">
          选择文件 (PDF/TXT/MD)
          <input type="file" accept=".pdf,.txt,.md" @change="handleUpload" hidden />
        </label>
        <p v-if="uploadStatus" class="upload-status">{{ uploadStatus }}</p>
      </div>

      <div v-if="activeTab === 'files'" class="file-list">
        <div v-if="files.length === 0" class="empty">暂无文件</div>
        <div v-for="f in files" :key="f.name" class="file-item">
          <span class="file-name">📄 {{ f.name }}</span>
          <span class="file-size">{{ f.size_display }}</span>
          <button class="delete-btn" @click="handleDelete(f.name)">✕</button>
        </div>
      </div>

      <div v-if="activeTab === 'extract'">
        <ExtractTab />
      </div>
    </div>
  </div>
</template>

<style scoped>
.knowledge-panel {
  flex: 1;
  display: flex;
  flex-direction: column;
  overflow: hidden;
}
.tabs {
  display: flex;
  border-bottom: 1px solid var(--border-color);
}
.tab {
  flex: 1;
  padding: 10px 0;
  font-size: 13px;
  background: none;
  border-radius: 0;
  color: var(--text-secondary);
  border-bottom: 2px solid transparent;
}
.tab.active {
  color: var(--accent);
  border-bottom-color: var(--accent);
}
.tab:hover {
  background: var(--bg-hover);
}
.tab-content {
  flex: 1;
  overflow-y: auto;
}
.upload-area {
  padding: 16px;
}
.upload-label {
  display: block;
  text-align: center;
  padding: 20px;
  border: 2px dashed var(--border-color);
  border-radius: var(--radius);
  cursor: pointer;
  color: var(--text-secondary);
  font-size: 14px;
}
.upload-label:hover {
  border-color: var(--accent);
  color: var(--accent);
}
.upload-status {
  margin-top: 12px;
  font-size: 13px;
  color: var(--text-secondary);
}
.file-list {
  padding: 8px 0;
}
.empty {
  text-align: center;
  padding: 20px;
  color: var(--text-muted);
  font-size: 13px;
}
.file-item {
  display: flex;
  align-items: center;
  gap: 8px;
  padding: 10px 16px;
  font-size: 13px;
  border-bottom: 1px solid var(--border-color);
}
.file-name {
  flex: 1;
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
}
.file-size {
  color: var(--text-muted);
  font-size: 12px;
  flex-shrink: 0;
}
.delete-btn {
  background: none;
  color: var(--error);
  padding: 2px 8px;
  font-size: 14px;
  flex-shrink: 0;
}
.delete-btn:hover {
  background: #fff0f0;
}
</style>
