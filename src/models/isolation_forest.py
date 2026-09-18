"""Isolation Forest sur le jeu non supervisé : référence face à l'autoencodeur.

Entraînement sur les seuls flux normaux du jour 2 (jeu `unsup`), jamais sur une
attaque ; hyperparamètres par défaut de la bibliothèque, non réglés (M16).

Seuil de décision : budget de faux positifs, calibré sur des scores HORS
ÉCHANTILLON des normaux d'entraînement, en blocs de temps contigus (voir
`calibration.py`). Le modèle final est entraîné sur tous les normaux, avec le
préprocesseur du jeu `unsup` écrit par prepare.py, et évalué sur le test.

Usage : python src/models/isolation_forest.py [--config config.toml]
"""

import argparse
import json
import sys
import time
from pathlib import Path

# Le script s'exécute depuis src/models/ : on ajoute src/ pour importer prepare et evaluate.
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

import numpy as np
import pandas as pd
from sklearn.ensemble import IsolationForest

from calibration import out_of_fold_scores, report_and_save
from prepare import load_config, load_set


def new_model(icfg: dict) -> IsolationForest:
    """Isolation Forest aux hyperparamètres de la configuration (défauts de la bibliothèque)."""
    return IsolationForest(n_estimators=icfg["n_estimators"], max_samples=icfg["max_samples"],
                           random_state=icfg["seed"], n_jobs=icfg["n_jobs"])


def anomaly_scores(model: IsolationForest, x: np.ndarray) -> np.ndarray:
    """Score d'anomalie : plus grand = plus suspect (opposé de `score_samples`)."""
    return -model.score_samples(x)


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--config", type=Path, default=Path("config.toml"))
    args = parser.parse_args()
    cfg = load_config(args.config)
    icfg = cfg["isolation_forest"]
    out = Path(cfg["data"]["processed_dir"])
    feature_cols = json.loads((out / "manifest.json").read_text())["feature_columns"]

    t0 = time.time()
    train_raw = pd.read_parquet(out / "train_unsup.parquet")
    if not train_raw["Stime"].is_monotonic_increasing:
        raise SystemExit("train_unsup n'est pas trié par Stime : les blocs ne seraient pas contigus")
    print(f"Jeu unsup : {len(train_raw)} normaux ; blocs de temps : {icfg['cv_folds']}")
    oof = out_of_fold_scores(
        train_raw, feature_cols, cfg, icfg["cv_folds"],
        lambda x_fit, x_held: anomaly_scores(new_model(icfg).fit(x_fit), x_held))
    print(f"Scores hors échantillon calculés ({time.time() - t0:.0f} s)", flush=True)

    x_train, _, _, x_test, _, _ = load_set("unsup", out)
    model = new_model(icfg).fit(x_train)
    s_test, s_train = anomaly_scores(model, x_test), anomaly_scores(model, x_train)
    print(f"Modèle final entraîné et test noté ({time.time() - t0:.0f} s)", flush=True)

    report_and_save("isolation_forest", cfg, icfg, oof, s_train, s_test, out)
    print(f"({time.time() - t0:.0f} s au total)")


if __name__ == "__main__":
    main()
