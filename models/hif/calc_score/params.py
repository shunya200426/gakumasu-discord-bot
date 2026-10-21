# models/hif/calc_score/params.py

from dataclasses import dataclass


@dataclass
class HifCalcScoreParams:
    # モード
    mode: str

    # パラメータ
    vo_status: int
    da_status: int
    vi_status: int

    # 試験終了時アビ点数
    vo_ability: int
    da_ability: int
    vi_ability: int

    # アイドル強化月間
    is_boost_active: bool
    kirameki: int

    # R1 / R2スコア
    round1_score: int | None
    round2_score: int | None

    # スター性
    star_before_round1: int | None
    star_before_round2: int | None

    # キャラクター
    character: str | None