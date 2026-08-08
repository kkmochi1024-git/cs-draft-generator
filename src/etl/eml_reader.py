"""
.emlファイルからメール本文・ヘッダーを抽出し、スレッド構築・ペア判定を行うモジュール。
"""

import email
import email.policy
import logging
from dataclasses import dataclass, field
from datetime import datetime
from email.utils import parsedate_to_datetime
from pathlib import Path

logger = logging.getLogger(__name__)


@dataclass
class ParsedEmail:
    subject: str
    from_address: str
    to_address: str
    date: datetime | None
    body: str
    message_id: str
    in_reply_to: str | None = None
    references: list[str] = field(default_factory=list)


@dataclass
class EmailThread:
    thread_id: str
    emails: list[ParsedEmail]
    pairs: list[tuple[str, str]] = field(default_factory=list)


class EmlReader:
    def parse_file(self, path: Path) -> ParsedEmail | None:
        try:
            with open(path, "rb") as f:
                msg = email.message_from_binary_file(f, policy=email.policy.default)
        except Exception:
            logger.warning("ファイルのパースに失敗しました: %s", path)
            return None

        body = self._extract_body(msg)
        if body is None:
            logger.warning("本文を抽出できませんでした: %s", path)
            return None

        date = None
        date_str = msg.get("Date")
        if date_str:
            try:
                date = parsedate_to_datetime(date_str)
            except Exception:
                pass

        references_raw = msg.get("References", "")
        references = [r.strip() for r in references_raw.split() if r.strip()] if references_raw else []

        return ParsedEmail(
            subject=msg.get("Subject", ""),
            from_address=msg.get("From", ""),
            to_address=msg.get("To", ""),
            date=date,
            body=body,
            message_id=msg.get("Message-ID", ""),
            in_reply_to=msg.get("In-Reply-To"),
            references=references,
        )

    def parse_directory(self, path: Path) -> list[ParsedEmail]:
        emails: list[ParsedEmail] = []
        eml_files = sorted(path.glob("*.eml"))

        if not eml_files:
            logger.warning(".emlファイルが見つかりません: %s", path)
            return emails

        for eml_file in eml_files:
            parsed = self.parse_file(eml_file)
            if parsed:
                emails.append(parsed)
            else:
                logger.warning("スキップ: %s", eml_file)

        return emails

    def detect_threads(self, emails: list[ParsedEmail], support_domain: str) -> list[EmailThread]:
        # Message-IDをキーにメールを索引化
        by_id: dict[str, ParsedEmail] = {}
        for em in emails:
            if em.message_id:
                by_id[em.message_id] = em

        # スレッドをグループ化（In-Reply-To / References で親を辿る）
        thread_map: dict[str, list[ParsedEmail]] = {}
        assigned: set[str] = set()

        for em in emails:
            thread_id = self._find_thread_root(em, by_id)
            if thread_id not in thread_map:
                thread_map[thread_id] = []
            if em.message_id not in assigned:
                thread_map[thread_id].append(em)
                assigned.add(em.message_id)

        threads: list[EmailThread] = []
        for thread_id, thread_emails in thread_map.items():
            thread_emails.sort(key=lambda e: e.date or datetime.min)
            pairs = self._detect_pairs(thread_emails, support_domain)
            threads.append(EmailThread(thread_id=thread_id, emails=thread_emails, pairs=pairs))

        return threads

    def _extract_body(self, msg: email.message.Message) -> str | None:
        """text/plain優先、なければtext/htmlをテキスト化"""
        if not msg.is_multipart():
            content_type = msg.get_content_type()
            if content_type == "text/plain":
                return self._decode_payload(msg)
            if content_type == "text/html":
                return self._html_to_text(self._decode_payload(msg) or "")
            return None

        # マルチパート: text/plainを優先探索
        plain_text = None
        html_text = None
        for part in msg.walk():
            content_type = part.get_content_type()
            if content_type == "text/plain" and plain_text is None:
                plain_text = self._decode_payload(part)
            elif content_type == "text/html" and html_text is None:
                html_text = self._decode_payload(part)

        if plain_text:
            return plain_text
        if html_text:
            return self._html_to_text(html_text)
        return None

    def _decode_payload(self, part: email.message.Message) -> str | None:
        payload = part.get_payload(decode=True)
        if payload is None:
            return None

        charset = part.get_content_charset()
        # エンコーディングのフォールバックチェーン
        for enc in [charset, "utf-8", "iso-2022-jp", "shift_jis", "cp932"]:
            if enc is None:
                continue
            try:
                return payload.decode(enc)
            except (UnicodeDecodeError, LookupError):
                continue

        return payload.decode("utf-8", errors="replace")

    def _html_to_text(self, html: str) -> str:
        try:
            from bs4 import BeautifulSoup

            soup = BeautifulSoup(html, "html.parser")
            return soup.get_text(separator="\n", strip=True)
        except ImportError:
            logger.warning("BeautifulSoup未インストール。HTMLタグを除去せずに返します。")
            return html

    def _find_thread_root(
        self, em: ParsedEmail, by_id: dict[str, ParsedEmail], visited: set[str] | None = None
    ) -> str:
        """In-Reply-To / References を辿ってスレッドの最初のMessage-IDを返す"""
        if visited is None:
            visited = set()
        # 循環参照を検出して無限再帰を防止
        if em.message_id in visited:
            return em.message_id or str(id(em))
        visited.add(em.message_id)

        if em.references:
            return em.references[0]
        if em.in_reply_to and em.in_reply_to in by_id:
            parent = by_id[em.in_reply_to]
            return self._find_thread_root(parent, by_id, visited)
        return em.message_id or str(id(em))

    def _detect_pairs(self, emails: list[ParsedEmail], support_domain: str) -> list[tuple[str, str]]:
        """顧客メール→直後のサポートメールをペアとして抽出"""
        pairs: list[tuple[str, str]] = []
        support_domain = support_domain.lower().lstrip("@")

        i = 0
        while i < len(emails) - 1:
            current = emails[i]
            next_email = emails[i + 1]

            current_is_customer = support_domain not in current.from_address.lower()
            next_is_support = support_domain in next_email.from_address.lower()

            if current_is_customer and next_is_support:
                pairs.append((current.body, next_email.body))
                i += 2
            else:
                i += 1

        return pairs
