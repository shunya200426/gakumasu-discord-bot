from typing import Literal, Final

# ステータス3種
Stat = Literal["Vo", "Da", "Vi"]
VO: Final[str] = "Vo"
DA: Final[str] = "Da"
VI: Final[str] = "Vi"

# 流行タイプ
TrendType = Literal["balanced", "focused"]
BALANCED: Final[str] = "balanced"
FOCUSED: Final[str] = "focused"

# モード
Mode = Literal["regular", "pro", "master"]
REGULAR: Final[str] = "regular"
PRO: Final[str] = "pro"
MASTER: Final[str] = "master"

# NIAのオーディション内部キー
Audition = Literal["finale", "quartet", "idol_bigup!"]
FINALE: Final[str] = "finale"
QUARTET: Final[str] = "quartet"
IDOL_BIGUP: Final[str] = "idol_bigup!"

# 表示名（Embed等はこれを使用。内部キーとは分離）
AUDITION_DISPLAY: dict[str, str] = {
    FINALE: "FINALE",
    QUARTET: "QUARTET",
    IDOL_BIGUP: "IDOLBigup!",
}
MODE_DISPLAY: dict[str, str] = {
    REGULAR: "レギュラー",
    PRO: "プロ",
    MASTER: "マスター",
}
