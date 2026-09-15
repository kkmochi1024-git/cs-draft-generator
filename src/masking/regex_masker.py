import re

from src.masking.models import Entity

# 住所の部品。都道府県名で始まる住所の検出（PATTERNS["ADDRESS"]）と、
# NERが検出した地名の後ろに続く番地の延長（MaskingService）で共用する
_PREFECTURE = (
    r"(?:北海道|東京都|京都府|大阪府|(?:青森|岩手|宮城|秋田|山形|福島|茨城|栃木|群馬|埼玉|千葉|神奈川"
    r"|新潟|富山|石川|福井|山梨|長野|岐阜|静岡|愛知|三重|滋賀|兵庫|奈良|和歌山|鳥取|島根|岡山|広島|山口"
    r"|徳島|香川|愛媛|高知|福岡|佐賀|長崎|熊本|大分|宮崎|鹿児島|沖縄)県)"
)
_ADDRESS_CHAR = r"[^\s、。，,：:（）()「」【】\[\]]"
_NUM = r"[0-9０-９一二三四五六七八九十]"
_HYPHEN = r"[-－‐―ー−]"
# 番地: 「1丁目1番1号」「北1条西2丁目」のような単位付き、または「1-1-1」のようなハイフン区切り。
# 直前が助詞なら番地とみなさない（「大阪府で3-4名」の「3-4」を住所にしないため）
ADDRESS_NUMBER = (
    rf"(?<![でにはをがとも])(?:[東西南北]?{_NUM}+(?:丁目|番地|番|号|条)|{_NUM}+(?:{_HYPHEN}{_NUM}+)+)+"
)
# NERが検出した地名の直後に続く「町名＋番地」（例: 「千代田区」の後ろの「丸の内1-1-1」）
ADDRESS_CONTINUATION = re.compile(rf"[^\s、。，,：:（）()「」【】\[\]0-9０-９]{{0,12}}?{ADDRESS_NUMBER}")

PATTERNS: dict[str, str] = {
    "EMAIL": r"[\w.\-+]+@[\w\-]+\.[\w.\-]+",
    # ハイフンまたはスペース区切り必須。区切りなし(0312345678)は郵便番号と誤検出するため除外
    "PHONE": r"0\d{1,4}[\-\s]\d{1,4}[\-\s]\d{3,4}",
    # 前後に数字がないことを確認し、電話番号の一部(例: 03-1234-5678の"234-5678")を誤検出しない
    "ZIPCODE": r"(?<!\d)\d{3}-\d{4}(?!\d)",
    # 都道府県名＋市区町村＋番地まで揃ったものだけを住所とする（誤検出を抑えるため）。
    # GiNZAが地名として検出しない住所（例: 大阪府大阪市北区梅田2-4-9）を補う
    "ADDRESS": rf"{_PREFECTURE}{_ADDRESS_CHAR}{{0,20}}?[市区町村郡]{_ADDRESS_CHAR}{{0,15}}?{ADDRESS_NUMBER}",
}

# 検出優先順位: 先に検出したパターンが該当範囲を占有し、後続パターンの重複検出を防ぐ
# ADDRESS は番地に数字を含むため最後にし、郵便番号・電話番号の検出を優先する
PRIORITY = ["EMAIL", "ZIPCODE", "PHONE", "ADDRESS"]


class RegexMasker:
    def detect(self, text: str) -> list[Entity]:
        entities: list[Entity] = []
        counters: dict[str, int] = {}
        # 検出済みの文字範囲を記録し、パターン間の重複マッチを排除する
        occupied: list[tuple[int, int]] = []

        for label in PRIORITY:
            pattern = PATTERNS[label]
            for match in re.finditer(pattern, text):
                start, end = match.start(), match.end()
                if any(not (end <= os or start >= oe) for os, oe in occupied):
                    continue
                counters[label] = counters.get(label, 0) + 1
                token = f"[{label}_{counters[label]}]"
                entities.append(
                    Entity(
                        original=match.group(),
                        label=label,
                        token=token,
                        start=start,
                        end=end,
                        source="regex",
                    )
                )
                occupied.append((start, end))

        entities.sort(key=lambda e: e.start)
        return entities
