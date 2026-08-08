"""IndexService/QueryServiceの統合テスト。
OllamaとChromaDBをモックし、外部接続なしでRAGパイプラインの動作を検証する。"""

import tempfile
from unittest.mock import MagicMock, patch

import pytest

from src.masking.models import MaskingResult
from src.masking.service import MaskingService
from src.rag.index_service import IndexService
from src.rag.models import AnswerResult, RegisterResult, StreamingAnswer
from src.rag.query_service import QueryService


@pytest.fixture
def masking_service():
    return MaskingService()


@pytest.fixture
def mock_embeddings():
    """OllamaEmbeddingsのモック。固定ベクトルを返す。"""
    mock = MagicMock()
    mock.embed_documents.return_value = [[0.1] * 768]
    mock.embed_query.return_value = [0.1] * 768
    return mock


@pytest.fixture
def tmp_persist_dir():
    with tempfile.TemporaryDirectory() as d:
        yield d


class TestIndexService:
    # PIIを含むテキストを登録し、RegisterResult（チャンク数+マスキング結果）が返ること
    def test_register_returns_result(self, masking_service, mock_embeddings, tmp_persist_dir):
        with (
            patch("src.rag.index_service.OllamaEmbeddings", return_value=mock_embeddings),
            patch("src.rag.index_service.config") as mock_config,
        ):
            mock_config.EMBEDDING_MODEL = "nomic-embed-text"
            mock_config.OLLAMA_BASE_URL = "http://localhost:11434"
            mock_config.COLLECTION_NAME = "test_collection"
            mock_config.PERSIST_DIR = tmp_persist_dir
            mock_config.CHUNK_SIZE = 512
            mock_config.CHUNK_OVERLAP = 50

            index = IndexService(masking_service=masking_service)
            result = index.register("テスト文書です。yamada@example.com に連絡してください。")

            assert isinstance(result, RegisterResult)
            assert result.chunk_count >= 1
            assert isinstance(result.masking_result, MaskingResult)

    # 登録時にPIIがマスキングされ、マスク済みテキストにはPIIが含まれないこと
    def test_register_masks_pii(self, masking_service, mock_embeddings, tmp_persist_dir):
        with (
            patch("src.rag.index_service.OllamaEmbeddings", return_value=mock_embeddings),
            patch("src.rag.index_service.config") as mock_config,
        ):
            mock_config.EMBEDDING_MODEL = "nomic-embed-text"
            mock_config.OLLAMA_BASE_URL = "http://localhost:11434"
            mock_config.COLLECTION_NAME = "test_collection"
            mock_config.PERSIST_DIR = tmp_persist_dir
            mock_config.CHUNK_SIZE = 512
            mock_config.CHUNK_OVERLAP = 50

            index = IndexService(masking_service=masking_service)
            result = index.register("山田太郎 yamada@example.com 03-1234-5678")

            assert "yamada@example.com" not in result.masking_result.masked_text
            assert "[EMAIL_1]" in result.masking_result.masked_text

    # カスタムメタデータ（source, subject等）を指定して登録できること
    def test_register_with_custom_metadata(self, masking_service, mock_embeddings, tmp_persist_dir):
        with (
            patch("src.rag.index_service.OllamaEmbeddings", return_value=mock_embeddings),
            patch("src.rag.index_service.config") as mock_config,
        ):
            mock_config.EMBEDDING_MODEL = "nomic-embed-text"
            mock_config.OLLAMA_BASE_URL = "http://localhost:11434"
            mock_config.COLLECTION_NAME = "test_collection"
            mock_config.PERSIST_DIR = tmp_persist_dir
            mock_config.CHUNK_SIZE = 512
            mock_config.CHUNK_OVERLAP = 50

            index = IndexService(masking_service=masking_service)
            result = index.register("テスト文書", metadata={"source": "eml", "subject": "テスト"})

            assert result.chunk_count >= 1

    # get_statsで登録済みドキュメント数を取得できること
    def test_get_stats(self, masking_service, mock_embeddings, tmp_persist_dir):
        with (
            patch("src.rag.index_service.OllamaEmbeddings", return_value=mock_embeddings),
            patch("src.rag.index_service.config") as mock_config,
        ):
            mock_config.EMBEDDING_MODEL = "nomic-embed-text"
            mock_config.OLLAMA_BASE_URL = "http://localhost:11434"
            mock_config.COLLECTION_NAME = "test_collection"
            mock_config.PERSIST_DIR = tmp_persist_dir
            mock_config.CHUNK_SIZE = 512
            mock_config.CHUNK_OVERLAP = 50

            index = IndexService(masking_service=masking_service)
            stats = index.get_stats()

            assert "total_documents" in stats
            assert isinstance(stats["total_documents"], int)

    # 空テキストを登録した場合、チャンク数0でエラーにならないこと
    def test_register_empty_text(self, masking_service, mock_embeddings, tmp_persist_dir):
        with (
            patch("src.rag.index_service.OllamaEmbeddings", return_value=mock_embeddings),
            patch("src.rag.index_service.config") as mock_config,
        ):
            mock_config.EMBEDDING_MODEL = "nomic-embed-text"
            mock_config.OLLAMA_BASE_URL = "http://localhost:11434"
            mock_config.COLLECTION_NAME = "test_collection"
            mock_config.PERSIST_DIR = tmp_persist_dir
            mock_config.CHUNK_SIZE = 512
            mock_config.CHUNK_OVERLAP = 50

            index = IndexService(masking_service=masking_service)
            result = index.register("")

            assert result.chunk_count == 0


class TestQueryService:
    def _make_mock_doc(self, content: str, metadata: dict | None = None):
        doc = MagicMock()
        doc.page_content = content
        doc.metadata = metadata or {"source": "manual", "date": "2026-06-23"}
        return doc

    # 質問に対してLLMが回答を生成し、AnswerResult（回答+参照元）が返ること
    def test_ask_returns_answer(self, masking_service, mock_embeddings, tmp_persist_dir):
        mock_llm = MagicMock()
        mock_response = MagicMock()
        mock_response.content = "パスワードはログイン画面からリセットできます。"
        mock_llm.invoke.return_value = mock_response

        mock_vectorstore = MagicMock()
        mock_vectorstore.similarity_search_with_score.return_value = [
            (self._make_mock_doc("パスワードリセット手順: ログイン画面でリセットリンクをクリック"), 0.1)
        ]

        with (
            patch("src.rag.query_service.OllamaEmbeddings", return_value=mock_embeddings),
            patch("src.rag.query_service.Chroma", return_value=mock_vectorstore),
            patch("src.rag.query_service.ChatOllama", return_value=mock_llm),
            patch("src.rag.query_service.config") as mock_config,
        ):
            mock_config.EMBEDDING_MODEL = "nomic-embed-text"
            mock_config.OLLAMA_BASE_URL = "http://localhost:11434"
            mock_config.COLLECTION_NAME = "test_collection"
            mock_config.PERSIST_DIR = tmp_persist_dir
            mock_config.MODEL_NAME = "gemma4:12b"
            mock_config.TEMPERATURE = 0.3
            mock_config.MAX_TOKENS = 1024
            mock_config.SEARCH_TOP_K = 5
            mock_config.SYSTEM_PROMPT = "参考情報:\n{context}\n"

            query = QueryService(masking_service=masking_service)
            result = query.ask("パスワードのリセット方法は？")

            assert isinstance(result, AnswerResult)
            assert "パスワード" in result.answer
            assert len(result.source_documents) >= 1

    # ChromaDBにデータがない場合、LLMを呼ばずに登録を促すメッセージを返すこと
    def test_ask_empty_db_returns_guidance(self, masking_service, mock_embeddings, tmp_persist_dir):
        mock_vectorstore = MagicMock()
        mock_vectorstore.similarity_search_with_score.return_value = []

        mock_llm = MagicMock()

        with (
            patch("src.rag.query_service.OllamaEmbeddings", return_value=mock_embeddings),
            patch("src.rag.query_service.Chroma", return_value=mock_vectorstore),
            patch("src.rag.query_service.ChatOllama", return_value=mock_llm),
            patch("src.rag.query_service.config") as mock_config,
        ):
            mock_config.EMBEDDING_MODEL = "nomic-embed-text"
            mock_config.OLLAMA_BASE_URL = "http://localhost:11434"
            mock_config.COLLECTION_NAME = "test_collection"
            mock_config.PERSIST_DIR = tmp_persist_dir
            mock_config.MODEL_NAME = "gemma4:12b"
            mock_config.TEMPERATURE = 0.3
            mock_config.MAX_TOKENS = 1024
            mock_config.SEARCH_TOP_K = 5

            query = QueryService(masking_service=masking_service)
            result = query.ask("テスト質問")

            assert "register" in result.answer
            mock_llm.invoke.assert_not_called()

    # 質問中のPIIがマスキングされ、LLM回答内のマスクトークンがアンマスクで復元されること
    def test_ask_unmasks_pii_in_answer(self, masking_service, mock_embeddings, tmp_persist_dir):
        mock_llm = MagicMock()
        mock_response = MagicMock()
        mock_response.content = "[EMAIL_1] 宛にリセットメールを送信しました。"
        mock_llm.invoke.return_value = mock_response

        mock_vectorstore = MagicMock()
        mock_vectorstore.similarity_search_with_score.return_value = [
            (self._make_mock_doc("メール送信手順"), 0.1)
        ]

        with (
            patch("src.rag.query_service.OllamaEmbeddings", return_value=mock_embeddings),
            patch("src.rag.query_service.Chroma", return_value=mock_vectorstore),
            patch("src.rag.query_service.ChatOllama", return_value=mock_llm),
            patch("src.rag.query_service.config") as mock_config,
        ):
            mock_config.EMBEDDING_MODEL = "nomic-embed-text"
            mock_config.OLLAMA_BASE_URL = "http://localhost:11434"
            mock_config.COLLECTION_NAME = "test_collection"
            mock_config.PERSIST_DIR = tmp_persist_dir
            mock_config.MODEL_NAME = "gemma4:12b"
            mock_config.TEMPERATURE = 0.3
            mock_config.MAX_TOKENS = 1024
            mock_config.SEARCH_TOP_K = 5
            mock_config.SYSTEM_PROMPT = "参考情報:\n{context}\n"

            query = QueryService(masking_service=masking_service)
            result = query.ask("yamada@example.com のアカウントについて")

            assert "yamada@example.com" in result.answer
            assert "[EMAIL_1]" not in result.answer
            assert "[EMAIL_1]" in result.masked_answer

    # ChromaDBの検索結果がLLMに渡すプロンプトに正しく含まれること
    def test_ask_passes_context_to_llm(self, masking_service, mock_embeddings, tmp_persist_dir):
        mock_llm = MagicMock()
        mock_response = MagicMock()
        mock_response.content = "回答です。"
        mock_llm.invoke.return_value = mock_response

        mock_vectorstore = MagicMock()
        mock_vectorstore.similarity_search_with_score.return_value = [
            (self._make_mock_doc("参照ドキュメントの内容ABC123"), 0.1)
        ]

        with (
            patch("src.rag.query_service.OllamaEmbeddings", return_value=mock_embeddings),
            patch("src.rag.query_service.Chroma", return_value=mock_vectorstore),
            patch("src.rag.query_service.ChatOllama", return_value=mock_llm),
            patch("src.rag.query_service.config") as mock_config,
        ):
            mock_config.EMBEDDING_MODEL = "nomic-embed-text"
            mock_config.OLLAMA_BASE_URL = "http://localhost:11434"
            mock_config.COLLECTION_NAME = "test_collection"
            mock_config.PERSIST_DIR = tmp_persist_dir
            mock_config.MODEL_NAME = "gemma4:12b"
            mock_config.TEMPERATURE = 0.3
            mock_config.MAX_TOKENS = 1024
            mock_config.SEARCH_TOP_K = 5
            mock_config.SYSTEM_PROMPT = "参考情報:\n{context}\n"

            query = QueryService(masking_service=masking_service)
            query.ask("テスト質問")

            prompt_arg = mock_llm.invoke.call_args[0][0]
            assert "参照ドキュメントの内容ABC123" in prompt_arg


class TestQueryServiceStreaming:
    """ask_stream（ストリーミング回答）のテスト。"""

    def _make_mock_doc(self, content: str, metadata: dict | None = None):
        doc = MagicMock()
        doc.page_content = content
        doc.metadata = metadata or {"source": "eml", "subject": "件名", "date": "2026-05-10"}
        return doc

    def _chunks(self, *texts: str) -> list:
        chunks = []
        for text in texts:
            chunk = MagicMock()
            chunk.content = text
            chunks.append(chunk)
        return chunks

    def _config(self, mock_config, tmp_persist_dir) -> None:
        mock_config.EMBEDDING_MODEL = "nomic-embed-text"
        mock_config.OLLAMA_BASE_URL = "http://localhost:11434"
        mock_config.COLLECTION_EMAILS = "emails"
        mock_config.COLLECTION_MANUALS = "manuals"
        mock_config.PERSIST_DIR = tmp_persist_dir
        mock_config.MODEL_NAME = "gemma4:12b"
        mock_config.TEMPERATURE = 0.3
        mock_config.MAX_TOKENS = 1024
        mock_config.SEARCH_TOP_K = 5
        mock_config.SYSTEM_PROMPT = "参考情報:\n{context}\n"

    # ask_stream がマスク済みチャンクを逐次yieldし、source_documentsを確定して返すこと
    def test_ask_stream_yields_chunks(self, masking_service, mock_embeddings, tmp_persist_dir):
        mock_llm = MagicMock()
        mock_llm.stream.return_value = self._chunks("パスワードは", "リセットできます。")

        mock_vectorstore = MagicMock()
        mock_vectorstore.similarity_search_with_score.return_value = [
            (self._make_mock_doc("パスワードリセット手順"), 0.1)
        ]

        with (
            patch("src.rag.query_service.OllamaEmbeddings", return_value=mock_embeddings),
            patch("src.rag.query_service.Chroma", return_value=mock_vectorstore),
            patch("src.rag.query_service.ChatOllama", return_value=mock_llm),
            patch("src.rag.query_service.config") as mock_config,
        ):
            self._config(mock_config, tmp_persist_dir)

            query = QueryService(masking_service=masking_service)
            streaming = query.ask_stream("パスワードのリセット方法は？")

            assert isinstance(streaming, StreamingAnswer)
            assert streaming.is_empty is False
            assert len(streaming.source_documents) == 1
            # tokens を消費するまでLLMは呼ばれない（遅延評価）
            chunks = list(streaming.tokens)
            assert chunks == ["パスワードは", "リセットできます。"]

    # 検索結果0件のとき is_empty=True・案内文・空トークンを返しLLMを呼ばないこと
    def test_ask_stream_empty_db(self, masking_service, mock_embeddings, tmp_persist_dir):
        mock_llm = MagicMock()
        mock_vectorstore = MagicMock()
        mock_vectorstore.similarity_search_with_score.return_value = []

        with (
            patch("src.rag.query_service.OllamaEmbeddings", return_value=mock_embeddings),
            patch("src.rag.query_service.Chroma", return_value=mock_vectorstore),
            patch("src.rag.query_service.ChatOllama", return_value=mock_llm),
            patch("src.rag.query_service.config") as mock_config,
        ):
            self._config(mock_config, tmp_persist_dir)

            query = QueryService(masking_service=masking_service)
            streaming = query.ask_stream("テスト質問")

            assert streaming.is_empty is True
            assert "register" in streaming.guidance
            assert list(streaming.tokens) == []
            mock_llm.stream.assert_not_called()

    # 質問中のPIIがmappingに含まれ、累積マスク文を最終unmaskすると原文が復元されること
    def test_ask_stream_mapping_enables_unmask(self, masking_service, mock_embeddings, tmp_persist_dir):
        mock_llm = MagicMock()
        mock_llm.stream.return_value = self._chunks("[EMAIL_1]", " 宛に送信しました。")

        mock_vectorstore = MagicMock()
        mock_vectorstore.similarity_search_with_score.return_value = [
            (self._make_mock_doc("メール送信手順"), 0.1)
        ]

        with (
            patch("src.rag.query_service.OllamaEmbeddings", return_value=mock_embeddings),
            patch("src.rag.query_service.Chroma", return_value=mock_vectorstore),
            patch("src.rag.query_service.ChatOllama", return_value=mock_llm),
            patch("src.rag.query_service.config") as mock_config,
        ):
            self._config(mock_config, tmp_persist_dir)

            query = QueryService(masking_service=masking_service)
            streaming = query.ask_stream("yamada@example.com のアカウントについて")

            masked_full = "".join(streaming.tokens)
            restored = masking_service.unmask(masked_full, streaming.mapping)
            assert "yamada@example.com" in restored
            assert "[EMAIL_1]" not in restored
