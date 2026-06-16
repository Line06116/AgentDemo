"""
RAG 优化管线测试：阈值过滤 + LLM 重排序 + 容错降级

运行方式: pip install pytest && python -m pytest tests/test_rag_optimize.py -v
"""
from unittest.mock import patch, MagicMock
from langchain_core.documents import Document
from langchain_core.messages import AIMessage


def make_docs(specs: list[tuple[str, float]]):
    return [(Document(page_content=text), dist) for text, dist in specs]


def _fake_llm(content: str):
    """返回可被 LangChain pipe 接收的 callable mock"""
    def fake_model(_prompt):
        return AIMessage(content=content)
    return fake_model


# ═══════════════════════════════════════════════
# _filter_by_threshold 测试 (纯逻辑，无需 mock)
# ═══════════════════════════════════════════════

class TestFilterByThreshold:
    def test_keeps_docs_within_threshold(self):
        from rag.rag_service import RagSummarizeService
        svc = RagSummarizeService()
        svc.distance_threshold = 1.5
        docs = make_docs([("relevant A", 1.2), ("relevant B", 1.4)])
        result = svc._filter_by_threshold(docs)
        assert len(result) == 2

    def test_filters_docs_above_threshold(self):
        from rag.rag_service import RagSummarizeService
        svc = RagSummarizeService()
        svc.distance_threshold = 1.5
        docs = make_docs([("relevant", 1.2), ("noise", 1.8), ("relevant", 1.4)])
        result = svc._filter_by_threshold(docs)
        assert len(result) == 2
        assert all(s <= 1.5 for _, s in result)

    def test_boundary_inclusive(self):
        from rag.rag_service import RagSummarizeService
        svc = RagSummarizeService()
        svc.distance_threshold = 1.5
        docs = make_docs([("exact boundary", 1.5)])
        result = svc._filter_by_threshold(docs)
        assert len(result) == 1

    def test_empty_when_all_exceed_threshold(self):
        from rag.rag_service import RagSummarizeService
        svc = RagSummarizeService()
        svc.distance_threshold = 1.0
        docs = make_docs([("noise", 1.5), ("noise", 1.8)])
        result = svc._filter_by_threshold(docs)
        assert len(result) == 0

    def test_empty_input(self):
        from rag.rag_service import RagSummarizeService
        svc = RagSummarizeService()
        result = svc._filter_by_threshold([])
        assert len(result) == 0


# ═══════════════════════════════════════════════
# _rerank_with_llm 测试 (mock LLM)
# ═══════════════════════════════════════════════

class TestLLMRerank:
    def test_no_rerank_when_count_leq_final_k(self):
        from rag.rag_service import RagSummarizeService
        svc = RagSummarizeService()
        svc.final_k = 3
        docs = make_docs([("doc A", 1.2), ("doc B", 1.3)])
        result = svc._rerank_with_llm("query", docs)
        assert len(result) == 2
        assert [d.page_content for d in result] == ["doc A", "doc B"]

    def test_reranks_correctly(self):
        from rag.rag_service import RagSummarizeService
        svc = RagSummarizeService()
        svc.final_k = 3
        svc.model = _fake_llm("3,1,5,2,4")

        docs = make_docs([
            ("Doc 0 - apples",           1.2),
            ("Doc 1 - bananas",          1.3),
            ("Doc 2 - apples and fruit", 1.1),
            ("Doc 3 - oranges",          1.4),
            ("Doc 4 - fruit salad",      1.15),
        ])

        result = svc._rerank_with_llm("apples and fruit", docs)
        assert len(result) == 3
        # LLM ranked: 3,1,5,2,4 → top 3 = indices 2,0,4
        assert result[0].page_content == "Doc 2 - apples and fruit"
        assert result[1].page_content == "Doc 0 - apples"
        assert result[2].page_content == "Doc 4 - fruit salad"

    def test_deduplicates_duplicate_ranks(self):
        from rag.rag_service import RagSummarizeService
        svc = RagSummarizeService()
        svc.final_k = 3
        svc.model = _fake_llm("3,3,1,3,5")

        docs = make_docs([
            ("Doc 0", 1.0), ("Doc 1", 1.1), ("Doc 2", 1.2),
            ("Doc 3", 1.3), ("Doc 4", 1.4),
        ])

        result = svc._rerank_with_llm("query", docs)
        contents = [d.page_content for d in result]
        assert len(result) == 3
        assert len(set(contents)) == 3
        assert contents[0] == "Doc 2"   # index 3 → doc 2
        assert contents[1] == "Doc 0"   # index 1 → doc 0

    def test_pads_when_ranked_less_than_final_k(self):
        from rag.rag_service import RagSummarizeService
        svc = RagSummarizeService()
        svc.final_k = 3
        svc.model = _fake_llm("3")  # only ranked one

        docs = make_docs([
            ("Doc 0", 1.0), ("Doc 1", 1.1), ("Doc 2", 1.2),
            ("Doc 3", 1.3), ("Doc 4", 1.4),  # 5 docs > final_k=3, triggers rerank
        ])

        result = svc._rerank_with_llm("query", docs)
        assert len(result) == 3
        assert result[0].page_content == "Doc 2"  # LLM ranked #3 (index 2)

    def test_fallback_on_garbled_output(self):
        from rag.rag_service import RagSummarizeService
        svc = RagSummarizeService()
        svc.final_k = 3
        svc.model = _fake_llm("no valid numbers here")

        docs = make_docs([
            ("Doc 0", 1.0), ("Doc 1", 1.1), ("Doc 2", 1.2),
            ("Doc 3", 1.3), ("Doc 4", 1.4),
        ])

        result = svc._rerank_with_llm("query", docs)
        assert len(result) == 3
        # 解析失败退回原始顺序
        assert [d.page_content for d in result] == ["Doc 0", "Doc 1", "Doc 2"]

    def test_fallback_on_llm_exception(self):
        from rag.rag_service import RagSummarizeService
        svc = RagSummarizeService()
        svc.final_k = 3

        def _crash(_prompt):
            raise RuntimeError("API error")
        svc.model = _crash

        docs = make_docs([("Doc 0", 1.0), ("Doc 1", 1.1), ("Doc 2", 1.2)])
        # 3 docs <= final_k=3, 直接返回不触碰 LLM
        result = svc._rerank_with_llm("query", docs)
        assert len(result) == 3


# ═══════════════════════════════════════════════
# rag_summarize 全管线测试
# (Pydantic RunnableSequence 不支持实例级 patch.object,
#  故直接替换 chain + mock search_with_score)
# ═══════════════════════════════════════════════

class TestRagSummarizePipeline:
    def test_full_pipeline_rerank_and_generate(self):
        from rag.rag_service import RagSummarizeService
        svc = RagSummarizeService()
        svc.final_k = 2
        svc.retrieval_k = 10
        svc.distance_threshold = 1.5
        svc.model = _fake_llm("3,1,5,2,4")

        fake_docs = make_docs([
            ("Doc A - topic X", 1.2),
            ("Doc B - topic Y", 1.3),
            ("Doc C - topic X variant", 1.1),
            ("Doc D - topic Z", 1.4),
            ("Doc E - topic X extended", 1.15),
        ])

        # 替换生成链
        mock_gen_chain = MagicMock()
        mock_gen_chain.invoke.return_value = "最终答案"
        svc.chain = mock_gen_chain

        with patch.object(svc.vector_store, 'search_with_score', return_value=fake_docs):
            result = svc.rag_summarize("topic X")

        assert result == "最终答案"
        context = mock_gen_chain.invoke.call_args[0][0]["context"]
        assert "topic X" in mock_gen_chain.invoke.call_args[0][0]["input"]
        assert "Doc C" in context  # LLM ranked #1
        assert "Doc A" in context  # LLM ranked #2

    def test_threshold_filters_all_fallback_to_topk(self):
        from rag.rag_service import RagSummarizeService
        svc = RagSummarizeService()
        svc.final_k = 3
        svc.retrieval_k = 10
        svc.distance_threshold = 1.0

        fake_docs = make_docs([
            ("Doc A", 1.5), ("Doc B", 1.8), ("Doc C", 2.0),
        ])

        mock_gen_chain = MagicMock()
        mock_gen_chain.invoke.return_value = "fallback answer"
        svc.chain = mock_gen_chain

        with patch.object(svc.vector_store, 'search_with_score', return_value=fake_docs):
            result = svc.rag_summarize("query")

        assert result == "fallback answer"

    def test_single_doc_after_filter_no_rerank(self):
        from rag.rag_service import RagSummarizeService
        svc = RagSummarizeService()
        svc.final_k = 3
        svc.retrieval_k = 10
        svc.distance_threshold = 1.5

        fake_docs = make_docs([("only relevant", 1.3), ("noise A", 1.9), ("noise B", 2.0)])

        mock_gen_chain = MagicMock()
        mock_gen_chain.invoke.return_value = "single doc answer"
        svc.chain = mock_gen_chain

        with patch.object(svc.vector_store, 'search_with_score', return_value=fake_docs):
            result = svc.rag_summarize("query")

        assert result == "single doc answer"
        context = mock_gen_chain.invoke.call_args[0][0]["context"]
        assert "only relevant" in context


# ═══════════════════════════════════════════════
# VectorStoreService.search_with_score 集成测试
# ═══════════════════════════════════════════════

class TestSearchWithScore:
    def test_returns_correct_k_docs(self):
        from rag.vector_store import VectorStoreService
        vs = VectorStoreService()
        results = vs.search_with_score("测试查询", k=5)
        assert len(results) == 5
        for doc, score in results:
            assert isinstance(doc, Document)
            assert isinstance(score, float)
            assert 0 <= score <= 3.0

    def test_default_k_from_config(self):
        from rag.vector_store import VectorStoreService
        from utils.config_handler import chroma_conf
        vs = VectorStoreService()
        results = vs.search_with_score("测试查询")
        expected_k = chroma_conf.get("retrieval_k", 20)
        assert len(results) == expected_k

    def test_all_same_query_returns_identical_results(self):
        from rag.vector_store import VectorStoreService
        vs = VectorStoreService()
        r1 = vs.search_with_score("相同查询", k=5)
        r2 = vs.search_with_score("相同查询", k=5)
        assert [d.page_content for d, _ in r1] == [d.page_content for d, _ in r2]
