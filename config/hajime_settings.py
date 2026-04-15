HAJIME = {
    "final_exam_rank_bonus": {
        "first": 1700,
        "second": 900,
        "third": 500,
        "other": 0,
    },


    "regular": {
        "name": "レギュラー",
        "st_max": 1000,
        "status_point_rates": 2.3,
        "exam_post_bonus": {
            "first": 30,
            "second": 20,
            "third": 10,
            "other": 0,
        },
        "score_attenuation": {
            "final_exam": {
                "thresholds": [0, 5000] + [i for i in range(10000, 200001, 10000)],
                "coefficients": [30, 15, 8, 4, 2] + [1 for _ in range(17)],
                "den": 100,
            },
        },
    },


    "pro": {
        "name": "プロ",
        "st_max": 1500,
        "status_point_rates": 2.3,
        "exam_post_bonus": {
            "first": 30,
            "second": 20,
            "third": 10,
            "other": 0,
        },
        "score_attenuation": {
            "final_exam": {
                "thresholds": [0, 5000] + [i for i in range(10000, 200001, 10000)],
                "coefficients": [30, 15, 8, 4, 2] + [1 for _ in range(17)],
                "den": 100,
            },
        },
    },


    "master": {
        "name": "マスター",
        "st_max": 1800,
        "status_point_rates": 2.3,
        "challenge_bonus_default": 45,
        "exam_post_bonus": {
            "first": 30,
            "second": 20,
            "third": 10,
            "other": 0,
        },
        "score_attenuation": {
            "final_exam": {
                "thresholds": [0, 5000] + [i for i in range(10000, 200001, 10000)],
                "coefficients": [30, 15, 8, 4, 2] + [1 for _ in range(17)],
                "den": 100,
            },
        },
    },


    "legend": {
        "name": "レジェンド",
        "st_max": 2800,
        "status_point_rates": 2.1,
        "challenge_bonus_default": 90,
        "exam_post_bonus": {
            "first": 120,
            "second": 60,
            "third": 30,
            "other": 0,
        },
        "score_attenuation": {
            "mid_exam": {
                "thresholds": [0, 10000, 20000, 30000, 40000, 50000, 60000, 200000],
                "coefficients": [110, 80, 50, 8, 3, 2, 1, 1],
                "den": 1000
            },
            "final_exam": {
                "thresholds": [0, 300000, 500000, 600000, 2000000],
                "coefficients": [15, 10, 8, 1, 1],
                "den": 1000,
            },
        },
    },
}