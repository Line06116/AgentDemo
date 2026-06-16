import re
from langchain_core.documents import Document
from langchain_core.output_parsers import StrOutputParser
from langchain_core.prompts import PromptTemplate
from model.factory import chat_model
from rag.vector_store import VectorStoreService
from utils.config_handler import chroma_conf
from utils.prompt_loader import load_rag_prompt, load_rerank_prompt
from utils.logger_handler import logger


class RagSummarizeService(object):
    def __init__(self):
        self.vector_store = VectorStoreService()
        self.retriever = self.vector_store.get_retriever()
        self.prompt_text = load_rag_prompt()
        self.prompt_template = PromptTemplate.from_template(self.prompt_text)
        self.model = chat_model
        self.chain = self._init_chain()

        self.retrieval_k = chroma_conf.get("retrieval_k", 20)
        self.distance_threshold = chroma_conf.get("distance_threshold", 1.5)
        self.final_k = chroma_conf.get("k", 3)

        self.rerank_prompt = PromptTemplate.from_template(load_rerank_prompt())

    def _init_chain(self):
        return self.prompt_template | self.model | StrOutputParser()

    def retriever_docs(self, query: str) -> list[Document]:
        return self.retriever.invoke(query)

    def _filter_by_threshold(self, docs_with_scores: list[tuple[Document, float]]) -> list[tuple[Document, float]]:
        return [(doc, score) for doc, score in docs_with_scores if score <= self.distance_threshold]

    def _rerank_with_llm(self, query: str, docs_with_scores: list[tuple[Document, float]]) -> list[Document]:
        if len(docs_with_scores) <= self.final_k:
            return [doc for doc, _ in docs_with_scores]

        docs_text = ""
        for i, (doc, _) in enumerate(docs_with_scores, 1):
            content = doc.page_content.replace("\n", " ")[:600]
            docs_text += f"[{i}] {content}\n"

        try:
            response = self.rerank_prompt | self.model | StrOutputParser()
            raw = response.invoke({"query": query, "documents": docs_text})
            ranked = [int(x.strip()) for x in re.findall(r'\d+', raw)]
            ranked = [i for i in ranked if 1 <= i <= len(docs_with_scores)]

            seen = set()
            ordered = []
            for i in ranked:
                if i not in seen:
                    seen.add(i)
                    ordered.append(docs_with_scores[i - 1][0])

            if len(ordered) < self.final_k:
                remaining = [doc for doc, _ in docs_with_scores if doc not in ordered]
                ordered += remaining

            return ordered[:self.final_k]
        except Exception as e:
            logger.warning(f"LLM重排序失败，退回原始排序: {e}")
            return [doc for doc, _ in docs_with_scores[:self.final_k]]

    def rag_summarize(self, query: str) -> str:
        docs_with_scores = self.vector_store.search_with_score(query, k=self.retrieval_k)
        filtered = self._filter_by_threshold(docs_with_scores)

        if not filtered:
            filtered = docs_with_scores[:self.final_k]

        final_docs = self._rerank_with_llm(query, filtered)

        context = ""
        for i, doc in enumerate(final_docs, 1):
            context += f"[参考资料{i}]:参考资料：{doc.page_content} | 参考元数据：{doc.metadata}\n"

        return self.chain.invoke({"input": query, "context": context})


if __name__ == '__main__':
    rs = RagSummarizeService()
    print(rs.rag_summarize("小户型适合哪种扫地机器人"))
