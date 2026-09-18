"""Isolation Forest sur le jeu non supervisé : référence face à l'autoencodeur.

Entraînement sur les seuls flux normaux du jour 2 (jeu `unsup`), jamais sur une
attaque ; hyperparamètres par défaut de la bibliothèque, non réglés (M16).

Seuil de décision : budget de faux positifs, calibré sur des scores HORS
ÉCHANTILLON des normaux d'entraînement. Les normaux, triés par `Stime`, sont
coupés en `cv_folds` blocs de temps contigus ; chaque bloc est noté par un
modèle entraîné sur les autres blocs, avec un préprocesseur (sélection log1p,
encodeur, scaler) réajusté sur ces autres blocs seuls. Des blocs contigus
évitent qu'une rafale de flux quasi identiques se partage entre entraînement et
validation. Le modèle final est entraîné sur tous les normaux, avec le
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

from evaluate import evaluate_scores, print_report, twin_flags
from prepare import build_preprocessor, load_config, load_set, select_log_columns


def new_model(icfg: dict) -> IsolationForest:
    """Isolation Forest aux hyperparamètres de la configuration (défauts de la bibliothèque)."""
    return IsolationForest(n_estimators=icfg["n_estimators"], max_samples=icfg["max_samples"],
                           random_state=icfg["seed"], n_jobs=icfg["n_jobs"])


def anomaly_scores(model: IsolationForest, x: np.ndarray) -> np.ndarray:
    """Score d'anomalie : plus grand = plus suspect (opposé de `score_samples`)."""
    return -model.score_samples(x)


def out_of_fold_scores(train_raw: pd.DataFrame, feature_cols: list[str], cfg: dict) -> np.ndarray:
    """Scores hors échantillon des normaux d'entraînement, par blocs de temps contigus.

    `train_raw` doit être trié par Stime. Le préprocesseur est réajusté à chaque
    bloc sur les seules lignes d'entraînement de ce bloc : ni le scaler ni la
    sélection log1p ne voient le bloc noté.
    """
    icfg = cfg["isolation_forest"]
    n = len(train_raw)
    oof = np.empty(n)
    for i, held in enumerate(np.array_split(np.arange(n), icfg["cv_folds"])):
        keep = np.ones(n, dtype=bool)
        keep[held] = False
        fit_rows = train_raw.loc[keep, feature_cols]
        log_cols, _ = select_log_columns(fit_rows, cfg)
        pre = build_preprocessor(cfg, feature_cols, log_cols).fit(fit_rows)
        model = new_model(icfg).fit(pre.transform(fit_rows).astype(np.float32))
        oof[held] = anomaly_scores(
            model, pre.transform(train_raw.iloc[held][feature_cols]).astype(np.float32))
        print(f"  bloc {i + 1}/{icfg['cv_folds']} : {len(held)} flux notés, "
              f"score médian {np.median(oof[held]):.4f}", flush=True)
    return oof


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--config", type=Path, default=Path("config.toml"))
    args = parser.parse_args()
    cfg = load_config(args.config)
    icfg, ecfg = cfg["isolation_forest"], cfg["evaluation"]
    out = Path(cfg["data"]["processed_dir"])
    (out / "results").mkdir(exist_ok=True)
    manifest = json.loads((out / "manifest.json").read_text())
    feature_cols = manifest["feature_columns"]

    t0 = time.time()
    train_raw = pd.read_parquet(out / "train_unsup.parquet")
    if not train_raw["Stime"].is_monotonic_increasing:
        raise SystemExit("train_unsup n'est pas trié par Stime : les blocs ne seraient pas contigus")
    print(f"Jeu unsup : {len(train_raw)} normaux ; blocs de temps : {icfg['cv_folds']}")
    oof = out_of_fold_scores(train_raw, feature_cols, cfg)
    print(f"Scores hors échantillon calculés ({time.time() - t0:.0f} s)", flush=True)

    x_train, _, _, x_test, y_test, family_test = load_set("unsup", out)
    model = new_model(icfg).fit(x_train)
    s_test = anomaly_scores(model, x_test)
    s_train = anomaly_scores(model, x_train)
    print(f"Modèle final entraîné et test noté ({time.time() - t0:.0f} s)", flush=True)

    test = pd.read_parquet(out / "test.parquet", columns=["Stime"])
    twins = twin_flags("unsup", out)
    args_eval = dict(y_true=y_test, family=family_test, scores=s_test,
                     budgets=ecfg["fpr_budgets"], stime=test["Stime"].to_numpy(),
                     has_twin=twins["has_twin"].to_numpy(), alpha=ecfg["confidence_alpha"])
    res = evaluate_scores(calibration_scores=oof, **args_eval)
    print_report(res, ecfg["reference_fpr"])

    print("\nQuantiles du score d'anomalie (50 %, 99 %, 99,9 %, 99,99 %) :")
    for label, x in (("normaux d'entraînement, hors échantillon", oof),
                     ("normaux d'entraînement, dans l'échantillon", s_train),
                     ("normaux du test", s_test[y_test == 0]),
                     ("attaques du test", s_test[y_test == 1])):
        q = np.quantile(x, [0.5, 0.99, 0.999, 0.9999])
        print(f"  {label:45s} " + " ".join(f"{v:.4f}" for v in q))

    # Diagnostic : seuil tiré des scores du modèle sur SES PROPRES normaux
    # d'entraînement (option 1 de M16), pour mesurer l'optimisme de cette option.
    naive = evaluate_scores(calibration_scores=s_train, **args_eval)
    print("\nDiagnostic (option 1) : seuil calculé sur les scores d'entraînement du modèle final")
    for key, b in res["budgets"].items():
        nb = naive["budgets"][key]
        oof_at_naive = float((oof > nb["threshold"]).mean())
        print(f"  budget {100 * b['fpr_target']:.3f} % : seuil hors échantillon {b['threshold']:.4f} "
              f"-> test {100 * b['fpr_test']:.4f} % ; seuil sur l'entraînement "
              f"{nb['threshold']:.4f} -> test {100 * nb['fpr_test']:.4f} %, "
              f"rappel {100 * nb['recall']:.2f} % ; taux hors échantillon au seuil "
              f"d'entraînement {100 * oof_at_naive:.4f} % (visé {100 * b['fpr_target']:.3f} %, "
              f"optimisme x{oof_at_naive / b['fpr_target']:.2f})")

    np.save(out / "results" / "isolation_forest_test_scores.npy", s_test)
    np.save(out / "results" / "isolation_forest_oof_scores.npy", oof)
    payload = {"config": cfg["isolation_forest"], "evaluation": res, "diagnostic_option_1": naive}
    (out / "results" / "isolation_forest.json").write_text(
        json.dumps(payload, indent=2, default=lambda o: None if o != o else float(o)))
    print(f"\nRésultats écrits dans {out / 'results'} ({time.time() - t0:.0f} s au total)")


if __name__ == "__main__":
    main()
