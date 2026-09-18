"""Asymétrie (skewness) des features numériques, avant et après log1p.

Calculée sur les jeux d'entraînement uniquement, jamais sur le test : le choix
des colonnes à transformer est un paramètre ajusté, au même titre que la moyenne
d'un scaler. Sert à proposer le seuil de `config.toml` (`log1p_skew_threshold`).

Usage : python src/inspect_skew.py [--config config.toml]
"""

import argparse
import json
from pathlib import Path

import numpy as np
import pandas as pd

from prepare import SET_NAMES, load_config


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--config", type=Path, default=Path("config.toml"))
    parser.add_argument("--threshold", type=float, default=2.0,
                        help="Seuil d'asymétrie au-dessus duquel log1p serait appliqué")
    parser.add_argument("--scale-columns", nargs="+", default=["ackdat", "tcprtt", "synack"],
                        help="Colonnes dont on détaille l'échelle (médiane, quantile 99 %%)")
    args = parser.parse_args()
    cfg = load_config(args.config)
    out = Path(cfg["data"]["processed_dir"])
    cols = json.loads((out / "manifest.json").read_text())["feature_columns"]
    numeric = [c for c in cols if c not in cfg["features"]["nominal"]]

    skew, skew_log, minimum, distinct = {}, {}, {}, {}
    for name in SET_NAMES:
        df = pd.read_parquet(out / f"train_{name}.parquet", columns=numeric)
        skew[name] = df.skew()
        skew_log[name] = np.log1p(df.clip(lower=0)).skew()
        minimum[name] = df.min()
        distinct[name] = df.nunique()

    s = pd.DataFrame(skew)
    order = s["A"].sort_values(ascending=False).index
    print(f"{len(numeric)} features numériques. Asymétrie brute par jeu, puis après log1p (jeu A).")
    print(f"{'colonne':18s} {'unsup':>8s} {'A':>8s} {'B':>8s} {'C':>8s} {'log1p(A)':>9s} "
          f"{'min':>6s} {'modalités':>10s}")
    for c in order:
        print(f"{c:18s} {skew['unsup'][c]:8.2f} {skew['A'][c]:8.2f} {skew['B'][c]:8.2f} "
              f"{skew['C'][c]:8.2f} {skew_log['A'][c]:9.2f} {minimum['A'][c]:6.1f} "
              f"{int(distinct['A'][c]):10d}")

    print("\nValeurs triées de l'asymétrie brute (jeu A), pour repérer un écart naturel :")
    print("  " + " ".join(f"{v:.1f}" for v in s["A"].sort_values(ascending=False)))
    for t in (0.5, 1, 2, 3, 5, 10):
        counts = {n: int((skew[n] > t).sum()) for n in SET_NAMES}
        same = all(set(skew[n].index[skew[n] > t]) == set(skew["A"].index[skew["A"] > t])
                   for n in SET_NAMES)
        print(f"  seuil {t:>4} : colonnes au-dessus {counts} ; même liste dans les 4 jeux : {same}")

    # Effet sur l'échelle : plus grande valeur standardisée |z| d'une colonne,
    # avant et après log1p, sur le jeu de l'autoencodeur (unsup, normaux seuls).
    selected = [c for c in numeric if skew["unsup"][c] > args.threshold]
    df = pd.read_parquet(out / "train_unsup.parquet", columns=numeric)

    def max_abs_z(x: pd.DataFrame) -> pd.Series:
        return ((x - x.mean()) / x.std(ddof=0)).abs().max()

    z_raw, z_log = max_abs_z(df[selected]), max_abs_z(np.log1p(df[selected]))
    print(f"\nSeuil {args.threshold} : {len(selected)} colonnes sélectionnées sur le jeu unsup : "
          f"{selected}")
    print("Plus grande valeur standardisée |z| par colonne (jeu unsup), avant -> après log1p :")
    for c in z_raw.sort_values(ascending=False).index[:10]:
        print(f"  {c:18s} {z_raw[c]:10.1f} -> {z_log[c]:6.1f}")
    print(f"  maximum sur les {len(selected)} colonnes : {z_raw.max():.1f} -> {z_log.max():.1f} ; "
          f"médiane des maxima : {z_raw.median():.1f} -> {z_log.median():.1f}")

    # Échelle des colonnes que log1p corrige mal : log1p(x) vaut presque x tant
    # que x est très inférieur à 1, donc ne comprime rien ; rapport log1p(x)/x
    # proche de 1 = pas de compression.
    print("\nÉchelle des colonnes inspectées (jeu unsup, valeurs brutes, avant log1p) :")
    for c in args.scale_columns:
        x = pd.read_parquet(out / "train_unsup.parquet", columns=[c])[c]
        pos = x[x > 0]
        q, qp = x.quantile([0.5, 0.99]), pos.quantile([0.5, 0.99])
        print(f"  {c} : {len(x)} lignes ; nulles {100 * (x == 0).mean():.1f} % ; "
              f"supérieures ou égales à 1 : {100 * (x >= 1).mean():.3f} %")
        print(f"    toutes les lignes : médiane {q[0.5]:.6g} ; quantile 99 % {q[0.99]:.6g} ; "
              f"max {x.max():.6g}")
        print(f"    lignes non nulles ({len(pos)}) : médiane {qp[0.5]:.6g} ; quantile 99 % "
              f"{qp[0.99]:.6g} ; log1p(x)/x à la médiane {np.log1p(qp[0.5]) / qp[0.5]:.4f}, "
              f"au quantile 99 % {np.log1p(qp[0.99]) / qp[0.99]:.4f}")


if __name__ == "__main__":
    main()
