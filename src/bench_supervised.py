"""Coût d'un gradient boosting (XGBoost) sur cette machine : mesure de temps.

Entraîne des XGBoost sur le jeu A (témoin complet, préprocesseur `A`) avec
différents nombres d'arbres et profondeurs, et chronomètre entraînement et
notation. N'évalue rien : aucune métrique de détection, aucun accès au test
hors notation chronométrée, aucun choix d'hyperparamètre. Sert à chiffrer les
18 entraînements du protocole (3 conditions x (5 blocs de calibration + 1 modèle
final)), car le temps par epoch de M18 a varié d'un facteur 3 selon le moment.

Usage : python src/bench_supervised.py [--config config.toml] [--set A]
"""

import argparse
import resource
import time
from pathlib import Path

import xgboost as xgb

from prepare import load_config, load_set


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--config", type=Path, default=Path("config.toml"))
    parser.add_argument("--set", default="A", choices=["A", "B", "C"])
    parser.add_argument("--trees", type=int, nargs="+", default=[100, 300])
    parser.add_argument("--depths", type=int, nargs="+", default=[6, 10])
    parser.add_argument("--threads", type=int, default=4)
    parser.add_argument("--seed", type=int, default=42)
    args = parser.parse_args()
    cfg = load_config(args.config)
    out = Path(cfg["data"]["processed_dir"])

    x_train, y_train, _, x_test, _, _ = load_set(args.set, out)
    print(f"xgboost {xgb.__version__} ; jeu {args.set} : {x_train.shape[0]} lignes x "
          f"{x_train.shape[1]} colonnes, {int(y_train.sum())} attaques "
          f"({100 * y_train.mean():.2f} %) ; {args.threads} threads")
    for depth in args.depths:
        for trees in args.trees:
            model = xgb.XGBClassifier(n_estimators=trees, max_depth=depth, tree_method="hist",
                                      random_state=args.seed, n_jobs=args.threads, verbosity=0)
            t = time.perf_counter()
            model.fit(x_train, y_train)
            t_fit = time.perf_counter() - t
            t = time.perf_counter()
            model.predict_proba(x_test)
            t_pred = time.perf_counter() - t
            print(f"  {trees:4d} arbres, profondeur {depth:2d} : entraînement {t_fit:6.1f} s ; "
                  f"notation de {x_test.shape[0]} lignes {t_pred:5.1f} s", flush=True)
    print(f"Pic de mémoire : {resource.getrusage(resource.RUSAGE_SELF).ru_maxrss / 1024:.0f} Mo")


if __name__ == "__main__":
    main()
