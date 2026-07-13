from __future__ import annotations

import asyncio
import time
from typing import Any

import numpy as np

from config.nia_settings import NIA
from models.nia.final_grade.params import (
    NiaFinalGradeParams,
)
from models.nia.final_grade_from_img.params import (
    NiaFinalGradeFromImgParams,
)
from models.nia.final_grade_from_img.result import (
    NiaFinalGradeFromImgResult,
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
    NIA最終評価画像コマンドにおける、
    画像推論・OCR結果検証・スコア計算を担当する。
    """

    def __init__(
        self,
        inference_service: InferenceService,
    ) -> None:
        self._inference_service = (
            inference_service
        )

    async def execute(
        self,
        *,
        params: NiaFinalGradeFromImgParams,
        schedule_image: np.ndarray,
        party_image: np.ndarray,
        score_image: np.ndarray,
    ) -> InferenceUseCaseResult:
        """
        3枚の画像から必要な値を読み取り、
        最終評価を計算する。
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

        score_inference = await asyncio.to_thread(
            self._inference_service.infer,
            score_image,
            parameter_maximum=PARAMETER_MAXIMUM,
        )

        parameters = schedule_inference.parameters
        bonuses = party_inference.bonuses
        scores = score_inference.scores

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

        score_dict: dict[
            str,
            int | None,
        ] = {
            "sum_score": scores.sum_score,
            "vo": scores.vo,
            "da": scores.da,
            "vi": scores.vi,
        }

        logger.debug(
            "Parameter OCR result: "
            "vo=%s da=%s vi=%s fans=%s star=%s "
            "total_ms=%.3f",
            parameters.vo,
            parameters.da,
            parameters.vi,
            parameters.fans,
            parameters.star,
            schedule_inference.total_ms,
        )

        logger.debug(
            "Bonus OCR result: "
            "vo=%s da=%s vi=%s kirameki=%s "
            "total_ms=%.3f",
            bonuses.vo,
            bonuses.da,
            bonuses.vi,
            bonuses.kirameki,
            party_inference.total_ms,
        )

        logger.debug(
            "Score OCR result: "
            "sum=%s vo=%s da=%s vi=%s "
            "total_ms=%.3f",
            scores.sum_score,
            scores.vo,
            scores.da,
            scores.vi,
            score_inference.total_ms,
        )

        failed_sections = self._find_failed_sections(
            is_boost_active=params.is_boost_active,
            parameters=parameters_dict,
            bonuses=bonus_dict,
            scores=score_dict,
        )

        if failed_sections:
            error_reason = (
                "OCR required values missing: "
                + ", ".join(failed_sections)
            )

            logger.warning(
                error_reason
            )

            return InferenceUseCaseResult(
                parameters=parameters_dict,
                bonuses=bonus_dict,
                scores=score_dict,
                schedule_inference=schedule_inference,
                party_inference=party_inference,
                score_inference=score_inference,
                failed_sections=failed_sections,
                error_reason=error_reason,
            )

        calculation_started_at = (
            time.perf_counter()
        )

        final_grade_result = self.calculate(
            character=params.character,
            mode=params.mode,
            audition=params.audition,
            challenge_p_item=(
                params.challenge_P_item
            ),
            is_boost_active=(
                params.is_boost_active
            ),
            values={
                "vo_status": parameters_dict["vo"],
                "da_status": parameters_dict["da"],
                "vi_status": parameters_dict["vi"],
                "vo_bonus": bonus_dict["vo"],
                "da_bonus": bonus_dict["da"],
                "vi_bonus": bonus_dict["vi"],
                "vo_score": score_dict["vo"],
                "da_score": score_dict["da"],
                "vi_score": score_dict["vi"],
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
            scores=score_dict,
            schedule_inference=schedule_inference,
            party_inference=party_inference,
            score_inference=score_inference,
            final_grade_result=(
                final_grade_result
            ),
            calculation_ms=calculation_ms,
        )

    def calculate(
        self,
        *,
        character: str,
        mode: str,
        audition: str,
        challenge_p_item: bool,
        is_boost_active: bool,
        values: dict[str, Any],
    ) -> NiaFinalGradeFromImgResult:
        """
        OCRを実行せず、渡された値から最終評価を計算する。

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
            "vo_score",
            "da_score",
            "vi_score",
            "now_fans",
        )

        missing_keys = [
            key
            for key in required_keys
            if values.get(key) is None
        ]

        if missing_keys:
            raise ValueError(
                "最終評価計算に必要な値が"
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

        final_grade_params = NiaFinalGradeParams(
            character=character,
            mode=mode,
            audition=audition,
            vo_status=values["vo_status"],
            da_status=values["da_status"],
            vi_status=values["vi_status"],
            vo_bonus=values["vo_bonus"],
            da_bonus=values["da_bonus"],
            vi_bonus=values["vi_bonus"],
            vo_score=values["vo_score"],
            da_score=values["da_score"],
            vi_score=values["vi_score"],
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
            final_grade_params,
        )

        scenario = NiaScenario(
            mode=final_grade_params.mode
        )

        result: NiaFinalGradeFromImgResult = (
            scenario.calculate_score(
                final_grade_params
            )
        )

        logger.info(
            "最終スコア: %s",
            result.final_score,
        )

        logger.info(
            "評価ランク: %s",
            result.final_grade,
        )

        return result

    @staticmethod
    def _find_failed_sections(
        *,
        is_boost_active: bool,
        parameters: dict[str, int | None],
        bonuses: dict[
            str,
            int | float | None,
        ],
        scores: dict[str, int | None],
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

        score_failed = any(
            scores.get(key) is None
            for key in (
                "vo",
                "da",
                "vi",
            )
        )

        if parameter_failed:
            failed_sections.append(
                "parameters"
            )

        if bonus_failed:
            failed_sections.append(
                "bonuses"
            )

        if score_failed:
            failed_sections.append(
                "scores"
            )

        return failed_sections
