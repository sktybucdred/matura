# -*- coding: utf-8 -*-
"""Jednorazowe pobranie przeciętnych wynagrodzeń brutto per powiat z API GUS BDL.

Uruchamiane ręcznie (python scripts/fetch_bdl_wages.py), wynik commitowany do
data/processed/wages.parquet — aplikacja NIE woła API przy starcie (limity
czasu/RAM na Streamlit Cloud + brak sensu odpytywać o dane roczne).

Zmienna BDL: 64428 = "przeciętne miesięczne wynagrodzenia brutto, ogółem [zł]"
(temat P2497), poziom 5 = powiaty. Znaleziona przez endpoint
/variables?subject-id=P2497 (wyszukiwarka /variables/search zwraca tylko
wariant relacyjny "Polska=100").

Identyfikator jednostki BDL (12 znaków) ma zaszyty TERYT:
pozycje [2:4] = województwo, ostatnie dwie cyfry segmentu [6:9] = powiat,
np. "011212001000" -> województwo 12 + powiat 01 = TERYT 1201 (bocheński).
Dopasowanie walidowane po nazwach powiatów (patrz niżej).
"""

from __future__ import annotations

import json
import sys
import urllib.parse
import urllib.request
from pathlib import Path

import pandas as pd

BASE_DIR = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(BASE_DIR))
import data  # noqa: E402

API = "https://bdl.stat.gov.pl/api/v1"
VARIABLE_ID = 64428  # przeciętne miesięczne wynagrodzenia brutto, zł
UNIT_LEVEL = 5  # powiaty
OUT_PATH = BASE_DIR / "data" / "processed" / "wages.parquet"


def api_get(path: str, **params) -> dict:
    query = urllib.parse.urlencode({"format": "json", **params})
    req = urllib.request.Request(
        f"{API}/{path}?{query}", headers={"Accept": "application/json"}
    )
    with urllib.request.urlopen(req, timeout=30) as resp:
        return json.loads(resp.read().decode("utf-8"))


def bdl_unit_to_teryt(unit_id: str) -> str:
    """'011212001000' -> '1201' (województwo [2:4] + powiat = 2 ostatnie cyfry
    segmentu [6:9])."""
    return unit_id[2:4] + unit_id[6:9][-2:]


def fetch_wages() -> pd.DataFrame:
    rows, page = [], 0
    while True:
        payload = api_get(
            f"data/by-variable/{VARIABLE_ID}",
            **{"unit-level": UNIT_LEVEL, "page-size": 100, "page": page},
        )
        for unit in payload.get("results", []):
            # bierzemy najnowszy dostępny rok per jednostka
            values = [v for v in unit.get("values", []) if v.get("val") is not None]
            if not values:
                continue
            latest = max(values, key=lambda v: int(v["year"]))
            rows.append(
                {
                    "teryt_county": bdl_unit_to_teryt(unit["id"]),
                    "bdl_name": unit["name"],
                    "wage": float(latest["val"]),
                    "wage_year": int(latest["year"]),
                }
            )
        if not payload.get("links", {}).get("next"):
            break
        page += 1
    return pd.DataFrame(rows)


def main() -> None:
    wages = fetch_wages()
    print(f"pobrano {len(wages)} jednostek, lata: {sorted(wages['wage_year'].unique())}")

    # Walidacja dekodowania TERYT: nazwa BDL ("Powiat bocheński" / "Powiat
    # m. Kraków") musi odpowiadać nazwie powiatu w danych CKE.
    counties = data.load_counties()
    ref = counties[["teryt_county", "county"]].drop_duplicates("teryt_county")
    merged = wages.merge(ref, on="teryt_county", how="outer", indicator=True)

    both = merged[merged["_merge"] == "both"]
    norm = lambda s: (
        s.str.lower().str.replace(r"^powiat( m\. ?st\.| m\.)? ", "", regex=True).str.strip()
    )
    name_ok = (norm(both["bdl_name"]) == both["county"].str.lower().str.strip()).mean()
    print(f"dopasowane do CKE: {len(both)}/{ref.shape[0]} powiatów; zgodność nazw: {name_ok:.1%}")
    print("w BDL bez CKE:", merged.loc[merged["_merge"] == "left_only", "bdl_name"].tolist())
    print("w CKE bez BDL:", merged.loc[merged["_merge"] == "right_only", "county"].tolist())
    if name_ok < 0.99:
        mism = both[norm(both["bdl_name"]) != both["county"].str.lower().str.strip()]
        print(mism[["teryt_county", "bdl_name", "county"]].to_string(index=False))
        raise SystemExit("Dekodowanie TERYT z kodu BDL wygląda na błędne — przerwano.")

    # Tylko najnowszy wspólny rok — odpadają jednostki historyczne
    # (np. "Powiat m. Wałbrzych do 2002" z ostatnią wartością z 2002 r.).
    top_year = int(wages["wage_year"].max())
    out = wages.loc[wages["wage_year"] == top_year, ["teryt_county", "wage", "wage_year"]]
    out.to_parquet(OUT_PATH, index=False)
    print(f"zapisano {OUT_PATH} ({len(out)} wierszy, rok {out['wage_year'].mode()[0]})")


if __name__ == "__main__":
    main()
