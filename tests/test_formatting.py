"""format_source（参照元表示整形）のユニットテスト。"""

from src.rag.formatting import format_source


class TestFormatSource:
    # PDFマニュアル: ファイル名とページが 📄 file (p.N) 形式で整形されること
    def test_pdf_with_page(self):
        meta = {"source": "pdf_manual", "file_name": "guide.pdf", "page": "12"}
        assert format_source(meta) == "📄 guide.pdf (p.12)"

    # PDFマニュアル: ページ範囲もそのまま表示されること
    def test_pdf_with_page_range(self):
        meta = {"source": "pdf_manual", "file_name": "guide.pdf", "page": "12-13"}
        assert format_source(meta) == "📄 guide.pdf (p.12-13)"

    # PDFマニュアル: ページ欠落時はファイル名のみ表示されること
    def test_pdf_without_page(self):
        meta = {"source": "pdf_manual", "file_name": "guide.pdf"}
        assert format_source(meta) == "📄 guide.pdf"

    # メール: 件名と日付が 📧 件名 (日付) 形式で整形されること
    def test_eml_with_subject_and_date(self):
        meta = {"source": "eml", "subject": "パスワードの件", "date": "2026-05-10"}
        assert format_source(meta) == "📧 パスワードの件 (2026-05-10)"

    # メール: 件名欠落時は 📧 メール と表示されること
    def test_eml_without_subject(self):
        meta = {"source": "eml", "date": "2026-05-10"}
        assert format_source(meta) == "📧 メール (2026-05-10)"

    # 未知のソースは source と日付をそのまま表示すること
    def test_unknown_source(self):
        meta = {"source": "manual", "date": "2026-05-10"}
        assert format_source(meta) == "manual (2026-05-10)"

    # メタデータが空でもクラッシュせず unknown を返すこと
    def test_empty_metadata(self):
        assert format_source({}) == "unknown"
