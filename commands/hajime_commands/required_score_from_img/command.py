# hajime_commands/required_score_from_img/command.py
import discord
from discord import ui, Embed
from models.hajime.required_score.params import HajimeRequiredScoreParams
from models.hajime.required_score.result import HajimeRequiredScoreResult
from models.hajime.required_score_from_img.params import HajimeRequiredScoreFromImgParams
# from models.hajime.final_grade.params import HajimeFinalGradeParams
# from models.hajime.final_grade.result import HajimeFinalGradeResult
from scenarios import HajimeScenario
from ocr.core import OCR
from commands.hajime_commands.required_score.command import HajimeRequiredScoreCommand
from commands.hajime_commands.required_score.container_builder import build_required_score_container
from .container_builder import build_error_container
# from commands.hajime_commands.final_grade.container_builder import build_final_grade_container
from config.settings import SETTINGS
from typing import Optional, Dict, Tuple
from utils.logger import get_logger
import time

COMMAND_NAME = "hajime_required_score_from_img"
logger = get_logger()

# --- ラベル <-> 内部キー ---
_LABEL2KEY = {
    "Voパラメータ": "vo_status",
    "Daパラメータ": "da_status",
    "Viパラメータ": "vi_status",
    "中間試験スコア": "mid_exam_score",
    # "Voパラメータボーナス": "vo_bonus",
    # "Daパラメータボーナス": "da_bonus",
    # "Viパラメータボーナス": "vi_bonus",
    "ほしのきらめき": "kirameki",
}

# --- Modal 定義 ---
class AddExamScoreModal(ui.Modal):
    def __init__(self, cmd: "HajimeRequiredScoreFromImgCommand"):
        super().__init__(title="最終試験のスコアを入力")
        self.cmd = cmd
        input_box = ui.TextInput(
            label="最終試験のスコア",
            required=False,
            placeholder="数値を入力"
        )
        self.add_item(input_box)
        self.input = input_box
        
    async def on_submit(self, interaction: discord.Interaction):
        await interaction.response.defer()
        raw = (self.input.value or "").strip()

        try:
            new_exam_score = int(raw)
        except ValueError:
            await interaction.response.send_message(
                "半角数字で入力してください。",
                ephemeral=True,
            )
            return
        
        await self.cmd._calc_final_grade(interaction, new_exam_score)


class ParamEditModal(ui.Modal):
    def __init__(self, cmd: "HajimeRequiredScoreFromImgCommand", selected_params: list[str], current: dict):
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

            # 2) 型/範囲の軽い検証＆キャスト（int前提）
            int_keys = ("vo_status", "da_status", "vi_status", "mid_exam_score", "kirameki")
            # float_keys = ("vo_bonus", "da_bonus", "vi_bonus")

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

            # for k in float_keys:
            #     if k in merged:
            #         try:
            #             merged[k] = float(str(merged[k]).strip() or 0.0)
            #             if merged[k] < 0:
            #                 raise ValueError(f"{k} は0.0以上にしてください")
            #         except Exception as e:
            #             await interaction.response.send_message(
            #                 embed=Embed(title="入力エラー", description=f"{k}: {e}"),
            #                 ephemeral=True
            #             )
                    
            # merged["boost_month"] = bool(merged.get("boost_month", self.cmd._static.get("is_boost_active", False)))
            merged["boost_month"] = bool(
                 merged.get("boost_month", getattr(self.cmd, "_static", {}).get("is_boost_active", False))
            )

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
    """
    パラメータの編集セレクト
    """
    def __init__(self, cmd: "HajimeRequiredScoreFromImgCommand"):
        # 強化月間フラグ
        is_boost = bool(getattr(cmd, "_static", {}).get("is_boost_active", False))

        # プルダウンメニューの構築
        options = [
            discord.SelectOption(label="Voパラメータ"),
            discord.SelectOption(label="Daパラメータ"),
            discord.SelectOption(label="Viパラメータ"),
            discord.SelectOption(label="中間試験スコア"),
            # discord.SelectOption(label="Voパラメータボーナス"),
            # discord.SelectOption(label="Daパラメータボーナス"),
            # discord.SelectOption(label="Viパラメータボーナス"),
            discord.SelectOption(label="ほしのきらめき"),
        ]

        # 強化月間適用時以外はきらめきを削除
        if not is_boost:
            options = [o for o in options if o.label != "ほしのきらめき"]

        max_vals = min(4, len(options))
        super().__init__(
            placeholder="パラメータを修正する",
            min_values=1,
            max_values=max_vals,
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
        

# --- Button 定義 ---
class AddExamScoreButton(ui.Button):
    def __init__(self, cmd: "HajimeRequiredScoreFromImgCommand"):
        super().__init__(
            style=discord.ButtonStyle.primary, 
            label="最終試験のスコアを入力する"
        )
        self.cmd = cmd
        
    async def callback(self, interaction: discord.Interaction):
        await interaction.response.send_modal(AddExamScoreModal(self.cmd))
        
        # ボタンを無効化
        self.disabled = True
        await interaction.message.edit(view=self.view)
        

class HajimeRequiredScoreFromImgCommand(HajimeRequiredScoreCommand):
    """
    初シナリオの目標グレード/スコアに必要な
    最終試験スコアを画像から読み取り計算するコマンド
    """
    async def execute(self, params: HajimeRequiredScoreFromImgParams):
        self.log_command_start(COMMAND_NAME)
        t0 = time.perf_counter()
        
        self._static = {
            "mode": params.mode,
            "vo_ability": params.vo_ability,
            "da_ability": params.da_ability,
            "vi_ability": params.vi_ability,
            "character": params.character,
            "target_grade": params.target_grade,
            "target_score": params.target_score,
            "is_boost_active": params.is_boost_active,
        }

        
        # 先に保留応答
        interaction: discord.Interaction = self.interaction
        await interaction.response.defer(thinking=True, ephemeral=False)
        
        # 入力画像の確認
        if params.schedule_img.content_type and not params.schedule_img.content_type.startswith("image/"):
            logger.warning("input img error")
            return await interaction.edit_original_response(
                content="画像ファイルを添付してください"
            )
        
        # if params.party_img.content_type and not params.party_img.content_type.startswith("image/"):
        #     logger.warning("input img error")
        #     return await interaction.edit_original_response(
        #         content="画像ファイルを添付してください"
        #     )
        
        if params.score_img.content_type and not params.score_img.content_type.startswith("image/"):
            logger.warning("input img error")
            return await interaction.edit_original_response(
                content="画像ファイルを添付してください"
            )
        
        # 読み取り試行
        try:
            # 画像の読み込み
            t1 = time.perf_counter()
            schedule_img_bytes = await params.schedule_img.read()
            # party_img_bytes = await params.party_img.read()
            score_img_bytes = await params.score_img.read()
            dt = (time.perf_counter() - t1) * 1000
            logger.debug("loading img time %.1f ms", dt)

            # パラメータの読み取り
            t2 = time.perf_counter()
            schedule_ocr = OCR(schedule_img_bytes)
            parameters_dict = schedule_ocr.read_params()
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
            # t3 = time.perf_counter()
            # party_ocr = OCR(party_img_bytes)
            # bonus_dict = party_ocr.read_bonus(params.is_boost_active)
            # dt = (time.perf_counter() - t3) * 1000
            # logger.debug(
            #     "read bonus vo: %s da: %s vi: %s time %.1f ms",
            #     bonus_dict.get("vo"), 
            #     bonus_dict.get("da"), 
            #     bonus_dict.get("vi"),
            #     dt
            # )
            
            
            # 中間試験スコアの読み取り
            t3 = time.perf_counter()
            score_ocr = OCR(score_img_bytes)
            score_dict = score_ocr.read_scores()
            dt = (time.perf_counter() - t3) * 1000
            logger.debug(
                "read score %s time %.1f ms",
                score_dict.get("sum_score"), 
                dt
            )
            
            # if None in parameters_dict.values() or None in bonus_dict.values():
            if parameters_dict.get("vo") is None or parameters_dict.get("da") is None or parameters_dict.get("vi") is None or score_dict.get("sum_score") is None:
                # 現在値を保持（モーダル初期値用）
                self._current_values = {
                    "vo_status":  parameters_dict.get("vo")   or 0,
                    "da_status":  parameters_dict.get("da")   or 0,
                    "vi_status":  parameters_dict.get("vi")   or 0,
                    "mid_exam_score": score_dict.get("sum_score") or 0,
                    # "vo_bonus":   bonus_dict.get("vo")        or 0,
                    # "da_bonus":   bonus_dict.get("da")        or 0,
                    # "vi_bonus":   bonus_dict.get("vi")        or 0,
                    # "boost_month": bool(params.is_boost_active),
                    # "kirameki":   (bonus_dict.get("kirameki") or 0) if params.is_boost_active else 0,
                }

                # View / Container構築 -> メッセージ送信
                logger.info("ERROR View/Container構築開始")
                err_layout = ui.LayoutView()
                err_container = build_error_container(
                    params=parameters_dict,
                    # bonus=bonus_dict,
                    score_dict = score_dict,
                    is_boost=params.is_boost_active,
                )
                err_container.add_item(ui.Separator())
                row = ui.ActionRow()
                row.add_item(ParamSelect(self))
                err_container.add_item(row)
                err_layout.add_item(err_container)
                logger.info("ERROR View/Container構築完了: メッセージ送信を開始")
                await interaction.edit_original_response(view=err_layout)

                # ▼ 失敗時も保存する（同意時）
                await self.maybe_archive_inputs(
                    interaction=interaction,
                    save_agree=params.save_agree,
                    command=COMMAND_NAME,
                    images={
                        "schedule": (params.schedule_img.filename or "schedule.png", schedule_img_bytes),
                        # "party":    (params.party_img.filename or "party.png",     party_img_bytes),
                        "sum_score": (params.score_img.filename or "score.png", score_img_bytes),
                    },
                    meta={
                        "error": "param_or_bonus_read_failed",
                        "ocr_params": parameters_dict,
                        # "ocr_bonus": bonus_dict,
                        "ocr_score": score_dict
                    },
                )
                self.log_command_end(COMMAND_NAME)
                return
            

        except Exception as e:
            logger.warning("%s: %s", type(e).__name__, e)
            logger.info("ERROR Embed構築開始")
            err = discord.Embed(
                title="画像の読み取りに失敗しました",
                description=f"`{type(e).__name__}: {e}`",
                color=0xE74C3C
            )
            logger.info("ERROR Embed構築完了: メッセージ送信を開始")
            await interaction.edit_original_response(content=None, embed=err)

            # ▼ 失敗時も保存する（同意時）: 取得済みバイトがなければ再読込を試みる
            try:
                images = {}
                if params.schedule_img:
                    images["schedule"] = (
                        params.schedule_img.filename or "schedule.png",
                        locals().get("schedule_img_bytes") or await params.schedule_img.read()
                    )
                if params.party_img:
                    images["party"] = (
                        params.party_img.filename or "party.png",
                        locals().get("party_img_bytes") or await params.party_img.read()
                    )
                    
                if params.score_img:
                    images["score"] = (
                        params.score_img.filename or "score.png",
                        locals().get("score_img_bytes") or await params.score_img.read()
                    )
            except Exception:
                images = {}

            await self.maybe_archive_inputs(
                interaction=interaction,
                save_agree=params.save_agree,
                command=COMMAND_NAME,
                images=images,
                meta={
                    "error": "exception",
                    "exception": f"{type(e).__name__}: {e}",
                },
            )
            self.log_command_end(COMMAND_NAME)
            return
            
        # ------------------------------------------------
        # ここから計算ロジック
        # ------------------------------------------------
        
        # 再計算に使う固定情報を保存
        self._static = {
            "mode": params.mode,
            "vo_status": parameters_dict['vo'],
            "da_status": parameters_dict['da'],
            "vi_status": parameters_dict['vi'],
            "vo_ability": params.vo_ability,
            "da_ability": params.da_ability,
            "vi_ability": params.vi_ability,
            "mid_exam_score": score_dict['sum_score'],
            "character": params.character,
            "is_boost_active": params.is_boost_active,
            # "kirameki": params.kirameki,
            "kirameki": 0,
            "exam_score": 0,
            "target_grade": params.target_grade,
            "target_score": params.target_score,
        }
        
        calc_params = HajimeRequiredScoreParams(
            mode            = params.mode,
            vo_status       = parameters_dict['vo'],
            da_status       = parameters_dict['da'],
            vi_status       = parameters_dict['vi'],
            vo_ability      = params.vo_ability,
            da_ability      = params.da_ability,
            vi_ability      = params.vi_ability,
            mid_exam_score  = score_dict['sum_score'],
            target_grade    = params.target_grade,
            target_score    = params.target_score,
            character       = params.character,
            is_boost_active = params.is_boost_active,
            kirameki        = 0
        )
        
        # インスタンス生成
        scenario = HajimeScenario(mode=calc_params.mode)
        
        # 要求スコアの計算
        result_dict = self._compute_required_result_dict(
            scenario= scenario,
            params= calc_params
        )
        logger.debug("[required_score] compute_result_dict finished")
        
        pairs, target_grade_norm, target_score_norm = self._build_pairs(
            result_dict=result_dict,
            target_grade=calc_params.target_grade,
            target_score=calc_params.target_score,
        )
        logger.debug(
            "[required_score] build_pairs finished mode=%s",
            ("target_score" if target_score_norm is not None else
             "target_grade" if target_grade_norm is not None else "all_grades")
        )
        
        result = HajimeRequiredScoreResult(
            **calc_params.__dict__,
            SS_required_score      = self._total_or_none(result_dict.get("SS")),
            SS_plus_required_score = self._total_or_none(result_dict.get("SS+")),
            SSS_required_score     = self._total_or_none(result_dict.get("SSS")),
            SSS_plus_required_score= self._total_or_none(result_dict.get("SSS+")),
        )
        
        # 出力サマリ（INFO）
        def _brief(v):
            if isinstance(v, dict):
                return f"{v.get('total')} (Vo={v.get('vo')},Da={v.get('da')},Vi={v.get('vi')})" + (" [CLEAR!]" if "note" in v else "")
            return v
        logger.info(
            "result summary SS=%s SS+=%s SSS=%s SSS+=%s",
            _brief(result_dict.get("SS")), _brief(result_dict.get("SS+")),
            _brief(result_dict.get("SSS")), _brief(result_dict.get("SSS+")),
        )
        
        # 現在値を保持（モーダル初期値用）
        self._current_values = {
            "vo_status":  parameters_dict.get("vo")   or 0,
            "da_status":  parameters_dict.get("da")   or 0,
            "vi_status":  parameters_dict.get("vi")   or 0,
            "mid_exam_score": score_dict.get("sum_score") or 0,
            # "vo_bonus":   bonus_dict.get("vo")        or 0,
            # "da_bonus":   bonus_dict.get("da")        or 0,
            # "vi_bonus":   bonus_dict.get("vi")        or 0,
            "boost_month": bool(params.is_boost_active),
            # "kirameki":   (bonus_dict.get("kirameki") or 0) if params.is_boost_active else 0,
            "kirameki": 0
        }

        # View / Container構築 -> メッセージ送信
        logger.info("View/Container構築開始")
        view = ui.LayoutView()
        container = build_required_score_container(result, override_pairs=pairs)
        container.add_item(ui.Separator())
        
        param_select_row = ui.ActionRow()
        param_select_row.add_item(ParamSelect(self))
        container.add_item(param_select_row)
        
        add_exam_score_button_row = ui.ActionRow()
        add_exam_score_button_row.add_item(AddExamScoreButton(self))
        container.add_item(add_exam_score_button_row)
        
        view.add_item(container)
        logger.info("View/Container構築完了：メッセージを送信")
        await self.interaction.followup.send(view=view)
        self.message = await interaction.original_response()

        
        # 送信後：同意時のみ保存（共通化）
        await self.maybe_archive_inputs(
            interaction=interaction,
            save_agree=params.save_agree,
            command="nia_required_score_from_img",
            images={
                "schedule": (params.schedule_img.filename or "schedule.png", schedule_img_bytes),
                # "party":    (params.party_img.filename or "party.png",     party_img_bytes),
            },
            meta={
                "mode": params.mode,
                "character": params.character,
                "runtime_ms": (time.perf_counter() - t0) * 1000.0,
                "ocr_params": parameters_dict,
                # "ocr_bonus":  bonus_dict,
            },
        )
        
        dt = (time.perf_counter() - t2) * 1000
        logger.debug("required score finished in %.2f ms", dt)

        dt = (time.perf_counter() - t0) * 1000
        logger.debug("%s finished in %.2f ms",COMMAND_NAME, dt)
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
        
        self._static.update({
            "vo_status": merged.get("vo_status", static.get("vo_status", 0)),
            "da_status": merged.get("da_status", static.get("da_status", 0)),
            "vi_status": merged.get("vi_status", static.get("vi_status", 0)),
            "mid_exam_score": merged.get("mid_exam_score", static.get("mid_exam_score", 0)),
            "kirameki": merged.get("kirameki", static.get("kirameki", 0)),
        })
        static = self._static
        
        # 2) kirameki は強化月間ONのときのみ有効
        kirameki = merged.get("kirameki", 0) if static["is_boost_active"] else 0

        # 3) ドメイン計算を再実行
        async with self.scoped_ctx(interaction):
            self.log_recompute_start(COMMAND_NAME)
            t0 = time.perf_counter()

            calc_params = HajimeRequiredScoreParams(
                mode            = static["mode"],
                vo_status       = merged["vo_status"],
                da_status       = merged["da_status"],
                vi_status       = merged["vi_status"],
                vo_ability      = static['vo_ability'],
                da_ability      = static['da_ability'],
                vi_ability      = static['vi_ability'],
                mid_exam_score  = merged["mid_exam_score"],
                target_grade    = static["target_grade"],
                target_score    = static["target_score"],
                character       = static["character"],
                is_boost_active = static["is_boost_active"],
                kirameki        = 0
            )
            
            # インスタンス生成
            scenario = HajimeScenario(mode=calc_params.mode)
            
            # 要求スコアの計算
            result_dict = self._compute_required_result_dict(
                scenario= scenario,
                params= calc_params
            )
            logger.debug("[required_score] compute_result_dict finished")
            
            t_pairs = time.perf_counter()
            pairs,target_grade_norm, target_score_norm = self._build_pairs(
                result_dict=result_dict,
                target_grade=static["target_grade"],
                target_score=static["target_score"],
            )
            logger.debug(
                "[required_score] build_pairs finished in %.1f ms mode=%s",
                (time.perf_counter() - t_pairs) * 1000,
                ("target_score" if target_score_norm is not None else
                "target_grade" if target_grade_norm is not None else "all_grades")
            )

            result = HajimeRequiredScoreResult(
                **calc_params.__dict__,
                SS_required_score      = self._total_or_none(result_dict.get("SS")),
                SS_plus_required_score = self._total_or_none(result_dict.get("SS+")),
                SSS_required_score     = self._total_or_none(result_dict.get("SSS")),
                SSS_plus_required_score= self._total_or_none(result_dict.get("SSS+")),
            )

            # 出力サマリ（INFO）
            def _brief(v):
                if isinstance(v, dict):
                    return f"{v.get('total')} (Vo={v.get('vo')},Da={v.get('da')},Vi={v.get('vi')})" + (" [CLEAR!]" if "note" in v else "")
                return v
            logger.info(
                "result summary SS=%s SS+=%s SSS=%s SSS+=%s",
                _brief(result_dict.get("SS")), _brief(result_dict.get("SS+")),
                _brief(result_dict.get("SSS")), _brief(result_dict.get("SSS+")),
            )

            # View / Container構築 -> メッセージ送信
            logger.info("View/Container構築開始")
            view = ui.LayoutView()
            container = build_required_score_container(result, override_pairs=pairs)
            container.add_item(ui.Separator())
            
            param_select_row = ui.ActionRow()
            param_select_row.add_item(ParamSelect(self))
            container.add_item(param_select_row)
            
            add_exam_score_button_row = ui.ActionRow()
            add_exam_score_button_row.add_item(AddExamScoreButton(self))
            container.add_item(add_exam_score_button_row)
            
            view.add_item(container)
            logger.info("View/Container構築完了：メッセージを送信")
            await self.interaction.followup.send(view=view)
            
            dt = (time.perf_counter() - t0) * 1000
            logger.debug(f"nia_required_score_command finished in {dt:.2f} ms")
            self.log_recompute_end(COMMAND_NAME)