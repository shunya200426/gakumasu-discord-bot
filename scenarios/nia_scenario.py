# scenarios/nia_scenario.py

from .base_scenario import ScenarioBase
from config.constants import MASTER
from config.accessors import (
    get_character_trend,
    get_nia_audition_status_block,
)
from models.nia.final_grade.params import NiaFinalGradeParams
from models.nia.final_grade.result import NiaFinalGradeResult
from config.settings import SETTINGS
from utils.logger import get_logger
import math

class NiaScenario(ScenarioBase):
    def __init__(self, mode: str):
        super().__init__(mode)
        self.settings = SETTINGS["NIA"]
        # 文脈付きロガー（シナリオ/モード）
        self.log = get_logger(context={"scenario": "NIA", "mode": mode})

    def calculate_score(self, params: NiaFinalGradeParams) -> NiaFinalGradeResult:
        """
        NIAの評価値を計算する
        """
        import time
        t0 = time.perf_counter()
        self.log.debug("start: calculate_score")
        self.log.debug(
            "input_summary character=%s audition=%s scores(vo,da,vi,tot)=(%d,%d,%d,%d) fans=%d boost=%s kirameki=%d",
            params.character, params.audition,
            params.vo_score, params.da_score, params.vi_score,
            params.vo_score + params.da_score + params.vi_score,
            params.now_fans, params.is_boost_active, params.kirameki
        )

        # 入力情報を整理
        audition_score = params.vo_score + params.da_score + params.vi_score

        # オーディションスコアからステータスの上昇量を計算
        get_vo_status, get_da_status, get_vi_status = self.calculate_get_status(
            character=params.character,
            audition=params.audition,
            vo_score=params.vo_score,
            da_score=params.da_score,
            vi_score=params.vi_score,
            vo_bonus=params.vo_bonus,
            da_bonus=params.da_bonus,
            vi_bonus=params.vi_bonus,
            challenge_P_item=params.challenge_P_item
        )

        # 最終ステータス
        final_vo_status = min(params.vo_status + get_vo_status, self.settings[self.mode]["st_max"])
        final_da_status = min(params.da_status + get_da_status, self.settings[self.mode]["st_max"])
        final_vi_status = min(params.vi_status + get_vi_status, self.settings[self.mode]["st_max"])


        # ステータスによる基本スコア
        status_score = self.calclate_stats_score(
            vo=final_vo_status,
            da=final_da_status,
            vi=final_vi_status
        )

        # オーディションスコアから得られるファン数
        get_fans = self.calculate_get_fans(audition=params.audition, audition_score=audition_score)

        # 最終ファン数 = 現在 + 獲得
        final_fans = params.now_fans + get_fans

        # ランク判定
        fan_grade = self.get_fan_grade(final_fans)

        # ファンによる加点スコア
        fan_score = self.calculate_fan_score(fan_grade=fan_grade, final_fans=final_fans)

        # 合算して最終スコア
        final_score = status_score + fan_score

        get_kiramekis = 0
        if params.is_boost_active:
            get_kiramekis = self.calculate_get_kirameki(audition_score)
            final_score = self.boosted_mode(final_score, params.kirameki + get_kiramekis)

        final_grade = self.get_grade(final_score)

        dt = (time.perf_counter() - t0) * 1000
        self.log.debug(
            "result_summary final_score=%d grade=%s status_score=%d fan_score=%d final_fans=%d fan_grade=%s time_ms=%.1f",
            final_score, final_grade, status_score, fan_score, final_fans, fan_grade, dt
        )
        self.log.debug("end: calculate_score")

        result = NiaFinalGradeResult(
            **params.__dict__,
            final_score=final_score,
            final_grade=final_grade,
            status_score=status_score,
            fan_score=fan_score,
            get_vo_status=get_vo_status,
            get_da_status=get_da_status,
            get_vi_status=get_vi_status,
            final_vo_status=final_vo_status,
            final_da_status=final_da_status,
            final_vi_status=final_vi_status,
            get_fans=get_fans,
            final_fans=final_fans,
            fan_grade=fan_grade
        )

        return result
    
    def _pick_segment_for_status(self, trend_data: dict, trend_key: str, score: int) -> str:
        """
        status用: trend_data = {base_score:{...}, first_damping:{...}, ..., max_score:{...}}
        各セグメントの threshold を trend_key ごとに動的取得し、score に合う帯名を返す。
        """
        # max_score は別扱い
        max_threshold = trend_data["max_score"][trend_key]["audition_score"]

        # max 超過なら即 max
        if score >= max_threshold:
            return "max_score"

        # max_score 以外を (audition_score 昇順) で走査
        segments = []
        for name, block in trend_data.items():
            if name == "max_score":
                continue
            segments.append((name, block[trend_key]["audition_score"]))
        segments.sort(key=lambda x: x[1])  # しきい値で昇順

        # デフォルトは最初の帯（例: base_score）
        picked = segments[0][0]
        for name, thr in segments:
            if score > thr:
                picked = name
            else:
                break
        return picked
        
    def calculate_get_status(
            self, 
            character:str, 
            audition: str, 
            vo_score: int, 
            da_score: int, 
            vi_score: int,
            vo_bonus: float,
            da_bonus: float,
            vi_bonus: float,
            challenge_P_item: int
    ) -> tuple[int, int, int]:
        """
        オーディションスコアからそれぞれのステータス上昇量を返す
        戻り値: (get_vo_status, get_da_status, get_vi_status)
        """
        self.log.debug("start: calculate_get_status character=%s audition=%s", character, audition)

        # キャラクターの流行情報を取得して整理
        trend = get_character_trend(character)
        trend_type = trend["type"]  # "balanced" or "focused"
        trend_data = get_nia_audition_status_block(self.mode, audition, trend_type)

        score_info = {"Vo": vo_score, "Da": da_score, "Vi": vi_score}
        bonus_info = {"Vo": vo_bonus, "Da": da_bonus, "Vi": vi_bonus}
        status_info: dict[str, int] = {"Vo": 0, "Da": 0, "Vi": 0}
       

        # 第1流行から第3流行まで順番に回す
        for trend_key in ("first_trend", "second_trend", "third_trend"):
            stat_name = trend[trend_key]
            score = score_info[stat_name]

            # スコアが0のときは0を返す
            if score <= 0:
                get_status = 0

            else: 
                # スコアの減衰ラインを取得
                line = self._pick_segment_for_status(trend_data, trend_key, score)

                # スコアが上限突破時は固定された上限値を返す
                if line == "max_score":
                    get_status = trend_data["max_score"][trend_key]["status"]
                    self.log.debug("segment=max_score trend=%s score=%d status=%d", trend_key, score, get_status)
            
                # 上限に届いていないときは
                # オーディションスコア × 係数 + 基礎点
                else:
                    coef = trend_data[line][trend_key]["status_score_coefficient"]
                    base = trend_data[line][trend_key]["correction_constant"]
                    get_status = score * coef + base
                    self.log.debug("segment=%s trend=%s: %d * %s + %s = %.2f",
                                   line, trend_key, score, coef, base, get_status)

            # パラメータボーナスによる加点を計算
            status_bonus = get_status * bonus_info[stat_name] / 100
            self.log.debug("status_bonus trend=%s raw=%.2f", trend_key, status_bonus)

            # プロとマスターで場合分けしてそれぞれの流行に格納
            if self.mode == MASTER:
                item_bonus = math.floor(get_status * challenge_P_item / 100) * (1 + bonus_info[stat_name] / 100)
                total = math.floor(get_status) + math.floor(status_bonus) + math.floor(item_bonus)
                self.log.debug("item_bonus %.2f (challenge=%d%%)", item_bonus, challenge_P_item)
                self.log.debug("get_%s_status=%d", stat_name, total)
            else:
                total = math.floor(get_status) + math.floor(status_bonus)
                self.log.debug("get_%s_status=%d", stat_name, total)
            
            status_info[stat_name] = total
        
        self.log.debug("end: calculate_get_status -> Vo=%d Da=%d Vi=%d",
                       status_info["Vo"], status_info["Da"], status_info["Vi"])
        return (status_info["Vo"], status_info["Da"], status_info["Vi"])


    def calculate_get_fans(self, audition: str, audition_score: int) -> int:
        """
        オーディションスコアから獲得するファン数を返す
        """
        # スコアがどの減衰ラインなのか判定
        damping_line = "base_score"
        for key, data in self.settings[self.mode][audition]["fan"].items():
            if audition_score <= data["audition_score"]:
                break
            damping_line = key

        # 減衰ラインの情報を取得
        data = self.settings[self.mode][audition]["fan"][damping_line]

        # 上限突破時はそのまま上限数を返す
        if damping_line == "max_score":
            return data["fans"]

        # それ以外のときは
        # （オーディションスコア - 減衰ラインスコア）* 補正係数 + 固定補正値
        # masterは1.5倍
        else:
            result_fans = (audition_score - data["audition_score"]) * data["fan_score_coefficient"] + data["correction_constant"]
            if self.mode == "master":
                result_fans *= 1.5
            return math.floor(result_fans)

    def get_fan_grade(self, final_fans) -> str:
        """
        最終ファン数に応じたランクを返す
        """
        result_grade = None
        for grade, data in self.settings["fan_grade"].items():
            if final_fans <= data["votes_num"]:
                break
            result_grade = grade
        return result_grade

    def calculate_fan_score(self, fan_grade: str, final_fans) -> int:
        """
        ファン数に応じたスコアを返す
        """
        data = self.settings["fan_grade"][fan_grade]

        if fan_grade == "SS":
            fan_score = data["constant"][self.mode] + final_fans * data["coefficient"][self.mode]
            return math.floor(fan_score)
        else:
            fan_score = data["constant"] + final_fans * data["coefficient"]
            return math.floor(fan_score)
        
    def calculate_get_kirameki(self, audition_score: int) -> int:
        """
        オーディションスコアに応じた「ほしのきらめき」の獲得数を返す
        """
        boost = self.settings[self.mode]["boost"]

        # 閾値を昇順に（audition_score が無い max 行は最後）
        ordered = sorted(
            boost.items(),
            key=lambda kv: kv[1].get("audition_score", float("inf"))
        )

        # score 以下で最も近い行 (= 適用すべき区間) を選ぶ
        chosen_key = None
        for key, row in ordered:
            if audition_score >= row.get("audition_score", float("inf")):
                chosen_key = key
            else:
                break

        # 上限（必ず存在）
        kirameki_cap = boost["max_score"]["kirameki"]

        # 上限区間なら即キャップ
        if chosen_key == "max_score":
            return kirameki_cap

        row = boost[chosen_key]  # base_score か first_damping

        cp = row["audition_score"]
        coeff = row["fan_score_coefficient"]
        offset = row["correction_constant"]

        # 区分直線： ((score - 変化点) / 係数) + 補正
        raw = ((audition_score - cp) / coeff) + offset
        gained = math.floor(raw)

        # 最低0、最大上限
        if gained < 0:
            gained = 0
        if gained > kirameki_cap:
            gained = kirameki_cap
        return gained