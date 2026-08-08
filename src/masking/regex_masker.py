import re

from src.masking.models import Entity

PATTERNS: dict[str, str] = {
    "EMAIL": r"[\w.\-+]+@[\w\-]+\.[\w.\-]+",
    # ハイフンまたはスペース区切り必須。区切りなし(0312345678)は郵便番号と誤検出するため除外
    "PHONE": r"0\d{1,4}[\-\s]\d{1,4}[\-\s]\d{3,4}",
    # 前後に数字がないことを確認し、電話番号の一部(例: 03-1234-5678の"234-5678")を誤検出しない
    "ZIPCODE": r"(?<!\d)\d{3}-\d{4}(?!\d)",
}

# 検出優先順位: 先に検出したパターンが該当範囲を占有し、後続パターンの重複検出を防ぐ
PRIORITY = ["EMAIL", "ZIPCODE", "PHONE"]


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
