# Results: synthetic

**Synthetic data with known truth. These numbers test the method; they say nothing about real-world accuracy.**

Shots after screening: {'coastal_chaparral': 7596, 'sierra_conifer': 6482}. Block size 3 km (variogram), buffer 1 km, 90% intervals, 10 block splits.

## RMSE vs GEDI RH98 (m) by evaluation scheme

| region | model | random | spatial | spatial+buffer | new area (synthetic) | other ecoregion |
|---|---|---|---|---|---|---|
| coastal_chaparral | linear | 4.46 | 4.54 | 4.63 | 5.36 | 6.13 |
| coastal_chaparral | rf | 3.15 | 3.32 | 3.59 | 4.19 | 6.04 |
| coastal_chaparral | xgb | 3.20 | 3.42 | 3.67 | 4.24 | 6.13 |
| sierra_conifer | linear | 7.07 | 7.38 | 7.48 | 7.26 | 7.89 |
| sierra_conifer | rf | 5.05 | 5.65 | 5.99 | 5.81 | 10.52 |
| sierra_conifer | xgb | 5.14 | 5.80 | 6.14 | 5.95 | 10.02 |

## xgb: spatial-block CV

| region | reference | n | rmse | bias | mae | r2 |
|---|---|---|---|---|---|---|
| coastal_chaparral | GEDI RH98 | 7596 | 3.419 | 0.061 | 2.194 | 0.807 |
| coastal_chaparral | true height | 7596 | 3.641 | 1.938 | 2.917 | 0.791 |
| sierra_conifer | GEDI RH98 | 6482 | 5.796 | -0.215 | 3.827 | 0.820 |
| sierra_conifer | true height | 6482 | 5.636 | 1.264 | 4.144 | 0.837 |

## xgb: cross-region transfer

| train_region | test_region | model | n | rmse | bias | mae | r2 |
|---|---|---|---|---|---|---|---|
| coastal_chaparral | sierra_conifer | xgb | 6482 | 10.024 | 2.325 | 6.861 | 0.463 |
| sierra_conifer | coastal_chaparral | xgb | 7596 | 6.127 | -1.603 | 3.315 | 0.381 |

## xgb: feature ablation (in-region spatial CV vs transfer)

| features | train_region | test_region | rmse_within | rmse_transfer | bias_transfer | bias_transfer_tall |
|---|---|---|---|---|---|---|
| all features | sierra_conifer | coastal_chaparral | 3.42 | 6.13 | -1.60 | -17.45 |
| all features | coastal_chaparral | sierra_conifer | 5.80 | 10.02 | 2.33 | 2.92 |
| without elevation | sierra_conifer | coastal_chaparral | 3.52 | 4.43 | -0.69 | -4.28 |
| without elevation | coastal_chaparral | sierra_conifer | 7.10 | 8.38 | -0.40 | -2.33 |
| spectral only | sierra_conifer | coastal_chaparral | 3.52 | 4.31 | -0.91 | -3.77 |
| spectral only | coastal_chaparral | sierra_conifer | 7.45 | 8.47 | -0.31 | -2.23 |

## Reference error: GEDI RH98 vs true height

| region | n | rmse | bias | mae | r2 |
|---|---|---|---|---|---|
| coastal_chaparral | 7596 | 2.837 | 1.877 | 2.095 | 0.873 |
| sierra_conifer | 6482 | 2.637 | 1.480 | 1.994 | 0.964 |

## xgb: by height class (binned on GEDI RH98)

| region | height_class | n | rmse | bias | mae | r2 | scheme |
|---|---|---|---|---|---|---|---|
| coastal_chaparral | <2 m grass/low shrub | 589 | 2.73 | 2.30 | 2.30 | -30.53 | spatial |
| coastal_chaparral | 2-5 m shrub | 3455 | 1.86 | 0.92 | 1.35 | -4.18 | spatial |
| coastal_chaparral | 5-15 m woodland | 2932 | 2.80 | -0.89 | 2.11 | -0.20 | spatial |
| coastal_chaparral | 15-30 m forest | 332 | 8.82 | 0.31 | 7.34 | -2.67 | spatial |
| coastal_chaparral | >=30 m tall forest | 288 | 9.07 | -5.45 | 6.97 | -1.08 | spatial |
| sierra_conifer | <2 m grass/low shrub | 430 | 1.97 | 1.69 | 1.69 | -17.66 | spatial |
| sierra_conifer | 2-5 m shrub | 1833 | 1.88 | 0.48 | 1.09 | -4.51 | spatial |
| sierra_conifer | 5-15 m woodland | 1010 | 4.03 | 0.45 | 2.84 | -0.87 | spatial |
| sierra_conifer | 15-30 m forest | 1874 | 6.48 | 2.65 | 5.06 | -1.59 | spatial |
| sierra_conifer | >=30 m tall forest | 1335 | 9.26 | -6.30 | 7.29 | -1.45 | spatial |
| coastal_chaparral | <2 m grass/low shrub | 589 | 2.84 | 2.30 | 2.30 | -33.05 | transfer |
| coastal_chaparral | 2-5 m shrub | 3455 | 2.00 | 0.96 | 1.37 | -4.97 | transfer |
| coastal_chaparral | 5-15 m woodland | 2932 | 3.65 | -2.06 | 2.82 | -1.05 | transfer |
| coastal_chaparral | 15-30 m forest | 332 | 12.59 | -12.00 | 12.01 | -6.49 | transfer |
| coastal_chaparral | >=30 m tall forest | 288 | 24.65 | -23.73 | 23.73 | -14.32 | transfer |
| sierra_conifer | <2 m grass/low shrub | 430 | 3.08 | 2.74 | 2.74 | -44.62 | transfer |
| sierra_conifer | 2-5 m shrub | 1833 | 2.37 | 1.45 | 1.69 | -7.73 | transfer |
| sierra_conifer | 5-15 m woodland | 1010 | 7.09 | 1.83 | 4.19 | -4.76 | transfer |
| sierra_conifer | 15-30 m forest | 1874 | 14.92 | 6.60 | 13.07 | -12.70 | transfer |
| sierra_conifer | >=30 m tall forest | 1335 | 11.26 | -2.23 | 8.59 | -2.62 | transfer |

## xgb: by vegetation type

| region | evt_group | n | rmse | bias | mae | r2 | scheme | reference |
|---|---|---|---|---|---|---|---|---|
| coastal_chaparral | Forest | 517 | 8.35 | -0.71 | 6.54 | -0.13 | spatial | GEDI RH98 |
| coastal_chaparral | Herbaceous | 1758 | 1.96 | 0.03 | 1.23 | 0.01 | spatial | GEDI RH98 |
| coastal_chaparral | Shrubland | 3588 | 2.47 | 0.76 | 1.73 | -0.62 | spatial | GEDI RH98 |
| coastal_chaparral | Woodland | 1733 | 3.73 | -1.13 | 2.83 | -0.43 | spatial | GEDI RH98 |
| sierra_conifer | Forest | 3286 | 7.77 | -0.67 | 6.01 | 0.19 | spatial | GEDI RH98 |
| sierra_conifer | Herbaceous | 1375 | 1.63 | 0.04 | 1.03 | 0.05 | spatial | GEDI RH98 |
| sierra_conifer | Shrubland | 1269 | 2.78 | 0.89 | 1.77 | -1.60 | spatial | GEDI RH98 |
| sierra_conifer | Woodland | 552 | 3.30 | -0.70 | 2.54 | -0.58 | spatial | GEDI RH98 |
| coastal_chaparral | Forest | 517 | 20.16 | -18.50 | 18.50 | -5.61 | transfer | GEDI RH98 |
| coastal_chaparral | Herbaceous | 1758 | 1.97 | 0.09 | 1.20 | 0.00 | transfer | GEDI RH98 |
| coastal_chaparral | Shrubland | 3588 | 2.62 | 0.94 | 1.81 | -0.83 | transfer | GEDI RH98 |
| coastal_chaparral | Woodland | 1733 | 5.02 | -3.55 | 4.04 | -1.59 | transfer | GEDI RH98 |
| sierra_conifer | Forest | 3286 | 13.68 | 3.31 | 11.33 | -1.50 | transfer | GEDI RH98 |
| sierra_conifer | Herbaceous | 1375 | 2.05 | 0.91 | 1.49 | -0.50 | transfer | GEDI RH98 |
| sierra_conifer | Shrubland | 1269 | 3.40 | 1.95 | 2.40 | -2.90 | transfer | GEDI RH98 |
| sierra_conifer | Woodland | 552 | 5.42 | 0.87 | 3.90 | -3.26 | transfer | GEDI RH98 |
| coastal_chaparral | Forest | 517 | 7.90 | 0.20 | 6.25 | -0.14 | spatial | true height |
| coastal_chaparral | Herbaceous | 1758 | 2.91 | 2.76 | 2.76 | -607.87 | spatial | true height |
| coastal_chaparral | Shrubland | 3588 | 3.21 | 2.72 | 2.73 | -21.24 | spatial | true height |
| coastal_chaparral | Woodland | 1733 | 3.09 | -0.01 | 2.47 | -0.53 | spatial | true height |
| sierra_conifer | Forest | 3286 | 7.36 | 0.40 | 5.76 | 0.22 | spatial | true height |
| sierra_conifer | Herbaceous | 1375 | 2.53 | 2.44 | 2.44 | -442.45 | spatial | true height |
| sierra_conifer | Shrubland | 1269 | 3.43 | 2.63 | 2.65 | -29.72 | spatial | true height |
| sierra_conifer | Woodland | 552 | 2.74 | 0.33 | 2.20 | -0.69 | spatial | true height |

## Interval coverage, pooled model, by overall

| calibration | method | n | coverage | coverage_sd | mean_width |
|---|---|---|---|---|---|
| source | raw | 2900.900 | 0.846 | 0.024 | 10.517 |
| source | cqr | 2900.900 | 0.899 | 0.023 | 11.900 |
| source | mondrian | 2900.900 | 0.902 | 0.020 | 13.015 |
| source | mondrian_region | 2900.900 | 0.898 | 0.023 | 12.243 |

## Interval coverage, pooled model, by region

| calibration | method | region | n | coverage | coverage_sd | mean_width |
|---|---|---|---|---|---|---|
| source | raw | coastal_chaparral | 1569.500 | 0.876 | 0.018 | 8.650 |
| source | raw | sierra_conifer | 1331.400 | 0.811 | 0.039 | 12.721 |
| source | cqr | coastal_chaparral | 1569.500 | 0.931 | 0.014 | 10.033 |
| source | cqr | sierra_conifer | 1331.400 | 0.861 | 0.039 | 14.104 |
| source | mondrian | coastal_chaparral | 1569.500 | 0.912 | 0.014 | 9.889 |
| source | mondrian | sierra_conifer | 1331.400 | 0.891 | 0.034 | 16.713 |
| source | mondrian_region | coastal_chaparral | 1569.500 | 0.908 | 0.016 | 9.375 |
| source | mondrian_region | sierra_conifer | 1331.400 | 0.886 | 0.049 | 15.621 |

## Interval coverage, pooled model, by pred_height_class

| calibration | method | pred_height_class | n | coverage | coverage_sd | mean_width |
|---|---|---|---|---|---|---|
| source | raw | <2 m grass/low shrub | 4.250 | 0.982 | 0.051 | 5.297 |
| source | raw | 2-5 m shrub | 1246.100 | 0.910 | 0.010 | 6.547 |
| source | raw | 5-15 m woodland | 893.200 | 0.832 | 0.027 | 9.906 |
| source | raw | 15-30 m forest | 509.600 | 0.757 | 0.038 | 17.085 |
| source | raw | >=30 m tall forest | 248.600 | 0.760 | 0.095 | 19.409 |
| source | cqr | <2 m grass/low shrub | 4.250 | 1.000 | 0.000 | 6.520 |
| source | cqr | 2-5 m shrub | 1246.100 | 0.967 | 0.016 | 7.930 |
| source | cqr | 5-15 m woodland | 893.200 | 0.895 | 0.023 | 11.289 |
| source | cqr | 15-30 m forest | 509.600 | 0.795 | 0.040 | 18.468 |
| source | cqr | >=30 m tall forest | 248.600 | 0.789 | 0.082 | 20.792 |
| source | mondrian | <2 m grass/low shrub | 4.250 | 0.991 | 0.025 | 6.359 |
| source | mondrian | 2-5 m shrub | 1246.100 | 0.902 | 0.015 | 6.427 |
| source | mondrian | 5-15 m woodland | 893.200 | 0.911 | 0.021 | 11.709 |
| source | mondrian | 15-30 m forest | 509.600 | 0.888 | 0.057 | 23.957 |
| source | mondrian | >=30 m tall forest | 248.600 | 0.897 | 0.077 | 27.910 |
| source | mondrian_region | <2 m grass/low shrub | 4.250 | 1.000 | 0.000 | 6.325 |
| source | mondrian_region | 2-5 m shrub | 1246.100 | 0.958 | 0.013 | 8.071 |
| source | mondrian_region | 5-15 m woodland | 893.200 | 0.887 | 0.018 | 11.177 |
| source | mondrian_region | 15-30 m forest | 509.600 | 0.815 | 0.052 | 19.702 |
| source | mondrian_region | >=30 m tall forest | 248.600 | 0.809 | 0.077 | 21.851 |

## Interval coverage, pooled model, by height_class

| calibration | method | height_class | n | coverage | coverage_sd | mean_width |
|---|---|---|---|---|---|---|
| source | raw | <2 m grass/low shrub | 203.300 | 0.525 | 0.049 | 6.176 |
| source | raw | 2-5 m shrub | 1087.700 | 0.934 | 0.012 | 7.211 |
| source | raw | 5-15 m woodland | 822.800 | 0.908 | 0.019 | 9.302 |
| source | raw | 15-30 m forest | 433.800 | 0.806 | 0.036 | 16.523 |
| source | raw | >=30 m tall forest | 353.300 | 0.676 | 0.069 | 18.829 |
| source | cqr | <2 m grass/low shrub | 203.300 | 0.800 | 0.118 | 7.559 |
| source | cqr | 2-5 m shrub | 1087.700 | 0.976 | 0.008 | 8.594 |
| source | cqr | 5-15 m woodland | 822.800 | 0.936 | 0.017 | 10.685 |
| source | cqr | 15-30 m forest | 433.800 | 0.839 | 0.037 | 17.906 |
| source | cqr | >=30 m tall forest | 353.300 | 0.717 | 0.058 | 20.212 |
| source | mondrian | <2 m grass/low shrub | 203.300 | 0.549 | 0.064 | 6.271 |
| source | mondrian | 2-5 m shrub | 1087.700 | 0.961 | 0.010 | 7.531 |
| source | mondrian | 5-15 m woodland | 822.800 | 0.942 | 0.012 | 10.696 |
| source | mondrian | 15-30 m forest | 433.800 | 0.901 | 0.042 | 23.200 |
| source | mondrian | >=30 m tall forest | 353.300 | 0.836 | 0.055 | 26.470 |
| source | mondrian_region | <2 m grass/low shrub | 203.300 | 0.755 | 0.081 | 7.767 |
| source | mondrian_region | 2-5 m shrub | 1087.700 | 0.970 | 0.007 | 8.683 |
| source | mondrian_region | 5-15 m woodland | 822.800 | 0.933 | 0.020 | 10.586 |
| source | mondrian_region | 15-30 m forest | 433.800 | 0.853 | 0.050 | 19.124 |
| source | mondrian_region | >=30 m tall forest | 353.300 | 0.742 | 0.061 | 21.271 |

## Interval coverage under transfer

| train_region | test_region | calibration | method | n | coverage | coverage_sd | mean_width |
|---|---|---|---|---|---|---|---|
| coastal_chaparral | sierra_conifer | source | raw | 5236.200 | 0.680 | 0.013 | 12.690 |
| coastal_chaparral | sierra_conifer | source | cqr | 5236.200 | 0.726 | 0.022 | 13.692 |
| coastal_chaparral | sierra_conifer | source | mondrian | 5236.200 | 0.771 | 0.046 | 16.464 |
| coastal_chaparral | sierra_conifer | local | raw | 5236.200 | 0.680 | 0.013 | 12.690 |
| coastal_chaparral | sierra_conifer | local | cqr | 5236.200 | 0.907 | 0.024 | 27.164 |
| coastal_chaparral | sierra_conifer | local | mondrian | 5236.200 | 0.905 | 0.019 | 25.694 |
| sierra_conifer | coastal_chaparral | source | raw | 6129.600 | 0.728 | 0.012 | 7.205 |
| sierra_conifer | coastal_chaparral | source | cqr | 6129.600 | 0.833 | 0.031 | 9.941 |
| sierra_conifer | coastal_chaparral | source | mondrian | 6129.600 | 0.793 | 0.017 | 8.785 |
| sierra_conifer | coastal_chaparral | local | raw | 6129.600 | 0.728 | 0.012 | 7.205 |
| sierra_conifer | coastal_chaparral | local | cqr | 6129.600 | 0.890 | 0.043 | 14.458 |
| sierra_conifer | coastal_chaparral | local | mondrian | 6129.600 | 0.891 | 0.035 | 15.196 |
