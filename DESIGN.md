# 智扫通机器人智能客服 — 详细设计文档

## 一、项目概述

本项目是一个基于 **LangChain ReAct Agent** 架构的智能客服系统，面向扫地/扫拖机器人产品线，具备 **RAG 知识库问答** 和 **用户使用报告自动生成** 两大核心能力。前端使用 Streamlit 构建，后端 LLM 采用通义千问（qwen3-max），向量存储使用 Chroma。

---

## 二、架构总览

```
┌─────────────────────────────────────────────────────────┐
│                    Streamlit UI (app.py)                 │
├─────────────────────────────────────────────────────────┤
│                    ReactAgent (agent/)                   │
│  ┌──────────────┬────────────────┬──────────────────┐   │
│  │  Middleware   │   7 Tools      │  Dynamic Prompt  │   │
│  │  · monitor    │                 │  · main_prompt   │   │
│  │  · log        │                 │  · report_prompt │   │
│  │  · switch     │                 │                  │   │
│  └──────────────┴────────────────┴──────────────────┘   │
├─────────────────────────────────────────────────────────┤
│  RAG Service (rag/)          │  Model Factory (model/)   │
│  · VectorStore (Chroma)      │  · ChatTongyi (LLM)       │
│  · Summarize Chain           │  · DashScope (Embedding)  │
├─────────────────────────────────────────────────────────┤
│  Utils (utils/) — 配置/文件/日志/路径/提示词加载          │
└─────────────────────────────────────────────────────────┘
```

**设计原则**：

- **分层解耦**：UI 层只负责渲染，Agent 层管理对话逻辑，RAG 层专注检索与总结，模型层统一管理模型实例。
- **配置外置**：所有可变参数（模型名、路径、阈值）集中在 `config/*.yml`，修改时无需动代码。
- **中间件模式**：用 LangChain 的中间件机制实现横切关注点（日志、监控、动态提示词），避免侵入业务逻辑。

---

## 三、目录结构

```
AgentDemo/
├── app.py                     # Streamlit 前端入口
├── agent/
│   ├── react_agent.py         # ReAct Agent 主类，组装 Agent 实例
│   └── tools/
│       ├── agent_tools.py     # 7 个 LangChain Tool 定义
│       └── middleware.py      # 3 个中间件（监控/日志/动态提示词）
├── rag/
│   ├── rag_service.py         # RAG 检索 + LLM 总结服务
│   └── vector_store.py        # Chroma 向量存储管理（入库/检索）
├── model/
│   └── factory.py             # 模型工厂（LLM + Embedding 实例化）
├── utils/
│   ├── config_handler.py      # YAML 配置加载器
│   ├── file_handler.py        # 文件处理（MD5、TXT/PDF 加载）
│   ├── logger_handler.py      # 日志配置（控制台 + 文件双输出）
│   ├── path_tool.py           # 项目根路径计算
│   └── prompt_loader.py       # 提示词模板文件加载
├── config/
│   ├── agent.yml              # Agent 相关配置
│   ├── chroma.yml             # 向量库相关配置
│   ├── prompts.yml            # 提示词文件路径配置
│   └── rag.yml                # RAG 模型配置
├── prompts/
│   ├── main_prompt.txt        # 主对话提示词
│   ├── rag_summarize.txt      # RAG 总结提示词
│   └── report_prompt.txt      # 报告生成提示词
├── data/                      # 知识库源文件 + 外部数据
├── chroma_db/                 # Chroma 持久化目录
└── logs/                      # 运行日志
```

---

## 四、模块详细设计

### 4.1 前端入口 — `app.py`

| 元素 | 说明 |
|------|------|
| **功能** | Streamlit 单页应用，提供对话 UI |
| **状态管理** | 使用 `st.session_state` 管理 Agent 单例和消息历史 |

#### 关键设计决策

**为什么用 `st.session_state` 而非全局变量？**

Streamlit 的渲染模型是"每次交互重新执行整个脚本"。普通 Python 变量在两次请求间不会保留。`st.session_state` 是 Streamlit 提供的跨 rerun 持久化机制，保证 Agent 实例和对话历史在用户会话期间存活。

**为什么 Agent 采用懒加载单例？**

```python
if "agent" not in st.session_state:
    st.session_state.agent = ReactAgent()
```

Agent 初始化涉及模型连接、工具注册、中间件绑定，成本较高。单例模式确保整个会话只初始化一次，避免每次 rerun 重复创建。

**为什么用流式输出 `write_stream`？**

逐字符渲染（0.01s 延时）模拟打字效果，显著改善长响应时的用户等待体验——用户看到内容"正在生成"而非空白等待。

---

### 4.2 ReAct Agent — `agent/react_agent.py`

#### 类 `ReactAgent`

| 成员 | 说明 |
|------|------|
| `__init__()` | 调用 `create_agent()` 组装 Agent，传入模型、系统提示词、工具列表、中间件 |
| `excute_stream(query)` | 流式执行对话，`yield` 每个 chunk 的最新消息内容 |

#### 关键设计决策

**为什么用 `create_agent()` 而非手动编写 ReAct 循环？**

LangChain 的 `create_agent()` 封装了 ReAct 模式的标准实现：思考 → 行动 → 观察 → 再思考。手动实现需要考虑工具调用解析、异常处理、最大迭代次数等边界情况，而框架已内置这些能力。项目中 Agent 只需关注"提供哪些工具"和"如何切换提示词"。

**为什么用 `stream_mode="values"`？**

`values` 模式在每次状态更新时返回完整的消息列表，而非仅返回增量。这简化了 UI 渲染——`chunk["messages"][-1]` 总是获取最新消息，无需拼接增量内容。

**`context` 参数的设计意图？**

```python
self.agent.stream(input_dict, context={"report": False})
```

这是一个"运行时上下文"机制，在 Agent 执行过程中可被中间件修改（`context["report"] = True`），进而触发动态提示词切换。它解决了**请求级别的状态传递**问题——不需要在工具参数中显式传递状态，而是通过框架的上下文机制隐式传递。

---

### 4.3 工具定义 — `agent/tools/agent_tools.py`

#### 7 个 Tool 的用途与设计理由

| 工具 | 用途 | 设计理由 |
|------|------|----------|
| `rag_summarize(query)` | RAG 检索 + 总结，回答产品知识类问题 | 知识库文档的语义检索，解决 LLM 对特定产品知识不熟悉的问题 |
| `get_weather(city)` | 获取城市天气（模拟） | 演示外部 API 调用模式。实际场景中可替换为真实天气 API，用于根据天气推荐使用模式（如雨天提醒处理潮湿地面） |
| `get_user_location()` | 获取用户城市（随机模拟） | 为后续个性化服务预留。实际场景应接入 IP 定位或用户注册信息 |
| `get_user_id()` | 获取用户 ID（随机模拟） | 报告生成流程的**入口标识**。随机值仅为演示，实际应接入登录系统 |
| `get_current_month()` | 获取当前月份（随机模拟） | 为 `fetch_external_data` 提供查询条件。随机值仅为演示，实际应返回系统时间 |
| `fetch_external_data(user_id, month)` | 查询用户使用记录 | 从 CSV 读取特定用户在特定月份的使用数据，为报告生成提供事实依据 |
| `fill_context_for_report()` | 触发报告模式 | **关键设计**：不直接产生用户可见的输出，而是通过中间件设置 `context["report"] = True`，切换后续的 LLM 提示词 |

**为什么用 `fill_context_for_report` 作为"开关工具"而非直接在 `fetch_external_data` 后切换？**

这是一种**关注点分离**设计：

1. 工具职责单一——`fill_context_for_report` 只做一件事：标记状态
2. 报告模式需要在"数据收集完成"这个时间点切换，而非在某个具体工具中硬编码
3. 提示词切换逻辑在中间件中集中管理，而非分散在多个工具里

Agent 按提示词指令在报告流程中自动调用此工具，形成清晰的模式切换边界。

**为什么模拟数据工具（用户 ID、位置、月份）使用随机值？**

这是一个**演示/开发阶段的设计**。真实部署时，这些工具应接入：
- `get_user_id()` → 登录态/session
- `get_user_location()` → IP 定位或用户信息
- `get_current_month()` → `datetime.now()`

当前随机值允许在不依赖外部系统的情况下完整演示 Agent 的推理和工具编排能力。

---

### 4.4 中间件 — `agent/tools/middleware.py`

这是项目中最精巧的设计。三个中间件分别处理：工具调用监控、LLM 调用日志、动态提示词切换。

#### `monitor_tool` — 工具调用监控器

| 属性 | 说明 |
|------|------|
| **装饰器** | `@wrap_tool_call` |
| **触发时机** | 每次工具调用前后 |

**工作流程**：

1. **调用前**：记录 `[开始调用工具: {name}] 参数: {args}`
2. **执行工具**：`handler(request)` — 实际调用目标工具
3. **成功时**：记录 `[工具调用成功: {name}]`
4. **失败时**：记录 `[工具调用失败: {name}] 错误: {error}`
5. **特殊逻辑**：如果工具名是 `fill_context_for_report`，在调用后将 `context["report"]` 设为 `True`

**为什么把 `context["report"]` 的设置放在这里而非工具内部？**

这是**控制反转**的体现。`fill_context_for_report` 工具本身不感知 `context` 机制的存在——它只是一个空操作。中间件观察工具调用事件并做出反应。这样做的好处是：

- 如果需要改变报告模式的触发方式（比如改为检测多个条件），只需修改中间件
- 工具保持可测试和可复用（不依赖特定的运行时上下文）

#### `log_before_model` — LLM 调用日志

| 属性 | 说明 |
|------|------|
| **装饰器** | `@before_model` |
| **触发时机** | 每次模型调用前 |

记录消息数量和最后一条消息的角色/内容，用于调试 Agent 的推理过程。始终返回 `None`（不修改模型输入）。

**为什么放在 `@before_model` 而非 `@after_model`？**

`@before_model` 在模型调用前触发，可以记录"Agent 准备发给模型什么"。这对于调试至关重要——因为 ReAct Agent 的模型调用频繁（每轮思考一次），追踪输入能验证系统提示词是否正确切换、上下文是否完整。

#### `report_prompt_switch` — 动态提示词切换

| 属性 | 说明 |
|------|------|
| **装饰器** | `@dynamic_prompt` |
| **触发时机** | 每次构建系统提示词前 |

**核心逻辑**：

```python
if request.runtime.context.get("report", False):
    return load_report_prompt()   # 报告模式提示词
else:
    return load_system_prompt()   # 主对话提示词
```

这是实现"双模式 Agent"的关键。同一个 Agent 实例，根据运行时上下文在两种行为模式间切换：

- **客服模式**：回答用户产品问题、处理售后咨询
- **报告模式**：收集用户数据 + RAG 知识，生成结构化报告

**为什么用动态提示词而非两个独立的 Agent？**

两个 Agent 方案的问题：
1. 需要显式地切换 Agent 实例，增加状态管理复杂度
2. 工具集共享（RAG 在两种模式下都需要）
3. 中间件（日志、监控）需要重复配置

动态提示词方案用一个 Agent 承载两种行为，通过上下文标记控制行为模式，更简洁。

---

### 4.5 RAG 服务 — `rag/rag_service.py`

#### 类 `RagSummarizeService`

| 成员 | 说明 |
|------|------|
| `__init__()` | 初始化向量存储、检索器、提示词模板和 LCEL Chain |
| `retriever_docs(query)` | 调用检索器获取 top-k 相关文档 |
| `rag_summarize(query)` | 完整流水线：检索 → 拼接 context → LLM 总结 → 返回结果 |

#### 关键设计决策

**为什么用 LCEL（LangChain Expression Language）构建 Chain？**

```python
self.chain = self.prompt_template | print_prompt | self.model | StrOutputParser()
```

LCEL 的管道语法提供了声明式组合方式：
- `|` 操作符直观表达数据流向
- 每个环节职责清晰：模板渲染 → 调试输出 → 模型推理 → 字符串解析
- 自动支持流式输出（`StrOutputParser` 原生支持 `stream`）
- `print_prompt` 是调试钩子：每次调用时在控制台打印完整 prompt，方便排查总结质量

**为什么在 context 中同时包含 `page_content` 和 `metadata`？**

`metadata` 包含文档来源信息（文件名、路径等）。在总结时，LLM 可以引用来源增强可信度。同时，metadata 中的标题/分类信息帮助 LLM 理解知识片段的上下文。

**为什么使用 `PromptTemplate.from_template()` 而非 `ChatPromptTemplate`？**

因为只有简单的文本输入（`{input}` 和 `{context}`），不需要复杂的消息角色编排。`from_template()` 是最轻量的方式。

---

### 4.6 向量存储 — `rag/vector_store.py`

#### 类 `VectorStoreService`

| 成员 | 说明 |
|------|------|
| `__init__()` | 初始化 Chroma 集合 + 文本分割器 |
| `get_retriever(k)` | 返回检索器，默认 top-3 |
| `load_document()` | 文档入库：MD5 去重 → 加载 → 分割 → 入库 → 记录 MD5 |

#### 关键设计决策

**为什么用 Chroma 而非 FAISS/其他向量库？**

- Chroma 原生支持持久化（`persist_directory`），无需手动 save/load
- Python 原生实现，Windows 下安装无编译依赖问题
- 内置 collection 管理，支持元数据过滤
- 与 LangChain 集成成熟（`langchain_chroma`）

**为什么 MD5 去重而非用 Chroma 自身的 upsert？**

Chroma 的文档 ID 管理需要调用方自行生成稳定 ID。MD5 去重方案的优势：

1. **基于内容去重**：同一文件无论何时刻入库，MD5 相同则跳过
2. **增量加载**：新增文件自动识别并加载
3. **`md5.text` 持久化**：即使重建 Chroma 实例，已处理文件不会重复入库

**分块策略（`chunk_size=200, chunk_overlap=20`）的设计考量**：

- `chunk_size=200`：足够容纳一个完整的问答对（Q 约 50 字 + A 约 150 字），同时足够小以保证检索精度
- `chunk_overlap=20`：防止关键信息在分块边界处被截断，但不过度重叠以免搜索结果冗余
- `separators`：先按自然段落分割，再按句子标点分割，保证语义完整性

**为什么 embedding 模型选择 `text-embedding-v4`？**

与 `ChatTongyi` 同属阿里 DashScope 生态，统一 API Key 管理。`v4` 是阿里当时最新的嵌入模型，中文表现优秀。

---

### 4.7 模型工厂 — `model/factory.py`

#### 设计理念：抽象工厂模式

```python
class BaseModelFactory(ABC):
    @abstractmethod
    def generator(self): pass

class ChatModelFactory(BaseModelFactory):
    def generator(self):
        return ChatTongyi(model="qwen3-max", api_key=os.getenv("DASHSCOPE_API_KEY"))

class EmbeddingModelFactory(BaseModelFactory):
    def generator(self):
        return DashScopeEmbeddings(model="text-embedding-v4")
```

**为什么用工厂模式？**

1. **统一实例化入口**：所有模型通过工厂创建，调用方不需要知道模型类的构造函数细节
2. **便于切换模型**：若要换成 OpenAI，只需新增 `OpenAIChatFactory` + `OpenAIEmbeddingFactory`，其他代码零修改
3. **模块级单例**：`chat_model = ChatModelFactory().generator()` 在模块加载时执行一次，后续 `import` 复用同一实例

**为什么 API Key 从环境变量读取而非配置文件？**

安全实践：API Key 是敏感信息，不应写入会被提交到 Git 的配置文件。`os.getenv("DASHSCOPE_API_KEY")` 从环境变量读取，保证密钥不出现在代码仓库中。

---

### 4.8 工具类模块 — `utils/`

#### `config_handler.py` — 配置加载器

**为什么模块 import 时立即加载所有配置？**

```python
rag_conf = load_rag_config()
chroma_conf = load_chroma_config()
```

这是一种"饥汉式"加载策略：
- 配置在应用启动时完成，运行期间零成本访问
- 配置错误在启动阶段暴露（fail-fast），而非运行时
- 适合本项目配置量小、启动频率低的场景

**为什么每个配置有独立加载函数而非一个通用函数？**

类型安全和自文档化。`load_chroma_config()` 的返回值类型明确（chunk_size 是 int，separators 是 list），调用方无需记忆配置文件的 key 名。

#### `file_handler.py` — 文件处理

- `get_file_md5_hex()`：流式读取（4KB 块），支持大文件
- `list_with_allowed_type()`：按文件扩展名过滤，排除 `.pyc` 等无关文件
- `pdf_loader()` / `txt_loader()`：适配 LangChain 的 Document 格式，统一加载接口

#### `logger_handler.py` — 日志配置

**为什么同时输出到控制台和文件？**

- 控制台（INFO 级别）：开发时实时观察运行状态
- 文件（DEBUG 级别）：线上问题排查时查看详细上下文

**防重复 Handler 的守卫逻辑**：

```python
if logger.handlers:
    return logger
```

LangChain 等库会多次 import 日志模块。若不加守卫，每次 import 都添加 handler，导致日志重复输出。

#### `path_tool.py` — 路径计算

**为什么基于文件位置而非 `os.getcwd()`？**

`os.getcwd()` 依赖执行目录——从不同位置启动应用会得到不同的结果。`path_tool.py` 基于自身文件位置向上推算项目根目录，无论从哪里启动应用，结果始终正确。

#### `prompt_loader.py` — 提示词加载

**为什么提示词存为独立 `.txt` 文件而非硬编码？**

- 提示词调优频繁，独立文件便于 A/B 测试
- 非技术人员（如产品经理）可直接编辑提示词，无需改代码
- 路径通过 `config/prompts.yml` 配置，可灵活切换不同版本的提示词

---

### 4.9 提示词设计 — `prompts/`

#### `main_prompt.txt` — 主系统提示词

定义了 Agent 的完整行为规范：

| 部分 | 内容 | 设计意图 |
|------|------|----------|
| 角色定义 | 扫地/扫拖机器人专业客服 | 限定 LLM 的领域范围，减少幻觉 |
| 思考准则 | 判断→调工具→再判断→兜底 | 防止无限循环调用工具，5 次上限 |
| 工具协议 | 7 个工具的能力边界、参数约束 | 帮助 LLM 正确选择和使用工具 |
| 报告流程 | 固定四步调用顺序 | 保证数据收集的完整性和一致性 |
| 输出规则 | 先思考再行动 | 确保 ReAct 模式稳定运行，提升可解释性 |

#### `rag_summarize.txt` — RAG 总结提示词

核心约束："**必须完全基于参考资料回答**"。这是 RAG 应用最重要的防幻觉措施——即使检索结果不够理想，也宁可不回答而非编造。

#### `report_prompt.txt` — 报告生成提示词

- 约束输出格式：Markdown 结构
- 指定报告标题："黑马程序员扫地机器人使用情况报告与保养建议"
- 要求根据数据生成"具体建议"而非简单罗列

---

## 五、核心数据流

### 5.1 客服问答流程

```
用户输入 "扫地机器人报E13错误怎么办"
  → app.py: agent.excute_stream(query)
    → log_before_model: 记录对话状态
    → report_prompt_switch: context["report"]=False → 返回 main_prompt.txt
    → Agent 推理: "需要查询知识库" → 调用 rag_summarize("E13错误")
      → monitor_tool: 记录工具调用
      → RagSummarizeService: Chroma 检索 → LLM 总结
      → monitor_tool: 记录调用成功
    → Agent 推理: "知识库有答案" → 整理回复
  → app.py: 流式输出 "E13错误是主刷缠绕..."
```

### 5.2 报告生成流程

```
用户输入 "帮我生成一份使用报告"
  → report_prompt_switch: context["report"]=False → main_prompt
  → Agent 推理: 按提示词中的固定流程
    → 调用 get_user_id()        → "1005"
    → 调用 get_current_month()   → "2025-06"
    → 调用 fill_context_for_report()
      → monitor_tool 检测到此工具 → context["report"] = True
  → report_prompt_switch: context["report"]=True → report_prompt
  → Agent 推理 (报告模式): 收集数据
    → 调用 fetch_external_data("1005", "2025-06") → 使用记录
    → 调用 rag_summarize("根据使用记录给出保养建议") → 专业知识
  → Agent 生成 Markdown 报告
  → app.py: 流式输出报告
```

**关键转折点**：`fill_context_for_report` → `monitor_tool` 设置 `context["report"]=True` → `report_prompt_switch` 切换提示词。后续的模型调用使用报告提示词，Agent 从"客服模式"切换到"报告模式"。

---

## 六、设计模式总结

| 模式 | 应用位置 | 作用 |
|------|----------|------|
| **单例模式** | `ReactAgent`（app.py 中的 session_state）和模型实例（factory.py 模块级变量） | 避免重复初始化昂贵资源 |
| **工厂模式** | `model/factory.py` | 解耦模型创建与使用，便于替换 |
| **策略模式** | `report_prompt_switch` 中间件 | 根据上下文动态选择提示词策略 |
| **装饰器模式** | `@tool`, `@wrap_tool_call`, `@before_model`, `@dynamic_prompt` | 在不修改业务逻辑的情况下增强功能 |
| **管道模式** | RAG Chain（`a \| b \| c \| d`） | 声明式数据流，清晰可组合 |
| **模板方法** | `BaseModelFactory.generator()` | 定义模型创建骨架，子类实现具体逻辑 |

---

## 七、已知问题

1. **`file_handler.py:33`** — `list_with_allowed_type()` 在路径不是目录时返回 `allowed_types`（输入参数）而非空列表，应改为 `return files`
2. **`middleware.py`** — 在 `get_user_location` 成功后记录了一条 `'StructuredTool' object has no attribute 'call'` 错误，是 `handler(request)` 调用方式的 bug
3. **模拟数据** — `get_user_id`、`get_user_location`、`get_current_month` 返回随机值，生产环境需接入真实数据源
4. **月份格式不一致** — `fetch_external_data` 期望 `YYYY-MM` 格式，但历史调用中出现过 `2025-1`（缺少前导零）导致查询失败

---

## 八、依赖清单

| 包名 | 用途 |
|------|------|
| `streamlit` | Web UI 框架 |
| `langchain` | Agent 框架核心 |
| `langchain_community` | 社区集成（ChatTongyi, DashScope, Document Loaders） |
| `langchain_chroma` | Chroma 向量库集成 |
| `langchain_text_splitters` | 递归文本分块器 |
| `chromadb` | Chroma 向量数据库 |
| `dashscope` | 阿里灵积模型服务 |
| `PyYAML` | YAML 配置解析 |
| `pypdf` | PDF 文件解析 |
