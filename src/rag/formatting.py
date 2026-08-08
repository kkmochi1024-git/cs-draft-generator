"""参照元メタデータの表示整形。CUI(main.py)とGUI(app/)で共通利用する。"""


def format_source(meta: dict) -> str:
    """参照元メタデータを表示用文字列に整形する。

    - PDFマニュアル: 📄 ファイル名 (p.ページ)
    - メール: 📧 件名 (日付)
    - その他: source (日付)
    """
    source = meta.get("source", "unknown")
    if source == "pdf_manual":
        file_name = meta.get("file_name", "manual.pdf")
        page = meta.get("page", "")
        return f"📄 {file_name} (p.{page})" if page else f"📄 {file_name}"
    if source == "eml":
        subject = meta.get("subject", "")
        date = meta.get("date", "")
        label = f"📧 {subject}" if subject else "📧 メール"
        return f"{label} ({date})" if date else label
    date = meta.get("date", "")
    return f"{source} ({date})" if date else source
