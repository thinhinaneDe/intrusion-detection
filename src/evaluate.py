"""Évaluation : seuil par budget de faux positifs, métriques, rappel par famille.

Le seuil de décision n'est jamais la valeur par défaut d'une bibliothèque : il
est calibré pour un budget de faux positifs (part des flux normaux qui
déclenchent une alerte) sur des scores de flux normaux que le modèle n'a pas
vus (M16). Le test ne sert jamais à régler un seuil ; on y lit seulement le
taux de faux positifs obtenu, à comparer au taux visé.

Un « jumeau » est une ligne d'entraînement du jeu évalué dont les 41 features
(valeurs nettoyées, avant encodage et scaler) sont identiques, quelle que soit
son étiquette (M11). Le rappel est rapporté séparément avec et sans jumeau,
notamment pour Reconnaissance, dont environ un quart des lignes de test ont un
jumeau dans le témoin A. Le marquage dépend du jeu évalué.

Les scores sont des scores d'anomalie : plus grand = plus suspect. Une alerte
est déclenchée quand le score est strictement supérieur au seuil.
"""

import json
from pathlib import Path
from statistics import NormalDist

import numpy as np
import pandas as pd
from sklearn.metrics import average_precision_score


def wilson(p: float, n: int, alpha: float = 0.05) -> tuple[float, float]:
    """Intervalle de Wilson de niveau 1 - alpha pour une proportion p sur n essais.

    Suppose des observations indépendantes, ce qui est optimiste pour des flux
    issus d'une même rafale.
    """
    z = NormalDist().inv_cdf(1 - alpha / 2)
    denom = 1 + z * z / n
    center = (p + z * z / (2 * n)) / denom
    half = z * np.sqrt(p * (1 - p) / n + z * z / (4 * n * n)) / denom
    return float(max(0.0, center - half)), float(min(1.0, center + half))


def row_hashes(df: pd.DataFrame, cols: list[str]) -> np.ndarray:
    """Empreinte 64 bits de chaque ligne sur les colonnes `cols`."""
    return pd.util.hash_pandas_object(df[cols], index=False).to_numpy()


def mark_twins(test: pd.DataFrame, train_set: pd.DataFrame, cols: list[str]) -> pd.DataFrame:
    """Marque chaque ligne de test selon qu'elle a un jumeau dans `train_set`.

    Retourne un DataFrame de même longueur et même ordre que `test`, avec
    `has_twin` (booléen) et `twin_kind` : « none » sans jumeau ; « attack » ou
    « normal » si tous les jumeaux d'entraînement ont cette étiquette binaire ;
    « mixed » s'ils en ont les deux.
    """
    lab = (pd.DataFrame({"h": row_hashes(train_set, cols), "y": train_set["label"].to_numpy()})
           .groupby("h")["y"].agg(["min", "max"]))
    m = pd.DataFrame({"h": row_hashes(test, cols)}).join(lab, on="h")
    has = m["min"].notna().to_numpy()
    kind = np.select([~has, (m["min"] != m["max"]).to_numpy(), (m["min"] == 1).to_numpy()],
                     ["none", "mixed", "attack"], default="normal")
    return pd.DataFrame({"has_twin": has, "twin_kind": kind}, index=test.index)


def twin_flags(name: str, processed_dir: Path = Path("data/processed")) -> pd.DataFrame:
    """Marquage des jumeaux du test pour le jeu d'entraînement `name` (unsup, A, B ou C)."""
    cols = json.loads((processed_dir / "manifest.json").read_text())["feature_columns"]
    test = pd.read_parquet(processed_dir / "test.parquet")
    train = pd.read_parquet(processed_dir / f"train_{name}.parquet")
    return mark_twins(test, train, cols)


def threshold_for_fpr(normal_scores, fpr: float) -> float:
    """Seuil tel qu'au plus `fpr` des scores normaux lui soient strictement supérieurs.

    `normal_scores` doit provenir de flux normaux non vus par le modèle qui les
    note (scores hors échantillon). Avec des scores égaux, le taux réel sur ces
    scores peut être inférieur au budget, jamais supérieur.
    """
    return float(np.quantile(np.asarray(normal_scores), 1 - fpr, method="higher"))


def _rate(hits: int, n: int, alpha: float) -> tuple[float, float, float]:
    """(taux, borne basse, borne haute de Wilson) ; NaN si n = 0."""
    if n == 0:
        return np.nan, np.nan, np.nan
    lo, hi = wilson(hits / n, n, alpha)
    return hits / n, lo, hi


def recall_by_family(family, y_true, y_pred, has_twin=None, alpha: float = 0.05) -> pd.DataFrame:
    """Rappel de détection par famille d'attaque, avec découpe optionnelle par jumeau.

    `y_pred` vaut 1 (ou True) quand la ligne est signalée comme attaque. Les
    lignes normales sont ignorées ici (le taux de faux positifs se calcule à
    part). Colonnes : effectif `n`, détections `hits`, `recall` et son intervalle
    de Wilson `recall_lo`, `recall_hi`. Avec `has_twin`, les mêmes grandeurs pour
    les lignes avec jumeau (`*_twin`) et sans jumeau (`*_no_twin`) ; un
    sous-ensemble vide donne NaN plutôt qu'un rappel inventé.
    """
    family, y_true = np.asarray(family), np.asarray(y_true)
    hit = np.asarray(y_pred).astype(bool)
    twin = None if has_twin is None else np.asarray(has_twin, dtype=bool)
    rows = []
    for fam in sorted(set(family[y_true == 1])):
        m = (family == fam) & (y_true == 1)
        r, lo, hi = _rate(int(hit[m].sum()), int(m.sum()), alpha)
        row = {"family": fam, "n": int(m.sum()), "hits": int(hit[m].sum()),
               "recall": r, "recall_lo": lo, "recall_hi": hi}
        if twin is not None:
            for suffix, sub in (("twin", m & twin), ("no_twin", m & ~twin)):
                r, lo, hi = _rate(int(hit[sub].sum()), int(sub.sum()), alpha)
                row.update({f"n_{suffix}": int(sub.sum()), f"hits_{suffix}": int(hit[sub].sum()),
                            f"recall_{suffix}": r, f"recall_{suffix}_lo": lo,
                            f"recall_{suffix}_hi": hi})
        rows.append(row)
    return pd.DataFrame(rows)


def evaluate_scores(y_true, family, scores, calibration_scores, budgets, stime,
                    has_twin=None, alpha: float = 0.05) -> dict:
    """Évalue des scores d'anomalie à chaque budget de faux positifs.

    `calibration_scores` : scores de flux normaux non vus par le modèle, dont on
    tire un seuil par budget (`threshold_for_fpr`). `stime` : horodatages du
    test, pour le nombre de fausses alertes par heure. Retourne l'AUC-PR (AP,
    indépendante du seuil) et, par budget : seuil, taux de faux positifs sur la
    calibration et sur le test (avec intervalle de Wilson), fausses alertes par
    heure (moyenne et pire heure), rappel global et par famille.
    """
    y_true, scores, stime = np.asarray(y_true), np.asarray(scores), np.asarray(stime)
    calibration_scores = np.asarray(calibration_scores)
    normal, attack = y_true == 0, y_true == 1
    span_h = float((stime.max() - stime.min()) / 3600)
    out = {"average_precision": float(average_precision_score(y_true, scores)),
           "prevalence": float(attack.mean()), "n_normal": int(normal.sum()),
           "n_attack": int(attack.sum()), "span_hours": span_h, "budgets": {}}
    for b in budgets:
        t = threshold_for_fpr(calibration_scores, b)
        alert = scores > t
        fp = alert & normal
        hourly = pd.Series((stime[fp] // 3600).astype(np.int64)).value_counts()
        fpr, fpr_lo, fpr_hi = _rate(int(fp.sum()), int(normal.sum()), alpha)
        rec, rec_lo, rec_hi = _rate(int((alert & attack).sum()), int(attack.sum()), alpha)
        tp, n_fp = int((alert & attack).sum()), int(fp.sum())
        # Point de fonctionnement lu sur le test : seuil au même taux de faux
        # positifs que le budget, mais mesuré sur les normaux du TEST. Borne
        # haute non déployable (elle utilise les étiquettes du test) ; sert à
        # comparer des modèles indépendamment de la qualité de leur calibration.
        t_m = threshold_for_fpr(scores[normal], b)
        alert_m = scores > t_m
        rec_m, rec_m_lo, rec_m_hi = _rate(int((alert_m & attack).sum()), int(attack.sum()), alpha)
        out["budgets"][str(b)] = {
            "fpr_target": b, "threshold": t,
            "fpr_calibration": float((calibration_scores > t).mean()),
            "fpr_test": fpr, "fpr_test_lo": fpr_lo, "fpr_test_hi": fpr_hi,
            "false_positives": int(fp.sum()),
            "false_alerts_per_hour_mean": float(fp.sum() / span_h),
            "false_alerts_max_hour": int(hourly.max()) if len(hourly) else 0,
            "recall": rec, "recall_lo": rec_lo, "recall_hi": rec_hi,
            "precision": tp / (tp + n_fp) if tp + n_fp else np.nan,
            "confusion": {"tp": tp, "fp": n_fp, "fn": int(attack.sum()) - tp,
                          "tn": int(normal.sum()) - n_fp},
            "by_family": recall_by_family(family, y_true, alert, has_twin, alpha)
            .to_dict(orient="records"),
            "matched": {"threshold": t_m, "fpr_test": float((alert_m & normal).sum() / normal.sum()),
                        "recall": rec_m, "recall_lo": rec_m_lo, "recall_hi": rec_m_hi,
                        "by_family": recall_by_family(family, y_true, alert_m, has_twin, alpha)
                        .to_dict(orient="records")},
        }
    return out


def _pct(x: float, digits: int = 2) -> str:
    return "  n/a" if x is None or np.isnan(x) else f"{100 * x:.{digits}f} %"


def print_report(res: dict, reference: float) -> None:
    """Affiche AUC-PR, rappel aux budgets, taux visé contre observé et rappel par famille."""
    print(f"AUC-PR (précision moyenne) : {res['average_precision']:.4f} "
          f"(référence d'un score aléatoire = prévalence : {_pct(res['prevalence'], 3)})")
    print(f"Test : {res['n_normal']} normaux, {res['n_attack']} attaques, "
          f"étendue {res['span_hours']:.1f} h")
    print("\nTaux de faux positifs visé contre observé, et rappel global :")
    for key, b in res["budgets"].items():
        print(f"  budget {_pct(b['fpr_target'], 3)} : seuil {b['threshold']:.4f} ; "
              f"calibration {_pct(b['fpr_calibration'], 4)} ; "
              f"test {_pct(b['fpr_test'], 4)} [{_pct(b['fpr_test_lo'], 4)} ; "
              f"{_pct(b['fpr_test_hi'], 4)}] ({b['false_positives']} faux positifs, "
              f"{b['false_alerts_per_hour_mean']:.1f} fausses alertes/h en moyenne, "
              f"{b['false_alerts_max_hour']} la pire heure) ; "
              f"rappel {_pct(b['recall'])} [{_pct(b['recall_lo'])} ; {_pct(b['recall_hi'])}]")
        c = b["confusion"]
        print(f"      matrice de confusion : VP {c['tp']}, FP {c['fp']}, FN {c['fn']}, VN {c['tn']} ; "
              f"précision {_pct(b['precision'])}")
    print("\nRappel au même taux de faux positifs LU SUR LE TEST (borne haute non déployable, "
          "pour comparer les modèles hors calibration) :")
    for key, b in res["budgets"].items():
        m = b["matched"]
        print(f"  taux {_pct(b['fpr_target'], 3)} : seuil {m['threshold']:.4f} ; "
              f"rappel {_pct(m['recall'])} [{_pct(m['recall_lo'])} ; {_pct(m['recall_hi'])}]")
    print("\nRappel par famille au même taux lu sur le test (mêmes budgets que ci-dessus) :")
    fams = [r["family"] for r in next(iter(res["budgets"].values()))["matched"]["by_family"]]
    for i, fam in enumerate(fams):
        cells = []
        for b in res["budgets"].values():
            r = b["matched"]["by_family"][i]
            cells.append(f"{_pct(b['fpr_target'], 3)} : {_pct(r['recall'])}")
        n = next(iter(res["budgets"].values()))["matched"]["by_family"][i]["n"]
        print(f"  {fam:15s} n={n:5d}  " + "  |  ".join(cells))
    for key, b in res["budgets"].items():
        ref = " (budget de référence)" if b["fpr_target"] == reference else ""
        print(f"\nRappel par famille, budget {_pct(b['fpr_target'], 3)}{ref} :")
        for r in b["by_family"]:
            line = (f"  {r['family']:15s} n={r['n']:5d}  rappel {_pct(r['recall'])} "
                    f"[{_pct(r['recall_lo'])} ; {_pct(r['recall_hi'])}]")
            if "n_twin" in r:
                line += (f"  | avec jumeau n={r['n_twin']:4d} {_pct(r['recall_twin'])}"
                         f"  | sans jumeau n={r['n_no_twin']:5d} {_pct(r['recall_no_twin'])}")
            print(line)
