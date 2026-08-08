import pytest

from src.masking.ner_masker import NerMasker

# GiNZAがロードできない環境ではテストをスキップ
_masker = NerMasker()
requires_ginza = pytest.mark.skipif(_masker._nlp is None, reason="GiNZAモデルが利用できない環境")


@requires_ginza
class TestNerMasker:
    def setup_method(self):
        self.masker = _masker

    # 人名を1件検出し、正しいラベル・元テキスト・トークン・検出元が返ること
    def test_detect_person(self):
        entities = self.masker.detect("山田太郎は会議に参加した。")
        person_entities = [e for e in entities if e.label == "Person"]
        assert len(person_entities) >= 1
        assert person_entities[0].original == "山田太郎"
        assert person_entities[0].token == "[Person_1]"
        assert person_entities[0].source == "ner"

    # 複数の人名が検出されること
    def test_detect_multiple_persons(self):
        entities = self.masker.detect("山田太郎と佐藤花子が出席した。")
        person_entities = [e for e in entities if e.label == "Person"]
        assert len(person_entities) >= 2

    # 地名がProvince/City/Country等のラベルで検出されること（GiNZAはLocationラベルを使わない）
    def test_detect_location(self):
        entities = self.masker.detect("東京都に住んでいます。")
        location_labels = {"Province", "City", "Country"}
        location_entities = [e for e in entities if e.label in location_labels]
        assert len(location_entities) >= 1

    # OrganizationラベルはTARGET_LABELSに含まれないため、検出結果に含まれないこと
    def test_ignore_organization(self):
        entities = self.masker.detect("株式会社テックサポートに連絡した。")
        org_entities = [e for e in entities if e.label == "Organization"]
        assert len(org_entities) == 0

    # PIIを含まないテキストでは人名が検出されないこと
    def test_detect_no_entities(self):
        entities = self.masker.detect("今日は天気がいいですね。")
        person_entities = [e for e in entities if e.label == "Person"]
        assert len(person_entities) == 0

    # 空文字列では何も検出されないこと
    def test_detect_empty_text(self):
        entities = self.masker.detect("")
        assert len(entities) == 0

    # 検出されたエンティティの位置情報（start/end）が元テキストの長さと一致すること
    def test_entity_has_position(self):
        entities = self.masker.detect("山田太郎です。")
        person_entities = [e for e in entities if e.label == "Person"]
        if person_entities:
            entity = person_entities[0]
            assert entity.start >= 0
            assert entity.end > entity.start
            assert entity.end - entity.start == len(entity.original)

    # 同じラベルが複数検出された場合、トークン番号が連番（[Person_1], [Person_2]）になること
    def test_token_numbering(self):
        entities = self.masker.detect("山田太郎と佐藤花子と鈴木一郎が参加した。")
        person_entities = [e for e in entities if e.label == "Person"]
        if len(person_entities) >= 2:
            tokens = [e.token for e in person_entities]
            assert "[Person_1]" in tokens
            assert "[Person_2]" in tokens


class TestNerMaskerGracefulDegradation:
    # GiNZA未ロード時（_nlp=None）にdetectが空リストを返し、クラッシュしないこと
    def test_detect_returns_empty_when_nlp_is_none(self):
        masker = NerMasker.__new__(NerMasker)
        masker._nlp = None
        entities = masker.detect("山田太郎は東京都に住んでいます。")
        assert entities == []
