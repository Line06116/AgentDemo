# 企业知识问答智能 Agent

基于 LangChain ReAct Agent + RAG 的企业知识库智能问答系统，支持多工具调用、SSE 流式响应、知识萃取与导出。

**前端：** Vue 3 + TypeScript + Pinia + Vite  
**后端：** FastAPI + LangChain + Chroma + SSE

---

## 功能特性

- **RAG 知识检索** — Chroma 向量库 + DashScope 文本嵌入，支持 PDF/TXT/MD 文档上传与自动索引
- **ReAct Agent** — 思考→行动→观察→再思考循环，可自主调用 5 种工具完成复杂查询
- **检索优化** — 候选召回 20 条 + L2 距离阈值过滤 + LLM 重排序，精准定位相关知识片段
- **SSE 流式输出** — 实时展示 Agent 思考过程、工具调用及结果，同步/异步安全桥接
- **知识萃取** — 一键提取对话关键要点，支持 TXT 导出
- **对话历史** — JSON 持久化，会话切换/恢复/删除，localStorage 记忆最后会话
- **LangGraph 中间件** — `wrap_tool_call` + `before_model` 拦截器，实现工具调用全链路可观测

---

## 项目结构

```
├── agent/                  # ReAct Agent
│   ├── react_agent.py      # Agent 定义与流式执行
│   ├── event_emitter.py    # SSE 事件发射器
│   └── tools/
│       ├── agent_tools.py  # 5 个工具定义
│       ├── knowledge_tools.py
│       └── middleware.py   # LangGraph 中间件（监控/日志）
├── rag/                    # RAG 检索管线
│   ├── rag_service.py      # 检索 + 阈值过滤 + LLM 重排序
│   └── vector_store.py     # Chroma 向量库封装
├── model/
│   └── factory.py          # LLM & Embedding 模型工厂
├── server/                 # FastAPI 后端
│   ├── main.py             # 应用入口
│   ├── session.py          # 会话管理（JSON 持久化）
│   └── routes/
│       ├── chat.py          # 对话 & SSE 流式接口
│       ├── documents.py     # 文档上传/删除
│       └── extract.py       # 知识萃取 & 导出
├── config/                 # YAML 配置文件
│   ├── chroma.yml          # 向量库 & 检索参数
│   ├── rag.yml             # 模型配置
│   └── prompts.yml         # Prompt 路径
├── prompts/                # Prompt 模板
│   ├── main_prompt.txt     # Agent 系统提示词
│   ├── rag_summarize.txt   # RAG 总结提示词
│   ├── extract_prompt.txt  # 知识萃取提示词
│   └── rerank.txt          # 重排序提示词
├── utils/                  # 工具函数
│   ├── config_handler.py   # 配置加载
│   ├── file_handler.py     # 文件读取/MD5 去重
│   ├── prompt_loader.py    # Prompt 加载
│   └── path_tool.py        # 路径解析
├── tests/
│   └── test_rag_optimize.py # RAG 优化管线测试 (17 用例)
├── frontend/               # Vue 3 前端
│   └── src/
│       ├── App.vue          # 布局（侧栏 + 对话区）
│       ├── stores/chat.ts   # Pinia 状态管理
│       ├── components/
│       │   ├── ChatPanel.vue     # 对话面板
│       │   ├── ProcessPanel.vue  # Agent 过程可视化
│       │   ├── KnowledgePanel.vue # 知识库管理
│       │   ├── HistoryPanel.vue  # 对话历史
│       │   └── ExtractTab.vue    # 知识萃取
│       └── styles/main.css  # 全局样式
└── data/                   # 运行时数据
    ├── documents/           # 上传文档存储
    └── sessions.json        # 会话持久化
```

---

## 快速开始

### 环境要求

- Python ≥ 3.11
- Node.js ≥ 18
- [DashScope API Key](https://dashscope.console.aliyun.com/)（百炼平台）

### 1. 克隆项目

```bash
git clone https://github.com/Line06116/AgentDemo.git
cd AgentDemo
```

### 2. 后端配置

```bash
# 创建虚拟环境
python -m venv .venv
source .venv/bin/activate   # Linux/Mac
# .venv\Scripts\activate    # Windows

# 安装依赖
pip install fastapi uvicorn langchain langchain-chroma langchain-community \
    langchain-text-splitters dashscope sse-starlette chromadb \
    unstructured pypdf pyyaml

# 设置环境变量
export DASHSCOPE_API_KEY="your-api-key"
# $env:DASHSCOPE_API_KEY="your-api-key"   # Windows PowerShell
```

创建 `config/agent.yml`（已从仓库移除，需手动创建）：

```yaml
serpapi_key: "your-serpapi-key"   # 可选，用于 web_search 工具
```

### 3. 前端构建

```bash
cd frontend
npm install
npm run build      # 产物输出到 dist/
cd ..
```

### 4. 启动

```bash
# 开发模式（后端 + 前端同端口）
uvicorn server.main:app --host 0.0.0.0 --port 8000 --reload
```

打开 http://localhost:8000 ，左侧「知识库」面板上传文档，即可开始问答。

---

## 配置说明

### `config/chroma.yml`

| 参数 | 默认值 | 说明 |
|------|--------|------|
| `k` | 3 | 最终返回给 LLM 的片段数 |
| `retrieval_k` | 20 | 初始候选召回数 |
| `distance_threshold` | 1.5 | L2 距离上限，超过此值视为噪音 |
| `chunk_size` | 1200 | 文档分块大小（字符） |
| `chunk_overlap` | 120 | 相邻分块重叠 |
| `collection_name` | agent | Chroma 集合名称 |
| `persist_directory` | chroma_db | 向量库持久化目录 |

### `config/rag.yml`

| 参数 | 默认值 | 说明 |
|------|--------|------|
| `chat_model_name` | qwen-plus-latest | 对话模型 |
| `embedding_model_name` | text-embedding-v4 | 嵌入模型 |

---

## API 概览

| 方法 | 路径 | 说明 |
|------|------|------|
| `POST` | `/api/session` | 创建新会话 |
| `GET` | `/api/sessions` | 获取会话列表 |
| `GET` | `/api/session/{id}` | 获取会话详情 |
| `DELETE` | `/api/session/{id}` | 删除会话 |
| `POST` | `/api/chat` | 发送消息（SSE 流式响应） |
| `POST` | `/api/upload` | 上传文档 |
| `GET` | `/api/documents` | 获取文档列表 |
| `DELETE` | `/api/documents/{name}` | 删除文档 |
| `POST` | `/api/extract` | 知识萃取 |
| `GET` | `/api/extract/download` | 导出萃取结果为 TXT |
| `GET` | `/api/health` | 健康检查 |

---

## Agent 工具

| 工具 | 入参 | 说明 |
|------|------|------|
| `rag_search` | query（检索词） | 从知识库检索并总结 |
| `knowledge_extract` | conversation_text | 结构化提取对话要点 |
| `get_knowledge_stats` | 无 | 查询知识库统计信息 |
| `get_current_time` | 无 | 获取当前时间 |
| `web_search` | query（关键词） | 互联网搜索补充 |

---

## 运行测试

```bash
pip install pytest
python -m pytest tests/ -v
```

---

## RAG 检索管线

```
用户 query
  → 向量检索 (k=20, 带 L2 距离)
  → 距离阈值过滤 (≤ 1.5)
  → LLM 重排序候选片段
  → 取 top 3 拼接 context
  → LLM 生成最终答案
```

容错设计：重排序失败自动退回原始距离排序；阈值过滤为空取 top k 兜底。
