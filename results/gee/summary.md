# Results: gee

**Real GEDI L2A / Sentinel-2 / SRTM samples.**

Shots after screening: {'coastal_chaparral': 8000, 'sierra_conifer': 8000}. Block size 13 km (variogram), buffer 1 km, 90% intervals, 10 block splits.

## RMSE vs GEDI RH98 (m) by evaluation scheme

| region | model | random | spatial | spatial+buffer | other ecoregion |
|---|---|---|---|---|---|
| coastal_chaparral | linear | 7.26 | 7.38 | 7.39 | 10.94 |
| coastal_chaparral | rf | 7.16 | 7.32 | 7.34 | 9.48 |
| coastal_chaparral | xgb | 7.28 | 7.43 | 7.48 | 9.99 |
| sierra_conifer | linear | 9.38 | 9.68 | 9.73 | 17.69 |
| sierra_conifer | rf | 9.14 | 9.35 | 9.35 | 12.10 |
| sierra_conifer | xgb | 9.23 | 9.49 | 9.52 | 13.74 |

## xgb: spatial-block CV

| region | reference | n | rmse | bias | mae | r2 |
|---|---|---|---|---|---|---|
| coastal_chaparral | GEDI RH98 | 8000 | 7.426 | -0.009 | 4.773 | 0.321 |
| sierra_conifer | GEDI RH98 | 8000 | 9.492 | 0.091 | 7.394 | 0.403 |

## xgb: cross-region transfer

| train_region | test_region | model | n | rmse | bias | mae | r2 |
|---|---|---|---|---|---|---|---|
| coastal_chaparral | sierra_conifer | xgb | 8000 | 13.737 | -8.659 | 10.774 | -0.251 |
| sierra_conifer | coastal_chaparral | xgb | 8000 | 9.986 | 5.754 | 8.124 | -0.228 |

## xgb: feature ablation (in-region spatial CV vs transfer)

| features | train_region | test_region | rmse_within | rmse_transfer | bias_transfer | bias_transfer_tall |
|---|---|---|---|---|---|---|
| all features | sierra_conifer | coastal_chaparral | 7.43 | 9.99 | 5.75 | -2.07 |
| all features | coastal_chaparral | sierra_conifer | 9.49 | 13.74 | -8.66 | -12.07 |
| without elevation | sierra_conifer | coastal_chaparral | 7.51 | 9.12 | 3.58 | -3.70 |
| without elevation | coastal_chaparral | sierra_conifer | 9.55 | 10.94 | -2.06 | -4.38 |
| spectral only | sierra_conifer | coastal_chaparral | 7.71 | 9.55 | 4.19 | -3.67 |
| spectral only | coastal_chaparral | sierra_conifer | 9.70 | 11.65 | -1.96 | -4.26 |

## xgb: by height class (binned on GEDI RH98)

| region | height_class | n | rmse | bias | mae | r2 | scheme |
|---|---|---|---|---|---|---|---|
| coastal_chaparral | <2 m grass/low shrub | 1 | 1.40 | 1.40 | 1.40 |  | spatial |
| coastal_chaparral | 2-5 m shrub | 1837 | 4.53 | 3.22 | 3.40 | -30.28 | spatial |
| coastal_chaparral | 5-15 m woodland | 3936 | 4.76 | 2.15 | 3.65 | -1.84 | spatial |
| coastal_chaparral | 15-30 m forest | 1951 | 7.20 | -4.27 | 5.83 | -2.48 | spatial |
| coastal_chaparral | >=30 m tall forest | 275 | 27.84 | -22.19 | 22.57 | -3.38 | spatial |
| sierra_conifer | 2-5 m shrub | 346 | 10.78 | 8.88 | 8.90 | -226.08 | spatial |
| sierra_conifer | 5-15 m woodland | 1476 | 10.14 | 8.08 | 8.54 | -11.56 | spatial |
| sierra_conifer | 15-30 m forest | 3332 | 7.06 | 1.93 | 5.60 | -1.77 | spatial |
| sierra_conifer | >=30 m tall forest | 2846 | 11.29 | -7.27 | 8.72 | -1.71 | spatial |
| coastal_chaparral | <2 m grass/low shrub | 1 | 7.96 | 7.96 | 7.96 |  | transfer |
| coastal_chaparral | 2-5 m shrub | 1837 | 11.50 | 10.66 | 10.66 | -200.53 | transfer |
| coastal_chaparral | 5-15 m woodland | 3936 | 9.30 | 7.89 | 8.06 | -9.83 | transfer |
| coastal_chaparral | 15-30 m forest | 1951 | 5.64 | 0.15 | 4.48 | -1.14 | transfer |
| coastal_chaparral | >=30 m tall forest | 275 | 23.52 | -17.79 | 17.95 | -2.12 | transfer |
| sierra_conifer | 2-5 m shrub | 346 | 7.19 | 6.32 | 6.33 | -100.07 | transfer |
| sierra_conifer | 5-15 m woodland | 1476 | 5.10 | 2.09 | 3.92 | -2.18 | transfer |
| sierra_conifer | 15-30 m forest | 3332 | 9.28 | -6.71 | 7.79 | -3.79 | transfer |
| sierra_conifer | >=30 m tall forest | 2846 | 20.25 | -18.34 | 18.37 | -7.71 | transfer |

## xgb: by vegetation type

| region | evt_group | n | rmse | bias | mae | r2 | scheme | reference |
|---|---|---|---|---|---|---|---|---|
| coastal_chaparral | Forest | 587 | 8.96 | -0.95 | 6.12 | 0.34 | spatial | GEDI RH98 |
| coastal_chaparral | Herbaceous | 1724 | 7.12 | 0.01 | 3.88 | 0.06 | spatial | GEDI RH98 |
| coastal_chaparral | Other | 757 | 6.45 | 0.68 | 3.92 | 0.26 | spatial | GEDI RH98 |
| coastal_chaparral | Riparian | 253 | 7.96 | -0.52 | 5.12 | 0.22 | spatial | GEDI RH98 |
| coastal_chaparral | Shrubland | 1840 | 7.13 | 0.13 | 4.45 | 0.13 | spatial | GEDI RH98 |
| coastal_chaparral | Woodland | 2839 | 7.64 | -0.06 | 5.44 | 0.22 | spatial | GEDI RH98 |
| sierra_conifer | Forest | 6178 | 9.45 | -0.09 | 7.41 | 0.39 | spatial | GEDI RH98 |
| sierra_conifer | Herbaceous | 67 | 9.38 | 1.95 | 7.62 | -0.40 | spatial | GEDI RH98 |
| sierra_conifer | Other | 198 | 9.77 | -1.20 | 7.56 | 0.54 | spatial | GEDI RH98 |
| sierra_conifer | Riparian | 313 | 10.70 | -1.01 | 8.14 | 0.29 | spatial | GEDI RH98 |
| sierra_conifer | Shrubland | 55 | 8.08 | 1.87 | 6.32 | -0.06 | spatial | GEDI RH98 |
| sierra_conifer | Woodland | 1189 | 9.38 | 1.34 | 7.14 | 0.19 | spatial | GEDI RH98 |
| coastal_chaparral | Forest | 587 | 10.21 | 3.73 | 8.12 | 0.14 | transfer | GEDI RH98 |
| coastal_chaparral | Herbaceous | 1724 | 9.99 | 6.51 | 8.21 | -0.85 | transfer | GEDI RH98 |
| coastal_chaparral | Other | 757 | 10.25 | 6.90 | 8.56 | -0.86 | transfer | GEDI RH98 |
| coastal_chaparral | Riparian | 253 | 9.06 | 3.51 | 6.82 | -0.02 | transfer | GEDI RH98 |
| coastal_chaparral | Shrubland | 1840 | 10.54 | 6.80 | 8.65 | -0.91 | transfer | GEDI RH98 |
| coastal_chaparral | Woodland | 2839 | 9.56 | 4.93 | 7.73 | -0.23 | transfer | GEDI RH98 |
| sierra_conifer | Forest | 6178 | 14.19 | -9.41 | 11.29 | -0.37 | transfer | GEDI RH98 |
| sierra_conifer | Herbaceous | 67 | 9.17 | -3.82 | 6.49 | -0.34 | transfer | GEDI RH98 |
| sierra_conifer | Other | 198 | 15.28 | -8.36 | 12.32 | -0.12 | transfer | GEDI RH98 |
| sierra_conifer | Riparian | 313 | 15.90 | -11.59 | 13.01 | -0.57 | transfer | GEDI RH98 |
| sierra_conifer | Shrubland | 55 | 8.84 | 1.55 | 6.84 | -0.26 | transfer | GEDI RH98 |
| sierra_conifer | Woodland | 1189 | 10.50 | -4.78 | 7.67 | -0.02 | transfer | GEDI RH98 |

## Interval coverage, pooled model, by overall

| calibration | method | n | coverage | coverage_sd | mean_width |
|---|---|---|---|---|---|
| source | raw | 3995.400 | 0.849 | 0.012 | 21.503 |
| source | cqr | 3995.400 | 0.902 | 0.023 | 24.022 |
| source | mondrian | 3995.400 | 0.900 | 0.017 | 24.565 |
| source | mondrian_region | 3995.400 | 0.901 | 0.018 | 24.462 |

## Interval coverage, pooled model, by region

| calibration | method | region | n | coverage | coverage_sd | mean_width |
|---|---|---|---|---|---|---|
| source | raw | coastal_chaparral | 1918.400 | 0.872 | 0.029 | 18.026 |
| source | raw | sierra_conifer | 2077.000 | 0.829 | 0.022 | 24.735 |
| source | cqr | coastal_chaparral | 1918.400 | 0.935 | 0.029 | 20.545 |
| source | cqr | sierra_conifer | 2077.000 | 0.873 | 0.026 | 27.254 |
| source | mondrian | coastal_chaparral | 1918.400 | 0.908 | 0.024 | 19.433 |
| source | mondrian | sierra_conifer | 2077.000 | 0.895 | 0.020 | 29.347 |
| source | mondrian_region | coastal_chaparral | 1918.400 | 0.903 | 0.040 | 18.986 |
| source | mondrian_region | sierra_conifer | 2077.000 | 0.902 | 0.031 | 29.653 |

## Interval coverage, pooled model, by pred_height_class

| calibration | method | pred_height_class | n | coverage | coverage_sd | mean_width |
|---|---|---|---|---|---|---|
| source | raw | 2-5 m shrub | 273.500 | 0.914 | 0.027 | 11.727 |
| source | raw | 5-15 m woodland | 1616.200 | 0.857 | 0.021 | 18.850 |
| source | raw | 15-30 m forest | 1543.700 | 0.841 | 0.016 | 25.257 |
| source | raw | >=30 m tall forest | 560.300 | 0.811 | 0.034 | 23.802 |
| source | cqr | 2-5 m shrub | 273.500 | 0.962 | 0.024 | 14.246 |
| source | cqr | 5-15 m woodland | 1616.200 | 0.930 | 0.024 | 21.369 |
| source | cqr | 15-30 m forest | 1543.700 | 0.883 | 0.023 | 27.776 |
| source | cqr | >=30 m tall forest | 560.300 | 0.845 | 0.041 | 26.321 |
| source | mondrian | 2-5 m shrub | 273.500 | 0.890 | 0.036 | 11.866 |
| source | mondrian | 5-15 m woodland | 1616.200 | 0.895 | 0.022 | 19.742 |
| source | mondrian | 15-30 m forest | 1543.700 | 0.904 | 0.023 | 29.226 |
| source | mondrian | >=30 m tall forest | 560.300 | 0.906 | 0.039 | 32.163 |
| source | mondrian_region | 2-5 m shrub | 273.500 | 0.947 | 0.029 | 12.913 |
| source | mondrian_region | 5-15 m woodland | 1616.200 | 0.907 | 0.030 | 20.581 |
| source | mondrian_region | 15-30 m forest | 1543.700 | 0.897 | 0.022 | 29.179 |
| source | mondrian_region | >=30 m tall forest | 560.300 | 0.875 | 0.042 | 28.687 |
| source | raw | <2 m grass/low shrub | 3.400 | 1.000 | 0.000 | 9.532 |
| source | cqr | <2 m grass/low shrub | 3.400 | 1.000 | 0.000 | 11.385 |
| source | mondrian | <2 m grass/low shrub | 3.400 | 1.000 | 0.000 | 11.385 |
| source | mondrian_region | <2 m grass/low shrub | 3.400 | 1.000 | 0.000 | 10.589 |

## Interval coverage, pooled model, by height_class

| calibration | method | height_class | n | coverage | coverage_sd | mean_width |
|---|---|---|---|---|---|---|
| source | raw | <2 m grass/low shrub | 1.000 | 0.000 | 0.000 | 13.113 |
| source | raw | 2-5 m shrub | 519.200 | 0.717 | 0.077 | 15.228 |
| source | raw | 5-15 m woodland | 1331.100 | 0.885 | 0.027 | 19.932 |
| source | raw | 15-30 m forest | 1320.300 | 0.925 | 0.012 | 23.749 |
| source | raw | >=30 m tall forest | 824.400 | 0.743 | 0.039 | 24.494 |
| source | cqr | <2 m grass/low shrub | 1.000 | 1.000 | 0.000 | 16.072 |
| source | cqr | 2-5 m shrub | 519.200 | 0.892 | 0.066 | 17.747 |
| source | cqr | 5-15 m woodland | 1331.100 | 0.934 | 0.028 | 22.451 |
| source | cqr | 15-30 m forest | 1320.300 | 0.948 | 0.010 | 26.268 |
| source | cqr | >=30 m tall forest | 824.400 | 0.781 | 0.044 | 27.013 |
| source | mondrian | <2 m grass/low shrub | 1.000 | 0.000 | 0.000 | 13.014 |
| source | mondrian | 2-5 m shrub | 519.200 | 0.801 | 0.073 | 16.005 |
| source | mondrian | 5-15 m woodland | 1331.100 | 0.936 | 0.023 | 21.620 |
| source | mondrian | 15-30 m forest | 1320.300 | 0.952 | 0.009 | 27.316 |
| source | mondrian | >=30 m tall forest | 824.400 | 0.815 | 0.039 | 30.489 |
| source | mondrian_region | <2 m grass/low shrub | 1.000 | 0.750 | 0.500 | 13.526 |
| source | mondrian_region | 2-5 m shrub | 519.200 | 0.852 | 0.091 | 16.973 |
| source | mondrian_region | 5-15 m woodland | 1331.100 | 0.926 | 0.031 | 21.947 |
| source | mondrian_region | 15-30 m forest | 1320.300 | 0.951 | 0.009 | 27.190 |
| source | mondrian_region | >=30 m tall forest | 824.400 | 0.805 | 0.043 | 29.106 |

## Interval coverage under transfer

| train_region | test_region | calibration | method | n | coverage | coverage_sd | mean_width |
|---|---|---|---|---|---|---|---|
| coastal_chaparral | sierra_conifer | source | raw | 6784.100 | 0.502 | 0.067 | 16.622 |
| coastal_chaparral | sierra_conifer | source | cqr | 6784.100 | 0.562 | 0.061 | 18.721 |
| coastal_chaparral | sierra_conifer | source | mondrian | 6784.100 | 0.595 | 0.049 | 20.438 |
| coastal_chaparral | sierra_conifer | local | raw | 6784.100 | 0.502 | 0.067 | 16.622 |
| coastal_chaparral | sierra_conifer | local | cqr | 6784.100 | 0.897 | 0.039 | 44.287 |
| coastal_chaparral | sierra_conifer | local | mondrian | 6784.100 | 0.891 | 0.032 | 43.065 |
| sierra_conifer | coastal_chaparral | source | raw | 6801.000 | 0.576 | 0.036 | 23.059 |
| sierra_conifer | coastal_chaparral | source | cqr | 6801.000 | 0.784 | 0.057 | 28.074 |
| sierra_conifer | coastal_chaparral | source | mondrian | 6801.000 | 0.709 | 0.045 | 26.812 |
| sierra_conifer | coastal_chaparral | local | raw | 6801.000 | 0.576 | 0.036 | 23.059 |
| sierra_conifer | coastal_chaparral | local | cqr | 6801.000 | 0.910 | 0.029 | 30.849 |
| sierra_conifer | coastal_chaparral | local | mondrian | 6801.000 | 0.913 | 0.029 | 31.107 |
