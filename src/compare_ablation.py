"""Compare, côte à côte, les résultats avec et sans les colonnes TTL (ablation, M25).

Lit les résultats écrits par les modèles dans les deux jeux de données (`config.toml`
et `config_sans_ttl.toml`) : Isolation Forest, autoencodeurs moyen et petit,
supervisé A, B et C. Aucun calcul de modèle. Mesure ce que le banc d'essai offre comme
raccourci : l'écart entre les deux colonnes est celui de la disparition des trois
colonnes TTL.

Usage : python src/compare_ablation.py [--with config.toml] [--without config_sans_ttl.toml]
"""

import argparse
import json
from pathlib import Path

from prepare import load_config

MODELS = [("isolation_forest", "Isolation Forest"), ("autoencoder_moyen", "Autoencodeur moyen"),
          ("autoencoder_petit", "Autoencodeur petit"), ("supervised_A", "Supervisé A"),
          ("supervised_B", "Supervisé B"), ("supervised_C", "Supervisé C")]
FAMILIES = ["Exploits", "Reconnaissance"]


def load(out: Path, name: str) -> dict | None:
    """Résultats JSON d'un modèle, ou None s'ils n'existent pas."""
    path = out / "results" / f"{name}.json"
    return json.loads(path.read_text()) if path.exists() else None


def pct(x: float, digits: int = 2) -> str:
    return f"{100 * x:.{digits}f}"


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--with", dest="with_cfg", type=Path, default=Path("config.toml"))
    parser.add_argument("--without", dest="without_cfg", type=Path, default=Path("config_sans_ttl.toml"))
    args = parser.parse_args()
    cfg = load_config(args.with_cfg)
    dirs = {"avec": Path(cfg["data"]["processed_dir"]),
            "sans": Path(load_config(args.without_cfg)["data"]["processed_dir"])}
    budgets = [str(b) for b in cfg["evaluation"]["fpr_budgets"]]
    res = {(k, name): load(d, name) for k, d in dirs.items() for name, _ in MODELS}

    print("AUC-PR au test (avec TTL / sans TTL) ; prévalence 1,395 % :")
    for name, label in MODELS:
        a, s = res[("avec", name)], res[("sans", name)]
        print(f"  {label:20s} " + (f"{a['evaluation']['average_precision']:.4f}" if a else "n/a")
              + " / " + (f"{s['evaluation']['average_precision']:.4f}" if s else "n/a"))

    for b in budgets:
        print(f"\nBudget {pct(float(b), 3)} % (avec TTL / sans TTL, en %) :")
        print(f"  {'modèle':20s} {'FPR observé':>18s} {'rappel calibré':>18s} {'rappel lu au même taux':>26s}")
        for name, label in MODELS:
            a, s = res[("avec", name)], res[("sans", name)]
            if not (a and s):
                print(f"  {label:20s} résultats manquants")
                continue
            ea, es = a["evaluation"]["budgets"][b], s["evaluation"]["budgets"][b]
            print(f"  {label:20s} {pct(ea['fpr_test'], 4):>8s} / {pct(es['fpr_test'], 4):<8s} "
                  f"{pct(ea['recall']):>8s} / {pct(es['recall']):<8s} "
                  f"{pct(ea['matched']['recall']):>11s} / {pct(es['matched']['recall']):<11s}")

    for fam in FAMILIES:
        print(f"\n{fam} : rappel lu au même taux (avec TTL / sans TTL, en %), aux budgets "
              + ", ".join(pct(float(b), 3) + " %" for b in budgets))
        for name, label in MODELS:
            a, s = res[("avec", name)], res[("sans", name)]
            if not (a and s):
                continue
            cells = []
            for b in budgets:
                ra = next(r for r in a["evaluation"]["budgets"][b]["matched"]["by_family"] if r["family"] == fam)
                rs = next(r for r in s["evaluation"]["budgets"][b]["matched"]["by_family"] if r["family"] == fam)
                cells.append(f"{pct(ra['recall']):>6s} / {pct(rs['recall']):<6s}")
            print(f"  {label:20s} " + "   ".join(cells))

    print("\nRappel de toutes les familles au budget de référence, lu au même taux "
          f"({pct(cfg['evaluation']['reference_fpr'], 3)} %) — avec TTL / sans TTL, en % :")
    ref = str(cfg["evaluation"]["reference_fpr"])
    families = [r["family"] for r in res[("avec", "supervised_A")]["evaluation"]["budgets"][ref]["matched"]["by_family"]] \
        if res[("avec", "supervised_A")] else []
    for fam in families:
        cells = []
        for name, label in MODELS:
            a, s = res[("avec", name)], res[("sans", name)]
            if not (a and s):
                cells.append("   n/a")
                continue
            ra = next(r for r in a["evaluation"]["budgets"][ref]["matched"]["by_family"] if r["family"] == fam)
            rs = next(r for r in s["evaluation"]["budgets"][ref]["matched"]["by_family"] if r["family"] == fam)
            cells.append(f"{pct(ra['recall'], 1):>5s}/{pct(rs['recall'], 1):<5s}")
        print(f"  {fam:15s} " + " ".join(cells))
    print("  colonnes : " + ", ".join(label for _, label in MODELS))

    print("\nÉcarts B − C et A − B par rééchantillonnage apparié (blocs de 10 minutes, IC à 95 %) :")
    for k, d in dirs.items():
        path = d / "results" / "paired_bootstrap.json"
        if not path.exists():
            print(f"  {k} TTL : non calculé")
            continue
        r = json.loads(path.read_text())["10"]
        for fam in FAMILIES:
            for kind in ("lu", "calibré"):
                for sub in ("toutes les lignes", "sans jumeau"):
                    for b in budgets[1:]:
                        e = r["rows"][f"{kind}|{sub}|{b}|{fam}"]
                        print(f"  {k} TTL, {fam:14s} {kind:7s} {sub:17s} budget {pct(float(b), 3):>5s} % : "
                              f"B − C {e['B − C']['point']:+7.2f} [{e['B − C']['lo']:+7.2f} ; {e['B − C']['hi']:+7.2f}] ; "
                              f"A − B {e['A − B']['point']:+7.2f} [{e['A − B']['lo']:+7.2f} ; {e['A − B']['hi']:+7.2f}]")


if __name__ == "__main__":
    main()
