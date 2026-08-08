"""CS Draft Generator - Streamlit Webアプリのエントリポイント。

起動: streamlit run src/app/main.py
"""

import sys
from pathlib import Path

# `streamlit run` はスクリプトのディレクトリを sys.path[0] に置くため、
# プロジェクトルートを明示的に追加して `src` パッケージを import 可能にする。
_PROJECT_ROOT = Path(__file__).resolve().parents[2]
if str(_PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(_PROJECT_ROOT))

import streamlit as st  # noqa: E402

from src.app.components.chat import render_chat  # noqa: E402
from src.app.components.sidebar import render_sidebar  # noqa: E402
from src.masking.service import MaskingService  # noqa: E402
from src.rag.query_service import QueryService  # noqa: E402


@st.cache_resource
def get_services() -> tuple[MaskingService, QueryService]:
    """重い初期化（GiNZAロード・Embedding/LLMクライアント生成）をセッション間でキャッシュする。"""
    masking = MaskingService()
    query = QueryService(masking_service=masking)
    return masking, query


def _init_session_state() -> None:
    if "messages" not in st.session_state:
        st.session_state.messages = []
    if "register_msgs" not in st.session_state:
        st.session_state.register_msgs = []


def main() -> None:
    st.set_page_config(page_title="CS Draft Generator", page_icon="💬", layout="wide")
    st.title("💬 CS回答ドラフト生成")
    st.caption("過去のメール対応履歴と製品マニュアル（PDF）を参照して回答ドラフトを生成します。")

    _init_session_state()
    masking, query = get_services()

    render_sidebar(masking)
    render_chat(query, masking)


main()
