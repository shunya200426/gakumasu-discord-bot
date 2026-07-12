import logging
import time
from dataclasses import replace
from typing import Dict, Optional, Tuple

from config.character_settings import CHARACTERS
from config.nia_settings import NIA
from config.settings import SETTINGS
from models.nia.final_grade.params import NiaFinalGradeParams
from scenarios.nia_scenario import NiaScenario
from utils.logger import get_logger

logger = get_logger()


class RequiredScoreCalculator:
    """
    NIAシナリオの必要スコア逆算ロジックを担当する。
    """

    def compute_required_result_dict(
        self,
        scenario: NiaScenario,
        calc_params: NiaFinalGradeParams,
        character: str,
        mode: str,
        audition: str,
        target_grade: Optional[str],
        target_score: Optional[int],
    ) -> Dict[str, object]:
        """
        共有コア：逆算ロジック本体
        戻り値: result_dict（"SS" などのキー: dict or "CLEAR不可" or None）
        """
        t0 = time.perf_counter()
        thresholds = dict(SETTINGS["grade_thresholds"])
        if target_grade is not None and isinstance(target_grade, str):
            g = target_grade.strip().upper().replace("＋", "+")
            if g not in ("SS", "SS+", "SSS", "SSS+"):
                raise ValueError(f"未知の評価ランクです: {target_grade}")
            target_grade = g

        # 目標の正規化（target_score 優先）
        if target_score is not None:
            grade_list = ["TARGET"]
            result_dict = {"TARGET": None}
            thresholds["TARGET"] = int(target_score)
        elif target_grade is not None:
            grade_list = [target_grade]
            result_dict = {target_grade: None}
        else:
            grade_list = ["SS", "SS+", "SSS", "SSS+"]
            result_dict = {g: None for g in grade_list}

        pass_score = NIA[mode][audition]["pass_score"]
        audition_total_cap = NIA[mode][audition]["fan"]["max_score"]["audition_score"]

        # キャラ流行マッピング
        status_dict = {}
        for trend in ("first_trend", "second_trend", "third_trend"):
            key = CHARACTERS[character]["trend"][trend]  # "Vo"|"Da"|"Vi"
            status_dict[key] = trend
        trend_type = CHARACTERS[character]["trend"]["type"]
        trend_data = NIA[mode][audition]["status"][trend_type]

        base_first = trend_data["first_damping"]["first_trend"]["audition_score"]
        max_first = trend_data["max_score"]["first_trend"]["audition_score"]
        base_second = trend_data["first_damping"]["second_trend"]["audition_score"]
        max_second = trend_data["max_score"]["second_trend"]["audition_score"]
        base_third = trend_data["first_damping"]["third_trend"]["audition_score"]
        max_third = trend_data["max_score"]["third_trend"]["audition_score"]

        start_third = pass_score - (base_first + base_second)
        if start_third < 0:
            start_third = 0
            base_second = pass_score - base_first

        score_dict = {
            "first_trend": base_first,
            "second_trend": base_second,
            "third_trend": start_third,
        }
        vo_key = status_dict["Vo"]
        da_key = status_dict["Da"]
        vi_key = status_dict["Vi"]
        vo_score = score_dict[vo_key]
        da_score = score_dict[da_key]
        vi_score = score_dict[vi_key]

        step = 2000
        index = 0
        grade = grade_list[index]
        target_score_for_grade = thresholds[grade]

        # calculate_score の冗長ログ抑制
        _underlying = getattr(scenario.log, "logger", scenario.log)
        _old_level = _underlying.getEffectiveLevel()
        _underlying.setLevel(logging.WARNING)
        try:
            # 初期値CLEAR!判定
            _params0 = replace(calc_params, vo_score=vo_score, da_score=da_score, vi_score=vi_score)
            initial_result = scenario.calculate_score(_params0)
            while index < len(grade_list) and initial_result.final_score >= thresholds[grade_list[index]]:
                total = vo_score + da_score + vi_score
                result_dict[grade_list[index]] = {
                    "total": total, "vo": vo_score, "da": da_score, "vi": vi_score, "note": "CLEAR!",
                }
                index += 1
                if index >= len(grade_list):
                    break
                grade = grade_list[index]
                target_score_for_grade = thresholds[grade]

            # 探索（CLEAR!上書きバグ対策の break を先頭に）
            phase = 0
            for _ in range(pass_score, audition_total_cap + step, step):
                if index >= len(grade_list):
                    break

                vo_score = score_dict[vo_key]
                da_score = score_dict[da_key]
                vi_score = score_dict[vi_key]
                _params = replace(calc_params, vo_score=vo_score, da_score=da_score, vi_score=vi_score)
                result = scenario.calculate_score(_params)

                if result.final_score >= target_score_for_grade:
                    total = vo_score + da_score + vi_score
                    prev = result_dict.get(grade)
                    # note を保持（上書き時も残す）
                    result_dict[grade] = {
                        "total": total, "vo": vo_score, "da": da_score, "vi": vi_score,
                        **({"note": prev.get("note")} if isinstance(prev, dict) and "note" in prev else {}),
                    }
                    index += 1
                    if index >= len(grade_list):
                        break
                    grade = grade_list[index]
                    target_score_for_grade = thresholds[grade]
                    continue

                # 届かない→加算フェーズ
                if phase == 0:
                    if score_dict["third_trend"] < base_third:
                        score_dict["third_trend"] = min(base_third, score_dict["third_trend"] + step)
                    else:
                        phase = 1
                        continue
                elif phase == 1:
                    if score_dict["first_trend"] < max_first:
                        score_dict["first_trend"] = min(max_first, score_dict["first_trend"] + step)
                    else:
                        phase = 2
                        continue
                elif phase == 2:
                    if score_dict["second_trend"] < max_second:
                        score_dict["second_trend"] = min(max_second, score_dict["second_trend"] + step)
                    else:
                        phase = 3
                        continue
                elif phase == 3:
                    if score_dict["third_trend"] < max_third:
                        score_dict["third_trend"] = min(max_third, score_dict["third_trend"] + step)
                    else:
                        phase = 4
                        continue
                else:
                    current_total = score_dict["first_trend"] + score_dict["second_trend"] + score_dict["third_trend"]
                    if current_total < audition_total_cap:
                        score_dict["first_trend"] = min(
                            score_dict["first_trend"] + step,
                            audition_total_cap - score_dict["second_trend"] - score_dict["third_trend"]
                        )

            # 未達埋め
            for i in range(index, len(grade_list)):
                g = grade_list[i]
                if result_dict[g] is None:
                    result_dict[g] = "**__CLEAR不可__**"
            return result_dict
        finally:
            _underlying.setLevel(_old_level)

    def build_pairs(
        self,
        result_dict: Dict[str, object],
        target_grade: Optional[str],
        target_score: Optional[int],
    ) -> Tuple[list, Optional[str], Optional[int]]:
        """
        表示ペア（タイトル, 値）を生成。embed_builder の override_pairs に渡す。
        戻り値: (pairs, 正規化済みランク or None, 正規化済みスコア or None)
        """
        g = target_grade.strip().upper().replace("＋", "+") if isinstance(target_grade, str) and target_grade else None
        s = int(target_score) if target_score is not None else None

        # 目標スコアあり
        if s is not None:
            logger.debug("[required_score] pairs mode=target_score value=%d", s)
            return [(f"**目標スコア = {s}**", _fmt_required(result_dict.get("TARGET", "—")))], None, s

        # 目標評価あり
        if g in ("SS", "SS+", "SSS", "SSS+"):
            logger.debug("[required_score] pairs mode=target_grade value=%s", g)
            return [(f"**{g}**", _fmt_required(result_dict.get(g, "—")))], g, None

        # 任意引数なし
        pairs = [
            ("- **SS**", _fmt_required(result_dict.get("SS", "—"))),
            ("- **SS+**", _fmt_required(result_dict.get("SS+", "—"))),
            ("- **SSS**", _fmt_required(result_dict.get("SSS", "—"))),
            ("- **SSS+**", _fmt_required(result_dict.get("SSS+", "—"))),
        ]
        logger.debug("[required_score] pairs mode=all_grades count=%d", len(pairs))
        return pairs, None, None

    def total_or_none(self, d):
        return d["total"] if isinstance(d, dict) else (None if d in (None, "CLEAR不可") else d)


def _fmt_required(v) -> str:
    """
    必要スコア(dict or str or None)を表示用文字列に整形
    """
    if isinstance(v, dict):
        base = f"{v['total']}\n  (Vo {v['vo']} / Da {v['da']} / Vi {v['vi']})"
        if 'note' in v:  # CLEAR!フラグがある場合
            base = f"~~{base}~~  **[{v['note']}]**"
        return base
    if v is None:
        return "—"
    return str(v)  # CLEAR不可などの文字列はそのまま
