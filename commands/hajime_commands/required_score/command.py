# hajime_commands/required_score/command.py
import discord
from discord import ui
from commands.base_command import BaseCommand
from models.hajime.required_score.params import HajimeRequiredScoreParams
from models.hajime.required_score.result import HajimeRequiredScoreResult
from models.hajime.final_grade.params import HajimeFinalGradeParams
from models.hajime.final_grade.result import HajimeFinalGradeResult
from scenarios import HajimeScenario
from .container_builder import build_required_score_container
from commands.hajime_commands.final_grade.container_builder import build_final_grade_container

from typing import Optional, Dict, Tuple
from utils.logger import get_logger
from config.settings import SETTINGS
from config.hajime_settings import HAJIME

COMMAND_NAME = "hajime_required_score"
logger = get_logger()

# --- Modal 定義 ---
class AddExamScoreModal(ui.Modal):
    def __init__(self, cmd: "HajimeRequiredScoreCommand"):
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

# --- Button 定義 ---
class AddExamScoreButton(ui.Button):
    def __init__(self, cmd: "HajimeRequiredScoreCommand"):
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

class HajimeRequiredScoreCommand(BaseCommand):
    """
    初シナリオの目標グレード/スコアに必要な
    最終試験スコアを計算するコマンド
    """

    async def execute(self, params: HajimeRequiredScoreParams):
        self.log_command_start(COMMAND_NAME)
        logger.info("calc params %s", params)
        
        # 再計算に使う固定情報を保存
        self._static = {
            "mode": params.mode,
            "vo_status": params.vo_status,
            "da_status": params.da_status,
            "vi_status": params.vi_status,
            "vo_ability": params.vo_ability,
            "da_ability": params.da_ability,
            "vi_ability": params.vi_ability,
            "mid_exam_score": params.mid_exam_score,
            "character": params.character,
            "is_boost_active": params.is_boost_active,
            "kirameki": params.kirameki,
            "exam_score": 0,
        }

        # インスタンス生成
        scenario = HajimeScenario(mode=params.mode)
        
        # 要求スコアの計算
        result_dict = self._compute_required_result_dict(
            scenario= scenario,
            params= params
        )
        logger.debug("[required_score] compute_result_dict finished")
        
        pairs, target_grade_norm, target_score_norm = self._build_pairs(
            result_dict=result_dict,
            target_grade=params.target_grade,
            target_score=params.target_score,
        )
        logger.debug(
            "[required_score] build_pairs finished mode=%s",
            ("target_score" if target_score_norm is not None else
             "target_grade" if target_grade_norm is not None else "all_grades")
        )
        
        result = HajimeRequiredScoreResult(
            **params.__dict__,
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
        row = ui.ActionRow()
        row.add_item(AddExamScoreButton(self))
        container.add_item(row)
        view.add_item(container)
        logger.info("View/Container構築完了：メッセージを送信")
        await self.interaction.response.send_message(view=view)

        self.log_command_end(COMMAND_NAME)

    def _compute_required_result_dict(
        self,
        scenario: HajimeScenario,
        params: HajimeRequiredScoreParams
    ) -> Dict[str, object]:
        
        # 目標の正規化（target_score 優先）
        thresholds = dict(SETTINGS["grade_thresholds"])     # 各グレードのスコアを取得して辞書へ変換
        if params.target_score is not None:
            grade_list = ["TARGET"]
            result_dict = {"TARGET": None}
            thresholds["TARGET"] = int(params.target_score)
        elif params.target_grade is not None:
            grade_list = [params.target_grade]
            result_dict = {params.target_grade: None}
        else:
            grade_list = ["SS", "SS+", "SSS", "SSS+"]
            result_dict = {g: None for g in grade_list}
        logger.debug("build result_dict fin: %s", result_dict)
        
        # ステータスの評価値点数を算出
        exam_post_bonus = HAJIME[params.mode]["exam_post_bonus"]["first"]
        rate = HAJIME[params.mode]["status_point_rates"]
        status_eval_points = scenario.calclate_stats_score(
            params.vo_status + exam_post_bonus + params.vo_ability, 
            params.da_status + exam_post_bonus + params.da_ability, 
            params.vi_status + exam_post_bonus + params.vi_ability,
            rate
        )
        logger.debug("calc status points fin: %s", status_eval_points)
        
        # 中間試験スコアの評価値点数を算出
        if params.mode == "legend":
            mid_exam_score_raw = params.mid_exam_score
            mid_exam_thresholds = HAJIME[params.mode]["score_attenuation"]["mid_exam"]["thresholds"]
            midexam_coefficients = HAJIME[params.mode]["score_attenuation"]["mid_exam"]["coefficients"]
            mid_den = HAJIME[params.mode]["score_attenuation"]["final_exam"]["den"]
            mid_exam_eval_points = scenario._apply_attenuation(mid_exam_score_raw, mid_exam_thresholds, midexam_coefficients, mid_den)
        else:
            mid_exam_eval_points = 0
        logger.debug("calc mid exam eval ponts: %s", mid_exam_eval_points)
        
        # 最終試験順位ボーナス
        final_exam_rank_bonus = HAJIME["final_exam_rank_bonus"]["first"]
        logger.debug("get final exam rank bonus: %s", final_exam_rank_bonus)
        
        # 試験の上限スコアの取得
        max_score = HAJIME[params.mode]["score_attenuation"]["final_exam"]["thresholds"][-1]
        logger.debug("max score: %s", max_score)
        
        # 逆算の実行開始
        for i in range(len(result_dict)):
            target_final_eval_points = thresholds[grade_list[i]]  # 目標スコア
            print(f"target_final_eval_points: {target_final_eval_points}")
            
            # 試験スコアのみを抽出
            exam_eval_points = target_final_eval_points - (status_eval_points + mid_exam_eval_points + final_exam_rank_bonus)
            print(f"exam_eval_points: {exam_eval_points}")
            
            # 逆算
            required_exam_score = scenario.invert_attenuation(required_eval_points=exam_eval_points)
            
            # 試験の上限スコアを超えていた場合、CLEAR不可を返す
            if required_exam_score >= max_score:
                required_exam_score = "**__CLEAR不可__**"
                
            print(f"required_exam_score: {required_exam_score}")
                
            result_dict[grade_list[i]] = required_exam_score
            
        return result_dict
    
    def _build_pairs(
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
            ("- **SS**",   _fmt_required(result_dict.get("SS",   "—"))),
            ("- **SS+**",  _fmt_required(result_dict.get("SS+",  "—"))),
            ("- **SSS**",  _fmt_required(result_dict.get("SSS",  "—"))),
            ("- **SSS+**", _fmt_required(result_dict.get("SSS+", "—"))),
        ]
        logger.debug("[required_score] pairs mode=all_grades count=%d", len(pairs))
        return pairs, None, None
    
    def _total_or_none(self, d):
        return d["total"] if isinstance(d, dict) else (None if d in (None, "CLEAR不可") else d)
    
    
    async def _calc_final_grade(
        self, 
        interaction: discord.Interaction, 
        add_exam_score: int,
    ):
        async with self.scoped_ctx(interaction):
            self.log_recompute_start(COMMAND_NAME)
            
            # params組み直し
            edit_params = HajimeFinalGradeParams(
                mode                = self._static["mode"],
                vo_status           = self._static["vo_status"],
                da_status           = self._static["da_status"],
                vi_status           = self._static["vi_status"],
                vo_ability          =  self._static["vo_ability"],
                da_ability          = self._static["da_ability"],
                vi_ability          = self._static["vi_ability"],
                mid_exam_score      = self._static["mid_exam_score"],
                final_exam_score    = add_exam_score,
                final_exam_rank     = "first",
                character           = self._static["character"],
                is_boost_active     = self._static["is_boost_active"],
                kirameki            = self._static["kirameki"],
            )
            logger.info("calc params %s", edit_params)
            
            scenario = HajimeScenario(mode=edit_params.mode)
            result: HajimeFinalGradeResult = scenario.calculate_score(edit_params)
            
            # View/Container 構築
            logger.info("View/Container構築開始")
            layout = ui.LayoutView()
            container = build_final_grade_container(result)
            container.add_item(ui.Separator())
            row = ui.ActionRow()
            row.add_item(AddExamScoreButton(self))
            container.add_item(row)
            layout.add_item(container)
            logger.info("View/Container構築完了：メッセージを送信")
            
            await interaction.followup.send(view=layout)
            self.log_recompute_end(COMMAND_NAME)

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
