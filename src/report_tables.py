"""Tables Markdown du README, générées depuis les résultats écrits par les modèles.

Aucun chiffre du README n'est recopié à la main : les tables viennent de
`results/block_ci.json` (intervalles par blocs de temps, M27),
`results/paired_bootstrap.json` (écarts appariés, M25) et des JSON des modèles, pour la
version SANS TTL (résultat principal) et la version AVEC TTL (mesure du raccourci).

Usage : python src/report_tables.py [--sans config_sans_ttl.toml] [--avec config.toml]
"""

import argparse
import json
from pathlib import Path

from prepare import load_config

MODELS = [("isolation_forest", "Isolation Forest"), ("autoencoder_moyen", "Autoencodeur moyen"),
          ("autoencoder_petit", "Autoencodeur petit"), ("supervised_A", "Supervisé A"),
          ("supervised_B", "Supervisé B"), ("supervised_C", "Supervisé C")]
FAMILIES = ["Analysis", "Backdoors", "DoS", "Exploits", "Fuzzers", "Generic", "Reconnaissance",
            "Shellcode", "Worms"]
FAMILY_N = {"Analysis": 301, "Backdoors": 299, "DoS": 825, "Exploits": 4042, "Fuzzers": 3991,
            "Generic": 2833, "Reconnaissance": 1740, "Shellcode": 223, "Worms": 24}  # M09
G_REMOVED, G_OTHERS = "retirées de C (Exploits, Reconnaissance)", "sept autres familles"


def ci(e: dict, scale: float = 100, digits: int = 1) -> str:
    """« valeur [borne basse ; borne haute] » d'une entrée de block_ci.json."""
    return f"{scale * e['point']:.{digits}f} [{scale * e['lo']:.{digits}f} ; {scale * e['hi']:.{digits}f}]"


def table(header: list[str], rows: list[list[str]]) -> str:
    """Table Markdown."""
    return "\n".join(["| " + " | ".join(header) + " |", "|" + "|".join("---" for _ in header) + "|",
                      *["| " + " | ".join(r) + " |" for r in rows]])


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--sans", type=Path, default=Path("config_sans_ttl.toml"))
    parser.add_argument("--avec", type=Path, default=Path("config.toml"))
    args = parser.parse_args()
    cfg = load_config(args.avec)
    dirs = {"sans": Path(load_config(args.sans)["data"]["processed_dir"]),
            "avec": Path(cfg["data"]["processed_dir"])}
    budgets = [str(b) for b in cfg["evaluation"]["fpr_budgets"]]
    bl = lambda b: f"{100 * float(b):g} %"  # noqa: E731
    ci_ = {k: json.loads((d / "results" / "block_ci.json").read_text())["models"] for k, d in dirs.items()}
    js = {(k, m): json.loads((d / "results" / f"{m}.json").read_text()) for k, d in dirs.items()
          for m, _ in MODELS}
    pb = {k: json.loads((d / "results" / "paired_bootstrap.json").read_text())["10"] for k, d in dirs.items()}

    print("### T1 — AUC-PR au test [intervalle par blocs], prévalence 1,395 %\n")
    print(table(["Modèle", "Sans TTL (principal)", "Avec TTL (raccourci)"],
                [[lab, ci(ci_["sans"][m]["ap"], 1, 3), ci(ci_["avec"][m]["ap"], 1, 3)] for m, lab in MODELS]))

    for b in budgets:
        print(f"\n### T2 — Sans TTL, budget de faux positifs {bl(b)} (en %, [intervalle par blocs])\n")
        print(table(["Modèle", "Taux de faux positifs observé", "Rappel au seuil calibré",
                     "Rappel lu au même taux (non déployable)"],
                    [[lab, ci(ci_["sans"][m][f"fpr_cal|{b}"], 100, 4), ci(ci_["sans"][m][f"recall_cal|{b}|all"]),
                      ci(ci_["sans"][m][f"recall_matched|{b}|all"])] for m, lab in MODELS]))

    for b in ("0.001", "0.0001"):
        print(f"\n### T3 — Sans TTL, rappel par famille lu au même taux {bl(b)} (en %, [intervalle par blocs])\n")
        print(table(["Famille (n test)", *[lab for _, lab in MODELS]],
                    [[f"{f} ({FAMILY_N[f]})", *[ci(ci_["sans"][m][f"recall_matched|{b}|{f}"], 100, 1) for m, _ in MODELS]]
                     for f in FAMILIES]))

    print("\n### T4 — Sans TTL, deux régimes : familles retirées de C contre les sept autres (rappel lu au même taux, en %)\n")
    rows = []
    for m, lab in MODELS:
        for b in ("0.001", "0.0001"):
            rows.append([lab, bl(b), ci(ci_["sans"][m][f"recall_matched|{b}|{G_OTHERS}"]),
                         ci(ci_["sans"][m][f"recall_matched|{b}|{G_REMOVED}"])])
    print(table(["Modèle", "Budget", "Sept autres familles (vues par A, B, C)", "Exploits + Reconnaissance (retirées de C)"], rows))

    for k, lab in (("sans", "Sans TTL"), ("avec", "Avec TTL")):
        print(f"\n### T5 — {lab} : écarts de rappel lu au même taux, en points, IC par blocs apparié\n")
        rows = []
        for fam in ("Reconnaissance", "Exploits"):
            for b in ("0.001", "0.0001"):
                e = pb[k]["rows"][f"lu|toutes les lignes|{b}|{fam}"]
                r = e["recall"]
                rows.append([fam, bl(b), f"{r['A']:.1f} / {r['B']:.1f} / {r['C']:.1f}",
                             f"{e['A − B']['point']:+.1f} [{e['A − B']['lo']:+.1f} ; {e['A − B']['hi']:+.1f}]",
                             f"{e['B − C']['point']:+.1f} [{e['B − C']['lo']:+.1f} ; {e['B − C']['hi']:+.1f}]"])
        print(table(["Famille", "Budget", "Rappel A / B / C", "A − B (volume)", "B − C (famille inédite)"], rows))

    for b in ("0.01", "0.001"):
        print(f"\n### T6 — Mesure du raccourci TTL : rappel lu au même taux {bl(b)} (en %, [intervalle par blocs])\n")
        print(table(["Modèle", "Sans TTL", "Avec TTL"],
                    [[lab, ci(ci_["sans"][m][f"recall_matched|{b}|all"]), ci(ci_["avec"][m][f"recall_matched|{b}|all"])]
                     for m, lab in MODELS]))

    for k, lab in (("sans", "Sans TTL"), ("avec", "Avec TTL")):
        print(f"\n### T8 — {lab} : écarts APPARIÉS entre modèles non supervisés (points de rappel ou d'AUC-PR ; [IC par blocs])\n")
        paired = json.loads((dirs[k] / "results" / "block_ci.json").read_text())["paired"]
        rows = []
        for name, e in paired.items():
            x, y = name.split(" - ")
            label = {m: l for m, l in MODELS}
            cells = [f"{e['ap']['point']:+.3f} [{e['ap']['lo']:+.3f} ; {e['ap']['hi']:+.3f}]"]
            for b in budgets:
                v = e[f"recall_matched|{b}|all"]
                cells.append(f"{100 * v['point']:+.2f} [{100 * v['lo']:+.2f} ; {100 * v['hi']:+.2f}]")
            rows.append([f"{label[x]} − {label[y]}", *cells])
        print(table(["Écart", "AUC-PR", *[f"Rappel lu au même taux {bl(b)}" for b in budgets]], rows))

    print("\n### T7 — Supervisé : rappel des attaques tenues à l'écart (jour 2) contre rappel du test, au seuil calibré "
          "(en %, sans intervalle par blocs)\n")
    rows = []
    for k, lab in (("sans", "sans TTL"), ("avec", "avec TTL")):
        for c in ("A", "B", "C"):
            p = js[(k, f"supervised_{c}")]
            for b in budgets:
                o = p["oof_attack_recall"][b]
                seen = {r["family"] for r in o["by_family"]}
                tb = p["evaluation"]["budgets"][b]
                hits = sum(r["hits"] for r in tb["by_family"] if r["family"] in seen)
                n = sum(r["n"] for r in tb["by_family"] if r["family"] in seen)
                rows.append([f"{c} ({lab})", bl(b), f"{100 * o['recall']:.1f}", f"{100 * hits / n:.1f}"])
    print(table(["Condition", "Budget", "Tenues à l'écart (jour 2)", "Test, mêmes familles"], rows))


if __name__ == "__main__":
    main()
