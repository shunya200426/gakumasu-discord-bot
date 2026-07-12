from __future__ import annotations

import asyncio
import time

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

        Args:
            params:
                コマンドから渡された計算条件。

            schedule_image:
                スケジュール画面のBGR画像。

            party_image:
                編成画面のBGR画像。

            score_image:
                スコア画面のBGR画像。

        Returns:
            推論結果、OCR失敗情報、
            最終評価計算結果をまとめた結果。
        """

        # ========================================
        # YOLO推論・切り出し・OCR
        # ========================================
        #
        # InferenceService.infer()は同期関数なので、
        # Discordのイベントループを止めないよう
        # asyncio.to_thread()で別スレッドへ移す。
        #
        # 同じDetector・TesseractEngineを共有するため、
        # 3画像は安全側に倒して順番に処理する。
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

        # ========================================
        # 使用するOCR結果を取得
        # ========================================
        parameters = (
            schedule_inference.parameters
        )

        bonuses = (
            party_inference.bonuses
        )

        scores = (
            score_inference.scores
        )

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

        # ========================================
        # 必須OCR項目の確認
        # ========================================
        parameter_failed = any(
            value is None
            for value in (
                parameters.vo,
                parameters.da,
                parameters.vi,
                parameters.fans,
            )
        )

        bonus_targets: list[
            int | float | None
        ] = [
            bonuses.vo,
            bonuses.da,
            bonuses.vi,
        ]

        if params.is_boost_active:
            bonus_targets.append(
                bonuses.kirameki
            )

        bonus_failed = any(
            value is None
            for value in bonus_targets
        )

        # 最終評価計算では属性別スコアを使う。
        # 合計スコアは必須値ではない。
        score_failed = any(
            value is None
            for value in (
                scores.vo,
                scores.da,
                scores.vi,
            )
        )

        failed_sections: list[str] = []

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

        # ========================================
        # OCR不足時
        # ========================================
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
                failed_sections=failed_sections,
                error_reason=error_reason,
                schedule_inference_ms=(
                    schedule_inference.total_ms
                ),
                party_inference_ms=(
                    party_inference.total_ms
                ),
                score_inference_ms=(
                    score_inference.total_ms
                ),
            )

        # ========================================
        # 型の絞り込み
        # ========================================
        #
        # 上の必須値チェックにより、
        # ここでは必要な値がすべて存在する。
        vo_status = parameters.vo
        da_status = parameters.da
        vi_status = parameters.vi
        now_fans = parameters.fans

        vo_bonus = bonuses.vo
        da_bonus = bonuses.da
        vi_bonus = bonuses.vi

        vo_score = scores.vo
        da_score = scores.da
        vi_score = scores.vi

        if (
            vo_status is None
            or da_status is None
            or vi_status is None
            or now_fans is None
            or vo_bonus is None
            or da_bonus is None
            or vi_bonus is None
            or vo_score is None
            or da_score is None
            or vi_score is None
        ):
            raise RuntimeError(
                "OCR必須値の型絞り込みに失敗しました。"
            )

        kirameki_value: int | float = 0

        if params.is_boost_active:
            if bonuses.kirameki is None:
                raise RuntimeError(
                    "強化月間ですが、"
                    "ほしのきらめきがありません。"
                )

            kirameki_value = (
                bonuses.kirameki
            )

        # ========================================
        # 最終評価計算
        # ========================================
        final_grade_params = NiaFinalGradeParams(
            character=params.character,
            mode=params.mode,
            audition=params.audition,
            vo_status=vo_status,
            da_status=da_status,
            vi_status=vi_status,
            vo_bonus=vo_bonus,
            da_bonus=da_bonus,
            vi_bonus=vi_bonus,
            vo_score=vo_score,
            da_score=da_score,
            vi_score=vi_score,
            now_fans=now_fans,
            challenge_P_item=(
                params.challenge_P_item
            ),
            is_boost_active=(
                params.is_boost_active
            ),
            kirameki=kirameki_value,
        )

        logger.info(
            "calc params %s",
            final_grade_params,
        )

        calculation_started_at = (
            time.perf_counter()
        )

        scenario = NiaScenario(
            mode=final_grade_params.mode
        )

        final_grade_result = (
            scenario.calculate_score(
                final_grade_params
            )
        )

        calculation_ms = (
            time.perf_counter()
            - calculation_started_at
        ) * 1000.0

        logger.info(
            "最終スコア: %s",
            final_grade_result.final_score,
        )

        logger.info(
            "評価ランク: %s",
            final_grade_result.final_grade,
        )

        return InferenceUseCaseResult(
            parameters=parameters_dict,
            bonuses=bonus_dict,
            scores=score_dict,
            final_grade_result=(
                final_grade_result
            ),
            schedule_inference_ms=(
                schedule_inference.total_ms
            ),
            party_inference_ms=(
                party_inference.total_ms
            ),
            score_inference_ms=(
                score_inference.total_ms
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
        values: dict,
    ) -> NiaFinalGradeFromImgResult:
        ...