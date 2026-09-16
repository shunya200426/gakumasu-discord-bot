from __future__ import annotations

import asyncio
import time
from typing import TYPE_CHECKING

import numpy as np

from commands.hajime_commands.required_score.calculator import (
    BOOST_MODE_NOT_SUPPORTED_MESSAGE,
    BoostModeNotSupportedError,
)
from config.hajime_settings import HAJIME
from models.hajime.final_grade.params import HajimeFinalGradeParams
from models.hajime.final_grade.result import HajimeFinalGradeResult
from models.hajime.final_grade_from_img.params import HajimeFinalGradeFromImgParams
from scenarios import HajimeScenario
from utils.logger import get_logger

from .inference_use_case_result import InferenceUseCaseResult

if TYPE_CHECKING:
    from services.inference_service import InferenceService

SUPPORTED_MODE = "legend"
UNSUPPORTED_MODE_MESSAGE = "初の画像最終評価計算はLegendのみ対応しています。"
PARAMETER_MAXIMUM = HAJIME[SUPPORTED_MODE]["st_max"]
logger = get_logger()


class InferenceUseCase:
    def __init__(self, inference_service: InferenceService) -> None:
        self._inference_service = inference_service

    @staticmethod
    def _validate_integer(
        name: str, value: int | None, maximum: int | None = None
    ) -> None:
        if type(value) is not int:
            raise ValueError(f"{name}は0以上の整数で指定してください。")
        if value < 0 or (maximum is not None and value > maximum):
            if maximum is not None:
                raise ValueError(f"{name}は0～{maximum}の範囲で指定してください。")
            raise ValueError(f"{name}は0以上の整数で指定してください。")

    async def execute(
        self,
        *,
        params: HajimeFinalGradeFromImgParams,
        schedule_image: np.ndarray,
        party_image: np.ndarray,
        final_exam_image: np.ndarray,
        mid_exam_image: np.ndarray | None,
    ) -> InferenceUseCaseResult:
        if params.is_boost_active:
            raise BoostModeNotSupportedError(BOOST_MODE_NOT_SUPPORTED_MESSAGE)
        if params.mode != SUPPORTED_MODE:
            raise ValueError(UNSUPPORTED_MODE_MESSAGE)
        if mid_exam_image is None:
            self._validate_integer("中間試験スコア", params.mid_exam_score, 200000)

        async def infer(image):
            return await asyncio.to_thread(
                self._inference_service.infer,
                image,
                parameter_maximum=PARAMETER_MAXIMUM,
            )

        schedule = await infer(schedule_image)
        party = await infer(party_image)
        final = await infer(final_exam_image)
        mid = await infer(mid_exam_image) if mid_exam_image is not None else None
        parameters = {
            key: getattr(schedule.parameters, key)
            for key in ("vo", "da", "vi", "fans", "star")
        }
        bonuses = {
            key: getattr(party.bonuses, key) for key in ("vo", "da", "vi", "kirameki")
        }
        final_scores = {
            key: getattr(final.scores, key) for key in ("sum_score", "vo", "da", "vi")
        }
        mid_scores = (
            {key: getattr(mid.scores, key) for key in ("sum_score", "vo", "da", "vi")}
            if mid is not None
            else {
                "sum_score": params.mid_exam_score,
                "vo": None,
                "da": None,
                "vi": None,
            }
        )
        result = InferenceUseCaseResult(
            parameters=parameters,
            bonuses=bonuses,
            mid_exam_scores=mid_scores,
            final_exam_scores=final_scores,
            mid_exam_score=mid_scores["sum_score"],
            mid_exam_score_source="image" if mid is not None else "manual",
            final_exam_score=final_scores["sum_score"],
            schedule_inference=schedule,
            party_inference=party,
            final_exam_inference=final,
            mid_exam_inference=mid,
        )
        errors = []
        for section, values in (
            ("parameters", {key: parameters[key] for key in ("vo", "da", "vi")}),
            ("mid_exam_scores", {"中間試験スコア": result.mid_exam_score}),
            ("final_exam_scores", {"最終試験スコア": result.final_exam_score}),
        ):
            section_errors = []
            for name, value in values.items():
                if value is None:
                    section_errors.append(f"{name}を取得できませんでした。")
                else:
                    try:
                        self._validate_integer(
                            name,
                            value,
                            200000 if section == "mid_exam_scores" else None,
                        )
                    except ValueError as exc:
                        section_errors.append(str(exc))
            if section_errors:
                result.failed_sections.append(section)
                errors.extend(section_errors)
        if errors:
            result.error_reason = "\n".join(errors)
            return result
        started_at = time.perf_counter()
        result.final_grade_result = self.calculate(
            mode=params.mode,
            character=params.character,
            vo_status=parameters["vo"],
            da_status=parameters["da"],
            vi_status=parameters["vi"],
            vo_ability=params.vo_ability,
            da_ability=params.da_ability,
            vi_ability=params.vi_ability,
            mid_exam_score=result.mid_exam_score,
            final_exam_score=result.final_exam_score,
            final_exam_rank=params.final_exam_rank,
        )
        result.calculation_ms = (time.perf_counter() - started_at) * 1000
        return result

    def calculate(
        self,
        *,
        mode: str,
        character: str | None,
        vo_status: int | None,
        da_status: int | None,
        vi_status: int | None,
        vo_ability: int,
        da_ability: int,
        vi_ability: int,
        mid_exam_score: int | None,
        final_exam_score: int | None,
        final_exam_rank: str,
    ) -> HajimeFinalGradeResult:
        if mode != SUPPORTED_MODE:
            raise ValueError(UNSUPPORTED_MODE_MESSAGE)
        for name, value in {
            "Voパラメータ": vo_status,
            "Daパラメータ": da_status,
            "Viパラメータ": vi_status,
            "Vo試験終了時アビ": vo_ability,
            "Da試験終了時アビ": da_ability,
            "Vi試験終了時アビ": vi_ability,
            "最終試験スコア": final_exam_score,
        }.items():
            self._validate_integer(name, value)
        self._validate_integer("中間試験スコア", mid_exam_score, 200000)
        if final_exam_rank not in ("first", "second", "third", "other"):
            raise ValueError("最終試験順位が不正です。")
        calc_params = HajimeFinalGradeParams(
            mode=mode,
            character=character,
            vo_status=vo_status,
            da_status=da_status,
            vi_status=vi_status,
            vo_ability=vo_ability,
            da_ability=da_ability,
            vi_ability=vi_ability,
            mid_exam_score=mid_exam_score,
            final_exam_score=final_exam_score,
            final_exam_rank=final_exam_rank,
            is_boost_active=False,
            kirameki=0,
        )
        logger.info("calc params %s", calc_params)
        return HajimeScenario(mode=mode).calculate_score(calc_params)
