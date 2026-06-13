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
        "知识库状态：",
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
