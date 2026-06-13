# 企业知识问答 Agent — Vue 前端 + FastAPI 后端重构设计

## 一、项目目标

将现有"智扫通机器人智能客服"转型为**通用企业知识问答 Agent**：

1. 用户上传企业文档（PDF/TXT/MD），构建专属知识库
2. Agent 基于知识库进行问答
3. 从对话中萃取知识要点，导出为 TXT 文件
4. 前端使用 Vue 3 + 原生 CSS，后端使用 FastAPI + SSE

---

## 二、架构总览

```
┌──────────────────────────────────────────────────────┐
│  Vue 3 Frontend (Vite + 原生 CSS)                    │
│  ┌──────────────┐ ┌──────────────────────────────┐  │
│  │ 知识面板(左30%)│ │ 对话区(右70%)                  │  │
│  │ Tab:上传/列表 │ │ · 消息气泡列表                  │  │
│  │ /萃取+导出    │ │ · 过程可视化面板(可折叠)        │  │
│  └──────────────┘ └──────────────────────────────┘  │
│                      [输入框 ████████] [发送]         │
└──────── SSE ────────────── REST ────────────────────┘
┌──────────────────────────────────────────────────────┐
│  FastAPI Server                                       │
│  · /api/session     创建会话                          │
│  · /api/chat        POST → SSE 流式返回               │
│  · /api/upload      上传文档入库                      │
│  · /api/documents   文件列表/删除                     │
│  · /api/extract     知识萃取 + TXT 下载               │
├──────────────────────────────────────────────────────┤
│  Agent Core                                           │
│  5 tools: rag_search, knowledge_extract,              │
│           get_knowledge_stats, get_current_time,       │
│           web_search                                  │
│  middleware → EventEmitter → asyncio.Queue → SSE      │
├──────────────────────────────────────────────────────┤
│  RAG Service (Chroma)       │  Document Manager       │
│  · 向量检索                  │  · 分块入库             │
│  · 持久化                    │  · 增删查               │
└──────────────────────────────────────────────────────┘
```

### 开发/生产模式

| 环境 | 前端 | 后端 | 通信 |
|------|------|------|------|
| 开发 | `npm run dev` → :5173 | `uvicorn` → :8000 | Vite proxy 转发 `/api/*` |
| 生产 | `npm run build` → 静态文件 | FastAPI serve dist | 同域 |

---

## 三、目录结构

```
AgentDemo/
├── server/                        # 新增：FastAPI 后端
│   ├── main.py                   # 应用入口，CORS，挂载静态文件
│   ├── routes/
│   │   ├── chat.py               # POST /api/chat — SSE 流式对话
│   │   ├── documents.py          # 上传/列表/删除
│   │   └── extract.py           # 萃取 + TXT 导出
│   ├── session.py               # 会话管理器（内存存储）
│   └── sse.py                  # SSE 事件发射器（asyncio.Queue）
├── frontend/                      # 新增：Vue 3 前端
│   ├── index.html
│   ├── package.json
│   ├── vite.config.ts
│   └── src/
│       ├── App.vue
│       ├── main.ts
│       ├── components/
│       │   ├── ChatPanel.vue         # 对话消息列表 + 输入框
│       │   ├── ProcessPanel.vue      # Agent 过程可视化(可折叠)
│       │   ├── KnowledgePanel.vue    # 左侧知识管理面板
│       │   ├── MessageBubble.vue     # 单条消息气泡
│       │   └── ExtractTab.vue        # 萃取展示 + TXT 导出
│       ├── stores/
│       │   └── chat.ts              # Pinia 状态：消息/过程/SSE 连接
│       └── styles/
│           └── main.css             # 全局样式
├── agent/                         # 重构
│   ├── react_agent.py             # 简化为通用 Agent
│   ├── event_emitter.py           # 异步事件发射器
│   └── tools/
│       ├── agent_tools.py         # 精简为 5 个通用工具
│       └── middleware.py           # 简化为监控 + SSE 事件捕获
├── rag/                           # 基本保留，小幅调整
├── model/                         # 不变
├── utils/                         # 基本保留
├── prompts/
│   ├── main_prompt.txt            # 重写：通用企业问答
│   └── extract_prompt.txt         # 新增：知识萃取提示词
├── config/
│   ├── agent.yml                  # 简化
│   ├── chroma.yml                 # 不变
│   └── ...
└── data/documents/                # 上传文件存储目录
```

---

## 四、SSE 事件协议

`POST /api/chat` 返回 `Content-Type: text/event-stream`

| 事件类型 | 触发时机 | 数据结构 |
|---------|---------|---------|
| `thinking` | Agent 决定调用工具 | `{"step": 1, "tool": "rag_search", "args": {...}, "reasoning": "..."}` |
| `tool_result` | 工具返回结果 | `{"step": 1, "tool": "rag_search", "result": "...", "duration_ms": 230}` |
| `token` | 最终回答的每个字符块 | `{"content": "根据知识库"}` |
| `done` | 本轮结束 | `{}` |
| `error` | 出错 | `{"message": "..."}` |

---

## 五、Agent 工具定义

### 5.1 rag_search
- 入参：`query: str`
- 出参：`str`
- 逻辑：Chroma 检索 → LLM 总结 → 返回
- 保留现有 RagSummarizeService

### 5.2 knowledge_extract
- 入参：`conversation_text: str`（当前会话完整对话历史文本）
- 出参：`str`（结构化 Markdown 知识点）
- 逻辑：加载 extract_prompt.txt → 拼接对话文本 → LLM 提炼 → 返回
- 实现：LCEL Chain（PromptTemplate | ChatModel | StrOutputParser），不依赖外部 API
- 同时被 Agent 工具调用和 `/api/extract` API 端点直接调用

### 5.3 get_knowledge_stats
- 入参：无
- 出参：`str`
- 逻辑：读取 Chroma collection 信息 + 文件列表 → 格式化返回
- 用途：用户问"知识库有什么内容"时调用

### 5.4 get_current_time
- 入参：无
- 出参：`str`
- 逻辑：`datetime.now().strftime("%Y-%m-%d %H:%M:%S")`

### 5.5 web_search
- 入参：`query: str`
- 出参：`str`
- 逻辑：调用 SerpAPI → 返回前 5 条结果的标题+摘要+链接
- API key 从 `config/agent.yml` 读取 `serpapi_key`
- 无 key 时返回错误提示

---

## 六、知识萃取流程

```
手动触发(按钮) ─┐
                ├→ knowledge_extract 工具(对话历史) → LLM 提炼
自然语言触发 ────┘                                      │
                                              ┌────────┘
                                              ├→ 前端"萃取"Tab 展示
                                              └→ 导出 TXT 按钮 → GET /api/extract/download
```

萃取结果格式：Markdown 结构，按主题分组，包含时间戳。

TXT 导出：`Content-Disposition: attachment; filename="knowledge-YYYY-MM-DD.txt"`。

---

## 七、会话管理

- 无登录，`POST /api/session` 创建新会话
- 后端分配 `session_id`（UUID）和 `user_id`（从 1001-9999 随机）
- 会话存储在内存 `dict[session_id] = SessionState(messages=[], extract_result="")`
- 页面刷新后会话丢失（演示性质）

---

## 八、中间件变更

保留 2 个中间件（移除 `report_prompt_switch`）：

1. **monitor_tool** — 工具调用监控：调用前后通过 EventEmitter 推 `thinking` 和 `tool_result` 事件到 asyncio.Queue
2. **log_before_model** — LLM 日志：保留不变

移除：
- `report_prompt_switch`（动态提示词切换）— 通用 Agent 不需要双模式
- `fill_context_for_report` 工具

---

## 九、需要移除的组件

| 组件 | 原因 |
|------|------|
| `get_weather` 工具 | 演示用 |
| `get_user_location` 工具 | 演示用 |
| `get_user_id` 工具(旧版) | 改为 session 分配 |
| `get_current_month` 工具(旧版随机) | 改为 `get_current_time` |
| `fetch_external_data` 工具 | 依赖固定 CSV |
| `fill_context_for_report` 工具 | 旧报告模式触发 |
| `report_prompt_switch` 中间件 | 不再需要双模式 |
| `data/external/records.csv` | 扫地机器人数据 |
| `prompts/report_prompt.txt` | 旧报告提示词 |
| `config/agent.yml` 中 `external_data_path` | 不再需要 |
| `app.py`（Streamlit） | 替换为 FastAPI + Vue |

---

## 十、依赖变更

| 新增 | 移除 |
|------|------|
| `fastapi` | `streamlit` |
| `uvicorn` | |
| `sse-starlette` | |
| `python-multipart`（文件上传） | |

前端新依赖：`vue@3`, `vite`, `pinia`, 无 UI 组件库。

---

## 十二、关键技术决策

### 12.1 同步 Agent + 异步 SSE 桥接

LangChain 的 `create_agent` 和中间件是同步的，而 FastAPI SSE 需要异步。解决方案：

- `stream()` 在主线程中运行，EventEmitter 通过 `asyncio.run_coroutine_threadsafe()` 将事件推入 `asyncio.Queue`
- FastAPI SSE 端点使用 `async for` 从 Queue 消费事件
- Agent 执行使用 `run_in_executor` 放入线程池，不阻塞事件循环

### 12.2 知识萃取的双路径

两个入口，不同逻辑：

| 入口 | 实现 | 说明 |
|------|------|------|
| Agent 自然语言触发 | `knowledge_extract` 工具，LLM 自主调用 | Agent 检测到萃取意图后调用此工具 |
| 前端按钮手动触发 | `POST /api/extract` API 端点 | 绕过 Agent，直接从会话捞对话历史 → LCEL Chain → 返回结果 → 存 session.extract_result |

TXT 导出读 `session.extract_result`，不重新计算。

### 12.3 config/agent.yml 变更

```yaml
# 移除
external_data_path: data/external/records.csv
weather_api: xxx

# 新增
serpapi_key: your_serpapi_key_here
```

### 12.4 Agent 同步执行策略

`create_agent().stream()` 是同步的，在 `run_in_executor` 中运行。中间件 `monitor_tool` 捕获工具调用事件，通过 EventEmitter 推送到线程安全的 asyncio.Queue。SSE 端点异步消费 Queue 并 yield 给客户端。

---

## 十一、前端组件职责

| 组件 | 职责 |
|------|------|
| `App.vue` | 三栏布局容器，管理 session 初始化 |
| `KnowledgePanel.vue` | 左侧面板，3 个 Tab（上传/文件列表/萃取） |
| `ChatPanel.vue` | 消息列表渲染 + 输入框 + 发送 |
| `ProcessPanel.vue` | 嵌入 ChatPanel 底部，可折叠，展示思考步骤时间线 |
| `MessageBubble.vue` | 单条消息气泡（用户/Agent 不同样式） |
| `ExtractTab.vue` | 萃取结果渲染 + "导出 TXT" 按钮 |
| `chat.ts` (Pinia) | 全局状态：消息数组、过程步骤数组、SSE EventSource、发送消息 action |
