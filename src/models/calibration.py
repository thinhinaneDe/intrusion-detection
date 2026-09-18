"""Calibration hors échantillon en blocs de temps et rapport, communs aux modèles non supervisés.

Un modèle non supervisé est décrit par une fonction `fit_score(x_fit, x_score)`
qui l'entraîne sur `x_fit` et retourne le score d'anomalie de chaque ligne de
`x_score` (plus grand = plus suspect). Ce module ajoute :

  - `out_of_fold_scores` : scores hors échantillon des normaux d'entraînement.
    Les normaux, triés par `Stime`, sont coupés en blocs de temps contigus ;
    chaque bloc est noté par un modèle entraîné sur les autres blocs, avec un
    préprocesseur (sélection log1p, encodeur, scaler) réajusté sur ces autres
    blocs seuls. Des blocs contigus évitent qu'une rafale de flux quasi
    identiques se partage entre entraînement et validation (M16) ;
  - `report_and_save` : évaluation sur le test aux budgets de faux positifs de
    la configuration, rapport, diagnostic de l'option 1 (seuil tiré des scores
    d'entraînement) et écriture des scores et des résultats.
"""

import json
import sys
from pathlib import Path
from typing import Callable

# Les scripts de src/models/ s'exécutent depuis ce dossier : on ajoute src/.
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

import numpy as np
import pandas as pd

from evaluate import evaluate_scores, print_report, twin_flags
from prepare import build_preprocessor, select_log_columns


def iter_time_blocks(train_raw: pd.DataFrame, feature_cols: list[str], cfg: dict, n_folds: int):
    """Génère (i, keep, held, x_fit, x_held) pour chaque bloc de temps contigu.

    `train_raw` doit être trié par Stime. `held` : indices du bloc tenu à
    l'écart ; `keep` : masque des lignes d'entraînement (tout sauf le bloc). Le
    préprocesseur (sélection log1p, encodeur, scaler) est réajusté sur les seules
    lignes de `keep` : ni le scaler ni la sélection log1p ne voient le bloc noté.
    """
    n = len(train_raw)
    for i, held in enumerate(np.array_split(np.arange(n), n_folds)):
        keep = np.ones(n, dtype=bool)
        keep[held] = False
        fit_rows = train_raw.loc[keep, feature_cols]
        log_cols, _ = select_log_columns(fit_rows, cfg)
        pre = build_preprocessor(cfg, feature_cols, log_cols).fit(fit_rows)
        yield (i, keep, held, pre.transform(fit_rows).astype(np.float32),
               pre.transform(train_raw.iloc[held][feature_cols]).astype(np.float32))


def out_of_fold_scores(train_raw: pd.DataFrame, feature_cols: list[str], cfg: dict, n_folds: int,
                       fit_score: Callable[[np.ndarray, np.ndarray], np.ndarray]) -> np.ndarray:
    """Scores hors échantillon des normaux d'entraînement, par blocs de temps contigus."""
    oof = np.empty(len(train_raw))
    for i, _, held, x_fit, x_held in iter_time_blocks(train_raw, feature_cols, cfg, n_folds):
        oof[held] = fit_score(x_fit, x_held)
        print(f"  bloc {i + 1}/{n_folds} : {len(held)} flux notés, "
              f"score médian {np.median(oof[held]):.4f}", flush=True)
    return oof


def report_and_save(name: str, cfg: dict, model_cfg: dict, oof: np.ndarray, s_train: np.ndarray,
                    s_test: np.ndarray, out: Path, extra: dict | None = None,
                    twin_set: str = "unsup") -> dict:
    """Évalue les scores du test, affiche le rapport, écrit scores et résultats.

    `oof` calibre les seuils ; `s_train` (scores du modèle final sur ses propres
    normaux d'entraînement) ne sert qu'au diagnostic de l'option 1. Les scores
    du test sont alignés sur `test.parquet`. Écrit
    `results/<name>_test_scores.npy`, `_oof_scores.npy` et `<name>.json`
    (`extra` : champs supplémentaires du modèle, ajoutés au fichier JSON).
    `twin_set` : jeu d'entraînement dont on marque les jumeaux du test.
    """
    ecfg = cfg["evaluation"]
    test = pd.read_parquet(out / "test.parquet", columns=["Stime", "label", "family"])
    y_test, family_test = test["label"].to_numpy(), test["family"].to_numpy()
    twins = twin_flags(twin_set, out)
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

    (out / "results").mkdir(exist_ok=True)
    np.save(out / "results" / f"{name}_test_scores.npy", s_test)
    np.save(out / "results" / f"{name}_oof_scores.npy", oof)
    payload = {"config": model_cfg, "evaluation": res, "diagnostic_option_1": naive,
               **(extra or {})}
    (out / "results" / f"{name}.json").write_text(
        json.dumps(payload, indent=2, default=lambda o: None if o != o else float(o)))
    print(f"\nRésultats écrits dans {out / 'results'}")
    return res
