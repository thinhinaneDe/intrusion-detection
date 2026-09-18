"""Compare les flux normaux des deux jours : où diffèrent-ils, et d'où vient la queue du jour 2 ?

Contexte (M16) : les scores de l'Isolation Forest des normaux du jour 2 ont une
queue plus lourde que ceux du jour 1, ce qui rend la calibration conservatrice.
Ce script mesure, sans rien ajuster :

  1. les colonnes nominales : parts par jour, distance de variation totale,
     catégories les plus différentes ;
  2. les colonnes numériques : statistique de Kolmogorov-Smirnov entre les deux
     jours (invariante par transformation monotone, donc sans log1p), médianes
     et quantiles 99 % par jour ;
  3. le lien avec la queue : parmi les normaux dont le score dépasse un seuil,
     quelles catégories sont sur-représentées, et pour chaque catégorie le taux
     de dépassement à chaque jour.

Descriptif uniquement : les normaux du test servent ici à décrire une
différence entre les jours, pas à régler un seuil ni un modèle.

Usage : python src/inspect_normals.py [--config config.toml] [--tail-quantile 0.99]
"""

import argparse
import json
from pathlib import Path

import numpy as np
import pandas as pd
from scipy.stats import ks_2samp

from prepare import load_config


def nominal_report(tr: pd.DataFrame, te: pd.DataFrame, col: str) -> None:
    """Parts par jour d'une colonne nominale, et catégories les plus différentes."""
    p2 = tr[col].value_counts(normalize=True)
    p1 = te[col].value_counts(normalize=True)
    cats = p1.index.union(p2.index)
    d = pd.DataFrame({"jour2": p2.reindex(cats, fill_value=0), "jour1": p1.reindex(cats, fill_value=0)})
    d["ecart"] = d["jour1"] - d["jour2"]
    tv = 0.5 * d["ecart"].abs().sum()
    print(f"  {col} : {len(p2)} catégories au jour 2, {len(p1)} au jour 1 ; "
          f"distance de variation totale {tv:.4f}")
    for c, r in d.reindex(d["ecart"].abs().sort_values(ascending=False).index).head(6).iterrows():
        print(f"    {c:10s} jour 2 {100 * r['jour2']:7.3f} %  jour 1 {100 * r['jour1']:7.3f} %  "
              f"écart {100 * r['ecart']:+7.3f} pts")


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--config", type=Path, default=Path("config.toml"))
    parser.add_argument("--tail-quantile", type=float, default=0.99,
                        help="Quantile des scores hors échantillon du jour 2 servant de seuil de queue")
    args = parser.parse_args()
    cfg = load_config(args.config)
    out = Path(cfg["data"]["processed_dir"])
    cols = json.loads((out / "manifest.json").read_text())["feature_columns"]
    nominal = cfg["features"]["nominal"]
    numeric = [c for c in cols if c not in nominal]

    tr = pd.read_parquet(out / "train_unsup.parquet")
    test = pd.read_parquet(out / "test.parquet")
    te_mask = (test["label"] == 0).to_numpy()
    te = test[te_mask].reset_index(drop=True)
    print(f"Normaux : jour 2 {len(tr)}, jour 1 {len(te)}")

    print("\n1. Colonnes nominales")
    for col in nominal:
        nominal_report(tr, te, col)

    print("\n2. Colonnes numériques, classées par statistique de Kolmogorov-Smirnov "
          "(0 = distributions identiques, 1 = disjointes)")
    rows = []
    for c in numeric:
        rows.append((c, ks_2samp(tr[c], te[c]).statistic, tr[c].median(), te[c].median(),
                     tr[c].quantile(0.99), te[c].quantile(0.99)))
    ks = pd.DataFrame(rows, columns=["col", "ks", "med2", "med1", "q99_2", "q99_1"]).sort_values(
        "ks", ascending=False)
    print(f"  {'colonne':18s} {'KS':>6s} {'méd. j2':>11s} {'méd. j1':>11s} {'q99 j2':>11s} {'q99 j1':>11s}")
    for r in ks.itertuples():
        print(f"  {r.col:18s} {r.ks:6.3f} {r.med2:11.5g} {r.med1:11.5g} {r.q99_2:11.5g} {r.q99_1:11.5g}")
    print(f"  colonnes avec KS > 0,1 : {int((ks['ks'] > 0.1).sum())} sur {len(ks)} ; "
          f"KS > 0,3 : {int((ks['ks'] > 0.3).sum())}")

    print("\n3. Lien avec la queue des scores de l'Isolation Forest (M16)")
    s2 = np.load(out / "results" / "isolation_forest_oof_scores.npy")
    s1 = np.load(out / "results" / "isolation_forest_test_scores.npy")[te_mask]
    t = float(np.quantile(s2, args.tail_quantile))
    tail2, tail1 = s2 > t, s1 > t
    print(f"  seuil = quantile {100 * args.tail_quantile:.2f} % des scores hors échantillon du jour 2 "
          f"= {t:.4f} ; dépassements : jour 2 {tail2.sum()} ({100 * tail2.mean():.3f} %), "
          f"jour 1 {tail1.sum()} ({100 * tail1.mean():.3f} %)")
    for col in nominal:
        d = pd.DataFrame({"n2": tr[col].value_counts(), "n1": te[col].value_counts()}).fillna(0)
        d["x2"] = tr.loc[tail2, col].value_counts().reindex(d.index, fill_value=0)
        d["x1"] = te.loc[tail1, col].value_counts().reindex(d.index, fill_value=0)
        d = d.sort_values("x2", ascending=False).head(6)
        print(f"  {col} : catégories qui fournissent le plus de dépassements du jour 2")
        print(f"    {'catégorie':10s} {'lignes j2':>9s} {'dépass. j2':>10s} {'taux j2':>8s} "
              f"{'lignes j1':>9s} {'dépass. j1':>10s} {'taux j1':>8s}")
        for c, r in d.iterrows():
            rate2 = 100 * r["x2"] / r["n2"] if r["n2"] else float("nan")
            rate1 = 100 * r["x1"] / r["n1"] if r["n1"] else float("nan")
            print(f"    {c:10s} {int(r['n2']):9d} {int(r['x2']):10d} {rate2:7.2f}% "
                  f"{int(r['n1']):9d} {int(r['x1']):10d} {rate1:7.2f}%")
        print(f"    part des dépassements du jour 2 dans ces 6 catégories : "
              f"{100 * d['x2'].sum() / max(tail2.sum(), 1):.1f} %")

    print("  colonnes numériques, médiane des lignes en dépassement contre médiane du jour "
          "(jour 2, puis jour 1) :")
    for c in ks["col"].head(8):
        print(f"    {c:18s} j2 : dépassements {tr.loc[tail2, c].median():11.5g} "
              f"tous {tr[c].median():11.5g} | j1 : dépassements "
              f"{te.loc[tail1, c].median() if tail1.any() else float('nan'):11.5g} "
              f"tous {te[c].median():11.5g}")

    print("\n4. Combinaisons (proto, state, service) qui fournissent le plus de dépassements du jour 2")
    key2 = list(zip(tr["proto"], tr["state"], tr["service"]))
    key1 = list(zip(te["proto"], te["state"], te["service"]))
    c = pd.DataFrame({"n2": pd.Series(key2).value_counts(), "n1": pd.Series(key1).value_counts()}).fillna(0)
    c["x2"] = pd.Series([k for k, f in zip(key2, tail2) if f]).value_counts().reindex(c.index, fill_value=0)
    c["x1"] = pd.Series([k for k, f in zip(key1, tail1) if f]).value_counts().reindex(c.index, fill_value=0)
    print(f"  {'(proto, state, service)':28s} {'lignes j2':>9s} {'dépass. j2':>10s} {'taux j2':>8s} "
          f"{'lignes j1':>9s} {'dépass. j1':>10s} {'taux j1':>8s}")
    for k, r in c.sort_values("x2", ascending=False).head(10).iterrows():
        r2 = 100 * r["x2"] / r["n2"] if r["n2"] else float("nan")
        r1 = 100 * r["x1"] / r["n1"] if r["n1"] else float("nan")
        print(f"  {str(k):28s} {int(r['n2']):9d} {int(r['x2']):10d} {r2:7.2f}% "
              f"{int(r['n1']):9d} {int(r['x1']):10d} {r1:7.2f}%")
    print(f"  part des dépassements du jour 2 dans ces 10 combinaisons : "
          f"{100 * c.sort_values('x2', ascending=False).head(10)['x2'].sum() / max(tail2.sum(), 1):.1f} %")

    print("\n5. Colonnes qui diffèrent ENTRE LES DEUX JOURS à l'intérieur d'une même catégorie "
          "(KS, médiane et quantile 99 % par jour)")
    for col, val in (("service", "dns"), ("state", "INT")):
        a, b = tr[tr[col] == val], te[te[col] == val]
        res = sorted(((n, ks_2samp(a[n], b[n]).statistic) for n in numeric), key=lambda x: -x[1])[:6]
        print(f"  {col} = {val} ({len(a)} lignes au jour 2, {len(b)} au jour 1)")
        for n, k in res:
            print(f"    {n:18s} KS {k:.3f} ; médiane j2 {a[n].median():11.5g} j1 {b[n].median():11.5g} ; "
                  f"q99 j2 {a[n].quantile(0.99):11.5g} j1 {b[n].quantile(0.99):11.5g}")

    print("\n6. Répartition des dépassements dans le temps (heure UTC : dépassements / normaux)")
    for label, stime, tail in (("jour 2", tr["Stime"], tail2), ("jour 1", te["Stime"], tail1)):
        hour = (stime // 3600).astype(int)
        h = pd.DataFrame({"hour": hour, "x": tail}).groupby("hour")["x"].agg(["sum", "size"])
        print(f"  {label} : " + ", ".join(
            f"{pd.Timestamp(t * 3600, unit='s'):%d %Hh} {int(r['sum'])}/{int(r['size'])}"
            f" ({100 * r['sum'] / r['size']:.1f}%)" for t, r in h.iterrows()))


if __name__ == "__main__":
    main()
