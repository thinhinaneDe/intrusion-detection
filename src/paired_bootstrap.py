"""Intervalles sur les écarts de rappel entre conditions supervisées, par rééchantillonnage apparié.

Méthode déclarée avant tout résultat (M25). Les lignes de test sont rééchantillonnées
par BLOCS DE TEMPS contigus, avec remise ; les conditions comparées sont évaluées sur
les mêmes lignes tirées (appariement). Les attaques d'une famille arrivent en quelques
rafales (Reconnaissance : 12 blocs de 10 minutes sur 76) : rééchantillonner les lignes
une à une supposerait des observations indépendantes et sous-estimerait fortement
l'incertitude ; ce cas est calculé pour mesurer cet écart.

Grandeur : écart de rappel d'une famille, en points de pourcentage, A - B (effet du
volume) et B - C (effet de la famille inédite à volume constant), à chaque budget.
Deux points de fonctionnement :
  - « lu » : au même taux de faux positifs lu sur le test ; le seuil de chaque condition
    est recalculé à chaque réplication sur les normaux tirés ;
  - « calibré » : seuils fixes de la calibration hors échantillon.
Variante « sans jumeau » : lignes de test sans jumeau dans A, B ni C, pour que la
contamination (M11) ne joue pas.

Usage : python src/paired_bootstrap.py [--config config.toml] [--n-boot 1000]
                                       [--block-minutes 10 5 0] [--families Exploits Reconnaissance]
                                       [--output paired_bootstrap.json]
Une famille nommée « sept autres familles » désigne le groupe des familles non retirées de C.
"""

import argparse
import json
from pathlib import Path

import numpy as np
import pandas as pd

from evaluate import twin_flags
from prepare import load_config

CONDITIONS = ["A", "B", "C"]
GROUP_OTHERS = "sept autres familles"  # attaques des familles non retirées de C, même définition que block_ci.py
COMPARISONS = {"A − B": ("A", "B"), "B − C": ("B", "C")}


def block_weights(rng: np.random.Generator, block_id: np.ndarray, n_blocks: int, n_rows: int,
                  block_minutes: int) -> np.ndarray:
    """Poids entiers de chaque ligne pour un tirage avec remise (blocs de temps, ou lignes si 0)."""
    if block_minutes == 0:
        return np.bincount(rng.integers(0, n_rows, n_rows), minlength=n_rows).astype(np.float64)
    counts = np.bincount(rng.integers(0, n_blocks, n_blocks), minlength=n_blocks)
    return counts[block_id].astype(np.float64)


def matched_threshold(sorted_scores: np.ndarray, cum_weights: np.ndarray, fpr: float) -> float:
    """Plus petit score dont le poids cumulé atteint la part 1 - fpr des normaux (tirés)."""
    k = np.searchsorted(cum_weights, (1 - fpr) * cum_weights[-1], side="left")
    return float(sorted_scores[min(k, len(sorted_scores) - 1)])


def run(cfg: dict, out: Path, families: list[str], n_boot: int, block_minutes: int,
        seed: int) -> dict:
    """Une variante de rééchantillonnage ; retourne point estimé et distribution des écarts."""
    budgets = [str(b) for b in cfg["evaluation"]["fpr_budgets"]]
    test = pd.read_parquet(out / "test.parquet", columns=["Stime", "label", "family"])
    label, family = test["label"].to_numpy(), test["family"].to_numpy()
    scores = {c: np.load(out / "results" / f"supervised_{c}_test_scores.npy") for c in CONDITIONS}
    cal = {c: {b: json.loads((out / "results" / f"supervised_{c}.json").read_text())
               ["evaluation"]["budgets"][b]["threshold"] for b in budgets} for c in CONDITIONS}
    no_twin = ~np.any([twin_flags(c, out)["has_twin"].to_numpy() for c in CONDITIONS], axis=0)

    n = len(test)
    minutes = block_minutes if block_minutes else 1
    block_id = ((test["Stime"] - test["Stime"].min()) // (minutes * 60)).astype(int).to_numpy()
    n_blocks = int(block_id.max()) + 1
    normal = np.flatnonzero(label == 0)
    order = {c: np.argsort(scores[c][normal], kind="stable") for c in CONDITIONS}
    sorted_scores = {c: scores[c][normal][order[c]] for c in CONDITIONS}
    removed = cfg["families"]["removed"]
    att = {f: np.flatnonzero((~np.isin(family, removed) if f == GROUP_OTHERS else family == f) & (label == 1))
           for f in families}
    cal_hit = {(c, b, f): scores[c][att[f]] > cal[c][b] for c in CONDITIONS for b in budgets for f in families}
    subsets = {"toutes les lignes": {f: np.ones(len(att[f]), bool) for f in families},
               "sans jumeau": {f: no_twin[att[f]] for f in families}}

    rng = np.random.default_rng(seed)
    keys = [(kind, sub, b, f, c) for kind in ("lu", "calibré") for sub in subsets for b in budgets
            for f in families for c in CONDITIONS]
    samples = {k: np.empty(n_boot + 1) for k in keys}
    for r in range(n_boot + 1):  # r = 0 : point estimé (poids tous égaux à 1)
        w = np.ones(n) if r == 0 else block_weights(rng, block_id, n_blocks, n, block_minutes)
        w_norm = w[normal]
        cum = {c: np.cumsum(w_norm[order[c]]) for c in CONDITIONS}
        for b in budgets:
            thr = {c: matched_threshold(sorted_scores[c], cum[c], float(b)) for c in CONDITIONS}
            for f in families:
                wf = w[att[f]]
                for sub, masks in subsets.items():
                    wm = wf * masks[f]
                    denom = wm.sum()
                    for c in CONDITIONS:
                        hit_l = scores[c][att[f]] > thr[c]
                        samples[("lu", sub, b, f, c)][r] = (wm * hit_l).sum() / denom if denom else np.nan
                        samples[("calibré", sub, b, f, c)][r] = (
                            (wm * cal_hit[(c, b, f)]).sum() / denom if denom else np.nan)

    result = {"block_minutes": block_minutes, "n_blocks": n_blocks, "n_boot": n_boot,
              "blocks_with_family": {f: int(len(np.unique(block_id[att[f]]))) for f in families},
              "rows": {}}
    for kind, sub, b, f in sorted({(k[0], k[1], k[2], k[3]) for k in keys}):  # trié : sortie identique d'une exécution à l'autre
        entry = {}
        for name, (x, y) in COMPARISONS.items():
            d = 100 * (samples[(kind, sub, b, f, x)] - samples[(kind, sub, b, f, y)])
            lo, hi = np.nanpercentile(d[1:], [2.5, 97.5])
            entry[name] = {"point": float(d[0]), "lo": float(lo), "hi": float(hi)}
        entry["recall"] = {c: float(100 * samples[(kind, sub, b, f, c)][0]) for c in CONDITIONS}
        # Réplications sans aucune ligne de la famille : rappel non défini, ignorées par nanpercentile.
        entry["n_undefined"] = int(np.isnan(samples[(kind, sub, b, f, "B")][1:]).sum())
        result["rows"][f"{kind}|{sub}|{b}|{f}"] = entry
    return result


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--config", type=Path, default=Path("config.toml"))
    parser.add_argument("--n-boot", type=int, default=1000)
    parser.add_argument("--block-minutes", type=int, nargs="+", default=[10, 5, 0],
                        help="Taille des blocs de temps ; 0 = lignes une à une. La première est la variante principale")
    parser.add_argument("--families", nargs="+", default=["Reconnaissance", "Exploits"])
    parser.add_argument("--seed", type=int, default=42)
    parser.add_argument("--output", default="paired_bootstrap.json",
                        help="Nom du fichier écrit dans results/ (les tirages ne dépendent pas des familles)")
    args = parser.parse_args()
    cfg = load_config(args.config)
    out = Path(cfg["data"]["processed_dir"])
    budgets = [str(b) for b in cfg["evaluation"]["fpr_budgets"]]

    results = {}
    for m in args.block_minutes:
        results[m] = run(cfg, out, args.families, args.n_boot, m, args.seed)
        label = f"blocs de {m} minutes" if m else "lignes une à une (indépendance supposée)"
        print(f"\n{'=' * 78}\nRééchantillonnage apparié : {label}, {args.n_boot} réplications, graine "
              f"{args.seed} ; {results[m]['n_blocks']} blocs ; blocs contenant la famille : "
              f"{results[m]['blocks_with_family']}\n{'=' * 78}", flush=True)
        for f in args.families:
            for kind in ("lu", "calibré"):
                for sub in ("toutes les lignes", "sans jumeau"):
                    print(f"\n{f}, rappel {'lu au même taux' if kind == 'lu' else 'au seuil calibré'}, {sub} "
                          "(écarts en points, intervalle à 95 %) :")
                    for b in budgets:
                        e = results[m]["rows"][f"{kind}|{sub}|{b}|{f}"]
                        rec = e["recall"]
                        print(f"  budget {100 * float(b):g} % : A {rec['A']:6.2f}  B {rec['B']:6.2f}  "
                              f"C {rec['C']:6.2f} ; réplications sans la famille {e['n_undefined']} ; " + " ; ".join(
                                  f"{name} {e[name]['point']:+7.2f} [{e[name]['lo']:+7.2f} ; "
                                  f"{e[name]['hi']:+7.2f}]" for name in COMPARISONS))
    (out / "results").mkdir(exist_ok=True)
    (out / "results" / args.output).write_text(json.dumps(results, indent=2))
    print(f"\nRésultats écrits dans {out / 'results' / args.output}")


if __name__ == "__main__":
    main()
