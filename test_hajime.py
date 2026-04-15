from scenarios import HajimeScenario
from models.hajime.final_grade.params import HajimeFinalGradeParams
import math

# HajimeScenarioのインスタンス作成（モードは "master"）
mode = "legend"
# mode = "master"
hajime = HajimeScenario(mode)

# テスト用入力
vo = 2458
da = 1905
vi = 1066
mid_exam_score = 200000
final_exam_score = 2000000

params = HajimeFinalGradeParams(
    mode      = mode,
    vo_status = vo,
    da_status = da,
    vi_status = vi,
    final_exam_score = final_exam_score,
    final_exam_rank = "first",
    character        = None,
    is_boost_active  = False,
    kirameki  = 0,
    mid_exam_score = mid_exam_score
)

# 計算実行
calc_score = hajime.calculate_score(params)

# 結果出力
print(f"最終評価スコア: {calc_score.final_point}, 評価ランク: {calc_score.final_grade}")
print(f"ステータスの評価値点数: {calc_score.status_eval_points}")
print(f"中間スコアの評価地点換算: {calc_score.mid_exam_eval_points}")
print(f"最終スコアの評価地点換算: {calc_score.final_exam_eval_points}")