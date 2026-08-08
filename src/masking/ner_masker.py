import logging

from src.masking.models import Entity

logger = logging.getLogger(__name__)

# GiNZAは地名を Location ではなく Province/City/Country 等で返す
TARGET_LABELS = {"Person", "Province", "City", "Country"}


class NerMasker:
    def __init__(self) -> None:
        self._nlp = None
        try:
            import spacy

            # ginza 5.2 + spaCy 3.8.x で compound_splitter の split_mode=None がバリデーションエラーになる問題の回避
            config = {"components": {"compound_splitter": {"split_mode": "A"}}}
            self._nlp = spacy.load("ja_ginza", config=config)
        except Exception:
            logger.warning("GiNZAモデルのロードに失敗しました。NERマスキングは無効です。正規表現のみで処理します。")

    def detect(self, text: str) -> list[Entity]:
        if self._nlp is None:
            return []

        doc = self._nlp(text)
        entities: list[Entity] = []
        counters: dict[str, int] = {}

        for ent in doc.ents:
            if ent.label_ not in TARGET_LABELS:
                continue
            counters[ent.label_] = counters.get(ent.label_, 0) + 1
            token = f"[{ent.label_}_{counters[ent.label_]}]"
            entities.append(
                Entity(
                    original=ent.text,
                    label=ent.label_,
                    token=token,
                    start=ent.start_char,
                    end=ent.end_char,
                    source="ner",
                )
            )

        return entities
