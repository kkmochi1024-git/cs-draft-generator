from pathlib import Path

from src.etl.eml_reader import EmlReader

FIXTURES_DIR = Path(__file__).parent / "fixtures"


class TestEmlReaderParseFile:
    def setup_method(self):
        self.reader = EmlReader()

    # 問い合わせメールから件名・送信元・本文・Message-ID・日時を正しく抽出できること
    def test_parse_inquiry(self):
        result = self.reader.parse_file(FIXTURES_DIR / "inquiry.eml")
        assert result is not None
        assert "パスワード" in result.subject
        assert "yamada-taro@customer.co.jp" in result.from_address
        assert result.body is not None
        assert "山田太郎" in result.body
        assert result.message_id == "<msg001@customer.co.jp>"
        assert result.date is not None

    # 返信メールからIn-Reply-To・Referencesヘッダーを正しく抽出できること
    def test_parse_response(self):
        result = self.reader.parse_file(FIXTURES_DIR / "response.eml")
        assert result is not None
        assert result.in_reply_to == "<msg001@customer.co.jp>"
        assert "<msg001@customer.co.jp>" in result.references
        assert "ログイン画面" in result.body

    # 存在しないファイルを指定した場合、Noneが返りクラッシュしないこと
    def test_parse_nonexistent_file(self):
        result = self.reader.parse_file(FIXTURES_DIR / "nonexistent.eml")
        assert result is None

    # 送信元・送信先・日時のメタデータが正しく抽出されること
    def test_parse_extracts_metadata(self):
        result = self.reader.parse_file(FIXTURES_DIR / "standalone.eml")
        assert result is not None
        assert "tanaka@other.co.jp" in result.from_address
        assert "techsupport.com" in result.to_address
        assert result.date is not None


class TestEmlReaderParseDirectory:
    def setup_method(self):
        self.reader = EmlReader()

    # ディレクトリ内の全.emlファイル（3件）がパースされること
    def test_parse_all_eml_files(self):
        emails = self.reader.parse_directory(FIXTURES_DIR)
        assert len(emails) == 3

    # .emlファイルが存在しないディレクトリでは空リストが返ること
    def test_parse_empty_directory(self, tmp_path):
        emails = self.reader.parse_directory(tmp_path)
        assert len(emails) == 0


class TestEmlReaderThreadDetection:
    def setup_method(self):
        self.reader = EmlReader()

    # In-Reply-To/Referencesヘッダーに基づきスレッドが1つ以上検出されること
    def test_detect_thread(self):
        emails = self.reader.parse_directory(FIXTURES_DIR)
        threads = self.reader.detect_threads(emails, support_domain="techsupport.com")
        assert len(threads) >= 1

    # 顧客メール→サポートメールの順で問い合わせ/回答ペアが正しく検出されること
    def test_detect_inquiry_response_pair(self):
        emails = self.reader.parse_directory(FIXTURES_DIR)
        threads = self.reader.detect_threads(emails, support_domain="techsupport.com")

        all_pairs = []
        for thread in threads:
            all_pairs.extend(thread.pairs)

        assert len(all_pairs) >= 1
        inquiry_body, response_body = all_pairs[0]
        assert "山田太郎" in inquiry_body
        assert "ログイン画面" in response_body

    # スレッドに属さない単独メールではペアが検出されないこと
    def test_standalone_email_has_no_pair(self):
        emails = self.reader.parse_directory(FIXTURES_DIR)
        threads = self.reader.detect_threads(emails, support_domain="techsupport.com")

        standalone_threads = [t for t in threads if any("tanaka" in e.from_address for e in t.emails)]
        for t in standalone_threads:
            assert len(t.pairs) == 0
