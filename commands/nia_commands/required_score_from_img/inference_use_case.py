from __future__ import annotations

import asyncio
import time
from typing import Any

import numpy as np

from commands.nia_commands.required_score.calculator import (
    RequiredScoreCalculator,
)
from config.nia_settings import NIA
from models.nia.final_grade.params import (
    NiaFinalGradeParams,
)
from models.nia.required_score_from_img.params import (
    NiaRequiredScoreFromImgParams,
)
from models.nia.required_score_from_img.result import (
    NiaRequiredScoreFromImgResult,
)
from scenarios import NiaScenario
from services.inference_service import InferenceService
from utils.logger import get_logger

from .inference_use_case_result import (
    InferenceUseCaseResult,
)

logger = get_logger()



# NIA Masterのパラメータ上限。
PARAMETER_MAXIMUM = NIA['master']['st_max']


class InferenceUseCase:
    """
    NIA必要スコア画像コマンドにおける、
    画像推論・OCR結果検証・必要スコア計算を担当する。
    """

    def __init__(
        self,
        inference_service: InferenceService,
    ) -> None:
        self._inference_service = (
            inference_service
        )
        self._calculator = (
            RequiredScoreCalculator()
        )

    async def execute(
        self,
        *,
        params: NiaRequiredScoreFromImgParams,
        schedule_image: np.ndarray,
        party_image: np.ndarray,
    ) -> InferenceUseCaseResult:
        """
        2枚の画像から必要な値を読み取り、
        必要スコアを計算する。
        """
        schedule_inference = await asyncio.to_thread(
            self._inference_service.infer,
            schedule_image,
            parameter_maximum=PARAMETER_MAXIMUM,
        )

        party_inference = await asyncio.to_thread(
            self._inference_service.infer,
            party_image,
            parameter_maximum=PARAMETER_MAXIMUM,
        )

        parameters = schedule_inference.parameters
        bonuses = party_inference.bonuses

        parameters_dict: dict[
            str,
            int | None,
        ] = {
            "vo": parameters.vo,
            "da": parameters.da,
            "vi": parameters.vi,
            "fans": parameters.fans,
            "star": parameters.star,
        }

        bonus_dict: dict[
            str,
            int | float | None,
        ] = {
            "vo": bonuses.vo,
            "da": bonuses.da,
            "vi": bonuses.vi,
            "kirameki": bonuses.kirameki,
        }

        logger.debug(
            "read params vo: %s da: %s vi: %s fans: %s time %.1f ms",
            parameters_dict.get("vo"),
            parameters_dict.get("da"),
            parameters_dict.get("vi"),
            parameters_dict.get("fans"),
            schedule_inference.total_ms,
        )

        logger.debug(
            "read bonus vo: %s da: %s vi: %s time %.1f ms",
            bonus_dict.get("vo"),
            bonus_dict.get("da"),
            bonus_dict.get("vi"),
            party_inference.total_ms,
        )

        failed_sections = self._find_failed_sections(
            is_boost_active=params.is_boost_active,
            parameters=parameters_dict,
            bonuses=bonus_dict,
        )

        if failed_sections:
            error_reason = (
                "OCR required values missing: "
                + ", ".join(failed_sections)
            )

            return InferenceUseCaseResult(
                parameters=parameters_dict,
                bonuses=bonus_dict,
                failed_sections=failed_sections,
                error_reason=error_reason,
                schedule_inference_ms=(
                    schedule_inference.total_ms
                ),
                party_inference_ms=(
                    party_inference.total_ms
                ),
            )

        calculation_started_at = (
            time.perf_counter()
        )

        result, pairs = self.calculate(
            character=params.character,
            mode=params.mode,
            audition=params.audition,
            target_grade=params.target_grade,
            target_score=params.target_score,
            challenge_p_item=(
                params.challenge_P_item
            ),
            is_boost_active=(
                params.is_boost_active
            ),
            values={
                "audition": params.audition,
                "vo_status": parameters_dict["vo"],
                "da_status": parameters_dict["da"],
                "vi_status": parameters_dict["vi"],
                "vo_bonus": bonus_dict["vo"],
                "da_bonus": bonus_dict["da"],
                "vi_bonus": bonus_dict["vi"],
                "now_fans": parameters_dict["fans"],
                "kirameki": bonus_dict["kirameki"],
            },
        )

        calculation_ms = (
            time.perf_counter()
            - calculation_started_at
        ) * 1000.0

        return InferenceUseCaseResult(
            parameters=parameters_dict,
            bonuses=bonus_dict,
            required_score_result=result,
            pairs=pairs,
            schedule_inference_ms=(
                schedule_inference.total_ms
            ),
            party_inference_ms=(
                party_inference.total_ms
            ),
            calculation_ms=calculation_ms,
        )

    def calculate(
        self,
        *,
        character: str,
        mode: str,
        audition: str,
        target_grade: str | None,
        target_score: int | None,
        challenge_p_item: int,
        is_boost_active: bool,
        values: dict[str, Any],
    ) -> tuple[NiaRequiredScoreFromImgResult, list]:
        """
        OCRを実行せず、渡された値から必要スコアを計算する。

        初回実行とModalによる再計算の両方で、
        同じ計算ロジックを使用するための共通メソッド。
        """
        required_keys = (
            "vo_status",
            "da_status",
            "vi_status",
            "vo_bonus",
            "da_bonus",
            "vi_bonus",
            "now_fans",
        )

        missing_keys = [
            key
            for key in required_keys
            if values.get(key) is None
        ]

        if missing_keys:
            raise ValueError(
                "必要スコア計算に必要な値が"
                "不足しています: "
                + ", ".join(missing_keys)
            )

        kirameki = (
            values.get(
                "kirameki",
                0,
            )
            if is_boost_active
            else 0
        )

        if (
            is_boost_active
            and kirameki is None
        ):
            raise ValueError(
                "強化月間ですが、"
                "ほしのきらめきがありません。"
            )

        if is_boost_active:
            logger.debug(
                "kiramek: %s",
                kirameki,
            )

        calc_params = NiaFinalGradeParams(
            character=character,
            mode=mode,
            audition=audition,
            vo_status=values["vo_status"],
            da_status=values["da_status"],
            vi_status=values["vi_status"],
            vo_bonus=values["vo_bonus"],
            da_bonus=values["da_bonus"],
            vi_bonus=values["vi_bonus"],
            vo_score=0,
            da_score=0,
            vi_score=0,
            now_fans=values["now_fans"],
            challenge_P_item=(
                challenge_p_item
            ),
            is_boost_active=(
                is_boost_active
            ),
            kirameki=kirameki,
        )

        logger.info(
            "calc params %s",
            calc_params,
        )

        scenario = NiaScenario(
            mode=mode
        )

        t_core = time.perf_counter()

        logger.info(
            "[required_score_from_img] compute start char=%s mode=%s audition=%s target_grade=%s target_score=%s",
            character,
            mode,
            audition,
            target_grade,
            target_score,
        )

        result_dict = (
            self._calculator.compute_required_result_dict(
                scenario=scenario,
                calc_params=calc_params,
                character=character,
                mode=mode,
                audition=audition,
                target_grade=target_grade,
                target_score=target_score,
            )
        )

        logger.debug(
            "[required_score_from_img] compute finished in %.1f ms",
            (time.perf_counter() - t_core) * 1000,
        )

        t_pairs = time.perf_counter()

        pairs, target_grade_norm, target_score_norm = (
            self._calculator.build_pairs(
                result_dict=result_dict,
                target_grade=target_grade,
                target_score=target_score,
            )
        )

        logger.debug(
            "[required_score] build_pairs finished in %.1f ms mode=%s",
            (time.perf_counter() - t_pairs) * 1000,
            (
                "target_score"
                if target_score_norm is not None
                else "target_grade"
                if target_grade_norm is not None
                else "all_grades"
            ),
        )

        result = NiaRequiredScoreFromImgResult(
            character=character,
            mode=mode,
            audition=audition,
            vo_status=values["vo_status"],
            da_status=values["da_status"],
            vi_status=values["vi_status"],
            vo_bonus=values["vo_bonus"],
            da_bonus=values["da_bonus"],
            vi_bonus=values["vi_bonus"],
            now_fans=values["now_fans"],
            challenge_P_item=challenge_p_item,
            is_boost_active=is_boost_active,
            kirameki=kirameki,
            SS_required_score=(
                self._calculator.total_or_none(
                    result_dict.get("SS")
                )
            ),
            SS_plus_required_score=(
                self._calculator.total_or_none(
                    result_dict.get("SS+")
                )
            ),
            SSS_required_score=(
                self._calculator.total_or_none(
                    result_dict.get("SSS")
                )
            ),
            SSS_plus_required_score=(
                self._calculator.total_or_none(
                    result_dict.get("SSS+")
                )
            ),
        )

        def _brief(v):
            if isinstance(v, dict):
                return (
                    f"{v.get('total')} "
                    f"(Vo={v.get('vo')},Da={v.get('da')},Vi={v.get('vi')})"
                    + (" [CLEAR!]" if "note" in v else "")
                )
            return v

        logger.info(
            "result summary SS=%s SS+=%s SSS=%s SSS+=%s",
            _brief(result_dict.get("SS")),
            _brief(result_dict.get("SS+")),
            _brief(result_dict.get("SSS")),
            _brief(result_dict.get("SSS+")),
        )

        return result, pairs

    @staticmethod
    def _find_failed_sections(
        *,
        is_boost_active: bool,
        parameters: dict[str, int | None],
        bonuses: dict[
            str,
            int | float | None,
        ],
    ) -> list[str]:
        """
        必須OCR項目が不足しているセクションを返す。
        """
        failed_sections: list[str] = []

        parameter_failed = any(
            parameters.get(key) is None
            for key in (
                "vo",
                "da",
                "vi",
                "fans",
            )
        )

        bonus_keys = [
            "vo",
            "da",
            "vi",
        ]

        if is_boost_active:
            bonus_keys.append(
                "kirameki"
            )

        bonus_failed = any(
            bonuses.get(key) is None
            for key in bonus_keys
        )

        if parameter_failed:
            failed_sections.append(
                "parameters"
            )

        if bonus_failed:
            failed_sections.append(
                "bonuses"
            )

        return failed_sections
