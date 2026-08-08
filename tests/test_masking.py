from src.masking.models import Entity
from src.masking.regex_masker import RegexMasker
from src.masking.service import MaskingService


class _StubNer:
    """GiNZAに依存せず、指定した固有表現の全出現を検出するNerMaskerスタブ"""

    def __init__(self, name: str, label: str = "Person") -> None:
        self._name = name
        self._label = label

    def detect(self, text: str) -> list[Entity]:
        entities: list[Entity] = []
        start = 0
        count = 0
        while True:
            idx = text.find(self._name, start)
            if idx == -1:
                break
            count += 1
            entities.append(
                Entity(
                    original=self._name,
                    label=self._label,
                    token=f"[{self._label}_{count}]",
                    start=idx,
                    end=idx + len(self._name),
                    source="ner",
                )
            )
            start = idx + len(self._name)
        return entities


class TestRegexMasker:
    def setup_method(self):
        self.masker = RegexMasker()

    # メールアドレスを1件検出し、正しいラベル・元テキスト・トークンが返ること
    def test_detect_email(self):
        entities = self.masker.detect("連絡先: yamada@example.com まで")
        assert len(entities) == 1
        assert entities[0].label == "EMAIL"
        assert entities[0].original == "yamada@example.com"
        assert entities[0].token == "[EMAIL_1]"

    # 複数のメールアドレスが連番トークン（[EMAIL_1], [EMAIL_2]）で検出されること
    def test_detect_multiple_emails(self):
        entities = self.masker.detect("a@b.com と c@d.com")
        assert len(entities) == 2
        assert entities[0].token == "[EMAIL_1]"
        assert entities[1].token == "[EMAIL_2]"

    # ハイフン区切りの電話番号を検出できること
    def test_detect_phone(self):
        entities = self.masker.detect("電話: 03-1234-5678")
        assert len(entities) == 1
        assert entities[0].label == "PHONE"
        assert entities[0].original == "03-1234-5678"

    # スペース区切りの電話番号を検出できること
    def test_detect_phone_with_space(self):
        entities = self.masker.detect("電話: 03 1234 5678")
        assert len(entities) == 1
        assert entities[0].label == "PHONE"

    # 郵便番号（XXX-XXXX形式）を検出できること
    def test_detect_zipcode(self):
        entities = self.masker.detect("住所: 〒100-0001")
        assert len(entities) == 1
        assert entities[0].label == "ZIPCODE"
        assert entities[0].original == "100-0001"

    # メール・電話・郵便番号が混在するテキストで全種類を検出できること
    def test_detect_mixed(self):
        text = "山田太郎 yamada@example.com 03-1234-5678 〒100-0001"
        entities = self.masker.detect(text)
        labels = {e.label for e in entities}
        assert "EMAIL" in labels
        assert "PHONE" in labels
        assert "ZIPCODE" in labels

    # PIIを含まないテキストでは何も検出されないこと
    def test_detect_no_pii(self):
        entities = self.masker.detect("これはPIIを含まないテキストです。")
        assert len(entities) == 0


class TestMaskingService:
    def setup_method(self):
        self.service = MaskingService()

    # メールアドレスがマスクトークンに置換され、マッピングに元の値が保持されること
    def test_mask_email(self):
        result = self.service.mask("連絡先: yamada@example.com")
        assert "yamada@example.com" not in result.masked_text
        assert "[EMAIL_1]" in result.masked_text
        assert result.mapping["[EMAIL_1]"] == "yamada@example.com"

    # 電話番号がマスクトークンに置換されること
    def test_mask_phone(self):
        result = self.service.mask("電話番号は03-1234-5678です")
        assert "03-1234-5678" not in result.masked_text
        assert "[PHONE_1]" in result.masked_text

    # 空文字列を渡した場合、空のMaskingResultが返ること
    def test_mask_empty_text(self):
        result = self.service.mask("")
        assert result.masked_text == ""
        assert result.mapping == {}
        assert result.entities == []

    # PIIを含まないテキストではマスクトークンが挿入されないこと
    def test_mask_no_pii(self):
        text = "これはPIIを含まないテキストです。"
        result = self.service.mask(text)
        assert "[EMAIL" not in result.masked_text
        assert "[PHONE" not in result.masked_text

    # unmaskでマスクトークンを元の値に復元できること
    def test_unmask(self):
        result = self.service.mask("yamada@example.com に連絡")
        unmasked = self.service.unmask(result.masked_text, result.mapping)
        assert "yamada@example.com" in unmasked

    # mask→unmaskの往復で元のPII値が全て復元されること
    def test_mask_unmask_roundtrip(self):
        original = "山田太郎 yamada@example.com 03-1234-5678 〒100-0001"
        result = self.service.mask(original)
        restored = self.service.unmask(result.masked_text, result.mapping)
        assert "yamada@example.com" in restored
        assert "03-1234-5678" in restored
        assert "100-0001" in restored

    # 検出されたエンティティに正しい位置情報（start/end）と検出元（source）が含まれること
    def test_entities_have_position(self):
        result = self.service.mask("test@example.com")
        assert len(result.entities) >= 1
        entity = result.entities[0]
        assert entity.start >= 0
        assert entity.end > entity.start
        assert entity.source in ("regex", "ner")

    # 同一の固有表現が複数回出現しても全出現がマスクされ、往復で完全に復元できること
    # （回帰テスト: 2026-07-15発見のバグ。全出現が最初の位置に重複マッピングされ、
    #   トークン破損と2回目以降のマスク漏れが起きていた）
    def test_mask_duplicate_ner_entity(self):
        self.service._ner = _StubNer("山田太郎")
        original = "山田太郎です。山田太郎さんによろしく。"
        result = self.service.mask(original)
        assert "山田太郎" not in result.masked_text
        assert result.masked_text == "[Person_1]です。[Person_2]さんによろしく。"
        restored = self.service.unmask(result.masked_text, result.mapping)
        assert restored == original

    # _map_ner_to_original が同一文字列の複数エンティティを別々の出現位置に対応付けること
    def test_map_ner_duplicates_to_distinct_positions(self):
        text = "山田太郎です。山田太郎さんによろしく。"
        ner_entities = [
            Entity("山田太郎", "Person", "[Person_1]", 0, 4, "ner"),
            Entity("山田太郎", "Person", "[Person_2]", 7, 11, "ner"),
        ]
        mapped = self.service._map_ner_to_original(text, [], ner_entities)
        assert [(e.start, e.end) for e in mapped] == [(0, 4), (7, 11)]
        assert [e.token for e in mapped] == ["[Person_1]", "[Person_2]"]
