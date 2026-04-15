from .character_settings import CHARACTERS
from .hajime_settings import HAJIME
from .nia_settings import NIA

SETTINGS = {
    # キャラクター辞書
    "characters": CHARACTERS,

    # シナリオ共通設定
    "stat_multiplier": 2.3,     # ステータス合計値倍率

    "grade_thresholds": {    # 評価ランク範囲
        "S4": 26000,
        "SSS+": 23000,
        "SSS": 20000,
        "SS+": 18000,
        "SS": 16000,
        "S+": 14500,
        "S": 13000,
        "A+": 11500,
        "A": 10000,
    },

    # 強化月間補正
    "boost": {
        "boost_coeff": 0.7,                                 # 強化月間スコア補正
        "kirameki_coeff": {"pro": 9.6625, "master": 10.82}, # きらめき1個あたりの加点
    },

    # シナリオ別設定
    "Hajime": HAJIME,   # 「初」専用設定
    "NIA": NIA,         # NIA専用設定
}