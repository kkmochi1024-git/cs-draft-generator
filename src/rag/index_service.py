from datetime import datetime, timezone

from langchain_chroma import Chroma
from langchain_ollama import OllamaEmbeddings
from langchain_text_splitters import RecursiveCharacterTextSplitter

from src import config
from src.etl.pdf_reader import ExtractedPage
from src.masking.models import Entity, MaskingResult
from src.masking.service import MaskingService
from src.rag.models import RegisterResult


class IndexService:
    def __init__(self, masking_service: MaskingService, collection_name: str | None = None) -> None:
        self._masking = masking_service
        # collection_name 未指定時は既存互換の support_emails（COLLECTION_NAME）に登録する
        self._collection_name = collection_name or config.COLLECTION_NAME
        self._embeddings = OllamaEmbeddings(model=config.EMBEDDING_MODEL, base_url=config.OLLAMA_BASE_URL)
        self._splitter = RecursiveCharacterTextSplitter(
            chunk_size=config.CHUNK_SIZE,
            chunk_overlap=config.CHUNK_OVERLAP,
        )
        self._vectorstore = Chroma(
            collection_name=self._collection_name,
            embedding_function=self._embeddings,
            persist_directory=config.PERSIST_DIR,
        )

    def register(self, text: str, metadata: dict | None = None) -> RegisterResult:
        masking_result = self._masking.mask(text)
        chunks = self._splitter.split_text(masking_result.masked_text)

        base_metadata = {
            "source": "manual",
            "date": datetime.now(timezone.utc).isoformat(),
        }
        if metadata:
            base_metadata.update(metadata)

        if not chunks:
            return RegisterResult(chunk_count=0, masking_result=masking_result)

        metadatas = [base_metadata.copy() for _ in chunks]
        self._add_texts(chunks, metadatas)

        return RegisterResult(chunk_count=len(chunks), masking_result=masking_result)

    def register_pages(
        self, pages: list[ExtractedPage], file_name: str, metadata: dict | None = None
    ) -> RegisterResult:
        """PDF等のページ単位テキストを登録する。

        全ページを結合してマスキング後にチャンク分割し、各チャンクが由来するページ番号を
        メタデータ（page="12" または範囲 "12-13"）として付与する。
        マスキングは既存 register と同じく全体を1回だけ行い、ページ境界のオフセットは
        マスキングによる文字数変化を考慮して補正する。
        """
        if not pages:
            return RegisterResult(chunk_count=0, masking_result=MaskingResult(masked_text=""))

        # ページ結合と、各ページのマスキング前オフセット範囲を記録
        sep = "\n\n"
        combined_parts: list[str] = []
        page_spans: list[tuple[int, int, int]] = []  # (start, end, page_number)
        cursor = 0
        for i, page in enumerate(pages):
            start = cursor
            combined_parts.append(page.text)
            cursor += len(page.text)
            page_spans.append((start, cursor, page.page_number))
            if i < len(pages) - 1:
                combined_parts.append(sep)
                cursor += len(sep)
        combined = "".join(combined_parts)

        masking_result = self._masking.mask(combined)
        masked_text = masking_result.masked_text

        if not masked_text.strip():
            return RegisterResult(chunk_count=0, masking_result=masking_result)

        # マスキング後テキスト上でのページ範囲に変換
        masked_page_spans = [
            (
                self._orig_to_masked_pos(start, masking_result.entities),
                self._orig_to_masked_pos(end, masking_result.entities),
                page_number,
            )
            for start, end, page_number in page_spans
        ]

        chunks = self._splitter.split_text(masked_text)
        if not chunks:
            return RegisterResult(chunk_count=0, masking_result=masking_result)

        base_metadata = {
            "source": "pdf_manual",
            "file_name": file_name,
            "date": datetime.now(timezone.utc).isoformat(),
        }
        if metadata:
            base_metadata.update(metadata)

        metadatas: list[dict] = []
        search_cursor = 0
        for chunk in chunks:
            pos = masked_text.find(chunk, search_cursor)
            if pos == -1:
                # 想定外（分割器がテキストを改変した場合）。全ページ範囲でフォールバック
                pos = search_cursor
                chunk_page = self._page_range_str(masked_page_spans, 0, len(masked_text))
            else:
                chunk_page = self._page_range_str(masked_page_spans, pos, pos + len(chunk))
                search_cursor = pos + 1
            meta = base_metadata.copy()
            meta["page"] = chunk_page
            metadatas.append(meta)

        self._add_texts(chunks, metadatas)

        return RegisterResult(chunk_count=len(chunks), masking_result=masking_result)

    def get_stats(self) -> dict:
        # Chroma公開APIにcount()がないため内部属性を参照（ライブラリ更新時に要確認）
        collection = self._vectorstore._collection
        return {"total_documents": collection.count()}

    def _add_texts(self, chunks: list[str], metadatas: list[dict]) -> None:
        try:
            self._vectorstore.add_texts(texts=chunks, metadatas=metadatas)
        except Exception as e:
            if "connect" in str(e).lower() or "connection" in type(e).__name__.lower():
                raise RuntimeError(
                    f"Ollamaに接続できません ({config.OLLAMA_BASE_URL})。"
                    "Ollamaが起動しているか確認してください: ollama serve"
                ) from e
            raise

    @staticmethod
    def _orig_to_masked_pos(orig_pos: int, entities: list[Entity]) -> int:
        """マスキング前の文字位置を、マスキング後テキスト上の位置に変換する。

        orig_pos より前にあるエンティティの「トークン長 - 元の長さ」の差分を累積して補正する。
        ページ境界（\\n\\n）がPII内部に入ることは稀だが、その場合はエンティティ開始位置に丸める。
        """
        delta = 0
        for e in sorted(entities, key=lambda x: x.start):
            if e.end <= orig_pos:
                delta += len(e.token) - (e.end - e.start)
            elif e.start < orig_pos < e.end:
                return e.start + delta
            else:
                break
        return orig_pos + delta

    @staticmethod
    def _page_range_str(masked_page_spans: list[tuple[int, int, int]], chunk_start: int, chunk_end: int) -> str:
        """チャンクの占有範囲 [chunk_start, chunk_end) と重なるページ番号を "12" / "12-13" で返す。"""
        overlapping = [
            page_number
            for ms, me, page_number in masked_page_spans
            if not (me <= chunk_start or ms >= chunk_end)
        ]
        if not overlapping:
            return ""
        lo, hi = min(overlapping), max(overlapping)
        return str(lo) if lo == hi else f"{lo}-{hi}"
