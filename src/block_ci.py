"""Intervalles par blocs de temps sur les chiffres du README, pour tous les modèles (M27).

Méthode de M25 : rééchantillonnage avec remise de blocs de temps contigus du test
(10 minutes), 1 000 réplications, graine 42, intervalle à 95 % par percentiles. Les
mêmes blocs sont tirés pour tous les modèles dans une réplication. Les attaques d'une
famille arrivent en rafales : rééchantillonner les lignes une à une, ou utiliser un
intervalle de Wilson, donnerait des intervalles trop étroits.

Grandeurs, pour chaque modèle (Isolation Forest, autoencodeurs moyen et petit,
supervisé A, B, C) : AUC-PR ; à chaque budget, taux de faux positifs observé au seuil
calibré ; rappel global, par famille et par groupe de familles (« retirées de C » :
Exploits et Reconnaissance ; « sept autres ») au seuil calibré (seuils fixes) et au même
taux lu sur le test (seuil recalculé à chaque réplication sur les normaux tirés).

Écarts appariés entre les trois modèles non supervisés (petit − moyen, Isolation Forest −
moyen, Isolation Forest − petit) : AUC-PR et rappel global à chaque budget.

Le point estimé (poids tous égaux à 1) est comparé aux valeurs déjà écrites par les
modèles : il doit coïncider.

Usage : python src/block_ci.py [--config config.toml] [--n-boot 1000] [--block-minutes 10]
"""

import argparse
import json
from pathlib import Path

import numpy as np
import pandas as pd

from prepare import load_config

MODELS = ["isolation_forest", "autoencoder_moyen", "autoencoder_petit",
          "supervised_A", "supervised_B", "supervised_C"]
PAIRS = [("autoencoder_petit", "autoencoder_moyen"), ("isolation_forest", "autoencoder_moyen"),
         ("isolation_forest", "autoencoder_petit")]
REMOVED = ["Exploits", "Reconnaissance"]
GROUP_REMOVED, GROUP_OTHERS = "retirées de C (Exploits, Reconnaissance)", "sept autres familles"


def block_weights(rng: np.random.Generator, block_id: np.ndarray, n_blocks: int) -> np.ndarray:
    """Poids de chaque ligne pour un tirage avec remise de blocs de temps."""
    return np.bincount(rng.integers(0, n_blocks, n_blocks), minlength=n_blocks)[block_id].astype(np.float64)


def grouped_average_precision(w_sorted: np.ndarray, y_sorted: np.ndarray,
                              boundaries: np.ndarray) -> float:
    """Précision moyenne pondérée, calculée aux seuils distincts (comme scikit-learn)."""
    tp = np.cumsum(w_sorted * y_sorted)[boundaries]
    fp = np.cumsum(w_sorted * (1 - y_sorted))[boundaries]
    seen = tp + fp
    # Aux seuils où aucune ligne tirée n'a encore été rencontrée, la précision n'est pas définie
    # et son poids (l'incrément de rappel) est nul : on la remplace par 0.
    precision = np.divide(tp, seen, out=np.zeros_like(tp), where=seen > 0)
    return float((np.diff(np.concatenate(([0.0], tp))) * precision).sum() / tp[-1])


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--config", type=Path, default=Path("config.toml"))
    parser.add_argument("--n-boot", type=int, default=1000)
    parser.add_argument("--block-minutes", type=int, default=10)
    parser.add_argument("--seed", type=int, default=42)
    args = parser.parse_args()
    cfg = load_config(args.config)
    out = Path(cfg["data"]["processed_dir"])
    budgets = [str(b) for b in cfg["evaluation"]["fpr_budgets"]]

    test = pd.read_parquet(out / "test.parquet", columns=["Stime", "label", "family"])
    label, family = test["label"].to_numpy(), test["family"].to_numpy()
    n = len(test)
    block_id = ((test["Stime"] - test["Stime"].min()) // (args.block_minutes * 60)).astype(int).to_numpy()
    n_blocks = int(block_id.max()) + 1
    normal, attack = np.flatnonzero(label == 0), np.flatnonzero(label == 1)
    fam_att = family[attack]
    families = sorted(set(fam_att))
    entities = {"all": np.ones(len(attack), bool), **{f: fam_att == f for f in families},
                GROUP_REMOVED: np.isin(fam_att, REMOVED), GROUP_OTHERS: ~np.isin(fam_att, REMOVED)}

    pre = {}
    for m in MODELS:
        scores = np.load(out / "results" / f"{m}_test_scores.npy")
        js = json.loads((out / "results" / f"{m}.json").read_text())["evaluation"]
        desc = np.argsort(-scores, kind="stable")
        s_sorted = scores[desc]
        bounds = np.append(np.flatnonzero(s_sorted[1:] != s_sorted[:-1]), n - 1)
        order = np.argsort(scores[normal], kind="stable")
        pre[m] = {"scores": scores, "desc": desc, "y_sorted": label[desc].astype(np.float64),
                  "bounds": bounds, "order": order, "norm_sorted": scores[normal][order],
                  "thr_cal": {b: js["budgets"][b]["threshold"] for b in budgets}, "json": js}

    def statistics(w: np.ndarray) -> dict:
        """Toutes les grandeurs d'une réplication de poids `w`."""
        w_norm, w_att = w[normal], w[attack]
        res = {}
        for m, p in pre.items():
            row = {"ap": grouped_average_precision(w[p["desc"]], p["y_sorted"], p["bounds"])}
            cum = np.cumsum(w_norm[p["order"]])
            s_att, s_norm = p["scores"][attack], p["scores"][normal]
            for b in budgets:
                t_c = p["thr_cal"][b]
                k = np.searchsorted(cum, (1 - float(b)) * cum[-1], side="left")
                t_m = p["norm_sorted"][min(k, len(cum) - 1)]
                row[f"fpr_cal|{b}"] = (w_norm * (s_norm > t_c)).sum() / w_norm.sum()
                for kind, t in (("cal", t_c), ("matched", t_m)):
                    hit = s_att > t
                    for ent, mask in entities.items():
                        den = (w_att * mask).sum()
                        row[f"recall_{kind}|{b}|{ent}"] = (w_att * mask * hit).sum() / den if den else np.nan
            res[m] = row
        return res

    point = statistics(np.ones(n))
    print("Contrôle : point estimé contre valeurs déjà écrites par les modèles (écart absolu maximal)")
    for m, p in pre.items():
        d_ap = abs(point[m]["ap"] - p["json"]["average_precision"])
        d_rec = max(max(abs(point[m][f"recall_cal|{b}|all"] - p["json"]["budgets"][b]["recall"]),
                        abs(point[m][f"recall_matched|{b}|all"] - p["json"]["budgets"][b]["matched"]["recall"]),
                        abs(point[m][f"fpr_cal|{b}"] - p["json"]["budgets"][b]["fpr_test"])) for b in budgets)
        print(f"  {m:20s} AUC-PR {d_ap:.2e} ; rappels et taux {d_rec:.2e}")

    rng = np.random.default_rng(args.seed)
    reps = {m: {k: np.empty(args.n_boot) for k in point[m]} for m in MODELS}
    for r in range(args.n_boot):
        s = statistics(block_weights(rng, block_id, n_blocks))
        for m in MODELS:
            for k, v in s[m].items():
                reps[m][k][r] = v
        if (r + 1) % 200 == 0:
            print(f"  {r + 1} réplications", flush=True)

    result = {"block_minutes": args.block_minutes, "n_blocks": n_blocks, "n_boot": args.n_boot,
              "seed": args.seed, "entities": list(entities), "models": {}}
    for m in MODELS:
        result["models"][m] = {}
        for k, v in point[m].items():
            lo, hi = np.nanpercentile(reps[m][k], [2.5, 97.5])
            result["models"][m][k] = {"point": float(v), "lo": float(lo), "hi": float(hi)}
    # Écarts APPARIÉS entre modèles non supervisés (mêmes blocs tirés dans chaque réplication) :
    # un intervalle sur la différence, non la comparaison de deux intervalles séparés.
    keys = ["ap"] + [f"recall_{k}|{b}|all" for k in ("cal", "matched") for b in budgets]
    result["paired"] = {}
    for x, y in PAIRS:
        entry = {}
        for k in keys:
            d = reps[x][k] - reps[y][k]
            lo, hi = np.nanpercentile(d, [2.5, 97.5])
            entry[k] = {"point": float(point[x][k] - point[y][k]), "lo": float(lo), "hi": float(hi)}
        result["paired"][f"{x} - {y}"] = entry
    (out / "results").mkdir(exist_ok=True)
    (out / "results" / "block_ci.json").write_text(json.dumps(result, indent=2))
    print(f"Résultats écrits dans {out / 'results' / 'block_ci.json'} ({n_blocks} blocs de "
          f"{args.block_minutes} minutes, {args.n_boot} réplications, graine {args.seed})")
    for m in MODELS:
        e = result["models"][m]["ap"]
        print(f"  {m:20s} AUC-PR {e['point']:.4f} [{e['lo']:.4f} ; {e['hi']:.4f}]")


if __name__ == "__main__":
    main()
