"""
PDFファイルからページ単位でテキストを抽出するモジュール。

製品マニュアル（PDF）をRAGに取り込むための前処理を担う。
PyMuPDF（fitz）を使用し、ページ単位でテキストを抽出する。
スキャンPDF（画像のみ）やOCRは対象外（D-003 スコープ外）。
"""

import logging
import re
from dataclasses import dataclass
from pathlib import Path

import fitz

logger = logging.getLogger(__name__)

# ページ番号のみ、または "- 12 -" のような行をヘッダー/フッターとみなして除去する簡易パターン
_PAGE_NUMBER_LINE = re.compile(r"^\s*[-–—]?\s*\d+\s*[-–—]?\s*$")


@dataclass
class ExtractedPage:
    file_name: str  # PDFファイル名（拡張子含む）
    page_number: int  # ページ番号（1始まり）
    text: str  # 抽出・整形後のテキスト


class PdfReader:
    def parse_file(self, path: Path) -> list[ExtractedPage]:
        """単一PDFからページ単位でテキストを抽出する。

        抽出できない・不正なPDFの場合は空リストを返し、クラッシュさせない。
        空白ページ（テキストなし）はスキップする。
        """
        try:
            doc = fitz.open(path)
        except Exception:
            logger.warning("PDFのオープンに失敗しました: %s", path)
            return []

        pages: list[ExtractedPage] = []
        try:
            for page_index, page in enumerate(doc):
                raw_text = page.get_text()
                cleaned = self._clean_text(raw_text)
                if not cleaned:
                    # 空白ページ・画像のみページはスキップ
                    continue
                pages.append(
                    ExtractedPage(
                        file_name=path.name,
                        page_number=page_index + 1,
                        text=cleaned,
                    )
                )
        except Exception:
            logger.warning("PDFのテキスト抽出中にエラーが発生しました: %s", path)
            return pages
        finally:
            doc.close()

        if not pages:
            logger.warning("テキストを抽出できませんでした（空白またはスキャンPDFの可能性）: %s", path)

        return pages

    def parse_directory(self, path: Path) -> list[ExtractedPage]:
        """ディレクトリ内の全PDFをファイル名順に処理し、全ページを平坦なリストで返す。"""
        pdf_files = sorted(path.glob("*.pdf"))

        if not pdf_files:
            logger.warning("PDFファイルが見つかりません: %s", path)
            return []

        all_pages: list[ExtractedPage] = []
        for pdf_file in pdf_files:
            pages = self.parse_file(pdf_file)
            if pages:
                all_pages.extend(pages)
            else:
                logger.warning("スキップ: %s", pdf_file)

        return all_pages

    def _clean_text(self, text: str) -> str:
        """ヘッダー・フッター（ページ番号のみの行等）を簡易的に除去し、前後空白を整える。"""
        if not text:
            return ""

        lines = []
        for line in text.splitlines():
            if _PAGE_NUMBER_LINE.match(line):
                # ページ番号のみの行はヘッダー/フッターとみなし除去
                continue
            lines.append(line.rstrip())

        # 連続する空行を1つに圧縮しつつ結合
        cleaned_lines: list[str] = []
        prev_blank = False
        for line in lines:
            is_blank = line.strip() == ""
            if is_blank and prev_blank:
                continue
            cleaned_lines.append(line)
            prev_blank = is_blank

        return "\n".join(cleaned_lines).strip()
