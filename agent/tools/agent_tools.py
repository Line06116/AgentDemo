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
