NIA = {
    "fan_grade": {
        "A": {"votes_num": 20000, "coefficient": 0.085, "constant": 300},
        "A+": {"votes_num": 40000, "coefficient": 0.07, "constant": 900},
        "S": {"votes_num": 60000, "coefficient": 0.065, "constant": 1200},
        "S+": {"votes_num": 80000, "coefficient": 0.06, "constant": 1600},
        "SS": {"votes_num": 100000, "coefficient": {"pro": 0.055, "master": 0.05}, "constant": {"pro": 2100, "master": 2600}},
        "SS+": {"votes_num": 120000, "coefficient": 0.04, "constant": 3800},
        "SSS": {"votes_num": 140000, "coefficient": 0.03, "constant": 5200},
        "SSS+": {"votes_num": 160000, "coefficient": 0.03, "constant": 5200},
    },

    "pro": {
        "name": "プロ",
        "st_max": 2000,
    },
    
    "master": {
        "name": "マスター",
        "st_max": 2600,
        "challenge_bonus_max": 40,

        "finale": {
            "name": "FINALE",
            "pass_score": 100000,

            "fan": {
                "base_score": {"audition_score":0, "correction_constant": 3656.17, "fan_score_coefficient": 0.07592333987},
                "first_damping": {"audition_score": 260417, "correction_constant": 23427.8, "fan_score_coefficient": 0.01821637749},
                "second_damping": {"audition_score": 640882, "correction_constant": 30358.5, "fan_score_coefficient": 0.004126232489},
                "max_score": {"audition_score": 1200582, "fans": 49002},
            },

            "status": {
                "balanced": {
                    "base_score": {
                        "first_trend": {"audition_score":0, "correction_constant": 0.5, "status_score_coefficient": 0.0018},
                        "second_trend": {"audition_score":0, "correction_constant": 0, "status_score_coefficient": 0.00325},
                        "third_trend": {"audition_score":0, "correction_constant": 0, "status_score_coefficient": 0.00465},
                    },
                    "first_damping": {
                        "first_trend": {"audition_score": 66600, "correction_constant": 70, "status_score_coefficient": 0.000765},
                        "second_trend": {"audition_score": 31350, "correction_constant": 61, "status_score_coefficient": 0.001276},
                        "third_trend": {"audition_score": 17600, "correction_constant": 50, "status_score_coefficient": 0.00182},
                    },
                    "max_score": {
                        "first_trend": {"audition_score": 134210, "status": 172},
                        "second_trend": {"audition_score": 63750, "status": 142},
                        "third_trend": {"audition_score": 36500, "status": 116},
                    },
                },

                "focused": {
                    "base_score": {
                        "first_trend": {"audition_score": 0, "correction_constant": 0, "status_score_coefficient": 0.0023},
                        "second_trend": {"audition_score": 0, "correction_constant": 0, "status_score_coefficient": 0.00295},
                        "third_trend": {"audition_score": 0, "correction_constant": 0, "status_score_coefficient": 0.003465},
                    },
                    "first_damping": {
                        "first_trend": {"audition_score": 65350, "correction_constant": 90.5, "status_score_coefficient": 0.000915},
                        "second_trend": {"audition_score": 30900, "correction_constant": 55, "status_score_coefficient": 0.00117},
                        "third_trend": {"audition_score": 17800, "correction_constant": 37, "status_score_coefficient": 0.00136},
                    },
                    "max_score": {
                        "first_trend": {"audition_score": 136070, "status": 215},
                        "second_trend": {"audition_score": 63250, "status": 129},
                        "third_trend": {"audition_score": 36100, "status": 86},
                    },
                },
            },
        },

        "quartet": {
            "name": "QUARTET",
            "pass_score": 50000,

            "fan": {
                "base_score": {"audition_score":0, "correction_constant": 3145.5, "fan_score_coefficient": 0.1289162297},
                "first_damping": {"audition_score": 119982, "correction_constant": 18613, "fan_score_coefficient": 0.08399651702},
                "second_damping": {"audition_score": 180000, "correction_constant": 23654, "fan_score_coefficient": 0.02800776858},
                "max_score": {"audition_score": 239970, "fans": 38001},
            },

            "status": {
                "balanced": {
                    "base_score": {
                        "first_trend": {"audition_score": 0, "correction_constant": 0.5, "status_score_coefficient": 0.002965},
                        "second_trend": {"audition_score": 0, "correction_constant": 2, "status_score_coefficient": 0.00512},
                        "third_trend": {"audition_score": 0, "correction_constant": 1, "status_score_coefficient": 0.00741},
                    },
                    "first_damping": {
                        "first_trend": {"audition_score": 34210, "correction_constant": 61.08, "status_score_coefficient": 0.001194},
                        "second_trend": {"audition_score": 16050, "correction_constant": 50, "status_score_coefficient": 0.00213},
                        "third_trend": {"audition_score": 9120, "correction_constant": 40.5, "status_score_coefficient": 0.00308},
                    },
                    "max_score": {
                        "first_trend": {"audition_score": 70300, "status": 145},
                        "second_trend": {"audition_score": 32870, "status": 120},
                        "third_trend": {"audition_score": 18670, "status": 98},
                    },
                },

                "focused": {
                    "base_score": {
                        "first_trend": {"audition_score": 0, "correction_constant": 0.5, "status_score_coefficient": 0.00373},
                        "second_trend": {"audition_score": 0, "correction_constant": 1, "status_score_coefficient": 0.00475},
                        "third_trend": {"audition_score": 0, "correction_constant": 0, "status_score_coefficient": 0.0056},
                    },
                    "first_damping": {
                        "first_trend": {"audition_score": 34133, "correction_constant": 77.3, "status_score_coefficient": 0.00148},
                        "second_trend": {"audition_score": 15970, "correction_constant": 46.5, "status_score_coefficient": 0.0019},
                        "third_trend": {"audition_score": 9000, "correction_constant": 30, "status_score_coefficient": 0.0023},
                    },
                    "max_score": {
                        "first_trend": {"audition_score": 70750, "status": 182},
                        "second_trend": {"audition_score": 32900, "status": 109},
                        "third_trend": {"audition_score": 19570, "status": 73},
                    },
                },
            },
        },

        "idol_bigup!": {
            "name": "IDOLBigup!",
            "pass_score": 30000,

            "fan": {
                "base_score": {"audition_score":0, "correction_constant": 4132.5, "fan_score_coefficient": 0.1274839693},
                "first_damping": {"audition_score": 66750, "correction_constant": 12642, "fan_score_coefficient": 0.2076203514},
                "second_damping": {"audition_score": 78867, "correction_constant": 15157.9, "fan_score_coefficient": 0.07020547945},
                "max_score": {"audition_score": 90862, "fans": 24000},
            },

            "status": {
                "balanced": {
                    "base_score": {
                        "first_trend": {"audition_score": 0, "correction_constant": 0, "status_score_coefficient": 0.003143},
                        "second_trend": {"audition_score": 0, "correction_constant": 0, "status_score_coefficient": 0.0055},
                        "third_trend": {"audition_score": 0, "correction_constant": 0, "status_score_coefficient": 0.008},
                    },
                    "first_damping": {
                        "first_trend": {"audition_score": 21510, "correction_constant": 39, "status_score_coefficient": 0.00133},
                        "second_trend": {"audition_score": 10250, "correction_constant": 33, "status_score_coefficient": 0.00228},
                        "third_trend": {"audition_score": 5700, "correction_constant": 28.5, "status_score_coefficient": 0.00305},
                    },
                    "max_score": {
                        "first_trend": {"audition_score": 43620, "status": 97},
                        "second_trend": {"audition_score": 20620, "status": 80},
                        "third_trend": {"audition_score": 12170, "status": 65},
                    },
                },

                "focused": {
                    "base_score": {
                        "first_trend": {"audition_score": 0, "correction_constant": 1.5, "status_score_coefficient": 0.00384},
                        "second_trend": {"audition_score": 0, "correction_constant": 0, "status_score_coefficient": 0.005},
                        "third_trend": {"audition_score": 0, "correction_constant": 0, "status_score_coefficient": 0.0062},
                    },
                    "first_damping": {
                        "first_trend": {"audition_score": 22150, "correction_constant": 52, "status_score_coefficient": 0.00152},
                        "second_trend": {"audition_score": 10170, "correction_constant": 29, "status_score_coefficient": 0.00215},
                        "third_trend": {"audition_score": 5280, "correction_constant": 20, "status_score_coefficient": 0.00241},
                    },
                    "max_score": {
                        "first_trend": {"audition_score": 45400, "status": 121},
                        "second_trend": {"audition_score": 20470, "status": 73},
                        "third_trend": {"audition_score": 11620, "status": 48},
                    },
                },
            },
        },

        "boost": {
            "base_score": {"audition_score": 0, "correction_constant": -4, "fan_score_coefficient": 1411},
            "first_damping": {"audition_score": 131200, "correction_constant": 89, "fan_score_coefficient": 5051},
            "max_score": {"audition_score": 339000, "kirameki": 130},
        },
    },
}