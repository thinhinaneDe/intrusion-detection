"""Débit horaire de flux dans les jeux écrits, pour chiffrer un budget de faux positifs.

Le cahier des charges illustre le critère de déploiement par un SOC à
10 000 flux par heure. Le débit réel de ce jeu synthétique est différent ; il
convertit un taux de faux positifs en nombre d'alertes fausses par heure.

Usage : python src/inspect_debit.py [--config config.toml]
"""

import argparse
from datetime import datetime, timezone
from pathlib import Path

import pandas as pd

from prepare import load_config


def hourly(stime: pd.Series) -> pd.Series:
    """Nombre de flux par heure UTC (heures sans flux absentes)."""
    return stime.floordiv(3600).value_counts().sort_index()


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--config", type=Path, default=Path("config.toml"))
    args = parser.parse_args()
    out = Path(load_config(args.config)["data"]["processed_dir"])

    for label, path in (("test (jour 1)", "test.parquet"), ("entraînement (jour 2)", "train_A.parquet")):
        df = pd.read_parquet(out / path, columns=["Stime", "label"])
        span_h = (df["Stime"].max() - df["Stime"].min()) / 3600
        print(f"{label} : {len(df)} flux, dont {int((df['label'] == 0).sum())} normaux ; "
              f"de {datetime.fromtimestamp(df['Stime'].min(), timezone.utc):%Y-%m-%d %H:%M} "
              f"à {datetime.fromtimestamp(df['Stime'].max(), timezone.utc):%Y-%m-%d %H:%M} UTC "
              f"({span_h:.1f} h)")
        for name, sub in (("tous flux", df), ("normaux", df[df["label"] == 0])):
            h = hourly(sub["Stime"])
            print(f"  {name} : {len(h)} heures avec des flux ; par heure : médiane "
                  f"{h.median():.0f}, min {h.min()}, max {h.max()} ; "
                  f"moyenne sur l'étendue : {len(sub) / span_h:.0f}")
        h = hourly(df[df["label"] == 0]["Stime"])
        print("  normaux par heure UTC : "
              + ", ".join(f"{datetime.fromtimestamp(t * 3600, timezone.utc):%d %Hh}:{n}"
                          for t, n in h.items()))


if __name__ == "__main__":
    main()
