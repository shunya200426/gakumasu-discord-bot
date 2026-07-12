# commands/nia_commands/required_score_from_img/command.py
import time

import discord
from discord import Embed, ui

from commands.nia_commands.required_score.command import NiaRequiredScoreCommand
from commands.nia_commands.required_score.container_builder import (
    build_required_score_container,
)
from models.nia.final_grade.params import NiaFinalGradeParams
from models.nia.required_score_from_img.params import NiaRequiredScoreFromImgParams
from models.nia.required_score_from_img.result import NiaRequiredScoreFromImgResult
from ocr.core import OCR
from scenarios.nia_scenario import NiaScenario
from utils.logger import get_logger

from .container_builder import build_error_container

COMMAND_NAME = "nia_required_score_from_img"
logger = get_logger()

# --- ラベル <-> 内部キー ---
_LABEL2KEY = {
    "Voパラメータ": "vo_status",
    "Daパラメータ": "da_status",
    "Viパラメータ": "vi_status",
    "Voパラメータボーナス": "vo_bonus",
    "Daパラメータボーナス": "da_bonus",
    "Viパラメータボーナス": "vi_bonus",
    "ファン数": "now_fans",
    "ほしのきらめき": "kirameki",
}

# --- Modal 定義 ---
class ParamEditModal(ui.Modal):
    def __init__(self, cmd: "NiaRequiredScoreFromImgCommand", selected_params: list[str], current: dict):
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
            int_keys = ("vo_status", "da_status", "vi_status", "now_fans", "kirameki")
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
            await self.cmd._recompute_end_edit(interaction=interaction, merged=merged, mode="fix_params")

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
    def __init__(self, cmd: "NiaRequiredScoreFromImgCommand"):
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

class AuditionSelect(ui.Select):
    """
    比較するオーディションのセレクト
    """
    def __init__(self, cmd: "NiaRequiredScoreFromImgCommand"):
        # 現在のオーディションを取得
        # audition = getattr(cmd, "_static", {}).get("audition")

        # プルダウンメニューの構築
        options = [
            discord.SelectOption(label="FINALE", value="finale"),
            discord.SelectOption(label="QUARTET", value="quartet"),
            discord.SelectOption(label="IDOLBigup!", value="idol_bigup!"),
        ]

        super().__init__(
            placeholder="他のオーディションと比較する",
            options=options
        )
        self.cmd = cmd

    async def callback(self, interaction: discord.Interaction):
        """
        選択したオーディションで再計算をする
        """
        await interaction.response.defer()
        
        # 選択したオーディションで再計算して新規メッセージを送信
        current = getattr(self.cmd, "_current_values", {}) or {}
        if self.values:
            selected_audition = self.values[0]
            current = {**current, "audition": selected_audition}

        self.cmd._current_values = current
        await self.cmd._recompute_end_edit(interaction=interaction, merged=current, mode="reselection_audition")

        # プルダウンを無効化
        self.disabled = True
        await interaction.message.edit(view=self.view)

class NiaRequiredScoreFromImgCommand(NiaRequiredScoreCommand):
    """
    NIAシナリオの逆計算コマンド
    """
    async def execute(self, params: NiaRequiredScoreFromImgParams):
        self.log_command_start(COMMAND_NAME)
        t0 = time.perf_counter()

        # 再計算で使う固定情報を保存
        self._static = {
            "character": params.character,
            "mode": params.mode,
            "target_grade": params.target_grade,
            "target_score": params.target_score,
            "challenge_P_item": params.challenge_P_item,
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
        
        if params.party_img.content_type and not params.party_img.content_type.startswith("image/"):
            logger.warning("input img error")
            return await interaction.edit_original_response(
                content="画像ファイルを添付してください"
            )
        
        # 読み取り試行
        try:
            # 画像の読み込み
            t1 = time.perf_counter()
            schedule_img_bytes = await params.schedule_img.read()
            party_img_bytes = await params.party_img.read()
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
            t3 = time.perf_counter()
            party_ocr = OCR(party_img_bytes)
            bonus_dict = party_ocr.read_bonus(params.is_boost_active)
            dt = (time.perf_counter() - t3) * 1000
            logger.debug(
                "read bonus vo: %s da: %s vi: %s time %.1f ms",
                bonus_dict.get("vo"), 
                bonus_dict.get("da"), 
                bonus_dict.get("vi"),
                dt
            )

            if None in parameters_dict.values() or None in bonus_dict.values():
                # 現在値を保持（モーダル初期値用）
                self._current_values = {
                    "audition" :  params.audition,
                    "vo_status":  parameters_dict.get("vo")   or 0,
                    "da_status":  parameters_dict.get("da")   or 0,
                    "vi_status":  parameters_dict.get("vi")   or 0,
                    "vo_bonus":   bonus_dict.get("vo")        or 0,
                    "da_bonus":   bonus_dict.get("da")        or 0,
                    "vi_bonus":   bonus_dict.get("vi")        or 0,
                    "now_fans":   parameters_dict.get("fans") or 0,
                    "boost_month": bool(params.is_boost_active),
                    "kirameki":   (bonus_dict.get("kirameki") or 0) if params.is_boost_active else 0,
                }

                # View / Container構築 -> メッセージ送信
                logger.info("ERROR View/Container構築開始")
                err_layout = ui.LayoutView()
                err_container = build_error_container(
                    params=parameters_dict,
                    bonus=bonus_dict,
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
                        "party":    (params.party_img.filename or "party.png",     party_img_bytes),
                    },
                    meta={
                        "error": "param_or_bonus_read_failed",
                        "ocr_params": parameters_dict,
                        "ocr_bonus": bonus_dict,
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
        
        # インスタンス生成
        t4 = time.perf_counter()
        scenario = NiaScenario(mode=params.mode)

        if params.is_boost_active:
            kirameki = bonus_dict['kirameki']
            logger.debug("kiramek: %s", kirameki)
        else:
            kirameki = 0

        calc_params = NiaFinalGradeParams(
            character     = params.character,
            mode          = params.mode,
            audition      = params.audition,
            vo_status     = parameters_dict['vo'],
            da_status     = parameters_dict['da'],
            vi_status     = parameters_dict['vi'],
            vo_bonus      = bonus_dict['vo'],
            da_bonus      = bonus_dict['da'],
            vi_bonus      = bonus_dict['vi'],
            vo_score      = 0,
            da_score      = 0,
            vi_score      = 0,
            now_fans      = parameters_dict['fans'],
            challenge_P_item = params.challenge_P_item,
            is_boost_active  = params.is_boost_active,
            kirameki         = kirameki
        )
        logger.info("calc params %s", calc_params)

        # 逆算ロジックは共有コアを呼ぶだけ
        t_core = time.perf_counter()
        logger.info(
            "[required_score_from_img] compute start char=%s mode=%s audition=%s target_grade=%s target_score=%s",
            params.character, params.mode, params.audition, params.target_grade, params.target_score
        )
        result_dict = self._compute_required_result_dict(
            scenario=scenario,
            calc_params=calc_params,
            character=params.character,
            mode=params.mode,
            audition=params.audition,
            target_grade=params.target_grade,
            target_score=params.target_score,
        )
        logger.debug(
            "[required_score_from_img] compute finished in %.1f ms",
            (time.perf_counter() - t_core) * 1000
        )

        # 表示ペアも共通で生成
        t_pairs = time.perf_counter()
        pairs, target_grade_norm, target_score_norm = self._build_pairs(
            result_dict=result_dict,
            target_grade=params.target_grade,
            target_score=params.target_score,
        )
        logger.debug(
            "[required_score] build_pairs finished in %.1f ms mode=%s",
            (time.perf_counter() - t_pairs) * 1000,
            ("target_score" if target_score_norm is not None else
             "target_grade" if target_grade_norm is not None else "all_grades")
        )

        result = NiaRequiredScoreFromImgResult(
            character              = params.character,
            mode                   = params.mode,
            audition               = params.audition,
            vo_status              = parameters_dict['vo'],
            da_status              = parameters_dict['da'],
            vi_status              = parameters_dict['vi'],
            vo_bonus               = bonus_dict['vo'],
            da_bonus               = bonus_dict['da'],
            vi_bonus               = bonus_dict['vi'],
            now_fans               = parameters_dict['fans'],
            challenge_P_item       = params.challenge_P_item,
            is_boost_active        = params.is_boost_active,
            kirameki               = kirameki,
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

        # Embed構築
        # logger.info("Embed構築開始")
        # self.embed = build_required_score_embed(result, override_pairs=pairs)
        # logger.info("Embed構築完了: メッセージ送信を開始")
        # await interaction.edit_original_response(content=None, embed=self.embed)


        # 現在値を保持（モーダル初期値用）
        self._current_values = {
            "audition" : params.audition,
            "vo_status":  parameters_dict.get("vo")   or 0,
            "da_status":  parameters_dict.get("da")   or 0,
            "vi_status":  parameters_dict.get("vi")   or 0,
            "vo_bonus":   bonus_dict.get("vo")        or 0,
            "da_bonus":   bonus_dict.get("da")        or 0,
            "vi_bonus":   bonus_dict.get("vi")        or 0,
            "now_fans":   parameters_dict.get("fans") or 0,
            "boost_month": bool(params.is_boost_active),
            "kirameki":   (bonus_dict.get("kirameki") or 0) if params.is_boost_active else 0,
        }

        # View / Container構築
        logger.debug("View/Container構築開始")
        layout = ui.LayoutView()
        container = build_required_score_container(result, override_pairs=pairs)
        container.add_item(ui.Separator())

        row = ui.ActionRow()
        row.add_item(ParamSelect(self))
        container.add_item(row)

        audition_select = ui.ActionRow()
        audition_select.add_item(AuditionSelect(self))
        container.add_item(audition_select)

        layout.add_item(container)
        logger.debug("View/Container構築完了: メッセージ送信を開始")
        await interaction.followup.send(view=layout)
        self.message = await interaction.original_response()

        # 送信後：同意時のみ保存（共通化）
        await self.maybe_archive_inputs(
            interaction=interaction,
            save_agree=params.save_agree,
            command="nia_required_score_from_img",
            images={
                "schedule": (params.schedule_img.filename or "schedule.png", schedule_img_bytes),
                "party":    (params.party_img.filename or "party.png",     party_img_bytes),
            },
            meta={
                "mode": params.mode,
                "audition": params.audition,
                "character": params.character,
                "runtime_ms": (time.perf_counter() - t0) * 1000.0,
                "ocr_params": parameters_dict,
                "ocr_bonus":  bonus_dict,
            },
        )
                
        dt = (time.perf_counter() - t4) * 1000
        logger.debug("required score finished in %.2f ms", dt)

        dt = (time.perf_counter() - t0) * 1000
        logger.debug("%s finished in %.2f ms",COMMAND_NAME, dt)
        self.log_command_end(COMMAND_NAME)


    # --- 内部: 再計算 ---
    async def _recompute_end_edit(self, interaction: discord.Interaction, merged: dict, mode: str):
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
            t0 = time.perf_counter()

            scenario = NiaScenario(mode=static["mode"])

            calc_params = NiaFinalGradeParams(
                character      = static["character"],
                mode           = static["mode"],
                audition       = merged["audition"],
                vo_status      = merged["vo_status"],
                da_status      = merged["da_status"],
                vi_status      = merged["vi_status"],
                vo_bonus       = merged["vo_bonus"],
                da_bonus       = merged["da_bonus"],
                vi_bonus       = merged["vi_bonus"],
                vo_score       = 0,
                da_score       = 0,
                vi_score       = 0,
                now_fans       = merged["now_fans"],
                challenge_P_item = static["challenge_P_item"],
                is_boost_active  = static["is_boost_active"],
                kirameki         = kirameki,
            )
            logger.info("calc params %s", calc_params)

            # --- 共通コアへ委譲 ---
            t_core = time.perf_counter()
            result_dict = self._compute_required_result_dict(
                scenario=scenario,
                calc_params=calc_params,
                character=static["character"],
                mode=static["mode"],
                audition=merged["audition"],
                target_grade=static["target_grade"],
                target_score=static["target_score"],
            )
            logger.debug(
                "[required_score] compute_result_dict finished in %.1f ms",
                (time.perf_counter() - t_core) * 1000
            )
            
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

            result = NiaRequiredScoreFromImgResult(
                character              = static["character"],
                mode                   = static["mode"],
                audition               = merged["audition"],
                vo_status              = merged["vo_status"],
                da_status              = merged["da_status"],
                vi_status              = merged["vi_status"],
                vo_bonus               = merged["vo_bonus"],
                da_bonus               = merged["da_bonus"],
                vi_bonus               = merged["vi_bonus"],
                now_fans               = merged["now_fans"],
                challenge_P_item       = static["challenge_P_item"],
                is_boost_active        = static["is_boost_active"],
                kirameki               = kirameki,
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
            logger.debug("View/Container構築開始")
            logger.debug("mode: %s", mode)
            layout = ui.LayoutView()

            if mode == "fix_params":
                container = build_required_score_container(result, override_pairs=pairs)
                container.add_item(ui.Separator())

                row = ui.ActionRow()
                row.add_item(ParamSelect(self))
                container.add_item(row)

                audition_select = ui.ActionRow()
                audition_select.add_item(AuditionSelect(self))
                container.add_item(audition_select)

            elif mode == "reselection_audition":
                pass

            layout.add_item(container)
            logger.debug("View/Container構築完了")

            await interaction.followup.send(view=layout)

            dt = (time.perf_counter() - t0) * 1000
            logger.debug(f"nia_required_score_command finished in {dt:.2f} ms")
            self.log_recompute_end(COMMAND_NAME)