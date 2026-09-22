HIF = {
    "default":{
        "st_max": 3200,
        "status_point_rate": 2.0,
        "star_point_rate": 7.5,
        "base_offset": -2000,

        "score_attenuation": {
            "round1": {
                "thresholds": [0, 300000, 700000, 1000000, 1200000, 1400000,],
                "coefficients": [0, 10, 3, 2, 1,],
                "den": 1000,
            },

            "round2": {
                "thresholds": [0, 600000, 900000, 1500000, 2000000, 2400000,],
                "coefficients": [0, 4, 8, 2, 1,],
                "den": 1000,
            },
        },

        "star_gain": {
            "round1": {
                "thresholds": [0, 240000, 360000, 600000],
                "coefficients": [1000, 1200, 400],
                "den": 4_000_000,
                "multiplier": 1.5,
            },

            "round2": {
                "thresholds": [0, 400000, 600000, 1000000],
                "coefficients": [750, 900, 300],
                "den": 4_000_000,
                "multiplier": 1.5,
            },
        },
    }
}