"""PdfReaderのユニットテスト。
PyMuPDFでフィクスチャPDFを動的生成し、外部ファイルに依存せず抽出処理を検証する。
IndexServiceのページ範囲算出ロジック（純粋関数）もあわせて検証する。"""

import fitz

from src.etl.pdf_reader import ExtractedPage, PdfReader
from src.masking.models import Entity
from src.rag.index_service import IndexService


def _make_pdf(path, pages_text: list[str]) -> None:
    """各要素を1ページとするPDFを生成する。空文字列は空白ページになる。"""
    doc = fitz.open()
    for text in pages_text:
        page = doc.new_page()
        if text:
            page.insert_text((72, 72), text, fontsize=11)
    doc.save(str(path))
    doc.close()


class TestPdfReaderParseFile:
    def setup_method(self):
        self.reader = PdfReader()

    # 複数ページPDFからページ単位でテキストが抽出され、ページ番号が1始まりで付与されること
    def test_parse_multipage(self, tmp_path):
        # PyMuPDFの既定フォント(helv)は日本語グリフを埋め込めないため、抽出内容の検証はASCIIで行う
        pdf = tmp_path / "manual.pdf"
        _make_pdf(pdf, ["First page content", "Second page content"])

        pages = self.reader.parse_file(pdf)

        assert len(pages) == 2
        assert all(isinstance(p, ExtractedPage) for p in pages)
        assert pages[0].page_number == 1
        assert pages[1].page_number == 2
        assert pages[0].file_name == "manual.pdf"
        assert "First page" in pages[0].text
        assert "Second page" in pages[1].text

    # テキストのない空白ページはスキップされ、番号は実在ページのものになること
    def test_blank_page_skipped(self, tmp_path):
        pdf = tmp_path / "with_blank.pdf"
        _make_pdf(pdf, ["Body page", "", "Last page"])

        pages = self.reader.parse_file(pdf)

        assert len(pages) == 2
        # 空白の2ページ目はスキップされ、3ページ目が残る
        assert pages[0].page_number == 1
        assert pages[1].page_number == 3

    # 存在しないファイルを指定した場合、空リストが返りクラッシュしないこと
    def test_nonexistent_file(self, tmp_path):
        pages = self.reader.parse_file(tmp_path / "nope.pdf")
        assert pages == []

    # PDFでない不正なファイルを指定した場合、空リストが返りクラッシュしないこと
    def test_invalid_file(self, tmp_path):
        bogus = tmp_path / "broken.pdf"
        bogus.write_bytes(b"this is not a pdf")
        pages = self.reader.parse_file(bogus)
        assert pages == []

    # ページ番号のみの行（ヘッダー/フッター）が除去されること
    def test_page_number_line_removed(self, tmp_path):
        pdf = tmp_path / "footer.pdf"
        _make_pdf(pdf, ["Important body text\n- 12 -"])

        pages = self.reader.parse_file(pdf)

        assert len(pages) == 1
        assert "Important body text" in pages[0].text
        assert "- 12 -" not in pages[0].text


class TestPdfReaderParseDirectory:
    def setup_method(self):
        self.reader = PdfReader()

    # ディレクトリ内の複数PDFがファイル名順に全ページ平坦化されて返ること
    def test_parse_directory(self, tmp_path):
        _make_pdf(tmp_path / "a.pdf", ["Aの1ページ", "Aの2ページ"])
        _make_pdf(tmp_path / "b.pdf", ["Bの1ページ"])

        pages = self.reader.parse_directory(tmp_path)

        assert len(pages) == 3
        file_names = {p.file_name for p in pages}
        assert file_names == {"a.pdf", "b.pdf"}

    # PDFが存在しないディレクトリでは空リストが返ること
    def test_empty_directory(self, tmp_path):
        assert self.reader.parse_directory(tmp_path) == []


class TestPageRangeLogic:
    """IndexServiceのページ範囲算出ロジック（マスキング非依存の純粋関数）を検証する。"""

    # チャンクが単一ページ内に収まる場合、そのページ番号のみが返ること
    def test_single_page(self):
        spans = [(0, 100, 1), (100, 200, 2)]
        assert IndexService._page_range_str(spans, 10, 50) == "1"

    # チャンクがページ境界をまたぐ場合、範囲 "1-2" が返ること
    def test_page_range(self):
        spans = [(0, 100, 1), (100, 200, 2)]
        assert IndexService._page_range_str(spans, 90, 150) == "1-2"

    # どのページにも重ならない場合は空文字が返ること
    def test_no_overlap(self):
        spans = [(0, 100, 12)]
        assert IndexService._page_range_str(spans, 200, 250) == ""

    # エンティティがない場合、マスキング後位置は元位置と同じであること
    def test_orig_to_masked_no_entities(self):
        assert IndexService._orig_to_masked_pos(50, []) == 50

    # 手前のエンティティのトークン長差分だけ位置が補正されること
    def test_orig_to_masked_with_entity(self):
        # 元 "山田太郎"(4文字) → トークン "[PERSON_1]"(10文字), +6 のずれ
        entity = Entity(original="山田太郎", label="PERSON", token="[PERSON_1]", start=0, end=4, source="ner")
        assert IndexService._orig_to_masked_pos(20, [entity]) == 26
