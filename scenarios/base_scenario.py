# scenariosbase.py
import math
from abc import ABC, abstractmethod

from config.settings import SETTINGS
from utils.logger import get_logger


class ScenarioBase(ABC):
    def __init__(
        self, 
        mode: str,
        scenario_key: str,
    ):
        """
        mode:
            シナリオ内の難易度

        scenario_key:
            SETTINGS["boost"] のシナリオキー
            例: "NIA", "Hajime", "HIF"

        boost_key:
            強化月間設定を取得するためのキー。
            未指定なら mode を使用する。
            HIFのように難易度が存在しない場合は "default" を指定する。
        """

        self.mode = mode
        self.scenario_key = scenario_key

        self.stat_multiplier = SETTINGS["stat_multiplier"]
        self.thresholds = SETTINGS["grade_thresholds"]

        self.log = get_logger(context={
            "scenario": self.__class__.__name__,  # 生成されたシナリオ名
            "mode": mode
        })
        self.log.debug("Initialized scenario=%s with mode=%s", self.__class__.__name__, mode)

    def _apply_attenuation(self, raw_exam_score: int, thresholds: list, coefficients: list, den: int = 1000) -> int:
        """
        試験のスコアを、評価値点へ変換する
        raw_exam_score: 試験のスコア
        thresholds: 減衰の区間のリスト
        coefficients: 係数のリスト
        den: 係数の母数
        """
        out = []
        for i in range(len(thresholds)-1):
            width = max(0, min(raw_exam_score, thresholds[i+1]) - thresholds[i])
            out.append((width * coefficients[i]) // den)
        
        exam_eval_points = sum(out)
        
        # 減衰処理をしたスコアの値を返す
        return exam_eval_points

    def calclate_stats_score(self, vo: int, da: int, vi: int, rate: float = 2.3):
        """ステータス合計値 × 共通倍率"""
        total = vo + da + vi
        st_value = total * rate
        return math.floor(st_value)
    
    def get_grade(self, score: int):
        """
        最終評価スコアに応じたランクを返す
        """
        for grade, threshold in sorted(self.thresholds.items(), key=lambda x: -x[1]):
            if score >= threshold:
                return grade
        return "B"  # 最低ランク
    
    def boosted_mode(self, score: int, kirameki: int) -> int:
        """
        アイドル強化月間

        通常評価値 × boost_coeff
        + きらめき × kirameki_coeff
        """
        boost = SETTINGS["boost"][self.scenario_key][self.mode]

        final_score = (
            score * boost["boost_coeff"]
            + kirameki * boost["kirameki_coeff"]
        )

        return math.floor(final_score)
    
    @abstractmethod
    def calculate_score(self):
        """
        評価値計算
        子クラスでそれぞれ実装
        """
