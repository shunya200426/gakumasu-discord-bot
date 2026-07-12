# commands/nia_commands/final_grade_from_img/command.py
import discord
from discord import Embed, ui
from commands.base_command import BaseCommand
from models.nia.final_grade_from_img.params import NiaFinalGradeFromImgParams
from models.nia.final_grade_from_img.result import NiaFinalGradeFromImgResult
from models.nia.final_grade.params import NiaFinalGradeParams
from scenarios import NiaScenario
from commands.nia_commands.final_grade.container_builder import build_final_grade_container
from .container_builder import build_error_container
from utils.logger import get_logger
from ocr.core import OCR
import time

logger = get_logger()

COMMAND_NAME="nia_final_grade_from_img"

# --- ラベル <-> 内部キー ---
_LABEL2KEY = {
    "Voパラメータ": "vo_status",
    "Daパラメータ": "da_status",
    "Viパラメータ": "vi_status",
    "Voパラメータボーナス": "vo_bonus",
    "Daパラメータボーナス": "da_bonus",
    "Viパラメータボーナス": "vi_bonus",
    "Voスコア": "vo_score",
    "Daスコア": "da_score",
    "Viスコア": "vi_score",
    "ファン数": "now_fans",
    "ほしのきらめき": "kirameki",
}

# --- Modal 定義 ---
class ParamEditModal(ui.Modal):
    def __init__(self, cmd: "NiaFinalGradeFromImgCommand", selected_params: list[str], current: dict):
        super().__init__(title="パラメータを編集")
        self.cmd = cmd
        self.current = current
        self.inputs = {}
        for param in selected_params:
            input_box = ui.TextInput(
                label=param,
                required=False,
                default=str(current.get(_LABEL2KEY.get(param, ""), "")),
                placeholder="数値を入力"
            )
            self.add_item(input_box)
            self.inputs[param] = input_box

    async def on_submit(self, interaction: discord.Interaction):
        await interaction.response.defer()

        # 1) 入力を current にマージ（空欄は据え置き）
        try:
            updates = {}
            for label, ti in self.inputs.items():
                if ti.value not in ("", None):
                    key = _LABEL2KEY.get(label)
                    if key:
                        updates[key] = ti.value
            merged = {**(self.current or {}), **updates}

            # 2) 型/範囲の軽い検証＆キャスト
            int_keys = ("vo_status", "da_status", "vi_status", "vo_score", "da_score", "vi_score", "now_fans", "kirameki")
            float_keys = ("vo_bonus", "da_bonus", "vi_bonus")

            for k in int_keys:
                if k in merged:
                    try:
                        merged[k] = int(str(merged[k]).strip() or 0)
                        if merged[k] < 0:
                            raise ValueError(f"{k} は0以上にしてください")
                    except Exception as e:
                        await interaction.response.send_message(
                            embed=Embed(title="入力エラー", description=f"{k}: {e}"),
                            ephemeral=True
                        )
                        return

            for k in float_keys:
                if k in merged:
                    try:
                        merged[k] = float(str(merged[k]).strip() or 0.0)
                        if merged[k] < 0:
                            raise ValueError(f"{k} は0.0以上にしてください")
                    except Exception as e:
                        await interaction.response.send_message(
                            embed=Embed(title="入力エラー", description=f"{k}: {e}"),
                            ephemeral=True
                        )
                        return
                    
            merged["boost_month"] = bool(merged.get("boost_month", self.cmd._static.get("is_boost_active", False)))

            # 3) 現在値を更新し、再計算して新規メッセージを送信
            self.cmd._current_values = merged
            await self.cmd._recompute_and_edit(interaction, merged)

        except Exception as e:
            logger.exception("ParamEditModal.on_submit failed")
            await interaction.followup.send(
                embed=discord.Embed(title="入力エラー", description=f"{type(e).__name__}: {e}"),
                ephemeral=True
            )


# --- プルダウン定義 ---
class ParamSelect(ui.Select):
    def __init__(self, cmd: "NiaFinalGradeFromImgCommand"):
        # 強化月間フラグ
        is_boost = bool(getattr(cmd, "_static", {}).get("is_boost_active", False))

        # プルダウンメニューの構築
        options = [
            discord.SelectOption(label="Voパラメータ"),
            discord.SelectOption(label="Daパラメータ"),
            discord.SelectOption(label="Viパラメータ"),
            discord.SelectOption(label="Voパラメータボーナス"),
            discord.SelectOption(label="Daパラメータボーナス"),
            discord.SelectOption(label="Viパラメータボーナス"),
            discord.SelectOption(label="Voスコア"),
            discord.SelectOption(label="Daスコア"),
            discord.SelectOption(label="Viスコア"),
            discord.SelectOption(label="ファン数"),
            discord.SelectOption(label="ほしのきらめき"),
        ]

        # 強化月間適用時以外はきらめきを削除
        if not is_boost:
            options = [o for o in options if o.label != "ほしのきらめき"]

        super().__init__(
            placeholder="パラメータを修正する",
            min_values=1,
            max_values=5,
            options=options
        )
        self.cmd = cmd

    async def callback(self, interaction: discord.Interaction):
        # 強化月間でない場合は「きらめき」を除外
        current = getattr(self.cmd, "_current_values", {}) or {}
        selected = [o for o in self.values if (o != "ほしのきらめき" or current.get("boost_month"))]
        await interaction.response.send_modal(ParamEditModal(self.cmd, selected, current))

        # プルダウンを無効化
        self.disabled = True
        await interaction.message.edit(view=self.view)


class NiaFinalGradeFromImgCommand(BaseCommand):
    """
    NIAシナリオの最終評価計算コマンド
    """

    async def execute(self, params: NiaFinalGradeFromImgParams):
        self.log_command_start(COMMAND_NAME)
        t0 = time.perf_counter()

        # 再計算で使う固定情報を保存
        self._static = {
            "character": params.character,
            "mode": params.mode,
            "audition": params.audition,
            "challenge_P_item": params.challenge_P_item,
            "is_boost_active": params.is_boost_active,
        }

        # 先に保留応答
        interaction: discord.Interaction = self.interaction
        await interaction.response.defer(thinking=True, ephemeral=False)

        # 入力画像の確認
        if params.schedule_img.content_type and not params.schedule_img.content_type.startswith("image/"):
            return await interaction.edit_original_response(
                content="画像ファイルを添付してください"
            )
        
        if params.party_img.content_type and not params.party_img.content_type.startswith("image/"):
            return await interaction.edit_original_response(
                content="画像ファイルを添付してください"
            )
        
        if params.score_img.content_type and not params.score_img.content_type.startswith("image/"):
            return await interaction.edit_original_response(
                content="画像ファイルを添付してください"
            )
        
        # 読み取り試行
        try:
            err_flag = False
            # 画像の読み込み
            t1 = time.perf_counter()
            schedule_img_bytes = await params.schedule_img.read()
            party_img_bytes = await params.party_img.read()
            score_img_bytes = await params.score_img.read()
            dt = (time.perf_counter() - t1) * 1000
            logger.debug("loading img time %.1f ms", dt)

            # パラメータの読み取り
            t2 = time.perf_counter()
            schedule_ocr = OCR(schedule_img_bytes)
            parameters_dict = schedule_ocr.read_params()
            if None in parameters_dict.values():
                err_flag = True
                e = "None in parameters_dict"
                logger.warning(e)
            dt = (time.perf_counter() - t2) * 1000
            logger.debug(
                "read params vo: %s da: %s vi: %s fans: %s time %.1f ms",
                parameters_dict.get("vo"),
                parameters_dict.get("da"),
                parameters_dict.get("vi"),
                parameters_dict.get("fans"),
                dt
            )

            # パラメータボーナスの読み取り
            t3 = time.perf_counter()
            party_ocr = OCR(party_img_bytes)
            bonus_dict = party_ocr.read_bonus(params.is_boost_active)
            if None in bonus_dict.values():
                err_flag = True
                e = "None in bonus_dict"
                logger.warning(e)
            dt = (time.perf_counter() - t3) * 1000
            logger.debug(
                "read bonus vo: %s da: %s vi: %s kirameki: %s time %.1f ms",
                bonus_dict.get("vo"), 
                bonus_dict.get("da"), 
                bonus_dict.get("vi"),
                bonus_dict.get("kirameki"),
                dt
            )

            # スコアの読み取り
            t4 = time.perf_counter()
            score_ocr = OCR(score_img_bytes)
            score_dict = score_ocr.read_scores()
            if None in score_dict.values():
                err_flag = True
                e = "None in score_dict"
                logger.warning(e)
            dt = (time.perf_counter() - t4) * 1000
            logger.debug(
                "read score vo: %s da: %s vi: %s sum_score: %s time %.1f ms",
                score_dict.get('vo'), 
                score_dict.get('da'),
                score_dict.get('vi'), 
                score_dict.get('sum_score'), 
                dt
            )

            if err_flag:
                logger.warning("error: %s", e)
                # 現在値を保持（モーダル初期値用）
                self._current_values = {
                    "vo_status":  parameters_dict.get("vo")   or 0,
                    "da_status":  parameters_dict.get("da")   or 0,
                    "vi_status":  parameters_dict.get("vi")   or 0,
                    "vo_bonus":   bonus_dict.get("vo")        or 0,
                    "da_bonus":   bonus_dict.get("da")        or 0,
                    "vi_bonus":   bonus_dict.get("vi")        or 0,
                    "vo_score":   score_dict.get("vo")        or 0,
                    "da_score":   score_dict.get("da")        or 0,
                    "vi_score":   score_dict.get("vi")        or 0,
                    "now_fans":   parameters_dict.get("fans") or 0,
                    "boost_month": bool(params.is_boost_active),
                    "kirameki":   (bonus_dict.get("kirameki") or 0) if params.is_boost_active else 0,
                }


                # View / Container構築
                logger.info("ERROR View / Container構築開始")
                view = ui.LayoutView()
                err_container = build_error_container(
                    params=parameters_dict,
                    bonus=bonus_dict,
                    score=score_dict,
                    is_boost=params.is_boost_active,
                )
                err_container.add_item(ui.Separator())
                row = ui.ActionRow()
                row.add_item(ParamSelect(self))
                err_container.add_item(row)
                view.add_item(err_container)
                logger.info("ERROR View / Container構築完了: メッセージ送信を開始")
                await interaction.edit_original_response(view=view)

                # ▼ 失敗時も保存する（同意時）
                await self.maybe_archive_inputs(
                    interaction=interaction,
                    save_agree=params.save_agree,
                    command="nia_required_score_from_img",
                    images={
                        "schedule": (params.schedule_img.filename or "schedule.png", schedule_img_bytes),
                        "party":    (params.party_img.filename or "party.png", party_img_bytes),
                        "score": (params.score_img.filename or "score.png", score_img_bytes),
                    },
                    meta={
                        "error": "{}".format(e),
                    },
                )
                self.log_command_end(COMMAND_NAME)
                return


        except Exception as e:
            logger.error("%s: %s", type(e).__name__, e)
            logger.info("ERROR Embed構築開始")
            err = discord.Embed(
                title="画像の読み取りに失敗しました",
                description=f"`{type(e).__name__}: {e}`",
                color=0xE74C3C
            )
            logger.info("ERROR Embed構築完了: メッセージ送信を開始")
            await interaction.edit_original_response(content=None, embed=err)
            self.log_command_end(COMMAND_NAME)

            # ▼ 失敗時も保存する（同意時）
            await self.maybe_archive_inputs(
                interaction=interaction,
                save_agree=params.save_agree,
                command="nia_required_score_from_img",
                images={
                    "schedule": (params.schedule_img.filename or "schedule.png", schedule_img_bytes),
                    "party":    (params.party_img.filename or "party.png",     party_img_bytes),
                    "score": (params.score_img.filename or "score.png", score_img_bytes),
                },
                meta={
                    "error": "{}".format(e),
                },
            )
            self.log_command_end(COMMAND_NAME)
            return
        
        kirameki_val = bonus_dict.get('kirameki') if params.is_boost_active else 0

        final_grade_params = NiaFinalGradeParams(
            character=params.character,
            mode=params.mode,
            audition=params.audition,
            vo_status=parameters_dict['vo'],
            da_status=parameters_dict['da'],
            vi_status=parameters_dict['vi'],
            vo_bonus=bonus_dict['vo'],
            da_bonus=bonus_dict['da'],
            vi_bonus=bonus_dict['vi'],
            vo_score=score_dict['vo'],
            da_score=score_dict['da'],
            vi_score=score_dict['vi'],
            now_fans=parameters_dict['fans'],
            challenge_P_item=params.challenge_P_item,
            is_boost_active=params.is_boost_active,
            kirameki=kirameki_val
        )

        logger.info("calc params %s", final_grade_params)

        # シナリオ実行
        t5 = time.perf_counter()
        scenario = NiaScenario(mode=final_grade_params.mode)
        result: NiaFinalGradeFromImgResult = scenario.calculate_score(final_grade_params)

        logger.info(f"最終スコア: {result.final_score}")
        logger.info(f"評価ランク: {result.final_grade}")


        # 現在値を保持（モーダル初期値用）
        self._current_values = {
            "vo_status":  parameters_dict.get("vo")   or 0,
            "da_status":  parameters_dict.get("da")   or 0,
            "vi_status":  parameters_dict.get("vi")   or 0,
            "vo_bonus":   bonus_dict.get("vo")        or 0,
            "da_bonus":   bonus_dict.get("da")        or 0,
            "vi_bonus":   bonus_dict.get("vi")        or 0,
            "vo_score":   score_dict.get("vo")        or 0,
            "da_score":   score_dict.get("da")        or 0,
            "vi_score":   score_dict.get("vi")        or 0,
            "now_fans":   parameters_dict.get("fans") or 0,
            "boost_month": bool(params.is_boost_active),
            "kirameki":   (bonus_dict.get("kirameki") or 0) if params.is_boost_active else 0,
        }

        # View/Container 構築
        logger.debug("View/Container 構築開始")
        view = ui.LayoutView()
        container = build_final_grade_container(result)
        container.add_item(ui.Separator())
        row = ui.ActionRow()
        row.add_item(ParamSelect(self))
        container.add_item(row)
        view.add_item(container)
        logger.debug("View/Container 構築完了：メッセージを送信")
        await interaction.edit_original_response(view=view)

        # 送信後：同意時のみ保存（共通化）
        await self.maybe_archive_inputs(
            interaction=interaction,
            save_agree=params.save_agree,
            command=COMMAND_NAME,
            images={
                "schedule": (params.schedule_img.filename or "schedule.png", schedule_img_bytes),
                "party":    (params.party_img.filename or "party.png",     party_img_bytes),
                "score":    (params.score_img.filename or "score.png",     score_img_bytes),
            },
            meta={
                "mode": params.mode,
                "audition": params.audition,
                "character": params.character,
                "runtime_ms": (time.perf_counter() - t0) * 1000.0,
                "ocr_params": parameters_dict,
                "ocr_bonus":  bonus_dict,
                "ocr_score":  score_dict,
            },
        )

        dt = (time.perf_counter() - t5) * 1000
        logger.debug("calculate_scores finished in %.2f ms", dt)

        dt = (time.perf_counter() - t0) * 1000
        logger.debug("%s command finished in %.2f ms",COMMAND_NAME, dt)
        self.log_command_end(COMMAND_NAME)


    # --- 内部: 再計算してメッセージを書き換える ---
    async def _recompute_and_edit(self, interaction: discord.Interaction, merged: dict):
        """
        merged には vo_status/vo_bonus/now_fans/kirameki などが int 化されて入っている想定。
        OCRは再実行せず、値だけ差し替えて必要スコアを再計算し、新規メッセージを送信。
        """
        # 1) 直近の固定情報（実行時の params 相当）を保持しておく
        #    初回 execute() で保存しておく
        static = getattr(self, "_static", None)
        if not static:
            # 初回に備えた保険。execute() 冒頭で _static を必ず埋めるのが理想。
            await interaction.response.send_message(
                embed=Embed(title="再計算エラー", description="内部状態が不足しています。もう一度コマンドを実行してください。"),
                ephemeral=True
            )
            return
        
        # 2) kirameki は強化月間ONのときのみ有効
        kirameki = merged.get("kirameki", 0) if static["is_boost_active"] else 0

        # 3) ドメイン計算を再実行
        async with self.scoped_ctx(interaction):
            self.log_recompute_start(COMMAND_NAME)
            final_grade_params = NiaFinalGradeParams(
                character      = static["character"],
                mode           = static["mode"],
                audition       = static["audition"],
                vo_status      = merged["vo_status"],
                da_status      = merged["da_status"],
                vi_status      = merged["vi_status"],
                vo_bonus       = merged["vo_bonus"],
                da_bonus       = merged["da_bonus"],
                vi_bonus       = merged["vi_bonus"],
                vo_score       = merged["vo_score"],
                da_score       = merged["da_score"],
                vi_score       = merged["vi_score"],
                now_fans       = merged["now_fans"],
                challenge_P_item = static["challenge_P_item"],
                is_boost_active  = static["is_boost_active"],
                kirameki         = kirameki,
            )
            logger.info("calc params %s", final_grade_params)
            
            scenario = NiaScenario(mode=final_grade_params.mode)
            result: NiaFinalGradeFromImgResult = scenario.calculate_score(final_grade_params)

            logger.info(f"最終スコア: {result.final_score}")
            logger.info(f"評価ランク: {result.final_grade}")

            logger.info("View/Container構築開始")
            layout = ui.LayoutView()
            container = build_final_grade_container(result)
            container.add_item(ui.Separator())
            row = ui.ActionRow()
            row.add_item(ParamSelect(self))
            container.add_item(row)
            layout.add_item(container)
            logger.info("View/Container構築完了：メッセージを送信")
            
            # 新規メッセージとして送信
            await interaction.followup.send(view=layout)
            self.log_recompute_end(COMMAND_NAME)