"""Gradient boosting supervisé (XGBoost) sur les conditions A, B et C.

  A : témoin complet (toutes les familles) ;
  B : témoin à volume égal à C (autant d'attaques, toutes les familles) ;
  C : traitement, Exploits et Reconnaissance retirés de l'entraînement.

Hyperparamètres : grille de `config.toml` (`[supervised.grid]`), déclarée avant la
recherche (M23). Recherche UNE FOIS, sur les données de C, par validation croisée
en blocs de temps contigus ; critère : moyenne, sur les blocs tenus à l'écart, de
la précision moyenne (AUC-PR) ; configuration retenue puis FIGÉE pour A, B et C.
Les familles retirées n'influencent ainsi aucune décision, même indirectement.

Seuil de déploiement : budget de faux positifs, quantile des scores hors
échantillon des seuls normaux (mêmes blocs de temps et mêmes budgets que les
modèles non supervisés, `calibration.py`). Les attaques ne servent jamais à fixer
le seuil. Score : marge (log-odds) du modèle, monotone en la probabilité ; le seuil
0,5 par défaut correspond à la marge 0.

Rapport commun (`evaluate.py`) plus deux ajouts : le rappel sur les attaques
tenues à l'écart (familles vues, jour d'entraînement, moment non vu), à comparer au
rappel du test, et un diagnostic au seuil par défaut.

Usage : python src/models/supervised.py [--config config.toml] [--conditions A B C]
                                        [--skip-tuning] [--compare-only]
"""

import argparse
import itertools
import json
import sys
import time
from pathlib import Path

# Exécuté depuis src/models/ : on ajoute src/ (prepare, evaluate) et src/models/.
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
sys.path.insert(0, str(Path(__file__).resolve().parent))

import numpy as np
import pandas as pd
import joblib
import xgboost as xgb
from sklearn.metrics import average_precision_score

from calibration import iter_time_blocks, report_and_save
from evaluate import rate_ci, recall_by_family, threshold_for_fpr
from prepare import load_config, load_set

CONDITIONS = ["A", "B", "C"]
REMOVED_FAMILIES = ["Exploits", "Reconnaissance"]


def new_model(hp: dict, scfg: dict) -> xgb.XGBClassifier:
    """XGBoost : hyperparamètres de la grille, défauts de la bibliothèque pour le reste."""
    return xgb.XGBClassifier(n_estimators=hp["n_estimators"], max_depth=hp["max_depth"],
                             tree_method="hist", random_state=scfg["seed"],
                             n_jobs=scfg["threads"], verbosity=0)


def margin(model: xgb.XGBClassifier, x: np.ndarray) -> np.ndarray:
    """Score d'anomalie : marge (log-odds) de la classe attaque ; plus grand = plus suspect."""
    return model.predict(x, output_margin=True)


def grid_configs(scfg: dict) -> list[dict]:
    """Les configurations de la grille, dans un ordre fixe (profondeur puis nombre d'arbres)."""
    g = scfg["grid"]
    return [{"max_depth": d, "n_estimators": n}
            for d, n in itertools.product(g["max_depth"], g["n_estimators"])]


def tune(cfg: dict, out: Path, feature_cols: list[str]) -> dict:
    """Recherche sur les données de la condition de réglage, par blocs de temps.

    Retourne {"best": hp, "table": [...]} : pour chaque configuration, la précision
    moyenne de chaque bloc, leur moyenne (critère) et la précision moyenne poolée
    (information seulement). Retenue : moyenne la plus haute à 4 décimales ; à
    égalité, moins d'arbres puis profondeur moindre.
    """
    scfg = cfg["supervised"]
    train = pd.read_parquet(out / f"train_{scfg['tuning_set']}.parquet")
    if not train["Stime"].is_monotonic_increasing:
        raise SystemExit("jeu de réglage non trié par Stime")
    y = train["label"].to_numpy()
    configs = grid_configs(scfg)
    fold_ap = {i: [] for i in range(len(configs))}
    pooled = np.empty((len(configs), len(train)))
    t0 = time.time()
    for i, keep, held, x_fit, x_held in iter_time_blocks(train, feature_cols, cfg, scfg["cv_folds"]):
        for c, hp in enumerate(configs):
            s = margin(new_model(hp, scfg).fit(x_fit, y[keep]), x_held)
            pooled[c, held] = s
            fold_ap[c].append(float(average_precision_score(y[held], s)))
        print(f"  bloc {i + 1}/{scfg['cv_folds']} : " + ", ".join(
            f"prof. {hp['max_depth']}/{hp['n_estimators']} arbres {fold_ap[c][-1]:.4f}"
            for c, hp in enumerate(configs)) + f" ({time.time() - t0:.0f} s)", flush=True)
    table = [{**hp, "fold_ap": fold_ap[c], "mean_ap": float(np.mean(fold_ap[c])),
              "pooled_ap": float(average_precision_score(y, pooled[c]))}
             for c, hp in enumerate(configs)]
    best = min(table, key=lambda r: (-round(r["mean_ap"], 4), r["n_estimators"], r["max_depth"]))
    return {"tuning_set": scfg["tuning_set"], "table": table,
            "best": {"max_depth": best["max_depth"], "n_estimators": best["n_estimators"]}}


def default_threshold_diagnostic(s_test, y_test, oof, y_oof) -> dict:
    """Ce que donne le seuil par défaut (marge 0, probabilité 0,5) : test et hors échantillon."""
    alert = s_test > 0.0
    tp, fp = int((alert & (y_test == 1)).sum()), int((alert & (y_test == 0)).sum())
    return {"test_fpr": fp / int((y_test == 0).sum()), "test_recall": tp / int((y_test == 1).sum()),
            "tp": tp, "fp": fp, "fn": int((y_test == 1).sum()) - tp,
            "tn": int((y_test == 0).sum()) - fp,
            "oof_fpr": float((oof[y_oof == 0] > 0.0).mean()),
            "oof_recall": float((oof[y_oof == 1] > 0.0).mean())}


def run_condition(name: str, hp: dict, cfg: dict, out: Path, feature_cols: list[str]) -> None:
    """Calibration hors échantillon, modèle final, rapport et rappel hors échantillon d'une condition."""
    scfg, ecfg = cfg["supervised"], cfg["evaluation"]
    t0 = time.time()
    print(f"\n{'=' * 78}\nCondition {name} : XGBoost, profondeur {hp['max_depth']}, "
          f"{hp['n_estimators']} arbres, {scfg['cv_folds']} blocs de temps\n{'=' * 78}", flush=True)
    train = pd.read_parquet(out / f"train_{name}.parquet")
    if not train["Stime"].is_monotonic_increasing:
        raise SystemExit(f"train_{name} n'est pas trié par Stime")
    y, family = train["label"].to_numpy(), train["family"].to_numpy()
    oof = np.empty(len(train))
    for i, keep, held, x_fit, x_held in iter_time_blocks(train, feature_cols, cfg, scfg["cv_folds"]):
        oof[held] = margin(new_model(hp, scfg).fit(x_fit, y[keep]), x_held)
        print(f"  bloc {i + 1}/{scfg['cv_folds']} : {len(held)} flux notés, "
              f"marge médiane des normaux {np.median(oof[held][y[held] == 0]):.3f} "
              f"({time.time() - t0:.0f} s)", flush=True)
    del train
    print(f"Scores hors échantillon calculés ({time.time() - t0:.0f} s)", flush=True)

    x_train, y_train, _, x_test, y_test, _ = load_set(name, out)
    model = new_model(hp, scfg).fit(x_train, y_train)
    s_test, s_train = margin(model, x_test), margin(model, x_train)
    print(f"Modèle final entraîné et test noté ({time.time() - t0:.0f} s)", flush=True)

    # Importance en gain du modèle final, par colonne préparée : montre d'emblée si la
    # détection repose sur quelques variables (raccourcis du banc d'essai).
    names = joblib.load(out / f"preprocessor_{name}.joblib").get_feature_names_out()
    importance = pd.Series(model.feature_importances_, index=names).sort_values(ascending=False)

    normals_oof = oof[y == 0]
    thresholds = {b: threshold_for_fpr(normals_oof, b) for b in ecfg["fpr_budgets"]}
    extra = {"hyperparameters": hp, "seconds": time.time() - t0,
             "top_features_gain": {k: float(v) for k, v in importance.head(10).items()},
             "default_threshold": default_threshold_diagnostic(s_test, y_test, oof, y),
             "oof_attack_recall": {}}
    for b, t in thresholds.items():
        alert = oof > t
        r, lo, hi = rate_ci(int((alert & (y == 1)).sum()), int((y == 1).sum()),
                            ecfg["confidence_alpha"])
        extra["oof_attack_recall"][str(b)] = {
            "threshold": t, "recall": r, "recall_lo": lo, "recall_hi": hi,
            "by_family": recall_by_family(family, y, alert, None,
                                          ecfg["confidence_alpha"]).to_dict(orient="records")}

    res = report_and_save(f"supervised_{name}", cfg, {**scfg, "hyperparameters": hp}, normals_oof,
                          s_train[y_train == 0], s_test, out, extra=extra, twin_set=name)
    d = extra["default_threshold"]
    print(f"\nDiagnostic au seuil par défaut (marge 0, probabilité 0,5) : test : taux de faux "
          f"positifs {100 * d['test_fpr']:.4f} %, rappel {100 * d['test_recall']:.2f} % (VP {d['tp']}, "
          f"FP {d['fp']}, FN {d['fn']}, VN {d['tn']}) ; hors échantillon : taux de faux positifs "
          f"{100 * d['oof_fpr']:.4f} %, rappel {100 * d['oof_recall']:.2f} %")
    print("Importance en gain du modèle final (10 premières colonnes préparées, part du total) : "
          + ", ".join(f"{k} {100 * v:.1f} %" for k, v in importance.head(10).items()))
    print("\nRappel sur les attaques TENUES À L'ÉCART (jour d'entraînement, moment non vu) contre "
          "rappel du test, au seuil calibré, mêmes familles :")
    for b, o in extra["oof_attack_recall"].items():
        tb = res["budgets"][b]
        seen = {r["family"]: r for r in o["by_family"]}
        hits = sum(r["hits"] for r in tb["by_family"] if r["family"] in seen)
        n = sum(r["n"] for r in tb["by_family"] if r["family"] in seen)
        print(f"  budget {100 * float(b):g} % : tenues à l'écart {100 * o['recall']:.2f} % "
              f"[{100 * o['recall_lo']:.2f} ; {100 * o['recall_hi']:.2f}] ; test {100 * hits / n:.2f} % "
              f"(seuil {o['threshold']:.3f}, taux de faux positifs observé au test "
              f"{100 * tb['fpr_test']:.4f} %)")
    ref = str(ecfg["reference_fpr"])
    print(f"  par famille au budget de référence {100 * float(ref):g} % (tenues à l'écart / test) :")
    test_by = {r["family"]: r for r in res["budgets"][ref]["by_family"]}
    for r in extra["oof_attack_recall"][ref]["by_family"]:
        t = test_by[r["family"]]
        print(f"    {r['family']:15s} tenues à l'écart n={r['n']:5d} {100 * r['recall']:6.2f} %  |  "
              f"test n={t['n']:5d} {100 * t['recall']:6.2f} %")
    print(f"({time.time() - t0:.0f} s au total pour la condition {name})")


def print_comparison(cfg: dict, out: Path) -> None:
    """Compare A, B et C sur le même pied, avec le rappel des familles retirées et la découpe jumeau."""
    res = {}
    for c in CONDITIONS:
        path = out / "results" / f"supervised_{c}.json"
        if path.exists():
            res[c] = json.loads(path.read_text())
    if not res:
        print("aucun résultat supervisé écrit")
        return
    budgets = [str(b) for b in cfg["evaluation"]["fpr_budgets"]]
    hp = next(iter(res.values()))["hyperparameters"]
    print(f"\n{'=' * 78}\nA, B et C sur le même pied (hyperparamètres figés : profondeur "
          f"{hp['max_depth']}, {hp['n_estimators']} arbres)\n{'=' * 78}")
    print(f"AUC-PR au test : " + ", ".join(
        f"{c} {p['evaluation']['average_precision']:.4f}" for c, p in res.items()))
    for b in budgets:
        print(f"\nBudget {100 * float(b):g} %")
        for c, p in res.items():
            e = p["evaluation"]["budgets"][b]
            o = p["oof_attack_recall"][b]
            seen = {r["family"] for r in o["by_family"]}
            hits = sum(r["hits"] for r in e["by_family"] if r["family"] in seen)
            n = sum(r["n"] for r in e["by_family"] if r["family"] in seen)
            print(f"  {c} : taux de faux positifs observé {100 * e['fpr_test']:.4f} % ; rappel calibré "
                  f"{100 * e['recall']:.2f} % (familles vues : {100 * hits / n:.2f} %, tenues à "
                  f"l'écart : {100 * o['recall']:.2f} %) ; rappel lu au même taux "
                  f"{100 * e['matched']['recall']:.2f} %")
    for fam in REMOVED_FAMILIES:
        print(f"\n{fam} (famille retirée de C) : rappel au test, avec / sans jumeau dans le jeu "
              "d'entraînement de la condition")
        for b in budgets:
            for kind, key in (("calibré", None), ("lu au même taux", "matched")):
                cells = []
                for c, p in res.items():
                    rows = p["evaluation"]["budgets"][b]
                    rows = rows["by_family"] if key is None else rows[key]["by_family"]
                    r = next(x for x in rows if x["family"] == fam)
                    tw = (f"jumeau {100 * r['recall_twin']:.1f} % (n={r['n_twin']}) / sans "
                          f"{100 * r['recall_no_twin']:.2f} % (n={r['n_no_twin']})"
                          if r["n_twin"] else f"sans jumeau {100 * r['recall_no_twin']:.2f} %")
                    cells.append(f"{c} {100 * r['recall']:.2f} % [{tw}]")
                print(f"  budget {100 * float(b):g} %, {kind:16s}: " + " ; ".join(cells))
    if all(c in res for c in CONDITIONS):
        print("\nÉcarts au rappel lu au même taux (points de pourcentage), même lignes de test : "
              "A − B (effet du volume), B − C (effet de la famille inédite à volume constant)")
        for fam in REMOVED_FAMILIES:
            for b in budgets:
                v = {c: next(x for x in res[c]["evaluation"]["budgets"][b]["matched"]["by_family"]
                             if x["family"] == fam)["recall"] for c in CONDITIONS}
                print(f"  {fam:15s} budget {100 * float(b):g} % : A {100 * v['A']:.2f}, B "
                      f"{100 * v['B']:.2f}, C {100 * v['C']:.2f} ; A − B {100 * (v['A'] - v['B']):+.2f}, "
                      f"B − C {100 * (v['B'] - v['C']):+.2f}")


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--config", type=Path, default=Path("config.toml"))
    parser.add_argument("--conditions", nargs="+", default=CONDITIONS, choices=CONDITIONS)
    parser.add_argument("--skip-tuning", action="store_true",
                        help="Réutilise la configuration retenue dans results/supervised_search.json")
    parser.add_argument("--compare-only", action="store_true",
                        help="N'entraîne rien : compare les résultats déjà écrits")
    args = parser.parse_args()
    cfg = load_config(args.config)
    out = Path(cfg["data"]["processed_dir"])
    if args.compare_only:
        print_comparison(cfg, out)
        return
    feature_cols = json.loads((out / "manifest.json").read_text())["feature_columns"]
    (out / "results").mkdir(exist_ok=True)
    search_path = out / "results" / "supervised_search.json"

    if args.skip_tuning:
        # `search_file` : configuration retenue ailleurs (ablation TTL : figée depuis la
        # recherche du jeu complet, sans nouvelle recherche).
        search = json.loads(Path(cfg["supervised"].get("search_file", search_path)).read_text())
    else:
        scfg = cfg["supervised"]
        print(f"Recherche d'hyperparamètres sur les données de C : {len(grid_configs(scfg))} "
              f"configurations, {scfg['cv_folds']} blocs de temps", flush=True)
        t0 = time.time()
        search = tune(cfg, out, feature_cols)
        search_path.write_text(json.dumps(search, indent=2))
        print("\nPrécision moyenne (AUC-PR) par bloc tenu à l'écart, moyenne (critère) et poolée :")
        for r in search["table"]:
            print(f"  profondeur {r['max_depth']:2d}, {r['n_estimators']:3d} arbres : blocs "
                  + " ".join(f"{a:.4f}" for a in r["fold_ap"])
                  + f" ; moyenne {r['mean_ap']:.4f} ; poolée {r['pooled_ap']:.4f}")
        print(f"Configuration retenue : {search['best']} ({time.time() - t0:.0f} s)", flush=True)
    for name in args.conditions:
        run_condition(name, search["best"], cfg, out, feature_cols)
    print_comparison(cfg, out)


if __name__ == "__main__":
    main()
