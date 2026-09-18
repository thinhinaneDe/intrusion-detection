"""Préparation des données : découpage temporel, nettoyage, quatre jeux + test.

Étapes (décisions consignées dans report/mesures.md, M05 à M11) :
  1. retrait des doublons de jonction entre les 4 CSV ;
  2. découpage temporel sur Stime : jour 2 = entraînement, jour 1 = test ;
  3. déduplication exacte sur les 49 colonnes, APRÈS le découpage, côté par côté ;
  4. normalisation des libellés (strip, Backdoor -> Backdoors) ;
  5. construction des jeux d'entraînement :
       unsup : normaux du jour 2 uniquement (aucune attaque) ;
       A     : témoin complet, toutes les familles ;
       B     : témoin à volume égal (autant d'attaques que C, tirées au hasard
               proportionnellement aux familles) ;
       C     : traitement, familles `removed` retirées ;
  6. ajustement d'un préprocesseur (encodeur, log1p sur les colonnes à queue
     lourde, scaler) PAR JEU, sur ses seules lignes d'entraînement. Un
     ajustement commun emporterait dans C les statistiques des familles
     retirées, et dans unsup celles des attaques. La liste des colonnes log1p
     est elle-même calculée sur l'entraînement du jeu (asymétrie > seuil).

Le test n'est jamais passé à `fit`. Il est transformé au chargement (`load_set`)
avec le préprocesseur du jeu évalué.

Usage : python src/prepare.py [--config config.toml]
"""

import argparse
import csv
import json
import tomllib
from datetime import datetime, timezone
from pathlib import Path

import joblib
import numpy as np
import pandas as pd
from sklearn.compose import ColumnTransformer
from sklearn.pipeline import make_pipeline
from sklearn.preprocessing import FunctionTransformer, OneHotEncoder, StandardScaler

BOM = b"\xef\xbb\xbf"
SET_NAMES = ["unsup", "A", "B", "C"]


def load_config(path: Path) -> dict:
    """Lit le fichier de configuration TOML."""
    with path.open("rb") as f:
        return tomllib.load(f)


def feature_names(path: Path) -> list[str]:
    """Noms des 49 colonnes d'après le fichier features, espaces retirés.

    Les CSV n'ont pas d'en-tête ; le fichier features contient `ct_src_ ltm`
    avec une espace (M01), normalisé en `ct_src_ltm`.
    """
    with path.open(newline="", encoding="utf-8-sig", errors="replace") as f:
        return [row[1].replace(" ", "") for row in list(csv.reader(f))[1:]]


def _first_line(path: Path) -> bytes:
    with path.open("rb") as f:
        return f.readline().removeprefix(BOM).rstrip(b"\r\n")


def _last_line(path: Path) -> bytes:
    with path.open("rb") as f:
        f.seek(0, 2)
        f.seek(max(0, f.tell() - 4096))
        return f.read().splitlines()[-1].rstrip(b"\r\n")


def read_raw(raw_dir: Path, csv_files: list[str], names: list[str]) -> pd.DataFrame:
    """Lit les CSV en texte brut, sans les doublons de jonction.

    La première ligne des fichiers 2 à 4 est une copie de la dernière ligne du
    fichier précédent (M01) : on le vérifie, puis on l'écarte. Tout est lu en
    chaînes pour que la déduplication compare le texte exact (M06).
    """
    frames = []
    for k, name in enumerate(csv_files):
        path = raw_dir / name
        skip = 0
        if k > 0:
            if _first_line(path) != _last_line(raw_dir / csv_files[k - 1]):
                raise SystemExit(f"{name} : la 1re ligne n'est pas le doublon attendu")
            skip = 1
        frames.append(pd.read_csv(path, header=None, names=names, dtype=str, na_filter=False,
                                  encoding="utf-8-sig", skiprows=skip))
    return pd.concat(frames, ignore_index=True)


def canonical_family(attack_cat: pd.Series, cfg: dict) -> pd.Series:
    """Famille normalisée : strip, minuscules, alias, et « Normal » pour les vides."""
    canon = {f.lower(): f for f in cfg["families"]["canonical"]}
    for alias, target in cfg["families"]["aliases"].items():
        canon[alias.lower()] = canon[target.lower()]
    key = attack_cat.str.strip().str.lower().replace("", "normal")
    family = key.map(canon)
    if family.isna().any():
        unknown = sorted(set(key[family.isna()]))
        raise SystemExit(f"libellés attack_cat inconnus : {unknown}")
    return family


def clean(df: pd.DataFrame, cfg: dict) -> pd.DataFrame:
    """Convertit les features en nombres, ajoute `family` et `label`, trie par Stime.

    Les colonnes de `blank_as_zero` sont vides au jour 2 alors que le jour 1
    écrit 0 (M11) : un blanc devient 0. Toute autre valeur non numérique
    lève une erreur plutôt que d'être ignorée.
    """
    feats = cfg["features"]
    numeric = [c for c in df.columns[:47]
               if c not in feats["excluded"] and c not in feats["nominal"]]
    out = pd.DataFrame(index=df.index)
    out["Stime"] = pd.to_numeric(df["Stime"])
    for c in feats["nominal"]:
        out[c] = df[c].str.strip()
    for c in numeric:
        s = df[c].str.strip()
        if c in feats["blank_as_zero"]:
            s = s.replace("", "0")
        out[c] = pd.to_numeric(s, errors="raise")
    out["family"] = canonical_family(df["attack_cat"], cfg)
    out["label"] = pd.to_numeric(df["Label"].str.strip()).astype(int)
    if ((out["label"] == 0) != (out["family"] == "Normal")).any():
        raise SystemExit("Label et attack_cat sont incohérents")
    return out


def allocate(counts: dict[str, int], total: int) -> dict[str, int]:
    """Répartit `total` proportionnellement à `counts`, somme exacte (plus grands restes)."""
    n = sum(counts.values())
    exact = {f: total * c / n for f, c in counts.items()}
    alloc = {f: int(e) for f, e in exact.items()}
    left = total - sum(alloc.values())
    for f in sorted(counts, key=lambda f: (-(exact[f] - alloc[f]), f))[:left]:
        alloc[f] += 1
    return alloc


def equal_volume_mask(train: pd.DataFrame, total: int, seed: int) -> pd.Series:
    """Masque de la condition B : tous les normaux + `total` attaques tirées par famille."""
    attacks = train[train["label"] == 1]
    counts = attacks["family"].value_counts().to_dict()
    alloc = allocate(counts, total)
    rng = np.random.default_rng(seed)
    chosen = []
    for fam in sorted(alloc):
        idx = attacks.index[attacks["family"] == fam].to_numpy()
        chosen.append(rng.choice(idx, size=alloc[fam], replace=False))
    return (train["label"] == 0) | train.index.isin(np.concatenate(chosen))


def select_log_columns(frame: pd.DataFrame, cfg: dict) -> tuple[list[str], dict[str, float]]:
    """Colonnes numériques à transformer par log1p, et asymétrie brute de chacune.

    Critère : asymétrie (skewness) de la colonne sur `frame`, qui doit être le
    jeu d'entraînement seul, strictement supérieure à `log1p_skew_threshold`.
    log1p n'est défini que pour x > -1 : une colonne sélectionnée qui prend une
    valeur négative arrête l'exécution plutôt que de produire des NaN.
    """
    nominal = cfg["features"]["nominal"]
    numeric = [c for c in frame.columns if c not in nominal]
    skew = frame[numeric].skew()
    selected = [c for c in numeric if skew[c] > cfg["preprocessing"]["log1p_skew_threshold"]]
    negative = [c for c in selected if frame[c].min() < 0]
    if negative:
        raise SystemExit(f"log1p impossible, valeurs négatives dans : {negative}")
    return selected, {c: round(float(skew[c]), 4) for c in numeric}


def build_preprocessor(cfg: dict, columns: list[str], log_columns: list[str]) -> ColumnTransformer:
    """Encodeur one-hot des nominales, puis [log1p +] StandardScaler des numériques.

    Les colonnes de `log_columns` passent par log1p avant le scaler ; les autres
    seulement par le scaler. Modalités rares et inconnues : voir `min_frequency`.
    """
    nominal = cfg["features"]["nominal"]
    numeric = [c for c in columns if c not in nominal]
    logged = [c for c in numeric if c in log_columns]
    plain = [c for c in numeric if c not in log_columns]
    onehot = OneHotEncoder(handle_unknown="infrequent_if_exist", sparse_output=False,
                           min_frequency=cfg["preprocessing"]["min_frequency"],
                           dtype=np.float32)
    transformers = [("nominal", onehot, nominal)]
    if logged:
        log_scale = make_pipeline(FunctionTransformer(np.log1p, feature_names_out="one-to-one"),
                                  StandardScaler())
        transformers.append(("numeric_log", log_scale, logged))
    if plain:
        transformers.append(("numeric", StandardScaler(), plain))
    return ColumnTransformer(transformers)


def load_set(name: str, processed_dir: Path = Path("data/processed")):
    """Charge un jeu d'entraînement et le test, transformés par le préprocesseur du jeu.

    Retourne (X_train, y_train, family_train, X_test, y_test, family_test),
    X en float32. Le préprocesseur a été ajusté sur l'entraînement seul.
    """
    manifest = json.loads((processed_dir / "manifest.json").read_text())
    cols = manifest["feature_columns"]
    pre = joblib.load(processed_dir / f"preprocessor_{name}.joblib")
    train = pd.read_parquet(processed_dir / f"train_{name}.parquet")
    test = pd.read_parquet(processed_dir / "test.parquet")
    return (pre.transform(train[cols]).astype(np.float32), train["label"].to_numpy(),
            train["family"].to_numpy(), pre.transform(test[cols]).astype(np.float32),
            test["label"].to_numpy(), test["family"].to_numpy())


def summary(df: pd.DataFrame) -> dict:
    """Effectifs d'un jeu : lignes, par famille."""
    return {"rows": int(len(df)), "normal": int((df["label"] == 0).sum()),
            "attack": int((df["label"] == 1).sum()),
            "families": {k: int(v) for k, v in df["family"].value_counts().sort_index().items()}}


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--config", type=Path, default=Path("config.toml"))
    args = parser.parse_args()
    cfg = load_config(args.config)
    raw_dir, out_dir = Path(cfg["data"]["raw_dir"]), Path(cfg["data"]["processed_dir"])
    out_dir.mkdir(parents=True, exist_ok=True)
    day2_ts = datetime.strptime(cfg["split"]["day2_start"], "%Y-%m-%d").replace(
        tzinfo=timezone.utc).timestamp()

    names = feature_names(raw_dir / cfg["data"]["features_file"])
    raw = read_raw(raw_dir, cfg["data"]["csv_files"], names)
    print(f"Lignes lues, doublons de jonction écartés : {len(raw)}")

    # Le côté entre dans la clé : la déduplication se fait par côté, après le découpage.
    raw["_side"] = np.where(pd.to_numeric(raw["Stime"]) >= day2_ts, "train", "test")
    dup = raw.duplicated(subset=names + ["_side"], keep="first")
    removed = {s: int(dup[raw["_side"] == s].sum()) for s in ("train", "test")}
    print(f"Doublons exacts supprimés : entraînement {removed['train']}, test {removed['test']}")
    side = raw.loc[~dup, "_side"]
    df = clean(raw.loc[~dup, names], cfg)
    del raw
    df["_side"] = side
    df = df.sort_values("Stime", kind="stable")

    train = df[df["_side"] == "train"].drop(columns="_side").reset_index(drop=True)
    test = df[df["_side"] == "test"].drop(columns="_side").reset_index(drop=True)
    if not (train["Stime"].min() >= day2_ts > test["Stime"].max()):
        raise SystemExit("le découpage temporel n'est pas étanche")

    removed_fams = cfg["families"]["removed"]
    mask_c = ~train["family"].isin(removed_fams)
    n_attacks_c = int((train.loc[mask_c, "label"] == 1).sum())
    sets = {
        "unsup": train[train["label"] == 0],
        "A": train,
        "B": train[equal_volume_mask(train, n_attacks_c, cfg["sampling"]["seed"])],
        "C": train[mask_c],
    }

    feature_cols = [c for c in train.columns if c not in ("Stime", "family", "label")]
    manifest = {"config": cfg, "duplicates_removed": removed, "feature_columns": feature_cols,
                "sets": {}, "test": summary(test)}
    test.to_parquet(out_dir / "test.parquet", index=False)
    for name, frame in sets.items():
        frame = frame.reset_index(drop=True)
        log_cols, skew = select_log_columns(frame[feature_cols], cfg)
        pre = build_preprocessor(cfg, feature_cols, log_cols).fit(frame[feature_cols])
        joblib.dump(pre, out_dir / f"preprocessor_{name}.joblib")
        frame.to_parquet(out_dir / f"train_{name}.parquet", index=False)
        manifest["sets"][name] = summary(frame)
        manifest["sets"][name]["log1p_columns"] = log_cols
        manifest["sets"][name]["skewness"] = skew
        print(f"  {name:6s} {manifest['sets'][name]['rows']} lignes, "
              f"log1p sur {len(log_cols)} colonnes")
    print(f"  test   {manifest['test']}")
    (out_dir / "manifest.json").write_text(json.dumps(manifest, indent=2, ensure_ascii=False))


if __name__ == "__main__":
    main()
