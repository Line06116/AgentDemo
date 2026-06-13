# 企业知识问答 Agent — Vue + FastAPI 重构 实现计划

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 将 Streamlit 扫地机器人客服重构为 FastAPI + Vue 3 通用企业知识问答 Agent，支持文档上传/RAG问答/知识萃取/TXT导出。

**Architecture:** FastAPI 后端提供 REST API + SSE 流式端点，同步 LangChain Agent 通过线程池 + asyncio.Queue 桥接实现流式事件推送。Vue 3 前端左侧知识面板 + 右侧对话区，SSE 接收 Agent 思考过程和回复。

**Tech Stack:** Python/FastAPI, LangChain/Chroma/Qwen, Vue 3/Vite/Pinia/native CSS

---

## 文件结构

### 新建文件
| 文件 | 职责 |
|------|------|
| `server/main.py` | FastAPI 入口，CORS，路由注册，生产静态文件挂载 |
| `server/session.py` | 内存会话管理器 |
| `server/sse.py` | SSE 事件发射器（async Queue + thread-safe push） |
| `server/routes/__init__.py` | 空 |
| `server/routes/chat.py` | POST /api/chat → SSE 流 |
| `server/routes/documents.py` | 文件上传/列表/删除 |
| `server/routes/extract.py` | 知识萃取 + TXT 导出 |
| `server/__init__.py` | 空 |
| `agent/event_emitter.py` | 事件队列封装，桥接同步 Agent 与异步 SSE |
| `agent/tools/knowledge_tools.py` | knowledge_extract 和 get_knowledge_stats 工具 |
| `prompts/extract_prompt.txt` | 知识萃取提示词 |
| `frontend/package.json` | Vue 项目依赖 |
| `frontend/vite.config.ts` | Vite 配置 + API 代理 |
| `frontend/index.html` | 入口 HTML |
| `frontend/src/main.ts` | Vue 应用挂载 |
| `frontend/src/App.vue` | 根布局组件 |
| `frontend/src/stores/chat.ts` | Pinia 全局状态 |
| `frontend/src/components/ChatPanel.vue` | 对话消息列表 + 输入框 |
| `frontend/src/components/ProcessPanel.vue` | Agent 过程可视化（可折叠） |
| `frontend/src/components/KnowledgePanel.vue` | 左侧知识管理面板 |
| `frontend/src/components/MessageBubble.vue` | 消息气泡 |
| `frontend/src/components/ExtractTab.vue` | 萃取展示 + TXT 导出 |
| `frontend/src/styles/main.css` | 全局样式 |
| `data/documents/.gitkeep` | 上传文件存储目录 |

### 修改文件
| 文件 | 变更 |
|------|------|
| `agent/react_agent.py` | 简化，用 EventEmitter 替换报告模式 |
| `agent/tools/agent_tools.py` | 移除旧工具，保留 rag_search，改用真实时间/SerpAPI |
| `agent/tools/middleware.py` | 移除 report_prompt_switch，monitor_tool 接入 EventEmitter |
| `config/agent.yml` | 移除 weather_api/external_data_path，添加 serpapi_key |
| `config/prompts.yml` | 移除 report_prompt_path，添加 extract_prompt_path |
| `prompts/main_prompt.txt` | 重写为通用企业问答 Agent |

### 删除文件
| 文件 | 原因 |
|------|------|
| `app.py` | Streamlit → 替换为 FastAPI |
| `prompts/report_prompt.txt` | 旧报告模式 |
| `data/external/records.csv` | 扫地机器人数据 |

---

### Task 1: 更新依赖和配置

**Files:**
- Modify: `config/agent.yml`
- Modify: `config/prompts.yml`
- Run: `pip install` 新增依赖

- [ ] **Step 1: 更新 agent.yml**

在 `config/agent.yml` 中替换内容：
```yaml
serpapi_key: your_serpapi_key_here
```

```bash
Write: config/agent.yml
```

- [ ] **Step 2: 更新 prompts.yml**

在 `config/prompts.yml` 中替换内容：
```yaml
main_prompt_path: prompts/main_prompt.txt
rag_summarize_prompt_path: prompts/rag_summarize.txt
extract_prompt_path: prompts/extract_prompt.txt
```

```bash
Write: config/prompts.yml
```

- [ ] **Step 3: 安装新增依赖**

```bash
pip install fastapi uvicorn sse-starlette python-multipart
```

- [ ] **Step 4: 创建 data/documents 目录**

```bash
mkdir -p data/documents
touch data/documents/.gitkeep
```

- [ ] **Step 5: Commit**

```bash
git add config/agent.yml config/prompts.yml data/documents/.gitkeep
git commit -m "chore: update configs for generic enterprise agent"
```

---

### Task 2: 创建 SSE 事件发射器

**Files:**
- Create: `agent/event_emitter.py`

- [ ] **Step 1: 编写 event_emitter.py**

```python
import asyncio
import json
from typing import Any


class EventEmitter:
    """线程安全的事件发射器，桥接同步 Agent 与异步 SSE。"""

    def __init__(self):
        self._queue: asyncio.Queue[str] = asyncio.Queue()

    def push(self, event_type: str, data: dict[str, Any]) -> None:
        """同步线程安全地将事件推入异步队列。"""
        payload = f"event: {event_type}\ndata: {json.dumps(data, ensure_ascii=False)}\n\n"
        try:
            loop = asyncio.get_running_loop()
        except RuntimeError:
            return
        loop.call_soon_threadsafe(self._queue.put_nowait, payload)

    def emit_thinking(
        self, step: int, tool: str, args: dict, reasoning: str
    ) -> None:
        self.push("thinking", {
            "step": step,
            "tool": tool,
            "args": {k: v for k, v in args.items() if k != "config" and k != "type"},
            "reasoning": reasoning,
        })

    def emit_tool_result(
        self, step: int, tool: str, result: str, duration_ms: int
    ) -> None:
        self.push("tool_result", {
            "step": step,
            "tool": tool,
            "result": result,
            "duration_ms": duration_ms,
        })

    def emit_token(self, content: str) -> None:
        self.push("token", {"content": content})

    def emit_done(self) -> None:
        self.push("done", {})

    def emit_error(self, message: str) -> None:
        self.push("error", {"message": message})

    async def get_queue(self) -> asyncio.Queue[str]:
        return self._queue
```

- [ ] **Step 2: Commit**

```bash
git add agent/event_emitter.py
git commit -m "feat: add thread-safe EventEmitter for sync-to-async bridging"
```

---

### Task 3: 创建会话管理器

**Files:**
- Create: `server/session.py`

- [ ] **Step 1: 编写 session.py**

```python
import uuid
import random
from dataclasses import dataclass, field


@dataclass
class SessionState:
    session_id: str
    user_id: str
    messages: list[dict] = field(default_factory=list)
    extract_result: str = ""


class SessionManager:
    def __init__(self):
        self._sessions: dict[str, SessionState] = {}

    def create(self) -> SessionState:
        session_id = uuid.uuid4().hex
        user_id = str(random.randint(1001, 9999))
        state = SessionState(session_id=session_id, user_id=user_id)
        self._sessions[session_id] = state
        return state

    def get(self, session_id: str) -> SessionState | None:
        return self._sessions.get(session_id)

    def add_message(self, session_id: str, role: str, content: str) -> None:
        session = self.get(session_id)
        if session:
            session.messages.append({"role": role, "content": content})

    def get_conversation_text(self, session_id: str) -> str:
        session = self.get(session_id)
        if not session:
            return ""
        lines = []
        for msg in session.messages:
            role = "用户" if msg["role"] == "user" else "助手"
            lines.append(f"{role}: {msg['content']}")
        return "\n".join(lines)


session_manager = SessionManager()
```

- [ ] **Step 2: Commit**

```bash
git add server/session.py server/__init__.py
git commit -m "feat: add in-memory session manager"
```

---

### Task 4: 创建 FastAPI 应用入口

**Files:**
- Create: `server/main.py`

- [ ] **Step 1: 编写 server/main.py**

```python
import os
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles

from server.routes.chat import router as chat_router
from server.routes.documents import router as documents_router
from server.routes.extract import router as extract_router

app = FastAPI(title="企业知识问答 Agent")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(chat_router, prefix="/api")
app.include_router(documents_router, prefix="/api")
app.include_router(extract_router, prefix="/api")


@app.get("/api/health")
async def health():
    return {"status": "ok"}


# 生产模式：serve 前端静态文件
frontend_dist = os.path.join(os.path.dirname(__file__), "..", "frontend", "dist")
if os.path.exists(frontend_dist):
    app.mount("/", StaticFiles(directory=frontend_dist, html=True), name="static")
```

- [ ] **Step 2: Commit**

```bash
git add server/main.py server/routes/__init__.py
git commit -m "feat: add FastAPI app entry with CORS and route registration"
```

---

### Task 5: 重写提示词

**Files:**
- Modify: `prompts/main_prompt.txt`
- Create: `prompts/extract_prompt.txt`

- [ ] **Step 1: 重写 main_prompt.txt 为通用企业知识问答 Agent**

```text
你是企业知识问答智能助手，严格遵循 ReAct「思考→行动→观察→再思考」流程回答用户问题。

### 核心准则
1. 你没有任何企业内部知识，所有企业相关信息必须通过 rag_search 工具获取，严禁编造
2. 先分析用户问题核心，判断是否能直接回答；若需要知识库支持，调用 rag_search
3. 工具调用后再次判断信息是否充分：
   - 充分 → 整合生成专业回答
   - 不足 → 二次调用工具补充
   - 5 次调用后仍不足 → 坦诚告知用户
4. 工具入参必须与定义一致，字符串参数为纯文本

### 可用工具

1. rag_search：
   - 入参：query（检索词）
   - 出参：基于知识库资料的总结回答
   - 使用场景：需要企业文件、流程、规范等知识库信息时调用
   - 规则：query 为纯文本字符串，精准提炼核心检索词

2. knowledge_extract：
   - 入参：conversation_text（完整对话历史文本）
   - 出参：结构化的知识要点摘要（Markdown 格式）
   - 使用场景：用户要求整理/总结/提炼当前对话内容时调用
   - 规则：conversation_text 传入当前完整对话历史

3. get_knowledge_stats：
   - 入参：无
   - 出参：知识库文件数量、入库时间、主题覆盖等统计信息
   - 使用场景：用户询问知识库状态、有哪些资料时调用

4. get_current_time：
   - 入参：无
   - 出参：当前日期时间字符串
   - 使用场景：用户需要当前时间信息时调用

5. web_search：
   - 入参：query（搜索关键词）
   - 出参：互联网搜索结果摘要
   - 使用场景：知识库不足以回答，需要补充公开信息时调用

### 输出规则
1. 调用工具前先输出自然语言思考过程，说明「为什么调用、调用哪个、获取什么信息」
2. 信息充足后整合为流畅专业的中文回答
3. 回答基于知识库资料，引用时可注明来源文件
```

- [ ] **Step 2: 编写 extract_prompt.txt**

```text
你是知识管理专家，负责从对话历史中提炼结构化知识要点。

### 任务
分析以下用户与助手的对话，提炼出有价值的知识点。

### 对话内容
{conversation}

### 提炼规则
1. 识别对话中涉及的企业知识、流程、规则、常见问题等
2. 每个知识点一个段落，包含：主题标题 + 具体内容描述
3. 去重：相同主题的知识点合并
4. 仅提炼对话中明确讨论的内容，不添加未提及的信息
5. 用中文输出，使用 Markdown 格式

### 输出格式
## 知识要点提炼 — {date}

### 1. [主题标题]
[内容描述]

### 2. [主题标题]
[内容描述]
```

- [ ] **Step 3: Commit**

```bash
git add prompts/main_prompt.txt prompts/extract_prompt.txt
git commit -m "feat: rewrite prompts for generic enterprise Q&A agent"
```

---

### Task 6: 新增知识工具模块

**Files:**
- Create: `agent/tools/knowledge_tools.py`

- [ ] **Step 1: 编写 knowledge_tools.py**

```python
from datetime import datetime

from langchain_core.tools import tool
from langchain_core.prompts import PromptTemplate
from langchain_core.output_parsers import StrOutputParser

from model.factory import chat_model
from rag.vector_store import VectorStoreService
from utils.prompt_loader import load_extract_prompt
from utils.file_handler import list_with_allowed_type
from utils.path_tool import get_abs_path


@tool(description="从当前对话历史中提炼结构化知识要点，入参 conversation_text 为完整对话文本字符串")
def knowledge_extract(conversation_text: str) -> str:
    prompt = PromptTemplate.from_template(load_extract_prompt())
    chain = prompt | chat_model | StrOutputParser()
    date_str = datetime.now().strftime("%Y-%m-%d")
    return chain.invoke({"conversation": conversation_text, "date": date_str})


@tool(description="获取知识库统计信息，包括文件数量、文件列表等")
def get_knowledge_stats() -> str:
    docs_dir = get_abs_path("data/documents")
    files = list_with_allowed_type(docs_dir, ["pdf", "txt", "md", "csv"])

    vs = VectorStoreService()
    collection = vs.collection
    chunk_count = collection.count()

    lines = [
        f"知识库状态：",
        f"- 文档文件数量：{len(files)} 个",
        f"- 向量片段数量：{chunk_count} 个",
    ]
    if files:
        lines.append("- 文件列表：")
        for f in files:
            lines.append(f"  · {f}")
    else:
        lines.append("- 知识库暂无文件，建议上传企业文档后使用")

    return "\n".join(lines)
```

- [ ] **Step 2: Update utils/prompt_loader.py — 添加 load_extract_prompt**

```python
def load_extract_prompt(config_path: str | None = None):
    if config_path is None:
        config_path = prompts_conf["extract_prompt_path"]
    with open(get_abs_path(config_path), "r", encoding="utf-8") as f:
        return f.read()
```

在文件中已有函数下方添加。

- [ ] **Step 3: Update utils/file_handler.py — 添加 MD 支持**

```python
from langchain_community.document_loaders import UnstructuredMarkdownLoader

def md_loader(file_path: str) -> list:
    loader = UnstructuredMarkdownLoader(file_path)
    return loader.load()
```

在文件末尾添加。

- [ ] **Step 4: Commit**

```bash
git add agent/tools/knowledge_tools.py utils/prompt_loader.py utils/file_handler.py
git commit -m "feat: add knowledge_extract and get_knowledge_stats tools"
```

---

### Task 7: 重构 Agent 工具文件

**Files:**
- Modify: `agent/tools/agent_tools.py`

- [ ] **Step 1: 重写 agent_tools.py —— 5 个工具**

```python
import json
import os
from datetime import datetime

import requests
from langchain_core.tools import tool

from rag.rag_service import RagSummarizeService
from agent.tools.knowledge_tools import knowledge_extract, get_knowledge_stats
from utils.config_handler import agent_conf
from utils.logger_handler import logger

rag = RagSummarizeService()


@tool(description="从企业知识库中检索并总结资料。入参 query 为检索词字符串")
def rag_search(query: str) -> str:
    return rag.rag_summarize(query)


@tool(description="获取当前日期时间，无入参")
def get_current_time() -> str:
    return datetime.now().strftime("%Y-%m-%d %H:%M:%S")


@tool(description="通过 SerpAPI 搜索互联网获取补充信息。入参 query 为搜索关键词字符串")
def web_search(query: str) -> str:
    api_key = agent_conf.get("serpapi_key", "")
    if not api_key or api_key == "your_serpapi_key_here":
        return "网络搜索未配置 API Key，请联系管理员"

    url = "https://serpapi.com/search"
    params = {"q": query, "api_key": api_key, "engine": "google"}

    try:
        resp = requests.get(url, params=params, timeout=10)
        resp.raise_for_status()
        data = resp.json()
        results = data.get("organic_results", [])[:5]

        if not results:
            return f"未找到与 '{query}' 相关的搜索结果"

        lines = [f"搜索 '{query}' 的结果："]
        for i, r in enumerate(results, 1):
            lines.append(f"{i}. {r.get('title', '')}")
            lines.append(f"   {r.get('snippet', '')}")
            lines.append(f"   {r.get('link', '')}")
        return "\n".join(lines)
    except Exception as e:
        logger.error(f"web_search failed: {e}")
        return f"网络搜索失败：{str(e)}"


__all__ = ["rag_search", "knowledge_extract", "get_knowledge_stats",
           "get_current_time", "web_search"]
```

- [ ] **Step 2: Commit**

```bash
git add agent/tools/agent_tools.py
git commit -m "feat: refactor agent tools to 5 generic tools"
```

---

### Task 8: 重构中间件

**Files:**
- Modify: `agent/tools/middleware.py`

- [ ] **Step 1: 重写 middleware.py —— 接入 EventEmitter**

```python
import time
from typing import Callable

from langchain.agents.middleware import wrap_tool_call, before_model
from langchain.tools.tool_node import ToolCallRequest
from langchain_core.messages import ToolMessage
from langgraph.types import Command

from utils.logger_handler import logger


_event_emitter = None


def set_event_emitter(emitter):
    global _event_emitter
    _event_emitter = emitter


_step_counter = 0


def _next_step() -> int:
    global _step_counter
    _step_counter += 1
    return _step_counter


def reset_step_counter():
    global _step_counter
    _step_counter = 0


@wrap_tool_call
def monitor_tool(
    request: ToolCallRequest,
    handler: Callable[[ToolCallRequest], ToolMessage | Command],
) -> ToolMessage | Command:
    tool_name = request.tool_call["name"]
    args = request.tool_call.get("args", {})
    step = _next_step()

    logger.info(f"[tool monitor] 执行工具: {tool_name}, 参数: {args}")

    if _event_emitter and hasattr(_event_emitter, 'emit_thinking'):
        _event_emitter.emit_thinking(
            step=step,
            tool=tool_name,
            args=args,
            reasoning=f"Agent 决定调用 {tool_name} 工具",
        )

    start = time.time()
    try:
        result = handler(request)
        duration_ms = int((time.time() - start) * 1000)
        logger.info(f"[tool monitor] 工具 {tool_name} 调用成功 ({duration_ms}ms)")

        result_str = result.content if hasattr(result, 'content') else str(result)
        if _event_emitter and hasattr(_event_emitter, 'emit_tool_result'):
            _event_emitter.emit_tool_result(
                step=step,
                tool=tool_name,
                result=result_str[:2000],
                duration_ms=duration_ms,
            )

        return result
    except Exception as e:
        logger.error(f"[tool monitor] 工具 {tool_name} 调用失败: {e}")
        raise


@before_model
def log_before_model(state, runtime):
    msgs = state.get("messages", [])
    logger.info(f"[log_before_model] 即将调用模型，{len(msgs)} 条消息")
    if msgs:
        logger.debug(f"[log_before_model] 最后一条: {type(msgs[-1]).__name__}")
    return None
```

- [ ] **Step 2: Commit**

```bash
git add agent/tools/middleware.py
git commit -m "feat: refactor middleware with EventEmitter integration"
```

---

### Task 9: 更新 Agent 主类

**Files:**
- Modify: `agent/react_agent.py`

- [ ] **Step 1: 重写 react_agent.py**

```python
from langchain.agents import create_agent

from model.factory import chat_model
from utils.prompt_loader import load_system_prompt
from agent.tools.agent_tools import (
    rag_search, knowledge_extract, get_knowledge_stats,
    get_current_time, web_search,
)
from agent.tools.middleware import (
    monitor_tool, log_before_model, set_event_emitter, reset_step_counter,
)


class ReactAgent:
    def __init__(self):
        tools = [
            rag_search,
            knowledge_extract,
            get_knowledge_stats,
            get_current_time,
            web_search,
        ]
        self.agent = create_agent(
            model=chat_model,
            system_prompt=load_system_prompt(),
            tools=tools,
            middleware=[monitor_tool, log_before_model],
        )

    def execute_stream(self, query: str, event_emitter=None):
        if event_emitter:
            set_event_emitter(event_emitter)
        reset_step_counter()

        input_dict = {"messages": [{"role": "user", "content": query}]}
        for chunk in self.agent.stream(
            input_dict, stream_mode="values", context={}
        ):
            latest = chunk["messages"][-1]
            content = latest.content
            if content:
                text = content.strip()
                if text and event_emitter:
                    event_emitter.emit_token(text)
                if text:
                    yield text
```

- [ ] **Step 2: Commit**

```bash
git add agent/react_agent.py
git commit -m "feat: simplify ReactAgent with EventEmitter support"
```

---

### Task 10: 创建对话 API 路由 (SSE)

**Files:**
- Create: `server/routes/chat.py`

- [ ] **Step 1: 编写 chat.py**

```python
import asyncio
from fastapi import APIRouter, HTTPException
from pydantic import BaseModel
from sse_starlette.sse import EventSourceResponse

from server.session import session_manager
from agent.react_agent import ReactAgent
from agent.event_emitter import EventEmitter

router = APIRouter()
_agent = ReactAgent()


class ChatRequest(BaseModel):
    session_id: str
    message: str


@router.post("/chat")
async def chat(req: ChatRequest):
    session = session_manager.get(req.session_id)
    if not session:
        raise HTTPException(status_code=404, detail="会话不存在")

    emitter = EventEmitter()

    async def event_generator():
        loop = asyncio.get_event_loop()
        queue = await emitter.get_queue()
        session_manager.add_message(req.session_id, "user", req.message)

        full_response = ""

        def run_agent():
            nonlocal full_response
            for text in _agent.execute_stream(req.message, event_emitter=emitter):
                full_response += text

        try:
            await loop.run_in_executor(None, run_agent)
            session_manager.add_message(req.session_id, "assistant", full_response)
            emitter.emit_done()
        except Exception as e:
            emitter.emit_error(str(e))

        while True:
            data = await queue.get()
            yield data
            if '"done"' in data.replace(" ", "") or '"error"' in data.replace(" ", ""):
                break

    return EventSourceResponse(event_generator())
```

- [ ] **Step 2: Commit**

```bash
git add server/routes/chat.py
git commit -m "feat: add chat SSE endpoint with agent streaming"
```

---

### Task 11: 创建文档管理 API 路由

**Files:**
- Create: `server/routes/documents.py`

- [ ] **Step 1: 编写 documents.py**

```python
import os
import shutil
from fastapi import APIRouter, UploadFile, File, HTTPException

from rag.vector_store import VectorStoreService
from utils.file_handler import txt_loader, pdf_loader, md_loader, get_file_md5_hex
from utils.path_tool import get_abs_path

router = APIRouter()
vs = VectorStoreService()
DOCS_DIR = get_abs_path("data/documents")
MD5_FILE = os.path.join(DOCS_DIR, ".md5_records")


def _load_md5_records() -> dict:
    if not os.path.exists(MD5_FILE):
        return {}
    records = {}
    with open(MD5_FILE, "r", encoding="utf-8") as f:
        for line in f:
            line = line.strip()
            if line and "," in line:
                md5, fname = line.split(",", 1)
                records[md5] = fname
    return records


def _save_md5_record(md5: str, fname: str):
    with open(MD5_FILE, "a", encoding="utf-8") as f:
        f.write(f"{md5},{fname}\n")


def _remove_md5_record(fname: str):
    records = _load_md5_records()
    records = {k: v for k, v in records.items() if v != fname}
    with open(MD5_FILE, "w", encoding="utf-8") as f:
        for md5, fn in records.items():
            f.write(f"{md5},{fn}\n")


LOADERS = {
    ".pdf": pdf_loader,
    ".txt": txt_loader,
    ".md": md_loader,
}


@router.post("/upload")
async def upload_document(file: UploadFile = File(...)):
    ext = os.path.splitext(file.filename or "")[1].lower()
    if ext not in LOADERS:
        raise HTTPException(400, f"不支持的文件类型: {ext}，支持: {list(LOADERS.keys())}")

    content = await file.read()
    save_path = os.path.join(DOCS_DIR, file.filename)
    with open(save_path, "wb") as f:
        f.write(content)

    md5 = get_file_md5_hex(save_path)
    records = _load_md5_records()
    if md5 in records:
        os.remove(save_path)
        return {"status": "skipped", "message": f"文件 {file.filename} 已存在（MD5 重复）"}

    try:
        loader = LOADERS[ext]
        docs = loader(save_path)
        vs.add_documents(docs)
        _save_md5_record(md5, file.filename)
        return {"status": "ok", "message": f"文件 {file.filename} 已入库", "chunks": len(docs)}
    except Exception as e:
        if os.path.exists(save_path):
            os.remove(save_path)
        raise HTTPException(500, f"文件处理失败: {str(e)}")


@router.get("/documents")
async def list_documents():
    files = []
    if os.path.exists(DOCS_DIR):
        for f in os.listdir(DOCS_DIR):
            path = os.path.join(DOCS_DIR, f)
            if os.path.isfile(path) and not f.startswith("."):
                size = os.path.getsize(path)
                files.append({"name": f, "size": size, "size_display": f"{size / 1024:.1f} KB"})
    return {"files": files}


@router.delete("/documents/{filename}")
async def delete_document(filename: str):
    file_path = os.path.join(DOCS_DIR, filename)
    if not os.path.exists(file_path):
        raise HTTPException(404, "文件不存在")

    os.remove(file_path)
    _remove_md5_record(filename)
    vs.collection.delete(where={"source": filename})
    return {"status": "ok", "message": f"文件 {filename} 已删除"}
```

- [ ] **Step 2: 检查 vector_store 是否有 add_documents 方法**

确认 `rag/vector_store.py` 中存在 `add_documents` 方法或等价方法（读取 `load_document`）。若无则添加：

```python
def add_documents(self, docs):
    self.collection.add_documents(docs)
```

- [ ] **Step 3: Commit**

```bash
git add server/routes/documents.py utils/file_handler.py rag/vector_store.py
git commit -m "feat: add document upload/list/delete API routes"
```

---

### Task 12: 创建知识萃取 API 路由

**Files:**
- Create: `server/routes/extract.py`

- [ ] **Step 1: 编写 extract.py**

```python
from datetime import datetime
from fastapi import APIRouter, HTTPException
from fastapi.responses import Response
from pydantic import BaseModel

from server.session import session_manager
from agent.tools.knowledge_tools import knowledge_extract

router = APIRouter()


class ExtractRequest(BaseModel):
    session_id: str


@router.post("/extract")
async def extract_knowledge(req: ExtractRequest):
    session = session_manager.get(req.session_id)
    if not session:
        raise HTTPException(status_code=404, detail="会话不存在")

    conversation = session_manager.get_conversation_text(req.session_id)
    if not conversation.strip():
        raise HTTPException(status_code=400, detail="当前对话无内容可萃取")

    result = knowledge_extract.invoke({"conversation_text": conversation})
    session.extract_result = result
    return {"result": result}


@router.get("/extract/download")
async def download_extract(session_id: str):
    session = session_manager.get(session_id)
    if not session or not session.extract_result:
        raise HTTPException(status_code=404, detail="没有萃取结果，请先执行萃取")

    date_str = datetime.now().strftime("%Y-%m-%d")
    filename = f"knowledge-{date_str}.txt"

    return Response(
        content=session.extract_result,
        media_type="text/plain; charset=utf-8",
        headers={"Content-Disposition": f'attachment; filename="{filename}"'},
    )
```

- [ ] **Step 2: Commit**

```bash
git add server/routes/extract.py
git commit -m "feat: add knowledge extraction and TXT download API routes"
```

---

### Task 13: 添加会话创建端点

**Files:**
- Modify: `server/routes/chat.py`

- [ ] **Step 1: 在 chat.py 末尾添加 session 端点**

```python
@router.post("/session")
async def create_session():
    session = session_manager.create()
    return {
        "session_id": session.session_id,
        "user_id": session.user_id,
    }
```

- [ ] **Step 2: Commit**

```bash
git add server/routes/chat.py
git commit -m "feat: add POST /api/session endpoint"
```

---

### Task 14: 搭建 Vue 前端脚手架

**Files:**
- Create: `frontend/package.json`
- Create: `frontend/vite.config.ts`
- Create: `frontend/index.html`

- [ ] **Step 1: 编写 package.json**

```json
{
  "name": "enterprise-agent-frontend",
  "private": true,
  "version": "1.0.0",
  "type": "module",
  "scripts": {
    "dev": "vite",
    "build": "vite build",
    "preview": "vite preview"
  },
  "dependencies": {
    "vue": "^3.4.0",
    "pinia": "^2.1.0"
  },
  "devDependencies": {
    "@vitejs/plugin-vue": "^5.0.0",
    "typescript": "^5.4.0",
    "vite": "^5.4.0",
    "vue-tsc": "^2.0.0"
  }
}
```

- [ ] **Step 2: 编写 vite.config.ts**

```typescript
import { defineConfig } from 'vite'
import vue from '@vitejs/plugin-vue'

export default defineConfig({
  plugins: [vue()],
  server: {
    port: 5173,
    proxy: {
      '/api': {
        target: 'http://localhost:8000',
        changeOrigin: true,
      }
    }
  }
})
```

- [ ] **Step 3: 编写 index.html**

```html
<!DOCTYPE html>
<html lang="zh-CN">
<head>
  <meta charset="UTF-8" />
  <meta name="viewport" content="width=device-width, initial-scale=1.0" />
  <title>企业知识问答 Agent</title>
</head>
<body>
  <div id="app"></div>
  <script type="module" src="/src/main.ts"></script>
</body>
</html>
```

- [ ] **Step 4: Commit**

```bash
git add frontend/package.json frontend/vite.config.ts frontend/index.html
git commit -m "feat: scaffold Vue 3 + Vite frontend project"
```

---

### Task 15: 创建 Pinia Store

**Files:**
- Create: `frontend/src/stores/chat.ts`

- [ ] **Step 1: 编写 chat.ts**

```typescript
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
```

- [ ] **Step 2: Commit**

```bash
git add frontend/src/stores/chat.ts
git commit -m "feat: add Pinia chat store with SSE handling and extract support"
```

---

### Task 16: 创建 Vue 入口和全局样式

**Files:**
- Create: `frontend/src/main.ts`
- Create: `frontend/src/styles/main.css`

- [ ] **Step 1: 编写 main.ts**

```typescript
import { createApp } from 'vue'
import { createPinia } from 'pinia'
import App from './App.vue'
import './styles/main.css'

const app = createApp(App)
app.use(createPinia())
app.mount('#app')
```

- [ ] **Step 2: 编写 main.css**

```css
* {
  margin: 0;
  padding: 0;
  box-sizing: border-box;
}

:root {
  --bg-primary: #f5f5f5;
  --bg-white: #ffffff;
  --bg-hover: #f0f0f0;
  --border-color: #e0e0e0;
  --text-primary: #333333;
  --text-secondary: #666666;
  --text-muted: #999999;
  --accent: #4a90d9;
  --accent-hover: #357abd;
  --user-bubble: #e3f2fd;
  --assistant-bubble: #f5f5f5;
  --success: #52c41a;
  --warning: #faad14;
  --error: #f5222d;
  --radius: 8px;
  --shadow: 0 2px 8px rgba(0, 0, 0, 0.08);
  --sidebar-width: 320px;
  --header-height: 48px;
}

body {
  font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", Roboto, sans-serif;
  color: var(--text-primary);
  background: var(--bg-primary);
  height: 100vh;
  overflow: hidden;
}

#app {
  height: 100vh;
  display: flex;
  flex-direction: column;
}

button {
  cursor: pointer;
  border: none;
  border-radius: var(--radius);
  padding: 8px 16px;
  font-size: 14px;
  transition: background 0.2s;
}

input, textarea {
  border: 1px solid var(--border-color);
  border-radius: var(--radius);
  padding: 8px 12px;
  font-size: 14px;
  outline: none;
  font-family: inherit;
}

input:focus, textarea:focus {
  border-color: var(--accent);
}
```

- [ ] **Step 3: Commit**

```bash
git add frontend/src/main.ts frontend/src/styles/main.css
git commit -m "feat: add Vue entry point and global styles"
```

---

### Task 17: 创建 MessageBubble 组件

**Files:**
- Create: `frontend/src/components/MessageBubble.vue`

- [ ] **Step 1: 编写 MessageBubble.vue**

```vue
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
```

- [ ] **Step 2: Commit**

```bash
git add frontend/src/components/MessageBubble.vue
git commit -m "feat: add MessageBubble component"
```

---

### Task 18: 创建 ProcessPanel 组件

**Files:**
- Create: `frontend/src/components/ProcessPanel.vue`

- [ ] **Step 1: 编写 ProcessPanel.vue**

```vue
<script setup lang="ts">
import { computed } from 'vue'
import type { ProcessStep } from '../stores/chat'

const props = defineProps<{
  steps: ProcessStep[]
}>()

const emit = defineEmits<{
  toggle: []
}>()

const visible = defineModel<boolean>('visible', { default: false })

const toolLabels: Record<string, string> = {
  rag_search: 'RAG 知识库检索',
  knowledge_extract: '知识萃取',
  get_knowledge_stats: '知识库统计',
  get_current_time: '获取当前时间',
  web_search: '网络搜索',
}

function toolLabel(tool: string) {
  return toolLabels[tool] || tool
}

function formatDuration(ms: number) {
  if (ms < 1000) return `${ms}ms`
  return `${(ms / 1000).toFixed(1)}s`
}
</script>

<template>
  <div class="process-panel">
    <button class="toggle-btn" @click="visible = !visible">
      {{ visible ? '▾' : '▸' }} Agent 思考过程 ({{ steps.length }} 步)
    </button>
    <div v-if="visible" class="steps">
      <div v-if="steps.length === 0" class="empty">暂无步骤</div>
      <div v-for="s in steps" :key="s.step" :class="['step', s.status]">
        <div class="step-header">
          <span class="step-icon">{{ s.status === 'running' ? '🔄' : '✅' }}</span>
          <span class="step-tool">{{ toolLabel(s.tool) }}</span>
          <span v-if="s.duration_ms" class="step-duration">{{ formatDuration(s.duration_ms) }}</span>
        </div>
        <div class="step-args" v-if="s.args && Object.keys(s.args).length">
          参数: {{ JSON.stringify(s.args) }}
        </div>
        <div class="step-result" v-if="s.result">
          {{ s.result.length > 300 ? s.result.slice(0, 300) + '...' : s.result }}
        </div>
      </div>
    </div>
  </div>
</template>

<style scoped>
.process-panel {
  border-top: 1px solid var(--border-color);
  background: var(--bg-white);
}
.toggle-btn {
  width: 100%;
  padding: 8px 16px;
  background: none;
  border: none;
  border-radius: 0;
  text-align: left;
  font-size: 13px;
  color: var(--text-secondary);
  cursor: pointer;
}
.toggle-btn:hover {
  background: var(--bg-hover);
}
.steps {
  padding: 0 16px 12px;
}
.empty {
  color: var(--text-muted);
  font-size: 13px;
}
.step {
  padding: 8px 0;
  border-bottom: 1px solid var(--border-color);
}
.step:last-child {
  border-bottom: none;
}
.step-header {
  display: flex;
  align-items: center;
  gap: 6px;
  font-size: 13px;
  font-weight: 500;
}
.step-icon {
  font-size: 14px;
}
.step-duration {
  margin-left: auto;
  color: var(--text-muted);
  font-size: 12px;
}
.step-args {
  font-size: 12px;
  color: var(--text-secondary);
  margin-top: 4px;
  padding-left: 20px;
}
.step-result {
  font-size: 12px;
  color: var(--text-primary);
  margin-top: 4px;
  padding: 6px 8px;
  background: var(--bg-primary);
  border-radius: 4px;
  white-space: pre-wrap;
  word-break: break-word;
}
.step.running .step-header {
  color: var(--accent);
}
</style>
```

- [ ] **Step 2: Commit**

```bash
git add frontend/src/components/ProcessPanel.vue
git commit -m "feat: add ProcessPanel component for agent step visualization"
```

---

### Task 19: 创建 ChatPanel 组件

**Files:**
- Create: `frontend/src/components/ChatPanel.vue`

- [ ] **Step 1: 编写 ChatPanel.vue**

```vue
<script setup lang="ts">
import { ref } from 'vue'
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
  // 滚动到底部
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

import { nextTick, watch } from 'vue'
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
```

- [ ] **Step 2: Commit**

```bash
git add frontend/src/components/ChatPanel.vue
git commit -m "feat: add ChatPanel component with message list and input"
```

---

### Task 20: 创建 ExtractTab 组件

**Files:**
- Create: `frontend/src/components/ExtractTab.vue`

- [ ] **Step 1: 编写 ExtractTab.vue**

```vue
<script setup lang="ts">
import { useChatStore } from '../stores/chat'

const store = useChatStore()
</script>

<template>
  <div class="extract-tab">
    <button
      class="extract-btn"
      @click="store.doExtract"
      :disabled="store.isStreaming || store.messages.length === 0"
    >
      🔍 从对话中萃取知识
    </button>

    <div v-if="store.extractResult" class="extract-header">
      <h4>萃取结果</h4>
      <button class="download-btn" @click="store.downloadTxt">📥 导出 TXT</button>
    </div>

    <div v-if="store.extractResult" class="extract-content">
      {{ store.extractResult }}
    </div>
    <div v-else class="extract-empty">
      点击按钮将当前对话内容提炼为知识要点
    </div>
  </div>
</template>

<style scoped>
.extract-tab {
  padding: 12px;
}
.extract-btn {
  width: 100%;
  background: var(--accent);
  color: white;
  font-weight: 500;
  padding: 10px;
}
.extract-btn:hover:not(:disabled) {
  background: var(--accent-hover);
}
.extract-btn:disabled {
  opacity: 0.6;
  cursor: not-allowed;
}
.extract-header {
  display: flex;
  justify-content: space-between;
  align-items: center;
  margin-top: 16px;
}
.extract-header h4 {
  font-size: 14px;
}
.download-btn {
  background: var(--success);
  color: white;
  font-size: 12px;
  padding: 4px 12px;
}
.extract-content {
  margin-top: 8px;
  font-size: 13px;
  line-height: 1.8;
  white-space: pre-wrap;
  background: var(--bg-primary);
  border-radius: var(--radius);
  padding: 12px;
  max-height: 400px;
  overflow-y: auto;
}
.extract-empty {
  margin-top: 12px;
  color: var(--text-muted);
  font-size: 13px;
  text-align: center;
}
</style>
```

- [ ] **Step 2: Commit**

```bash
git add frontend/src/components/ExtractTab.vue
git commit -m "feat: add ExtractTab component with TXT export"
```

---

### Task 21: 创建 KnowledgePanel 组件

**Files:**
- Create: `frontend/src/components/KnowledgePanel.vue`

- [ ] **Step 1: 编写 KnowledgePanel.vue**

```vue
<script setup lang="ts">
import { ref, onMounted } from 'vue'
import ExtractTab from './ExtractTab.vue'

const activeTab = ref<'upload' | 'files' | 'extract'>('upload')
const files = ref<{ name: string; size_display: string }[]>([])
const uploadStatus = ref('')

async function loadFiles() {
  const resp = await fetch('/api/documents')
  const data = await resp.json()
  files.value = data.files
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
  await fetch(`/api/documents/${filename}`, { method: 'DELETE' })
  loadFiles()
}

onMounted(loadFiles)
</script>

<template>
  <div class="knowledge-panel">
    <div class="tabs">
      <button
        v-for="tab in [
          { key: 'upload' as const, label: '📤 上传' },
          { key: 'files' as const, label: '📁 文件' },
          { key: 'extract' as const, label: '💡 萃取' },
        ]"
        :key="tab.key"
        :class="['tab', { active: activeTab === tab.key }]"
        @click="activeTab = tab.key"
      >
        {{ tab.label }}
      </button>
    </div>

    <div class="tab-content">
      <!-- 上传 Tab -->
      <div v-if="activeTab === 'upload'" class="upload-area">
        <label class="upload-label">
          选择文件 (PDF/TXT/MD)
          <input type="file" accept=".pdf,.txt,.md" @change="handleUpload" hidden />
        </label>
        <p v-if="uploadStatus" class="upload-status">{{ uploadStatus }}</p>
      </div>

      <!-- 文件 Tab -->
      <div v-if="activeTab === 'files'" class="file-list">
        <div v-if="files.length === 0" class="empty">暂无文件</div>
        <div v-for="f in files" :key="f.name" class="file-item">
          <span class="file-name">📄 {{ f.name }}</span>
          <span class="file-size">{{ f.size_display }}</span>
          <button class="delete-btn" @click="handleDelete(f.name)">✕</button>
        </div>
      </div>

      <!-- 萃取 Tab -->
      <div v-if="activeTab === 'extract'">
        <ExtractTab />
      </div>
    </div>
  </div>
</template>

<style scoped>
.knowledge-panel {
  width: var(--sidebar-width);
  height: 100%;
  background: var(--bg-white);
  border-right: 1px solid var(--border-color);
  display: flex;
  flex-direction: column;
  overflow-y: auto;
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
```

- [ ] **Step 2: Commit**

```bash
git add frontend/src/components/KnowledgePanel.vue
git commit -m "feat: add KnowledgePanel with upload/files/extract tabs"
```

---

### Task 22: 创建 App.vue 根组件

**Files:**
- Create: `frontend/src/App.vue`

- [ ] **Step 1: 编写 App.vue**

```vue
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
```

- [ ] **Step 2: Commit**

```bash
git add frontend/src/App.vue
git commit -m "feat: add App.vue root layout component"
```

---

### Task 23: 清理旧文件与集成测试

**Files:**
- Delete: `app.py`
- Delete: `prompts/report_prompt.txt`
- Delete: `data/external/records.csv`

- [ ] **Step 1: 删除旧文件**

```bash
rm app.py
rm prompts/report_prompt.txt
rm data/external/records.csv
```

- [ ] **Step 2: 安装前端依赖**

```bash
cd frontend
npm install
```

- [ ] **Step 3: 验证后端可启动**

```bash
cd ..
python -c "from server.main import app; print('FastAPI app OK')"
```

预期：`FastAPI app OK`

- [ ] **Step 4: 验证前端可构建**

```bash
cd frontend
npx vite build
```

预期：构建成功，`dist/` 目录生成

- [ ] **Step 5: 验证 Agent 可初始化**

```bash
cd ..
python -c "from agent.react_agent import ReactAgent; a = ReactAgent(); print('Agent OK')"
```

预期：`Agent OK`（可能输出 Chroma 初始化日志）

- [ ] **Step 6: Commit**

```bash
git add -A
git commit -m "chore: remove old Streamlit files, verify integration"
```

---

## 自审查

1. **Spec coverage**: 逐一对照设计文档：
   - ✅ 架构总览 → Tasks 4-12 覆盖后端所有路由和中间件
   - ✅ SSE 事件协议 → Task 2 (EventEmitter) + Task 15 (Store SSE解析)
   - ✅ 5 个工具 → Tasks 6-7
   - ✅ 知识萃取双路径 → Task 12 (API) + Task 6 (tool)
   - ✅ 会话管理 → Task 3 + Task 13
   - ✅ 中间件变更 → Task 8
   - ✅ 配置更新 → Task 1
   - ✅ 提示词重写 → Task 5
   - ✅ 前端组件 → Tasks 14-22
   - ✅ 移除旧组件 → Task 23

2. **Placeholder scan**: 无 "TBD"/"TODO"/"implement later" 等占位符。所有步骤含具体代码。

3. **Type consistency**: 
   - `EventEmitter` 接口在 Task 2 定义，Task 9 (Agent) 和 Task 10 (chat route) 使用一致
   - Store 类型 (`Message`, `ProcessStep`, `ProcessPanel.vue` 导入) 在 Task 15 定义，各组件引用一致
   - API 端点路径：`/api/session`, `/api/chat`, `/api/upload`, `/api/documents`, `/api/extract`, `/api/extract/download` 前后端一致
   - SSE 事件类型 `thinking`, `tool_result`, `token`, `done`, `error` 在 EventEmitter 和 Store 中一致
