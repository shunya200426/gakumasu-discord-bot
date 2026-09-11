from __future__ import annotations

import asyncio
import time
from typing import TYPE_CHECKING

import numpy as np

from commands.hajime_commands.required_score.calculator import (
    BOOST_MODE_NOT_SUPPORTED_MESSAGE,
    BoostModeNotSupportedError,
    RequiredScoreCalculator,
)
from config.hajime_settings import HAJIME
from models.hajime.required_score.params import HajimeRequiredScoreParams
from models.hajime.required_score_from_img.params import (
    HajimeRequiredScoreFromImgParams,
)
from models.hajime.required_score_from_img.result import (
    HajimeRequiredScoreFromImgResult,
)
from scenarios import HajimeScenario
from utils.logger import get_logger

from .inference_use_case_result import InferenceUseCaseResult, MidExamScoreSource

if TYPE_CHECKING:
    from services.inference_service import InferenceService

logger = get_logger()

SUPPORTED_MODE = "legend"
PARAMETER_MAXIMUM = HAJIME[SUPPORTED_MODE]["st_max"]
MID_EXAM_SCORE_MINIMUM = 0
MID_EXAM_SCORE_MAXIMUM = 200000


class InferenceUseCase:
    """
    初の必要スコア画像推論、検証、計算を担当する。
    """

    def __init__(
        self,
        inference_service: InferenceService,
        calculator: RequiredScoreCalculator | None = None,
    ) -> None:
        self._inference_service = inference_service
        self._calculator = calculator or RequiredScoreCalculator()

    async def execute(
        self,
        *,
        params: HajimeRequiredScoreFromImgParams,
        schedule_image: np.ndarray,
        party_image: np.ndarray,
        mid_exam_image: np.ndarray | None,
    ) -> InferenceUseCaseResult:
        """
        画像を推論し、取得値から必要スコアを計算する。
        """
        self._validate_supported_request(params)

        if mid_exam_image is None:
            self._validate_mid_exam_score(params.mid_exam_score)

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
        mid_exam_inference = None
        if mid_exam_image is not None:
            mid_exam_inference = await asyncio.to_thread(
                self._inference_service.infer,
                mid_exam_image,
                parameter_maximum=PARAMETER_MAXIMUM,
            )

        parameters = schedule_inference.parameters
        bonuses = party_inference.bonuses
        parameters_dict: dict[str, int | None] = {
            "vo": parameters.vo,
            "da": parameters.da,
            "vi": parameters.vi,
            "fans": parameters.fans,
            "star": parameters.star,
        }
        bonus_dict: dict[str, int | float | None] = {
            "vo": bonuses.vo,
            "da": bonuses.da,
            "vi": bonuses.vi,
            "kirameki": bonuses.kirameki,
        }

        if mid_exam_inference is not None:
            score_result = mid_exam_inference.scores
            score_dict: dict[str, int | None] = {
                "sum_score": score_result.sum_score,
                "vo": score_result.vo,
                "da": score_result.da,
                "vi": score_result.vi,
            }
            mid_exam_score = score_result.sum_score
            mid_exam_score_source: MidExamScoreSource = "image"
        else:
            score_dict = {
                "sum_score": params.mid_exam_score,
                "vo": None,
                "da": None,
                "vi": None,
            }
            mid_exam_score = params.mid_exam_score
            mid_exam_score_source = "manual"

        failed_sections: list[str] = []
        error_reasons: list[str] = []
        if any(parameters_dict[key] is None for key in ("vo", "da", "vi")):
            failed_sections.append("parameters")
            error_reasons.append("OCR required values missing: parameters")

        if mid_exam_score is None:
            failed_sections.append("scores")
            error_reasons.append("OCR required values missing: scores.sum_score")
        else:
            try:
                self._validate_mid_exam_score(mid_exam_score)
            except (TypeError, ValueError) as exc:
                failed_sections.append("scores")
                error_reasons.append(str(exc))

        if failed_sections:
            return InferenceUseCaseResult(
                parameters=parameters_dict,
                bonuses=bonus_dict,
                scores=score_dict,
                mid_exam_score=mid_exam_score,
                mid_exam_score_source=mid_exam_score_source,
                schedule_inference=schedule_inference,
                party_inference=party_inference,
                mid_exam_inference=mid_exam_inference,
                failed_sections=failed_sections,
                error_reason="; ".join(error_reasons),
            )

        calculation_started_at = time.perf_counter()
        result, pairs = self.calculate(
            mode=params.mode,
            character=params.character,
            target_grade=params.target_grade,
            target_score=params.target_score,
            vo_ability=params.vo_ability,
            da_ability=params.da_ability,
            vi_ability=params.vi_ability,
            vo_status=parameters_dict["vo"],
            da_status=parameters_dict["da"],
            vi_status=parameters_dict["vi"],
            mid_exam_score=mid_exam_score,
        )
        calculation_ms = (time.perf_counter() - calculation_started_at) * 1000.0

        return InferenceUseCaseResult(
            parameters=parameters_dict,
            bonuses=bonus_dict,
            scores=score_dict,
            mid_exam_score=mid_exam_score,
            mid_exam_score_source=mid_exam_score_source,
            schedule_inference=schedule_inference,
            party_inference=party_inference,
            mid_exam_inference=mid_exam_inference,
            required_score_result=result,
            pairs=pairs,
            calculation_ms=calculation_ms,
        )

    def calculate(
        self,
        *,
        mode: str,
        character: str | None,
        target_grade: str | None,
        target_score: int | None,
        vo_ability: int,
        da_ability: int,
        vi_ability: int,
        vo_status: int | None,
        da_status: int | None,
        vi_status: int | None,
        mid_exam_score: int | None,
    ) -> tuple[HajimeRequiredScoreFromImgResult, list[tuple[str, str]]]:
        """
        推論を再実行せず、渡された値から必要スコアを計算する。
        """
        if mode != SUPPORTED_MODE:
            raise ValueError("初の画像必要スコア計算はLegendのみ対応しています。")
        required_values = {
            "vo_status": vo_status,
            "da_status": da_status,
            "vi_status": vi_status,
            "mid_exam_score": mid_exam_score,
        }
        missing = [key for key, value in required_values.items() if value is None]
        if missing:
            raise ValueError(
                "必要スコア計算に必要な値が不足しています: " + ", ".join(missing)
            )
        self._validate_mid_exam_score(mid_exam_score)

        calc_params = HajimeRequiredScoreParams(
            mode=mode,
            vo_status=vo_status,
            da_status=da_status,
            vi_status=vi_status,
            vo_ability=vo_ability,
            da_ability=da_ability,
            vi_ability=vi_ability,
            mid_exam_score=mid_exam_score,
            target_grade=target_grade,
            target_score=target_score,
            character=character,
            is_boost_active=False,
            kirameki=0,
        )
        scenario = HajimeScenario(mode=mode)
        result_dict = self._calculator.compute_required_result_dict(
            scenario=scenario,
            params=calc_params,
        )
        pairs, _, _ = self._calculator.build_pairs(
            result_dict=result_dict,
            target_grade=target_grade,
            target_score=target_score,
        )
        result = HajimeRequiredScoreFromImgResult(
            **calc_params.__dict__,
            SS_required_score=result_dict.get("SS"),
            SS_plus_required_score=result_dict.get("SS+"),
            SSS_required_score=result_dict.get("SSS"),
            SSS_plus_required_score=result_dict.get("SSS+"),
        )
        return result, pairs

    @staticmethod
    def _validate_supported_request(
        params: HajimeRequiredScoreFromImgParams,
    ) -> None:
        if params.is_boost_active:
            raise BoostModeNotSupportedError(
                BOOST_MODE_NOT_SUPPORTED_MESSAGE
            )
        if params.mode != SUPPORTED_MODE:
            raise ValueError("初の画像必要スコア計算はLegendのみ対応しています。")

    @staticmethod
    def _validate_mid_exam_score(value: int) -> None:
        if not isinstance(value, int):
            raise TypeError("中間試験スコアは整数で指定してください。")
        if not MID_EXAM_SCORE_MINIMUM <= value <= MID_EXAM_SCORE_MAXIMUM:
            raise ValueError("中間試験スコアは0～200000の範囲で指定してください。")
