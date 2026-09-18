"""Contrôles d'intégrité des jeux écrits par prepare.py.

  1. le scaler de chaque jeu a été ajusté sur son entraînement seul (moyennes
     égales à celles de l'entraînement transformé, différentes de celles du test) ;
  2. les colonnes log1p sont celles du manifeste, calculées sur l'entraînement ;
  3. les jeux sont imbriqués comme prévu (B et C dans A, mêmes normaux partout) ;
  4. lignes de test ayant un jumeau exact dans l'entraînement, par famille ;
  5. les jeux se chargent, sans NaN ni infini ;
  6. empreinte de B, pour comparer deux exécutions (reproductibilité du tirage).

Usage : python src/verify_prepare.py [--config config.toml]
"""

import argparse
import json
from pathlib import Path

import joblib
import numpy as np
import pandas as pd

from evaluate import mark_twins, recall_by_family, row_hashes
from prepare import SET_NAMES, load_config, load_set


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--config", type=Path, default=Path("config.toml"))
    args = parser.parse_args()
    cfg = load_config(args.config)
    out = Path(cfg["data"]["processed_dir"])
    manifest = json.loads((out / "manifest.json").read_text())
    cols = manifest["feature_columns"]

    test = pd.read_parquet(out / "test.parquet")
    train = {n: pd.read_parquet(out / f"train_{n}.parquet") for n in SET_NAMES}
    pre = {n: joblib.load(out / f"preprocessor_{n}.joblib") for n in SET_NAMES}

    print("1. Scaler ajusté sur l'entraînement seul")
    print("   (écart max entre la moyenne du scaler et celle de l'entraînement transformé ;"
          " écart relatif max avec celle du test transformé)")
    for n in SET_NAMES:
        d_train, d_test = 0.0, 0.0
        for name, fitted, sub in pre[n].transformers_:
            if not name.startswith("numeric"):
                continue
            scaler = fitted[-1] if name == "numeric_log" else fitted
            tr, te = train[n][sub], test[sub]
            if name == "numeric_log":
                tr, te = np.log1p(tr), np.log1p(te)
            d_train = max(d_train, float(np.abs(scaler.mean_ - tr.mean().to_numpy()).max()))
            rel = np.abs(scaler.mean_ - te.mean().to_numpy()) / (np.abs(scaler.mean_) + 1e-12)
            d_test = max(d_test, float(rel.max()))
        print(f"  {n:6s} entraînement : {d_train:.3e} ; test : {d_test:.3f}")

    print("\n2. Colonnes log1p (asymétrie > "
          f"{cfg['preprocessing']['log1p_skew_threshold']} sur l'entraînement du jeu)")
    lists = {n: manifest["sets"][n]["log1p_columns"] for n in SET_NAMES}
    for n in SET_NAMES:
        fitted = [c for name, _, sub in pre[n].transformers_ if name == "numeric_log" for c in sub]
        print(f"  {n:6s} {len(lists[n])} colonnes ; conforme au préprocesseur : "
              f"{fitted == [c for c in cols if c in lists[n]]}")
    print(f"  listes identiques dans les quatre jeux : "
          f"{all(lists[n] == lists['A'] for n in SET_NAMES)}")

    print("\n3. Imbrication des jeux")
    h_all = {n: row_hashes(train[n], cols + ["Stime"]) for n in SET_NAMES}
    for n in ("B", "C"):
        print(f"  {n} inclus dans A : {np.isin(h_all[n], h_all['A']).all()}")
    normals = {n: np.sort(h_all[n][train[n]["label"].to_numpy() == 0]) for n in SET_NAMES}
    print("  mêmes normaux dans les quatre jeux : "
          f"{all(np.array_equal(normals['A'], normals[n]) for n in SET_NAMES)}")
    print(f"  unsup sans attaque : {(train['unsup']['label'] == 0).all()}")
    print(f"  C sans les familles retirées : "
          f"{not train['C']['family'].isin(cfg['families']['removed']).any()}")

    print("\n4. Jumeaux test/entraînement (41 features, sans Stime), par famille de test")
    for n in SET_NAMES:
        twins = mark_twins(test, train[n], cols)
        print(f"  jeu {n} : {int(twins['has_twin'].sum())} lignes de test ont un jumeau")
        for fam, g in twins.groupby(test["family"]):
            k = g["twin_kind"]
            total = len(g)
            n_tw = int(g["has_twin"].sum())
            if n_tw == 0:
                continue
            print(f"    {fam:15s} {n_tw:5d} sur {total:8d} ({100 * n_tw / total:5.2f} %) ; "
                  f"jumeaux attaque {int((k == 'attack').sum())}, normal "
                  f"{int((k == 'normal').sum())}, mixte {int((k == 'mixed').sum())}")
    # Cohérence de recall_by_family : un prédicteur « mémoriseur » (signale une
    # ligne s'il a un jumeau attaque) doit avoir un rappel de 1 avec jumeau
    # attaque et de 0 sans jumeau.
    twins_a = mark_twins(test, train["A"], cols)
    r = recall_by_family(test["family"], test["label"], (twins_a["twin_kind"] == "attack"),
                         twins_a["has_twin"])
    rec = r[r["family"] == "Reconnaissance"].iloc[0]
    print("  contrôle recall_by_family, Reconnaissance, prédicteur mémoriseur sur A : "
          f"n {rec['n']} ; avec jumeau {rec['n_twin']} (rappel {rec['recall_twin']:.3f}) ; "
          f"sans jumeau {rec['n_no_twin']} (rappel {rec['recall_no_twin']:.3f})")

    print("\n5. Chargement")
    for n in SET_NAMES:
        x_tr, y_tr, _, x_te, y_te, _ = load_set(n, out)
        print(f"  {n:6s} X_train {x_tr.shape} X_test {x_te.shape} "
              f"fini : {np.isfinite(x_tr).all() and np.isfinite(x_te).all()} ; "
              f"max |X_train| {np.abs(x_tr).max():.1f}, max |X_test| {np.abs(x_te).max():.1f}")

    print("\n6. Empreinte de B (somme des empreintes de lignes, entier 64 bits)")
    print(f"  {int(h_all['B'].sum(dtype=np.uint64))}")


if __name__ == "__main__":
    main()
