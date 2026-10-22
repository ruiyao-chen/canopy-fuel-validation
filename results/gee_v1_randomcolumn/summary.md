# Results: gee_v1_randomcolumn

**Real GEDI L2A / Sentinel-2 / SRTM samples.**

Shots after screening: {'coastal_chaparral': 7817, 'sierra_conifer': 7732}. Block size 10 km (variogram), buffer 1 km, 90% intervals, 10 block splits.

## RMSE vs GEDI RH98 (m) by evaluation scheme

| region | model | random | spatial | spatial+buffer | other ecoregion |
|---|---|---|---|---|---|
| coastal_chaparral | linear | 7.40 | 7.49 | 7.51 | 10.11 |
| coastal_chaparral | rf | 7.22 | 7.43 | 7.50 | 10.90 |
| coastal_chaparral | xgb | 7.29 | 7.53 | 7.64 | 11.63 |
| sierra_conifer | linear | 9.57 | 9.64 | 9.65 | 16.72 |
| sierra_conifer | rf | 9.26 | 9.44 | 9.47 | 12.50 |
| sierra_conifer | xgb | 9.36 | 9.57 | 9.60 | 12.96 |

## xgb: spatial-block CV

| region | reference | n | rmse | bias | mae | r2 |
|---|---|---|---|---|---|---|
| coastal_chaparral | GEDI RH98 | 7817 | 7.526 | 0.171 | 4.992 | 0.314 |
| sierra_conifer | GEDI RH98 | 7732 | 9.565 | 0.005 | 7.427 | 0.399 |

## xgb: cross-region transfer

| train_region | test_region | model | n | rmse | bias | mae | r2 |
|---|---|---|---|---|---|---|---|
| coastal_chaparral | sierra_conifer | xgb | 7732 | 12.965 | -7.584 | 10.060 | -0.104 |
| sierra_conifer | coastal_chaparral | xgb | 7817 | 11.632 | 7.692 | 9.649 | -0.638 |

## xgb: feature ablation (in-region spatial CV vs transfer)

| features | train_region | test_region | rmse_within | rmse_transfer | bias_transfer | bias_transfer_tall |
|---|---|---|---|---|---|---|
| all features | sierra_conifer | coastal_chaparral | 7.53 | 11.63 | 7.69 | 0.96 |
| all features | coastal_chaparral | sierra_conifer | 9.57 | 12.96 | -7.58 | -10.63 |
| without elevation | sierra_conifer | coastal_chaparral | 7.58 | 9.07 | 3.05 | -4.11 |
| without elevation | coastal_chaparral | sierra_conifer | 9.60 | 11.47 | -3.14 | -5.75 |
| spectral only | sierra_conifer | coastal_chaparral | 7.78 | 9.27 | 3.50 | -3.88 |
| spectral only | coastal_chaparral | sierra_conifer | 9.78 | 11.59 | -3.22 | -5.93 |

## xgb: by height class (binned on GEDI RH98)

| region | height_class | n | rmse | bias | mae | r2 | scheme |
|---|---|---|---|---|---|---|---|
| coastal_chaparral | 2-5 m shrub | 1814 | 4.82 | 3.56 | 3.70 | -32.80 | spatial |
| coastal_chaparral | 5-15 m woodland | 3828 | 5.00 | 2.45 | 3.90 | -2.08 | spatial |
| coastal_chaparral | 15-30 m forest | 1882 | 7.29 | -4.39 | 5.88 | -2.52 | spatial |
| coastal_chaparral | >=30 m tall forest | 293 | 26.46 | -21.24 | 21.57 | -3.85 | spatial |
| sierra_conifer | 2-5 m shrub | 323 | 11.13 | 9.11 | 9.17 | -210.04 | spatial |
| sierra_conifer | 5-15 m woodland | 1426 | 9.68 | 7.67 | 8.00 | -10.21 | spatial |
| sierra_conifer | 15-30 m forest | 3224 | 7.21 | 2.13 | 5.73 | -1.90 | spatial |
| sierra_conifer | >=30 m tall forest | 2759 | 11.52 | -7.50 | 8.92 | -1.73 | spatial |
| coastal_chaparral | 2-5 m shrub | 1814 | 11.91 | 10.73 | 10.73 | -205.81 | transfer |
| coastal_chaparral | 5-15 m woodland | 3828 | 12.05 | 10.07 | 10.26 | -16.91 | transfer |
| coastal_chaparral | 15-30 m forest | 1882 | 7.94 | 3.45 | 6.50 | -3.18 | transfer |
| coastal_chaparral | >=30 m tall forest | 293 | 20.71 | -14.98 | 15.23 | -1.97 | transfer |
| sierra_conifer | 2-5 m shrub | 323 | 7.04 | 5.79 | 5.87 | -83.48 | transfer |
| sierra_conifer | 5-15 m woodland | 1426 | 5.41 | 2.16 | 4.01 | -2.50 | transfer |
| sierra_conifer | 15-30 m forest | 3224 | 9.00 | -5.65 | 7.54 | -3.52 | transfer |
| sierra_conifer | >=30 m tall forest | 2759 | 18.85 | -16.45 | 16.62 | -6.31 | transfer |

## xgb: by vegetation type

| region | evt_group | n | rmse | bias | mae | r2 | scheme | reference |
|---|---|---|---|---|---|---|---|---|
| coastal_chaparral | Forest | 610 | 9.19 | -1.17 | 6.60 | 0.38 | spatial | GEDI RH98 |
| coastal_chaparral | Herbaceous | 1734 | 7.43 | 0.06 | 4.25 | 0.10 | spatial | GEDI RH98 |
| coastal_chaparral | Other | 713 | 6.48 | 0.77 | 3.81 | 0.17 | spatial | GEDI RH98 |
| coastal_chaparral | Riparian | 231 | 7.64 | -0.65 | 5.62 | 0.32 | spatial | GEDI RH98 |
| coastal_chaparral | Shrubland | 1725 | 6.90 | 0.39 | 4.66 | 0.10 | spatial | GEDI RH98 |
| coastal_chaparral | Woodland | 2804 | 7.79 | 0.31 | 5.56 | 0.17 | spatial | GEDI RH98 |
| sierra_conifer | Forest | 5980 | 9.53 | -0.13 | 7.46 | 0.38 | spatial | GEDI RH98 |
| sierra_conifer | Herbaceous | 75 | 9.34 | 1.75 | 7.35 | -0.25 | spatial | GEDI RH98 |
| sierra_conifer | Other | 190 | 9.32 | -0.42 | 7.32 | 0.59 | spatial | GEDI RH98 |
| sierra_conifer | Riparian | 287 | 11.42 | -1.09 | 8.68 | 0.26 | spatial | GEDI RH98 |
| sierra_conifer | Shrubland | 48 | 7.81 | 1.96 | 6.06 | 0.19 | spatial | GEDI RH98 |
| sierra_conifer | Woodland | 1152 | 9.34 | 0.88 | 7.02 | 0.25 | spatial | GEDI RH98 |
| coastal_chaparral | Forest | 610 | 12.24 | 5.77 | 10.19 | -0.10 | transfer | GEDI RH98 |
| coastal_chaparral | Herbaceous | 1734 | 10.69 | 7.00 | 8.84 | -0.86 | transfer | GEDI RH98 |
| coastal_chaparral | Other | 713 | 10.36 | 6.91 | 8.26 | -1.13 | transfer | GEDI RH98 |
| coastal_chaparral | Riparian | 231 | 11.74 | 7.68 | 9.94 | -0.61 | transfer | GEDI RH98 |
| coastal_chaparral | Shrubland | 1725 | 11.28 | 7.87 | 9.46 | -1.40 | transfer | GEDI RH98 |
| coastal_chaparral | Woodland | 2804 | 12.53 | 8.63 | 10.47 | -1.15 | transfer | GEDI RH98 |
| sierra_conifer | Forest | 5980 | 13.21 | -8.08 | 10.41 | -0.19 | transfer | GEDI RH98 |
| sierra_conifer | Herbaceous | 75 | 9.93 | -2.09 | 7.32 | -0.41 | transfer | GEDI RH98 |
| sierra_conifer | Other | 190 | 13.56 | -7.70 | 10.38 | 0.13 | transfer | GEDI RH98 |
| sierra_conifer | Riparian | 287 | 16.29 | -10.87 | 12.81 | -0.51 | transfer | GEDI RH98 |
| sierra_conifer | Shrubland | 48 | 7.95 | -0.18 | 5.92 | 0.16 | transfer | GEDI RH98 |
| sierra_conifer | Woodland | 1152 | 10.81 | -4.83 | 7.83 | -0.01 | transfer | GEDI RH98 |

## Interval coverage, pooled model, by overall

| calibration | method | n | coverage | coverage_sd | mean_width |
|---|---|---|---|---|---|
| source | raw | 3471.000 | 0.840 | 0.016 | 22.146 |
| source | cqr | 3471.000 | 0.902 | 0.014 | 24.707 |
| source | mondrian | 3471.000 | 0.903 | 0.014 | 25.428 |
| source | mondrian_region | 3471.000 | 0.904 | 0.013 | 25.146 |

## Interval coverage, pooled model, by region

| calibration | method | region | n | coverage | coverage_sd | mean_width |
|---|---|---|---|---|---|---|
| source | raw | coastal_chaparral | 1730.600 | 0.860 | 0.021 | 18.806 |
| source | raw | sierra_conifer | 1740.400 | 0.821 | 0.019 | 25.447 |
| source | cqr | coastal_chaparral | 1730.600 | 0.932 | 0.014 | 21.368 |
| source | cqr | sierra_conifer | 1740.400 | 0.872 | 0.018 | 28.009 |
| source | mondrian | coastal_chaparral | 1730.600 | 0.908 | 0.020 | 20.569 |
| source | mondrian | sierra_conifer | 1740.400 | 0.897 | 0.017 | 30.219 |
| source | mondrian_region | coastal_chaparral | 1730.600 | 0.904 | 0.019 | 20.075 |
| source | mondrian_region | sierra_conifer | 1740.400 | 0.903 | 0.018 | 30.129 |

## Interval coverage, pooled model, by pred_height_class

| calibration | method | pred_height_class | n | coverage | coverage_sd | mean_width |
|---|---|---|---|---|---|---|
| source | raw | <2 m grass/low shrub | 2.250 | 0.833 | 0.192 | 11.086 |
| source | raw | 2-5 m shrub | 218.400 | 0.911 | 0.025 | 11.748 |
| source | raw | 5-15 m woodland | 1416.400 | 0.848 | 0.022 | 19.241 |
| source | raw | 15-30 m forest | 1346.500 | 0.826 | 0.020 | 25.767 |
| source | raw | >=30 m tall forest | 488.800 | 0.828 | 0.032 | 25.378 |
| source | cqr | <2 m grass/low shrub | 2.250 | 0.833 | 0.192 | 13.622 |
| source | cqr | 2-5 m shrub | 218.400 | 0.962 | 0.013 | 14.310 |
| source | cqr | 5-15 m woodland | 1416.400 | 0.933 | 0.017 | 21.803 |
| source | cqr | 15-30 m forest | 1346.500 | 0.874 | 0.018 | 28.328 |
| source | cqr | >=30 m tall forest | 488.800 | 0.863 | 0.027 | 27.939 |
| source | mondrian | <2 m grass/low shrub | 2.250 | 0.833 | 0.192 | 13.622 |
| source | mondrian | 2-5 m shrub | 218.400 | 0.907 | 0.034 | 11.849 |
| source | mondrian | 5-15 m woodland | 1416.400 | 0.897 | 0.025 | 20.410 |
| source | mondrian | 15-30 m forest | 1346.500 | 0.907 | 0.021 | 30.516 |
| source | mondrian | >=30 m tall forest | 488.800 | 0.907 | 0.030 | 32.123 |
| source | mondrian_region | <2 m grass/low shrub | 2.250 | 0.833 | 0.192 | 12.378 |
| source | mondrian_region | 2-5 m shrub | 218.400 | 0.955 | 0.017 | 13.206 |
| source | mondrian_region | 5-15 m woodland | 1416.400 | 0.914 | 0.023 | 21.142 |
| source | mondrian_region | 15-30 m forest | 1346.500 | 0.892 | 0.021 | 29.613 |
| source | mondrian_region | >=30 m tall forest | 488.800 | 0.886 | 0.026 | 30.030 |

## Interval coverage, pooled model, by height_class

| calibration | method | height_class | n | coverage | coverage_sd | mean_width |
|---|---|---|---|---|---|---|
| source | raw | 2-5 m shrub | 439.500 | 0.662 | 0.062 | 15.498 |
| source | raw | 5-15 m woodland | 1169.300 | 0.881 | 0.022 | 20.629 |
| source | raw | 15-30 m forest | 1194.100 | 0.925 | 0.013 | 24.195 |
| source | raw | >=30 m tall forest | 668.100 | 0.732 | 0.032 | 25.540 |
| source | cqr | 2-5 m shrub | 439.500 | 0.884 | 0.037 | 18.060 |
| source | cqr | 5-15 m woodland | 1169.300 | 0.933 | 0.015 | 23.191 |
| source | cqr | 15-30 m forest | 1194.100 | 0.949 | 0.009 | 26.757 |
| source | cqr | >=30 m tall forest | 668.100 | 0.772 | 0.029 | 28.102 |
| source | mondrian | 2-5 m shrub | 439.500 | 0.795 | 0.063 | 16.479 |
| source | mondrian | 5-15 m woodland | 1169.300 | 0.943 | 0.016 | 22.746 |
| source | mondrian | 15-30 m forest | 1194.100 | 0.953 | 0.007 | 28.158 |
| source | mondrian | >=30 m tall forest | 668.100 | 0.812 | 0.031 | 31.106 |
| source | mondrian_region | 2-5 m shrub | 439.500 | 0.850 | 0.045 | 17.360 |
| source | mondrian_region | 5-15 m woodland | 1169.300 | 0.935 | 0.017 | 22.870 |
| source | mondrian_region | 15-30 m forest | 1194.100 | 0.952 | 0.006 | 27.579 |
| source | mondrian_region | >=30 m tall forest | 668.100 | 0.799 | 0.032 | 29.919 |

## Interval coverage under transfer

| train_region | test_region | calibration | method | n | coverage | coverage_sd | mean_width |
|---|---|---|---|---|---|---|---|
| coastal_chaparral | sierra_conifer | source | raw | 6491.000 | 0.479 | 0.035 | 16.227 |
| coastal_chaparral | sierra_conifer | source | cqr | 6491.000 | 0.548 | 0.046 | 18.743 |
| coastal_chaparral | sierra_conifer | source | mondrian | 6491.000 | 0.581 | 0.042 | 20.608 |
| coastal_chaparral | sierra_conifer | local | raw | 6491.000 | 0.479 | 0.035 | 16.227 |
| coastal_chaparral | sierra_conifer | local | cqr | 6491.000 | 0.871 | 0.045 | 42.336 |
| coastal_chaparral | sierra_conifer | local | mondrian | 6491.000 | 0.870 | 0.042 | 42.095 |
| sierra_conifer | coastal_chaparral | source | raw | 6490.700 | 0.541 | 0.043 | 22.566 |
| sierra_conifer | coastal_chaparral | source | cqr | 6490.700 | 0.788 | 0.106 | 28.352 |
| sierra_conifer | coastal_chaparral | source | mondrian | 6490.700 | 0.750 | 0.112 | 27.940 |
| sierra_conifer | coastal_chaparral | local | raw | 6490.700 | 0.541 | 0.043 | 22.566 |
| sierra_conifer | coastal_chaparral | local | cqr | 6490.700 | 0.895 | 0.037 | 31.297 |
| sierra_conifer | coastal_chaparral | local | mondrian | 6490.700 | 0.886 | 0.028 | 31.090 |
