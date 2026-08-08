from collections.abc import Iterator
from dataclasses import dataclass, field

from src.masking.models import MaskingResult


@dataclass
class RegisterResult:
    chunk_count: int
    masking_result: MaskingResult


@dataclass
class AnswerResult:
    answer: str
    masked_answer: str
    source_documents: list[dict] = field(default_factory=list)
    masking_result: MaskingResult = field(default_factory=lambda: MaskingResult(masked_text=""))


@dataclass
class StreamingAnswer:
    """ストリーミング回答の結果。tokens はマスク済みチャンクを逐次yieldするイテレータ。

    UI側は tokens を accumulate して逐次表示し、生成完了後に mapping で unmask して確定表示する
    （マスクトークンがチャンク境界で分断されうるため、確定時に一括unmaskする）。
    """

    is_empty: bool
    guidance: str
    source_documents: list[dict]
    mapping: dict[str, str]
    tokens: Iterator[str]
