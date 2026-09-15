from src.masking.models import Entity, MaskingResult
from src.masking.ner_masker import ADDRESS_LABELS, NerMasker
from src.masking.regex_masker import ADDRESS_CONTINUATION, RegexMasker


class MaskingService:
    def __init__(self) -> None:
        self._regex = RegexMasker()
        self._ner = NerMasker()

    def mask(self, text: str) -> MaskingResult:
        if not text:
            return MaskingResult(masked_text="", mapping={}, entities=[])

        # Docker tty経由の日本語入力でサロゲート文字が混入する場合があるため除去
        text = text.encode("utf-8", errors="surrogateescape").decode("utf-8", errors="replace")

        # 第1層: 正規表現で定型PII（メアド・電話・郵便番号）を検出
        regex_entities = self._regex.detect(text)
        # 正規表現でマスク済みのテキストをNERに渡すことで、同じPIIの二重検出を防ぐ
        masked_text = self._apply_entities(text, regex_entities)

        # 第2層: GiNZA NERで人名・住所を検出（マスク済みテキスト上で実行）
        ner_entities = self._ner.detect(masked_text)
        # NERの検出位置はマスク済みテキスト上のものなので、元テキストの位置に変換する
        all_ner_on_original = self._map_ner_to_original(text, regex_entities, ner_entities)
        # GiNZAは地名の後ろの番地（例: 「千代田区」の後ろの「1-1-1」）を含めないため、番地まで範囲を延ばす
        all_ner_on_original = self._extend_address_entities(text, regex_entities, all_ner_on_original)

        all_entities = regex_entities + all_ner_on_original
        # 末尾から置換することで、前方の置換が後方の位置情報をずらす問題を回避
        all_entities.sort(key=lambda e: e.start, reverse=True)

        result_text = text
        for entity in all_entities:
            result_text = result_text[: entity.start] + entity.token + result_text[entity.end :]

        mapping = {e.token: e.original for e in all_entities}

        all_entities.sort(key=lambda e: e.start)
        return MaskingResult(masked_text=result_text, mapping=mapping, entities=all_entities)

    def unmask(self, text: str, mapping: dict[str, str]) -> str:
        result = text
        for token, original in mapping.items():
            result = result.replace(token, original)
        return result

    def _apply_entities(self, text: str, entities: list[Entity]) -> str:
        result = text
        for entity in sorted(entities, key=lambda e: e.start, reverse=True):
            result = result[: entity.start] + entity.token + result[entity.end :]
        return result

    def _map_ner_to_original(
        self, original_text: str, regex_entities: list[Entity], ner_entities: list[Entity]
    ) -> list[Entity]:
        """NERはマスク済みテキスト上で検出するため、元テキスト上の正しい位置を再特定する。
        正規表現で既にマスクされた範囲と重複するNER結果は除外する。
        マッピング済みのNER範囲も占有扱いにし、同一の固有表現が複数回出現しても
        各エンティティが別々の出現位置に対応付くようにする（同一位置への多重マッピングを防ぐ）。"""
        occupied = {(e.start, e.end) for e in regex_entities}
        mapped: list[Entity] = []

        for ner_ent in ner_entities:
            orig_text = ner_ent.original
            search_start = 0
            while True:
                idx = original_text.find(orig_text, search_start)
                if idx == -1:
                    break
                span = (idx, idx + len(orig_text))
                # 正規表現マスク済み・マッピング済みNERの範囲と重複していないことを確認
                overlaps = any(not (span[1] <= os or span[0] >= oe) for os, oe in occupied)
                if not overlaps:
                    mapped.append(
                        Entity(
                            original=orig_text,
                            label=ner_ent.label,
                            token=ner_ent.token,
                            start=idx,
                            end=idx + len(orig_text),
                            source="ner",
                        )
                    )
                    occupied.add(span)
                    break
                search_start = idx + 1

        return mapped

    def _extend_address_entities(
        self, original_text: str, regex_entities: list[Entity], ner_entities: list[Entity]
    ) -> list[Entity]:
        """住所系ラベル（ADDRESS_LABELS）のNERエンティティについて、直後に続く町名・番地を範囲に含める。
        延長後の範囲が他のエンティティと重なる場合は延長しない（置換の衝突によるトークン破損を防ぐ）。"""
        others = regex_entities + ner_entities
        extended: list[Entity] = []

        for ent in ner_entities:
            match = ADDRESS_CONTINUATION.match(original_text, ent.end) if ent.label in ADDRESS_LABELS else None
            if match:
                new_end = match.end()
                overlaps = any(o is not ent and o.start < new_end and ent.start < o.end for o in others)
                if not overlaps:
                    ent = Entity(
                        original=original_text[ent.start : new_end],
                        label=ent.label,
                        token=ent.token,
                        start=ent.start,
                        end=new_end,
                        source=ent.source,
                    )
            extended.append(ent)

        return extended
