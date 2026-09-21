SETTINGS = {
    # シナリオ共通設定
    "stat_multiplier": 2.3,     # ステータス合計値倍率

    "grade_thresholds": {    # 評価ランク範囲
        "S5": 35000,
        "S4+": 30000,
        "S4": 26000,
        "SSS+": 23000,
        "SSS": 20000,
        "SS+": 18000,
        "SS": 16000,
        "S+": 14500,
        "S": 13000,
        "A+": 11500,
        "A": 10000,
    },

    "boost": {
        "NIA": {
            "pro": {
                "boost_coeff": 0.7,
                "kirameki_coeff": 9.6625,
            },
            "master": {
                "boost_coeff": 0.7,
                "kirameki_coeff": 10.82,
            },
        },

        "Hajime": {
            "legend": {
                "boost_coeff": 0.72,
                "kirameki_coeff": 11.016,
            },
        },  

        "H.I.F": {
            "default": {
                "boost_coeff": 0.72,
                "kirameki_coeff": 0.8888,
            },
        },
    },
}