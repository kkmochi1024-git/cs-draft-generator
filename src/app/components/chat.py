"""チャットUI: 会話履歴表示・ストリーミング回答・参照元表示。"""

import streamlit as st

from src.masking.service import MaskingService
from src.rag.formatting import format_source
from src.rag.query_service import QueryService


def _render_sources(sources: list[dict]) -> None:
    if not sources:
        return
    with st.expander("📎 参照元ドキュメント"):
        for doc in sources:
            st.markdown(f"- {format_source(doc.get('metadata', {}))}")
            st.caption(doc.get("content", ""))


def _render_history() -> None:
    for message in st.session_state.messages:
        with st.chat_message(message["role"]):
            st.markdown(message["content"])
            if message["role"] == "assistant":
                _render_sources(message.get("sources", []))


def _generate_answer(query_service: QueryService, masking: MaskingService, question: str) -> None:
    """ストリーミングで回答を生成・表示し、session_stateに追記する。"""
    with st.chat_message("assistant"):
        try:
            streaming = query_service.ask_stream(question)
        except Exception as e:  # noqa: BLE001 - 検索時の接続エラー等でUIを落とさない
            st.error(f"回答生成に失敗しました: {e}")
            return

        if streaming.is_empty:
            st.markdown(streaming.guidance)
            st.session_state.messages.append({"role": "assistant", "content": streaming.guidance})
            return

        placeholder = st.empty()
        masked_full = ""
        try:
            for chunk in streaming.tokens:
                masked_full += chunk
                # 生成中はマスク済みテキストを逐次表示（マスクトークンは確定時に復元）
                placeholder.markdown(masked_full + "▌")
        except Exception as e:  # noqa: BLE001
            st.error(f"回答生成中にエラーが発生しました: {e}")
            return

        # 生成完了後に一括unmaskして確定表示（トークンのチャンク分断対策）
        answer = masking.unmask(masked_full, streaming.mapping)
        placeholder.markdown(answer)
        _render_sources(streaming.source_documents)

        st.session_state.messages.append(
            {"role": "assistant", "content": answer, "sources": streaming.source_documents}
        )


def render_chat(query_service: QueryService, masking: MaskingService) -> None:
    _render_history()

    question = st.chat_input("質問を入力してください")
    if question:
        st.session_state.messages.append({"role": "user", "content": question})
        with st.chat_message("user"):
            st.markdown(question)
        _generate_answer(query_service, masking, question)
