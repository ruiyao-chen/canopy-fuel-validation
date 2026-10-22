"""Model factory: XGBoost and the baselines it has to beat.

* ``linear`` - standardised ridge regression; shows how much is linear signal.
* ``rf``     - random forest, the usual canopy-height workhorse.
* ``xgb``    - gradient-boosted trees (XGBoost, ``hist``).

Hyper-parameters are fixed, sensible defaults, not tuned: tuning inside the
same folds used for evaluation would bias the comparison, and the point of
this project is the evaluation.
"""

from __future__ import annotations

import numpy as np
from sklearn.ensemble import RandomForestRegressor
from sklearn.linear_model import RidgeCV
from sklearn.pipeline import make_pipeline
from sklearn.preprocessing import StandardScaler

MODEL_NAMES = ["linear", "rf", "xgb"]
MODEL_LABELS = {"linear": "Ridge (linear)", "rf": "Random forest", "xgb": "XGBoost"}


def make_model(name: str, seed: int = 0, fast: bool = False):
    """Return an unfitted regressor. ``fast`` shrinks ensembles for tests."""
    if name == "linear":
        return make_pipeline(StandardScaler(), RidgeCV(alphas=np.logspace(-3, 3, 13)))
    if name == "rf":
        return RandomForestRegressor(
            n_estimators=80 if fast else 300, min_samples_leaf=3, max_features=0.5,
            n_jobs=-1, random_state=seed,
        )
    if name == "xgb":
        from xgboost import XGBRegressor
        return XGBRegressor(
            n_estimators=150 if fast else 500, learning_rate=0.1 if fast else 0.05,
            max_depth=6, min_child_weight=5, subsample=0.8, colsample_bytree=0.8,
            reg_lambda=1.0, tree_method="hist", n_jobs=4, random_state=seed,
        )
    raise ValueError(f"unknown model {name!r}; choose from {MODEL_NAMES}")
