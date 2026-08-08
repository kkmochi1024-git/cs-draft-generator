import argparse
import sys

from src.masking.service import MaskingService


def _read_multiline(prompt: str) -> str:
    """Docker tty環境ではsys.stdin.read()のCtrl+Dが効かないため、input()ループで1行ずつ読み取る。
    1行以上入力後に空行Enterで入力完了とする。"""
    print(prompt)
    print("（入力完了は空行のみでEnter）")
    lines: list[str] = []
    try:
        while True:
            line = input()
            if line == "" and lines:
                break
            lines.append(line)
    except (EOFError, KeyboardInterrupt):
        pass
    return "\n".join(lines).strip()


def cmd_mask(args: argparse.Namespace) -> None:
    service = MaskingService()

    if args.text:
        text = " ".join(args.text)
    elif not sys.stdin.isatty():
        text = sys.stdin.read().strip()
    else:
        text = _read_multiline("テキストを入力してください（空行でEnter、またはCtrl+Dで終了）:")

    if not text:
        print("テキストが入力されていません。")
        return

    result = service.mask(text)
    print("\n[マスキング結果]")
    print(result.masked_text)
    print("\n[検出PII]")
    if result.entities:
        for entity in result.entities:
            print(f"  {entity.token} → {entity.original} ({entity.label}, {entity.source})")
    else:
        print("  PIIは検出されませんでした。")


def cmd_register(args: argparse.Namespace) -> None:
    # Ollama接続が必要なためインポートを遅延し、maskコマンド等では接続不要にする
    from src import config
    from src.rag.index_service import IndexService

    masking = MaskingService()

    # PDFはマニュアル専用コレクションに登録する
    if args.pdf:
        pdf_index = IndexService(masking_service=masking, collection_name=config.COLLECTION_MANUALS)
        _register_pdf_file(args, pdf_index)
        return
    if args.pdf_dir:
        pdf_index = IndexService(masking_service=masking, collection_name=config.COLLECTION_MANUALS)
        _register_pdf_dir(args, pdf_index)
        return

    index = IndexService(masking_service=masking)

    if args.eml:
        _register_eml_file(args, index)
        return
    if args.eml_dir:
        _register_eml_dir(args, index)
        return

    # テキスト直接入力
    if not sys.stdin.isatty():
        text = sys.stdin.read().strip()
    else:
        text = _read_multiline("登録するテキストを入力してください（空行でEnter、またはCtrl+Dで終了）:")

    if not text:
        print("テキストが入力されていません。")
        return

    if not args.yes:
        preview = masking.mask(text)
        print("\n[マスキングプレビュー]")
        print(preview.masked_text)
        print("\n[検出PII]")
        for entity in preview.entities:
            print(f"  {entity.token} → {entity.original}")
        confirm = input("\nこの内容で登録しますか？ (y/N): ")
        if confirm.lower() != "y":
            print("登録をキャンセルしました。")
            return

    result = index.register(text)
    print(f"\n登録完了: {result.chunk_count} チャンクを登録しました。")

    stats = index.get_stats()
    print(f"登録済みドキュメント数: {stats['total_documents']}")


def _register_eml_file(args: argparse.Namespace, index) -> None:
    from pathlib import Path

    from src.etl.eml_reader import EmlReader

    reader = EmlReader()
    parsed = reader.parse_file(Path(args.eml))
    if not parsed:
        print(f"ファイルのパースに失敗しました: {args.eml}")
        return

    metadata = {"source": "eml", "subject": parsed.subject}
    if parsed.date:
        metadata["date"] = parsed.date.isoformat()

    result = index.register(parsed.body, metadata=metadata)
    print(f"登録完了: {result.chunk_count} チャンク（{parsed.subject}）")

    stats = index.get_stats()
    print(f"登録済みドキュメント数: {stats['total_documents']}")


def _register_eml_dir(args: argparse.Namespace, index) -> None:
    from pathlib import Path

    from src import config
    from src.etl.eml_reader import EmlReader

    reader = EmlReader()
    support_domain = args.support_domain or config.SUPPORT_DOMAIN

    emails = reader.parse_directory(Path(args.eml_dir))
    if not emails:
        print(f".emlファイルが見つかりません: {args.eml_dir}")
        return

    print(f"{len(emails)} 件の.emlファイルを検出しました。")

    total_chunks = 0

    if support_domain:
        # スレッド検出+ペア登録
        threads = reader.detect_threads(emails, support_domain)
        for thread in threads:
            if thread.pairs:
                first_email = thread.emails[0]
                base_meta = {
                    "source": "eml",
                    "thread_id": thread.thread_id,
                    "subject": first_email.subject,
                }
                if first_email.date:
                    base_meta["date"] = first_email.date.isoformat()
                for inquiry_body, response_body in thread.pairs:
                    for body, role in [(inquiry_body, "inquiry"), (response_body, "response")]:
                        metadata = {**base_meta, "role": role}
                        result = index.register(body, metadata=metadata)
                        total_chunks += result.chunk_count
            else:
                # ペアなしのメールは個別登録
                for em in thread.emails:
                    metadata = {"source": "eml", "subject": em.subject}
                    if em.date:
                        metadata["date"] = em.date.isoformat()
                    result = index.register(em.body, metadata=metadata)
                    total_chunks += result.chunk_count
    else:
        # サポートドメイン未設定: 全メールを個別登録
        for em in emails:
            metadata = {"source": "eml", "subject": em.subject}
            if em.date:
                metadata["date"] = em.date.isoformat()
            result = index.register(em.body, metadata=metadata)
            total_chunks += result.chunk_count

    print(f"\n登録完了: {total_chunks} チャンク（{len(emails)} 件のメール）")

    stats = index.get_stats()
    print(f"登録済みドキュメント数: {stats['total_documents']}")


def _register_pdf_file(args: argparse.Namespace, index) -> None:
    from pathlib import Path

    from src.etl.pdf_reader import PdfReader

    reader = PdfReader()
    path = Path(args.pdf)
    pages = reader.parse_file(path)
    if not pages:
        print(f"PDFからテキストを抽出できませんでした: {args.pdf}")
        return

    result = index.register_pages(pages, file_name=path.name)
    print(f"登録完了: {result.chunk_count} チャンク（{path.name} / {len(pages)} ページ）")

    stats = index.get_stats()
    print(f"登録済みマニュアルチャンク数: {stats['total_documents']}")


def _register_pdf_dir(args: argparse.Namespace, index) -> None:
    from pathlib import Path

    from src.etl.pdf_reader import PdfReader

    reader = PdfReader()
    pages = reader.parse_directory(Path(args.pdf_dir))
    if not pages:
        print(f"PDFファイルが見つかりません（またはテキスト抽出不可）: {args.pdf_dir}")
        return

    # ファイル名ごとにページをまとめて登録する
    pages_by_file: dict[str, list] = {}
    for page in pages:
        pages_by_file.setdefault(page.file_name, []).append(page)

    total_chunks = 0
    for file_name, file_pages in pages_by_file.items():
        result = index.register_pages(file_pages, file_name=file_name)
        total_chunks += result.chunk_count
        print(f"  {file_name}: {result.chunk_count} チャンク（{len(file_pages)} ページ）")

    print(f"\n登録完了: {total_chunks} チャンク（{len(pages_by_file)} 件のPDF）")

    stats = index.get_stats()
    print(f"登録済みマニュアルチャンク数: {stats['total_documents']}")


def cmd_ask(args: argparse.Namespace) -> None:
    from src.rag.formatting import format_source
    from src.rag.query_service import QueryService

    masking = MaskingService()
    query = QueryService(masking_service=masking)

    question = " ".join(args.question)
    if not question:
        print("質問を入力してください。")
        return

    print("回答を生成中...")
    result = query.ask(question)

    print(f"\n[回答]\n{result.answer}")

    if result.source_documents:
        print("\n[参照元]")
        for doc in result.source_documents:
            print(f"  - {format_source(doc.get('metadata', {}))}")


def cmd_chat(args: argparse.Namespace) -> None:
    from src.rag.formatting import format_source
    from src.rag.query_service import QueryService

    masking = MaskingService()
    query = QueryService(masking_service=masking)

    print("チャットモードを開始します（'quit' または 'exit' で終了）")
    print("-" * 50)

    while True:
        try:
            question = input("\n質問> ").strip()
        except (EOFError, KeyboardInterrupt):
            print("\nチャットを終了します。")
            break

        if question.lower() in ("quit", "exit", "q"):
            print("チャットを終了します。")
            break

        if not question:
            continue

        print("回答を生成中...")
        result = query.ask(question)
        print(f"\n{result.answer}")

        if result.source_documents:
            print("\n[参照元]")
            for doc in result.source_documents:
                print(f"  - {format_source(doc.get('metadata', {}))}")


def main() -> None:
    parser = argparse.ArgumentParser(description="CS Draft Generator - カスタマーサポート回答ドラフト生成")
    subparsers = parser.add_subparsers(dest="command", required=True)

    mask_parser = subparsers.add_parser("mask", help="PIIマスキングのみ実行")
    mask_parser.add_argument("text", nargs="*", help="マスキング対象テキスト")

    register_parser = subparsers.add_parser("register", help="テキストをRAGに登録")
    register_parser.add_argument("--yes", "-y", action="store_true", help="確認をスキップ")
    register_parser.add_argument("--eml", help=".emlファイルのパス")
    register_parser.add_argument("--eml-dir", help=".emlファイルが格納されたディレクトリのパス")
    register_parser.add_argument("--support-domain", help="サポート側メールドメイン（ペア判定用）")
    register_parser.add_argument("--pdf", help="製品マニュアルPDFファイルのパス")
    register_parser.add_argument("--pdf-dir", help="PDFが格納されたディレクトリのパス")

    ask_parser = subparsers.add_parser("ask", help="質問に回答を生成")
    ask_parser.add_argument("question", nargs="+", help="質問テキスト")

    subparsers.add_parser("chat", help="対話モード")

    args = parser.parse_args()

    commands = {
        "mask": cmd_mask,
        "register": cmd_register,
        "ask": cmd_ask,
        "chat": cmd_chat,
    }
    commands[args.command](args)


if __name__ == "__main__":
    main()
