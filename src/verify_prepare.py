"""Contrôles d'intégrité des jeux écrits par prepare.py.

  1. le scaler de chaque jeu a été ajusté sur son entraînement seul (moyennes
     égales à celles de l'entraînement, différentes de celles du test) ;
  2. les jeux sont imbriqués comme prévu (B et C dans A, mêmes normaux partout) ;
  3. aucune ligne de test n'a de copie comportementale dans l'entraînement ;
  4. les jeux se chargent, sans NaN ni infini ;
  5. empreinte de B, pour comparer deux exécutions (reproductibilité du tirage).

Usage : python src/verify_prepare.py [--config config.toml]
"""

import argparse
import json
from pathlib import Path

import joblib
import numpy as np
import pandas as pd

from prepare import SET_NAMES, load_config, load_set


def row_hashes(df: pd.DataFrame, cols: list[str]) -> np.ndarray:
    """Empreinte 64 bits de chaque ligne sur les colonnes `cols`."""
    return pd.util.hash_pandas_object(df[cols], index=False).to_numpy()


def twin_table(test: pd.DataFrame, train_set: pd.DataFrame, cols: list[str]) -> pd.DataFrame:
    """Lignes de test ayant une copie sur `cols` dans `train_set`, avec la nature du jumeau.

    `twin` vaut « attaque » ou « normal » si tous les jumeaux d'entraînement
    partagent cette étiquette binaire, « mixte » sinon.
    """
    t = pd.DataFrame({"h": row_hashes(test, cols), "family": test["family"].to_numpy(),
                      "y": test["label"].to_numpy()})
    tr = pd.DataFrame({"h": row_hashes(train_set, cols), "y": train_set["label"].to_numpy()})
    lab = tr.groupby("h")["y"].agg(["min", "max"])
    m = t.join(lab, on="h", how="inner")
    m["twin"] = np.where(m["min"] != m["max"], "mixte", np.where(m["min"] == 1, "attaque", "normal"))
    return m


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--config", type=Path, default=Path("config.toml"))
    args = parser.parse_args()
    cfg = load_config(args.config)
    out = Path(cfg["data"]["processed_dir"])
    manifest = json.loads((out / "manifest.json").read_text())
    cols = manifest["feature_columns"]
    numeric = [c for c in cols if c not in cfg["features"]["nominal"]]

    test = pd.read_parquet(out / "test.parquet")
    train = {n: pd.read_parquet(out / f"train_{n}.parquet") for n in SET_NAMES}

    print("1. Scaler ajusté sur l'entraînement seul (écart max des moyennes, en unités brutes)")
    for n in SET_NAMES:
        mean = joblib.load(out / f"preprocessor_{n}.joblib").named_transformers_["numeric"].mean_
        d_train = np.abs(mean - train[n][numeric].mean().to_numpy()).max()
        d_test = np.abs(mean - test[numeric].mean().to_numpy())
        rel = (d_test / (np.abs(mean) + 1e-12)).max()
        print(f"  {n:6s} vs moyenne entraînement : {d_train:.3e} ; "
              f"vs moyenne test : écart relatif max {rel:.3f}")

    print("\n2. Imbrication des jeux")
    h_all = {n: row_hashes(train[n], cols + ["Stime"]) for n in SET_NAMES}
    for n in ("B", "C"):
        print(f"  {n} inclus dans A : {np.isin(h_all[n], h_all['A']).all()}")
    normals = {n: np.sort(h_all[n][train[n]["label"].to_numpy() == 0]) for n in SET_NAMES}
    print("  mêmes normaux dans les quatre jeux : "
          f"{all(np.array_equal(normals['A'], normals[n]) for n in SET_NAMES)}")
    print(f"  unsup sans attaque : {(train['unsup']['label'] == 0).all()}")
    print(f"  C sans les familles retirées : "
          f"{not train['C']['family'].isin(cfg['families']['removed']).any()}")

    print("\n3. Copies comportementales test/entraînement (41 features, sans Stime)")
    for n in SET_NAMES:
        twins = twin_table(test, train[n], cols)
        print(f"  jeu {n} : {len(twins)} lignes de test ont des features identiques à une "
              "ligne d'entraînement")
        for fam, g in twins.groupby("family"):
            total = int((test["family"] == fam).sum())
            same = int((g["twin"] == np.where(g["y"] == 1, "attaque", "normal")).sum())
            mixed = int((g["twin"] == "mixte").sum())
            print(f"    {fam:15s} {len(g):5d} sur {total:8d} ({100 * len(g) / total:5.2f} %) ; "
                  f"même étiquette binaire {same}, opposée {len(g) - same - mixed}, "
                  f"jumeaux mixtes {mixed}")

    print("\n4. Chargement")
    for n in SET_NAMES:
        x_tr, y_tr, _, x_te, y_te, _ = load_set(n, out)
        print(f"  {n:6s} X_train {x_tr.shape} X_test {x_te.shape} "
              f"fini : {np.isfinite(x_tr).all() and np.isfinite(x_te).all()}")

    print("\n5. Empreinte de B (somme des empreintes de lignes, entier 64 bits)")
    print(f"  {int(h_all['B'].sum(dtype=np.uint64))}")


if __name__ == "__main__":
    main()
