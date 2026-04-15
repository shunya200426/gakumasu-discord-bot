# scenariosbase.py
from abc import ABC, abstractmethod
from config.settings import SETTINGS
from utils.logger import get_logger
import math

class ScenarioBase(ABC):
    def __init__(self, mode: str):
        """"
        モード選択のみどのシナリオも共通
        """
        self.mode = mode
        self.stat_multiplier = SETTINGS["stat_multiplier"]
        self.thresholds = SETTINGS["grade_thresholds"]

        self.log = get_logger(context={
            "scenario": self.__class__.__name__,  # 生成されたシナリオ名
            "mode": mode
        })
        self.log.debug("Initialized scenario=%s with mode=%s", self.__class__.__name__, mode)

    def calclate_stats_score(self, vo: int, da: int, vi: int, rate: float = 2.3):
        """ステータス合計値 × 共通倍率"""
        total = vo + da + vi
        # st_value = total * self.stat_multiplier
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
        """
        boost = SETTINGS["boost"]
        final_score = score * boost["boost_coeff"] + kirameki * boost["kirameki_coeff"][self.mode]
        return math.floor(final_score)
    
    @abstractmethod
    def calculate_score(self):
        """
        評価値計算
        子クラスでそれぞれ実装
        """
        pass