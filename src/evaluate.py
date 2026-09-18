"""Évaluation : marquage des jumeaux et rappel par famille.

État actuel : seulement ce qu'exige la lecture des résultats sur Reconnaissance
(M11). Dans le témoin A, environ un quart des lignes de test de cette famille
ont un jumeau exact (mêmes 41 features) dans l'entraînement ; le rappel doit
donc être rapporté séparément avec et sans jumeau. Les métriques par famille
complètes, les seuils et les matrices de confusion viendront avec les modèles.

Un « jumeau » est une ligne d'entraînement du jeu évalué dont les 41 features
(valeurs nettoyées, avant encodage et scaler) sont identiques, quelle que soit
son étiquette. Le marquage dépend du jeu : une ligne de test peut avoir un
jumeau dans A et pas dans C.
"""

import json
from pathlib import Path

import numpy as np
import pandas as pd


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


def recall_by_family(family, y_true, y_pred, has_twin=None) -> pd.DataFrame:
    """Rappel de détection par famille d'attaque, avec découpe optionnelle par jumeau.

    `y_pred` vaut 1 quand la ligne est signalée comme attaque. Les lignes
    normales sont ignorées ici (le taux de faux positifs se calcule à part).
    Avec `has_twin`, ajoute pour chaque famille l'effectif et le rappel des
    lignes avec jumeau (`*_twin`) et sans jumeau (`*_no_twin`) ; un sous-ensemble
    vide donne NaN plutôt qu'un rappel inventé.
    """
    family, y_true = np.asarray(family), np.asarray(y_true)
    hit = np.asarray(y_pred) == 1
    twin = None if has_twin is None else np.asarray(has_twin, dtype=bool)
    rows = []
    for fam in sorted(set(family[y_true == 1])):
        m = (family == fam) & (y_true == 1)
        row = {"family": fam, "n": int(m.sum()), "recall": float(hit[m].mean())}
        if twin is not None:
            for suffix, sub in (("twin", m & twin), ("no_twin", m & ~twin)):
                row[f"n_{suffix}"] = int(sub.sum())
                row[f"recall_{suffix}"] = float(hit[sub].mean()) if sub.any() else np.nan
        rows.append(row)
    return pd.DataFrame(rows)
