"""マスキング結果のプレビュー表示部品。"""

import pandas as pd
import streamlit as st

from src.masking.models import MaskingResult

_LABEL_JA = {
    "PERSON": "人名",
    "EMAIL": "メール",
    "PHONE": "電話",
    "POSTAL": "郵便番号",
    "ADDRESS": "住所",
}


def render_masking_result(result: MaskingResult) -> None:
    """マスキング後テキストと検出PII一覧をインライン表示する。"""
    st.markdown("**[マスキング後]**")
    st.code(result.masked_text or "(空)", language=None)

    st.markdown("**[検出されたPII]**")
    if result.entities:
        rows = [
            {"トークン": e.token, "元の値": e.original, "種別": _LABEL_JA.get(e.label, e.label)}
            for e in result.entities
        ]
        st.dataframe(pd.DataFrame(rows), hide_index=True, use_container_width=True)
    else:
        st.caption("PIIは検出されませんでした。")
