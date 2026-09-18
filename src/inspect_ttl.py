"""Ce que séparent les colonnes TTL (sttl, dttl, ct_state_ttl) entre normaux et attaques.

Le modèle supervisé s'appuie surtout sur `ct_state_ttl` (M24). Ce script mesure,
sur les jeux écrits, la distribution du TTL source par étiquette et par famille,
et de `ct_state_ttl`, pour chaque jour. Descriptif uniquement : aucun modèle,
aucun réglage.

Usage : python src/inspect_ttl.py [--config config.toml] [--high 200]
"""

import argparse
from pathlib import Path

import pandas as pd

from prepare import load_config


def summarize(df: pd.DataFrame, label: str, high: int) -> None:
    """Affiche, par famille, la part des flux à TTL source élevé et les valeurs de ct_state_ttl."""
    print(f"\n{label} : {len(df)} flux")
    print(f"  {'famille':15s} {'lignes':>8s} {'sttl >= ' + str(high):>10s} {'dttl >= ' + str(high):>10s}"
          f"  valeurs de sttl les plus fréquentes ; ct_state_ttl")
    for fam, g in df.groupby("family"):
        top = g["sttl"].value_counts(normalize=True).head(3)
        ct = g["ct_state_ttl"].value_counts(normalize=True).head(3)
        print(f"  {fam:15s} {len(g):8d} {100 * (g['sttl'] >= high).mean():9.2f}% "
              f"{100 * (g['dttl'] >= high).mean():9.2f}%  "
              + ", ".join(f"{int(k)} : {100 * v:.1f} %" for k, v in top.items()) + " ; "
              + ", ".join(f"{int(k)} : {100 * v:.1f} %" for k, v in ct.items()))


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--config", type=Path, default=Path("config.toml"))
    parser.add_argument("--high", type=int, default=200,
                        help="Seuil à partir duquel un TTL est dit « élevé »")
    args = parser.parse_args()
    out = Path(load_config(args.config)["data"]["processed_dir"])
    cols = ["family", "label", "sttl", "dttl", "ct_state_ttl"]
    summarize(pd.read_parquet(out / "train_A.parquet", columns=cols), "Jour 2 (jeu A, entraînement)",
              args.high)
    summarize(pd.read_parquet(out / "test.parquet", columns=cols), "Jour 1 (test)", args.high)
    for label, path in (("Jour 2 (A)", "train_A.parquet"), ("Jour 1 (test)", "test.parquet")):
        df = pd.read_parquet(out / path, columns=cols)
        att, nor = df[df["label"] == 1], df[df["label"] == 0]
        print(f"\n{label} : part à sttl >= {args.high} : attaques {100 * (att['sttl'] >= args.high).mean():.2f} %, "
              f"normaux {100 * (nor['sttl'] >= args.high).mean():.2f} % ; ct_state_ttl : attaques "
              + ", ".join(f"{int(k)} : {100 * v:.1f} %" for k, v in
                          att["ct_state_ttl"].value_counts(normalize=True).sort_index().items())
              + " ; normaux "
              + ", ".join(f"{int(k)} : {100 * v:.1f} %" for k, v in
                          nor["ct_state_ttl"].value_counts(normalize=True).sort_index().items()))


if __name__ == "__main__":
    main()
