from collections.abc import Iterator

from langchain_chroma import Chroma
from langchain_ollama import ChatOllama, OllamaEmbeddings

from src import config
from src.masking.service import MaskingService
from src.rag.models import AnswerResult, StreamingAnswer

_EMPTY_GUIDANCE = "参照データが登録されていません。先に register コマンドでデータを登録してください。"


class QueryService:
    def __init__(self, masking_service: MaskingService, collection_names: list[str] | None = None) -> None:
        self._masking = masking_service
        # 既定ではメール履歴（support_emails）とマニュアル（product_manuals）の両方を検索対象にする
        self._collection_names = collection_names or [config.COLLECTION_EMAILS, config.COLLECTION_MANUALS]
        self._embeddings = OllamaEmbeddings(model=config.EMBEDDING_MODEL, base_url=config.OLLAMA_BASE_URL)
        self._vectorstores = [
            Chroma(
                collection_name=name,
                embedding_function=self._embeddings,
                persist_directory=config.PERSIST_DIR,
            )
            for name in self._collection_names
        ]
        self._llm = ChatOllama(
            model=config.MODEL_NAME,
            base_url=config.OLLAMA_BASE_URL,
            temperature=config.TEMPERATURE,
            num_predict=config.MAX_TOKENS,
        )

    def ask(self, question: str) -> AnswerResult:
        # 質問文にもPIIが含まれる場合があるため、検索前にマスキングする
        masking_result = self._masking.mask(question)

        docs = self._search(masking_result.masked_text)

        if not docs:
            return AnswerResult(
                answer=_EMPTY_GUIDANCE,
                masked_answer="",
                source_documents=[],
                masking_result=masking_result,
            )

        prompt = self._build_prompt(docs, masking_result.masked_text)

        try:
            response = self._llm.invoke(prompt)
        except Exception as e:
            raise self._wrap_connection_error(e) from e
        # ChatOllamaはAIMessageオブジェクトを返すが、バージョンによりstr直接返却の場合もある
        masked_answer = response.content if hasattr(response, "content") else str(response)

        # LLM回答内のマスクトークン([PERSON_1]等)を元のPII値に復元して返す
        answer = self._masking.unmask(masked_answer, masking_result.mapping)

        return AnswerResult(
            answer=answer,
            masked_answer=masked_answer,
            source_documents=self._to_source_documents(docs),
            masking_result=masking_result,
        )

    def ask_stream(self, question: str) -> StreamingAnswer:
        """回答をストリーミングで生成する。

        検索・質問マスキングは同期実行し、source_documents と mapping を先に確定させる。
        tokens はマスク済みチャンクを逐次yieldするイテレータで、実際のLLM呼び出しは
        最初のイテレーション時に開始される（呼び出し側が表示ループで消費する）。
        """
        masking_result = self._masking.mask(question)
        docs = self._search(masking_result.masked_text)

        if not docs:
            return StreamingAnswer(
                is_empty=True,
                guidance=_EMPTY_GUIDANCE,
                source_documents=[],
                mapping={},
                tokens=iter(()),
            )

        prompt = self._build_prompt(docs, masking_result.masked_text)
        return StreamingAnswer(
            is_empty=False,
            guidance="",
            source_documents=self._to_source_documents(docs),
            mapping=masking_result.mapping,
            tokens=self._stream_tokens(prompt),
        )

    def _stream_tokens(self, prompt: str) -> Iterator[str]:
        """LLMのストリーミング応答をマスク済みチャンク文字列として逐次yieldする。"""
        try:
            for chunk in self._llm.stream(prompt):
                # ChatOllamaのstreamはAIMessageChunkを返すが、str直接返却の場合もある
                yield chunk.content if hasattr(chunk, "content") else str(chunk)
        except Exception as e:
            raise self._wrap_connection_error(e) from e

    @staticmethod
    def _build_prompt(docs: list, masked_question: str) -> str:
        # 検索結果を区切り文字で結合し、LLMが参照情報と質問を区別できるプロンプトを構築
        context = "\n\n---\n\n".join(doc.page_content for doc in docs)
        return config.SYSTEM_PROMPT.format(context=context) + f"\n\n## お客様の質問\n{masked_question}"

    @staticmethod
    def _to_source_documents(docs: list) -> list[dict]:
        return [{"content": doc.page_content[:200], "metadata": doc.metadata} for doc in docs]

    @staticmethod
    def _wrap_connection_error(e: Exception) -> Exception:
        """Ollama接続エラーを分かりやすいRuntimeErrorに変換する。それ以外はそのまま返す。"""
        if "connect" in str(e).lower() or "connection" in type(e).__name__.lower():
            return RuntimeError(
                f"Ollamaに接続できません ({config.OLLAMA_BASE_URL})。"
                "Ollamaが起動しているか確認してください: ollama serve"
            )
        return e

    def _search(self, masked_query: str) -> list:
        """全コレクションを距離付きで検索し、距離昇順にマージして上位 SEARCH_TOP_K 件を返す。

        同一内容のチャンクが複数コレクションから返ってもページ内容で重複排除する。
        """
        scored: list[tuple[object, float]] = []
        for vectorstore in self._vectorstores:
            results = vectorstore.similarity_search_with_score(masked_query, k=config.SEARCH_TOP_K)
            scored.extend(results)

        # 距離（小さいほど類似）昇順でマージ
        scored.sort(key=lambda pair: pair[1])

        merged: list = []
        seen: set[str] = set()
        for doc, _score in scored:
            if doc.page_content in seen:
                continue
            seen.add(doc.page_content)
            merged.append(doc)
            if len(merged) >= config.SEARCH_TOP_K:
                break

        return merged
