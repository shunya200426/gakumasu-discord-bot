from models.hif.final_grade.params import HifFinalGradeParams
from scenarios.hif_scenario import HifScenario


def test_calculate_score_normal():
    scenario = HifScenario(mode="default")

    params = HifFinalGradeParams(
        mode="default",

        vo_status=1500,
        da_status=3100,
        vi_status=2400,

        vo_ability=0,
        da_ability=0,
        vi_ability=0,

        round1_score=1_440_034,
        round2_score=2_460_907,

        star_before_round2=1110,

        is_boost_active=True,
        kirameki=420,
    )

    result = scenario.calculate_score(params)

    assert result.round1_score_corrected == 1_728_040

    assert result.final_vo_status == 1500
    assert result.final_da_status == 3100
    assert result.final_vi_status == 2400

    assert result.status_eval_points == 14000

    assert result.round1_eval_points == 5500
    assert result.round2_eval_points == 7400

    assert result.round2_star_gain == 225
    assert result.final_star == 1335
    assert result.star_eval_points == 10012

    assert result.final_point == 30556
    assert result.final_grade == "S4+"