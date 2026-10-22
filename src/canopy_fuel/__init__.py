"""canopy_fuel: validation-first canopy-height modelling for wildfire fuels.

GEDI L2A canopy height (RH98) is the reference; Sentinel-2 composites and SRTM
terrain are the predictors. The emphasis is on *how the model is evaluated*:
spatial block cross-validation, cross-ecoregion transfer, calibrated prediction
intervals, and error analysis by vegetation type.

The package separates concerns so the validation science is independent of
the data source:

    config        ecoregion AOIs, GEE asset ids, feature lists, height classes
    data          output contract, synthetic backend (known truth), CSV cache
    gee           Google Earth Engine extraction (GEDI + Sentinel-2 + SRTM + LANDFIRE)
    features      spectral indices and terrain derivatives
    spatial       local projection, spatial blocks, buffers, empirical variogram
    models        XGBoost, random-forest and linear baselines
    validation    random vs spatial-block CV, cross-region transfer, metrics
    uncertainty   quantile XGBoost, split-conformal / CQR, coverage checks
    plotting      report figures
"""

__version__ = "0.1.0"
