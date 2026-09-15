"""ChromaDBのデータを確認するスクリプト（ホストから直接実行可能）"""

import argparse
import sys
from pathlib import Path

import chromadb


def get_client(db_path: str) -> chromadb.ClientAPI:
    return chromadb.PersistentClient(path=db_path)


def cmd_list(client: chromadb.ClientAPI, args: argparse.Namespace) -> None:
    collections = client.list_collections()
    if not collections:
        print("コレクションが存在しません。")
        return

    print(f"{'コレクション名':<25} {'ドキュメント数':>10}")
    print("-" * 40)
    for col in collections:
        # chromadb 1.x は Collection オブジェクト、0.5 系は名前（str）を返すため両方に対応する
        name = col if isinstance(col, str) else col.name
        count = client.get_collection(name).count()
        print(f"{name:<25} {count:>10}")


def cmd_show(client: chromadb.ClientAPI, args: argparse.Namespace) -> None:
    try:
        collection = client.get_collection(args.collection)
    except Exception:
        print(f"コレクション '{args.collection}' が見つかりません。")
        return

    count = collection.count()
    print(f"=== {args.collection} ({count}件) ===\n")

    if count == 0:
        print("データなし")
        return

    limit = args.limit or count
    results = collection.get(include=["documents", "metadatas"], limit=limit)

    for i, (doc_id, text, meta) in enumerate(
        zip(results["ids"], results["documents"], results["metadatas"])
    ):
        print(f"--- [{i + 1}] ID: {doc_id[:16]}... ---")
        print(f"  メタデータ: {meta}")
        max_len = args.text_length
        display = text[:max_len] + "..." if len(text) > max_len else text
        print(f"  テキスト: {display}")
        print()


def cmd_search(client: chromadb.ClientAPI, args: argparse.Namespace) -> None:
    try:
        collection = client.get_collection(args.collection)
    except Exception:
        print(f"コレクション '{args.collection}' が見つかりません。")
        return

    # メタデータでフィルタ検索
    where = {}
    if args.source:
        where["source"] = args.source

    results = collection.get(
        include=["documents", "metadatas"],
        where=where if where else None,
    )

    if not results["ids"]:
        print("該当データなし")
        return

    print(f"=== 検索結果: {len(results['ids'])}件 ===\n")
    for i, (doc_id, text, meta) in enumerate(
        zip(results["ids"], results["documents"], results["metadatas"])
    ):
        print(f"--- [{i + 1}] ID: {doc_id[:16]}... ---")
        print(f"  メタデータ: {meta}")
        max_len = args.text_length
        display = text[:max_len] + "..." if len(text) > max_len else text
        print(f"  テキスト: {display}")
        print()


def cmd_delete(client: chromadb.ClientAPI, args: argparse.Namespace) -> None:
    try:
        collection = client.get_collection(args.collection)
    except Exception:
        print(f"コレクション '{args.collection}' が見つかりません。")
        return

    before = collection.count()

    if args.all:
        ids = collection.get()["ids"]
        if ids:
            collection.delete(ids=ids)
        print(f"{before}件を全削除しました。")
    elif args.id:
        collection.delete(ids=[args.id])
        print(f"ID '{args.id}' を削除しました。")
    else:
        print("--all または --id を指定してください。")


def main() -> None:
    parser = argparse.ArgumentParser(description="ChromaDB データ確認ツール")
    parser.add_argument(
        "--db-path",
        default=str(Path(__file__).parent.parent / "data" / "chroma_db"),
        help="ChromaDBのデータディレクトリ",
    )

    subparsers = parser.add_subparsers(dest="command", required=True)

    subparsers.add_parser("list", help="コレクション一覧を表示")

    show_parser = subparsers.add_parser("show", help="コレクションのデータを表示")
    show_parser.add_argument("collection", help="コレクション名")
    show_parser.add_argument("--limit", type=int, help="表示件数")
    show_parser.add_argument("--text-length", type=int, default=200, help="テキスト表示文字数")

    search_parser = subparsers.add_parser("search", help="メタデータでフィルタ検索")
    search_parser.add_argument("collection", help="コレクション名")
    search_parser.add_argument("--source", help="ソース種別でフィルタ（manual/eml/zendesk等）")
    search_parser.add_argument("--text-length", type=int, default=200, help="テキスト表示文字数")

    delete_parser = subparsers.add_parser("delete", help="データを削除")
    delete_parser.add_argument("collection", help="コレクション名")
    delete_parser.add_argument("--id", help="削除するドキュメントID")
    delete_parser.add_argument("--all", action="store_true", help="全件削除")

    args = parser.parse_args()
    client = get_client(args.db_path)

    commands = {
        "list": cmd_list,
        "show": cmd_show,
        "search": cmd_search,
        "delete": cmd_delete,
    }
    commands[args.command](client, args)


if __name__ == "__main__":
    main()
