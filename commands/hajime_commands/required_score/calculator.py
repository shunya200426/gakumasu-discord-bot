from config.hajime_settings import HAJIME
from config.settings import SETTINGS
from models.hajime.required_score.params import HajimeRequiredScoreParams
from scenarios import HajimeScenario
from utils.logger import get_logger

logger = get_logger()

CLEAR = "CLEAR!"
CLEAR_IMPOSSIBLE = "**__CLEAR不可__**"
BOOST_MODE_NOT_SUPPORTED_MESSAGE = (
    "初シナリオのアイドル強化月間は、現在必要スコア計算に対応していません。"
)
SUPPORTED_GRADES = ("SS", "SS+", "SSS", "SSS+")


class BoostModeNotSupportedError(NotImplementedError):
    """強化月間の必要スコア計算が未対応であることを表す。"""


class RequiredScoreCalculator:
    """初シナリオの必要最終試験スコア計算を担当する。"""

    def compute_required_result_dict(
        self,
        scenario: HajimeScenario,
        params: HajimeRequiredScoreParams,
    ) -> dict[str, int | str | None]:
        """目標ごとの必要最終試験スコアを返す。"""
        if params.is_boost_active:
            raise BoostModeNotSupportedError(BOOST_MODE_NOT_SUPPORTED_MESSAGE)

        thresholds = dict(SETTINGS["grade_thresholds"])
        if params.target_score is not None:
            grade_list = ["TARGET"]
            result_dict: dict[str, int | str | None] = {"TARGET": None}
            thresholds["TARGET"] = int(params.target_score)
        elif params.target_grade is not None:
            grade_list = [params.target_grade]
            result_dict = {params.target_grade: None}
        else:
            grade_list = list(SUPPORTED_GRADES)
            result_dict = {grade: None for grade in grade_list}

        # ここから通常モードの計算。既存実装の計算順序と丸めを維持する。
        exam_post_bonus = HAJIME[params.mode]["exam_post_bonus"]["first"]
        rate = HAJIME[params.mode]["status_point_rates"]
        status_eval_points = scenario.calclate_stats_score(
            params.vo_status + exam_post_bonus + params.vo_ability,
            params.da_status + exam_post_bonus + params.da_ability,
            params.vi_status + exam_post_bonus + params.vi_ability,
            rate,
        )

        if params.mode == "legend":
            mid_exam = HAJIME[params.mode]["score_attenuation"]["mid_exam"]
            # 既存実装は最終試験側の den を参照しているため、その挙動を維持する。
            mid_den = HAJIME[params.mode]["score_attenuation"]["final_exam"]["den"]
            mid_exam_eval_points = scenario._apply_attenuation(
                params.mid_exam_score,
                mid_exam["thresholds"],
                mid_exam["coefficients"],
                mid_den,
            )
        else:
            mid_exam_eval_points = 0

        final_exam_rank_bonus = HAJIME["final_exam_rank_bonus"]["first"]
        base_eval_points = (
            status_eval_points
            + mid_exam_eval_points
            + final_exam_rank_bonus
        )
        max_score = HAJIME[params.mode]["score_attenuation"]["final_exam"][
            "thresholds"
        ][-1]

        for grade in grade_list:
            required_eval_points = thresholds[grade] - base_eval_points
            if required_eval_points <= 0:
                result_dict[grade] = CLEAR
                continue

            required_exam_score = scenario.invert_attenuation(
                required_eval_points=required_eval_points
            )
            result_dict[grade] = (
                CLEAR_IMPOSSIBLE
                if required_exam_score > max_score
                else required_exam_score
            )

        return result_dict

    def build_pairs(
        self,
        result_dict: dict[str, int | str | None],
        target_grade: str | None,
        target_score: int | None,
    ) -> tuple[list[tuple[str, str]], str | None, int | None]:
        """Containerへ渡す表示用の名前と値を構築する。"""
        grade = (
            target_grade.strip().upper().replace("＋", "+")
            if isinstance(target_grade, str) and target_grade
            else None
        )
        score = int(target_score) if target_score is not None else None

        if score is not None:
            logger.debug("[required_score] pairs mode=target_score value=%d", score)
            return [
                (
                    f"**目標スコア = {score}**",
                    self._format_required_score(result_dict.get("TARGET")),
                )
            ], None, score

        if grade in SUPPORTED_GRADES:
            logger.debug("[required_score] pairs mode=target_grade value=%s", grade)
            return [
                (f"**{grade}**", self._format_required_score(result_dict.get(grade)))
            ], grade, None

        pairs = [
            (f"- **{grade_name}**", self._format_required_score(result_dict.get(grade_name)))
            for grade_name in SUPPORTED_GRADES
        ]
        logger.debug("[required_score] pairs mode=all_grades count=%d", len(pairs))
        return pairs, None, None

    @staticmethod
    def _format_required_score(value: int | str | None) -> str:
        if value is None:
            return "—"
        return str(value)
