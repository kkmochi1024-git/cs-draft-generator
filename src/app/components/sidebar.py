"""サイドバー: データ登録（.eml/PDF/テキスト）と登録済み件数表示。

登録の中核ロジック（register_*_bytes / register_text / get_collection_counts）は
Streamlit 非依存の純粋関数として実装し、UIコード（render_sidebar）から呼び出す。
アップロードファイルはPIIを含むため、一時ファイルは登録後に必ず削除する。
"""

import tempfile
from pathlib import Path

import streamlit as st

from src import config
from src.app.components.masking_preview import render_masking_result
from src.etl.eml_reader import EmlReader
from src.etl.pdf_reader import PdfReader
from src.masking.service import MaskingService
from src.rag.index_service import IndexService


def register_pdf_bytes(data: bytes, file_name: str, masking: MaskingService) -> str:
    """PDFバイト列をマニュアルコレクションに登録し、結果メッセージを返す。"""
    tmp = tempfile.NamedTemporaryFile(suffix=".pdf", delete=False)
    try:
        tmp.write(data)
        tmp.close()
        pages = PdfReader().parse_file(Path(tmp.name))
        if not pages:
            return f"⚠️ {file_name}: テキストを抽出できませんでした（スキャンPDF等の可能性）"
        index = IndexService(masking, collection_name=config.COLLECTION_MANUALS)
        result = index.register_pages(pages, file_name=file_name)
        return f"✅ {file_name}: {result.chunk_count} チャンク登録（{len(pages)} ページ）"
    finally:
        # PIIを含む一時ファイルを確実に削除
        Path(tmp.name).unlink(missing_ok=True)


def register_eml_bytes(data: bytes, file_name: str, masking: MaskingService) -> str:
    """.emlバイト列をメールコレクションに登録し、結果メッセージを返す。"""
    tmp = tempfile.NamedTemporaryFile(suffix=".eml", delete=False)
    try:
        tmp.write(data)
        tmp.close()
        parsed = EmlReader().parse_file(Path(tmp.name))
        if parsed is None:
            return f"⚠️ {file_name}: メールのパースに失敗しました"
        metadata = {"source": "eml", "subject": parsed.subject}
        if parsed.date:
            metadata["date"] = parsed.date.isoformat()
        index = IndexService(masking)
        result = index.register(parsed.body, metadata=metadata)
        return f"✅ {file_name}: {result.chunk_count} チャンク登録（{parsed.subject}）"
    finally:
        Path(tmp.name).unlink(missing_ok=True)


def register_text(text: str, masking: MaskingService) -> str:
    """テキストをメールコレクションに登録し、結果メッセージを返す。"""
    index = IndexService(masking)
    result = index.register(text)
    return f"✅ テキスト: {result.chunk_count} チャンク登録"


def get_collection_counts(masking: MaskingService) -> dict[str, int]:
    """コレクション別の登録済みチャンク数を返す。取得失敗時は -1。"""
    counts: dict[str, int] = {}
    for label, name in (("emails", config.COLLECTION_EMAILS), ("manuals", config.COLLECTION_MANUALS)):
        try:
            index = IndexService(masking, collection_name=name)
            counts[label] = index.get_stats()["total_documents"]
        except Exception:
            counts[label] = -1
    return counts


def _run_registration(handler, *args) -> None:
    """登録ハンドラを実行し、結果を session_state に積んでエラーはUI表示する。"""
    try:
        with st.spinner("登録中..."):
            msg = handler(*args)
        st.session_state.register_msgs.append(msg)
    except RuntimeError as e:  # Ollama接続エラー等
        st.error(str(e))
    except Exception as e:  # noqa: BLE001 - UIをクラッシュさせない
        st.error(f"登録に失敗しました: {e}")


@st.dialog("マスキング結果プレビュー")
def _confirm_text_registration(text: str, masking: MaskingService) -> None:
    """登録前に原文・マスキング後・検出PIIを確認し、続行/キャンセルを選ばせる。"""
    st.markdown("**[原文]**")
    st.text(text)
    render_masking_result(masking.mask(text))

    col_ok, col_cancel = st.columns(2)
    if col_ok.button("このまま登録", type="primary", use_container_width=True):
        _run_registration(register_text, text, masking)
        st.rerun()
    if col_cancel.button("キャンセル", use_container_width=True):
        st.rerun()


def render_sidebar(masking: MaskingService) -> None:
    with st.sidebar:
        st.header("◆ データ管理")

        eml_file = st.file_uploader(".emlファイル", type=["eml"], key="eml_up")
        if eml_file is not None and st.button(".emlを登録", key="eml_btn"):
            _run_registration(register_eml_bytes, eml_file.getvalue(), eml_file.name, masking)

        pdf_file = st.file_uploader("PDFマニュアル", type=["pdf"], key="pdf_up")
        if pdf_file is not None and st.button("PDFを登録", key="pdf_btn"):
            _run_registration(register_pdf_bytes, pdf_file.getvalue(), pdf_file.name, masking)

        text_input = st.text_area("テキスト登録", key="text_up", height=100)
        if text_input and st.button("マスキング確認して登録", key="text_btn"):
            # 登録前にマスキング結果を確認するモーダルを開く
            _confirm_text_registration(text_input, masking)

        # 登録結果メッセージ（最新5件）
        for msg in st.session_state.register_msgs[-5:]:
            if msg.startswith("✅"):
                st.success(msg)
            else:
                st.warning(msg)

        st.divider()
        st.header("◆ 登録済みチャンク数")
        counts = get_collection_counts(masking)
        emails = counts["emails"]
        manuals = counts["manuals"]
        st.markdown(f"📧 メール: {'取得失敗' if emails < 0 else f'{emails} 件'}")
        st.markdown(f"📄 マニュアル: {'取得失敗' if manuals < 0 else f'{manuals} 件'}")
