# -*- coding: utf-8 -*-
"""Wczytywanie i czyszczenie danych maturalnych CKE (mapa.wyniki.edu.pl).

Pliki wejściowe: data/raw/EM2023_<rok>_{powiaty|szkoly}_09.xlsx
(Formuła 2023, aktualizacja wrześniowa = sesja główna + poprawkowa, arkusz "SAS").

Moduł jest samowystarczalny: dorzucenie pliku za kolejny rok (np.
EM2023_2026_powiaty_09.xlsx) do data/raw/ wystarczy — rok jest brany z nazwy
pliku, a lista plików z glob-a, więc kod nie wymaga zmian.

UWAGA METODOLOGICZNA: w 2023 r. Formułę 2023 zdawali niemal wyłącznie
absolwenci LO (technika kończyły jeszcze Formułę 2015), więc rocznik 2023
obejmuje ~2,3 tys. szkół zamiast ~4,7 tys., a średnie krajowe są zawyżone
względem pełnej populacji. Porównania LO vs technikum mają sens od 2024 r.
"""

from __future__ import annotations

import re
import zipfile
from pathlib import Path

import pandas as pd

# Wszystkie ścieżki względne względem położenia tego pliku (wymóg deploymentu
# na Streamlit Community Cloud — brak ścieżek absolutnych).
BASE_DIR = Path(__file__).resolve().parent
RAW_DIR = BASE_DIR / "data" / "raw"

# Pliki ~5 KB pobrane z portalu to w rzeczywistości strony HTML z błędem,
# nie XLSX. Prawdziwe eksporty mają setki KB — odcinamy się progiem rozmiaru.
MIN_XLSX_SIZE_BYTES = 50_000

SHEET_NAME = "SAS"  # portal zawsze umieszcza dane w arkuszu "SAS"

# ---------------------------------------------------------------------------
# Zakres analizy.
#
# Plik zawiera ~75 wariantów przedmiot×poziom. Świadomie zawężamy do:
#   - matematyka PP i PR (główny temat dashboardu),
#   - język polski PP i język angielski PP (tło porównawcze),
#   - zdawalność ogólna ("dla całego egzaminu dojrzałości").
# Pozostałe przedmioty odrzucamy przy czyszczeniu — nie wnoszą nic do
# narracji "matematyka jako wąskie gardło matury".
#
# PUŁAPKA W DANYCH: obok wariantów z sufiksem "(M)" istnieją bliźniacze
# kolumny bez "(M)" (np. "matematyka poziom podstawowy"), w większości puste.
# Używamy WYŁĄCZNIE wariantów "(M)" — to one niosą właściwe dane.
# ---------------------------------------------------------------------------
SUBJECT_PREFIXES = {
    "matematyka poziom podstawowy (m)": "math_pp",
    "matematyka poziom rozszerzony (m)": "math_pr",
    "język polski poziom podstawowy (m)": "pol_pp",
    "język angielski poziom podstawowy (m)": "eng_pp",
}

# Metryki per przedmiot (po normalizacji nazw). Poziom rozszerzony NIE MA
# zdawalności — dla przedmiotów dodatkowych nie istnieje próg zdania, więc
# kolumna "zdawalność (%)" występuje tylko dla poziomu podstawowego.
METRIC_MAP = {
    "liczba zdających": "n",
    "zdawalność (%)": "pass_rate",
    "średni wynik (%)": "mean",
    "odchylenie standardowe (%)": "std",
    "mediana (%)": "median",
    "modalna (%)": "mode",
    # "liczba laureatów/finalistów" — pomijamy, znikomo mała i bez znaczenia
    # dla analizy rynkowej.
}

# Zdawalność ogólna całej matury (świadectwo dojrzałości).
OVERALL_BAND = "dla całego egzaminu dojrzałości"
OVERALL_METRIC_MAP = {
    "otrzymali świadectwo dojrzałości - liczba": "overall_certificates",
    "liczba zdających, którzy przystąpili do wszystkich egzaminów wymaganych": "overall_taken",
    "zdawalność (%)": "overall_pass_rate",
}

# Kolumny identyfikacyjne (nazwy po normalizacji → nazwy docelowe).
# Nagłówki bywają niespójne między plikami (wielkość liter, "typ placówki\n"
# z twardym znakiem nowej linii) — stąd dopasowanie po znormalizowanej formie.
ID_COLUMN_MAP = {
    "id oke": "oke_id",
    "województwo - nazwa": "voivodeship",
    "powiat - nazwa": "county",
    "kod teryt powiatu": "teryt_county",
    "gmina - nazwa": "gmina",
    "typ gminy": "gmina_type",
    "kod teryt gminy": "teryt_gmina",
    "rspo szkoły": "rspo",
    "nazwa szkoły": "school_name",
    "miejscowość": "town",
    "typ placówki": "school_type_raw",
    "czy publiczna": "is_public_raw",
    # "ulica nr", "rodzaj placówki" — świadomie pomijane (bez wartości analitycznej)
}


# ---------------------------------------------------------------------------
# Walidacja plików
# ---------------------------------------------------------------------------
def validate_raw_file(path: Path) -> None:
    """Odrzuca pliki, które nie są prawdziwymi XLSX (np. strony HTML z portalu)."""
    path = Path(path)
    if not path.exists():
        raise FileNotFoundError(f"Brak pliku: {path}")
    size = path.stat().st_size
    if size < MIN_XLSX_SIZE_BYTES:
        raise ValueError(
            f"Plik {path.name} ma tylko {size} B — to prawdopodobnie strona HTML "
            f"zapisana przez portal zamiast eksportu XLSX. Pobierz plik ponownie."
        )
    # XLSX to archiwum ZIP — szybki test nagłówka bez pełnego parsowania.
    if not zipfile.is_zipfile(path):
        raise ValueError(f"Plik {path.name} nie jest poprawnym plikiem XLSX (brak struktury ZIP).")


def year_from_filename(path: Path) -> int:
    """Rok egzaminu bierzemy z NAZWY pliku (EM2023_<rok>_..._09.xlsx), nie z
    zawartości — zawartość nie ma kolumny roku, a prefiks EM2023 oznacza
    formułę egzaminu, nie rocznik."""
    m = re.search(r"_(20\d{2})_", Path(path).name)
    if not m:
        raise ValueError(f"Nie mogę odczytać roku z nazwy pliku: {path}")
    return int(m.group(1))


# ---------------------------------------------------------------------------
# Parser trzyrzędowego nagłówka
# ---------------------------------------------------------------------------
def _norm(text: object) -> str:
    """Normalizacja nazwy: usuwa prefiks '* ', znaki nowej linii, nadmiarowe
    białe znaki; sprowadza do małych liter."""
    s = str(text) if text is not None else ""
    s = s.replace("\n", " ").strip()
    s = re.sub(r"^\*\s*", "", s)  # część metryk ma prefiks "* "
    s = re.sub(r"\s+", " ", s)
    return s.lower()


def _forward_fill(row: list) -> list:
    """Rzędy 0 (pasmo) i 1 (przedmiot+poziom) są scalone w XLSX — po wczytaniu
    wartość stoi tylko w pierwszej komórce zakresu. Uzupełniamy w prawo."""
    filled, last = [], None
    for value in row:
        if value is not None and str(value).strip() not in ("", "nan"):
            last = value
        filled.append(last)
    return filled


def parse_header(raw: pd.DataFrame) -> list[tuple[str, str, str]]:
    """Składa trzyrzędowy nagłówek (pasmo / przedmiot / metryka) w krotki
    znormalizowanych nazw dla każdej kolumny."""
    band_row = _forward_fill(list(raw.iloc[0]))
    subject_row = _forward_fill(list(raw.iloc[1]))
    metric_row = list(raw.iloc[2])
    return [
        (_norm(b), _norm(s), _norm(m))
        for b, s, m in zip(band_row, subject_row, metric_row)
    ]


# ---------------------------------------------------------------------------
# Wybór i przemianowanie kolumn
# ---------------------------------------------------------------------------
def select_columns(header: list[tuple[str, str, str]]) -> dict[int, str]:
    """Mapuje indeks kolumny → docelowa nazwa. Kolumny spoza zakresu analizy
    (inne przedmioty, warianty bez '(M)', laureaci itd.) są pomijane."""
    selected: dict[int, str] = {}
    for idx, (_band, subject, metric) in enumerate(header):
        # Kolumny identyfikacyjne mają puste rzędy 0-1, nazwa siedzi w rzędzie 2.
        if metric in ID_COLUMN_MAP:
            selected[idx] = ID_COLUMN_MAP[metric]
        elif subject == OVERALL_BAND and metric in OVERALL_METRIC_MAP:
            selected[idx] = OVERALL_METRIC_MAP[metric]
        elif subject in SUBJECT_PREFIXES and metric in METRIC_MAP:
            selected[idx] = f"{SUBJECT_PREFIXES[subject]}_{METRIC_MAP[metric]}"
    return selected


def _clean_teryt(value: object, width: int) -> object:
    """Kody TERYT trzymamy jako string z wiodącymi zerami (np. '0401').
    Excel potrafi zamienić je na liczby — cofamy to i dopełniamy zerami."""
    if value is None or (isinstance(value, float) and pd.isna(value)):
        return pd.NA
    s = str(value).strip()
    s = re.sub(r"\.0$", "", s)  # '401.0' → '401'
    if not s or not s.isdigit():
        return pd.NA
    return s.zfill(width)


# ---------------------------------------------------------------------------
# Wczytanie pojedynczego pliku
# ---------------------------------------------------------------------------
def load_file(path: Path) -> pd.DataFrame:
    """Wczytuje jeden plik XLSX do płaskiej, oczyszczonej ramki."""
    path = Path(path)
    validate_raw_file(path)

    raw = pd.read_excel(path, sheet_name=SHEET_NAME, header=None, engine="openpyxl")
    header = parse_header(raw)
    selected = select_columns(header)

    df = raw.iloc[3:, list(selected.keys())].copy()
    df.columns = list(selected.values())
    df = df.reset_index(drop=True)

    # --- typy ---------------------------------------------------------------
    id_cols = [c for c in df.columns if c in set(ID_COLUMN_MAP.values())]
    numeric_cols = [c for c in df.columns if c not in id_cols]
    for col in numeric_cols:
        # Puste komórki, kreski i teksty (małe powiaty/szkoły bez wyników albo
        # z utajnionymi metrykami) → NaN. NIE usuwamy tych wierszy: liczba
        # zdających bywa dostępna nawet, gdy metryki wynikowe są puste.
        df[col] = pd.to_numeric(df[col], errors="coerce")

    for col in id_cols:
        df[col] = df[col].astype("string").str.strip()

    if "teryt_county" in df.columns:
        df["teryt_county"] = df["teryt_county"].map(lambda v: _clean_teryt(v, 4))
    if "teryt_gmina" in df.columns:
        df["teryt_gmina"] = df["teryt_gmina"].map(lambda v: _clean_teryt(v, 6))
        # Kod powiatu = pierwsze 4 cyfry kodu gminy — pozwala łączyć szkoły
        # z ramką powiatową i z GeoJSON-em granic powiatów.
        df["teryt_county"] = df["teryt_gmina"].str[:4]

    df["year"] = year_from_filename(path)
    return df


# ---------------------------------------------------------------------------
# Kolumny pochodne
# ---------------------------------------------------------------------------
def weighted_mean(df: pd.DataFrame, value_col: str, weight_col: str) -> float:
    """Średnia ważona liczbą zdających — średnia arytmetyczna po powiatach
    zawyżałaby wpływ małych powiatów; ważona odtwarza średnią krajową CKE."""
    sub = df[[value_col, weight_col]].dropna()
    if sub.empty or sub[weight_col].sum() == 0:
        return float("nan")
    return float((sub[value_col] * sub[weight_col]).sum() / sub[weight_col].sum())


def add_derived_columns(df: pd.DataFrame) -> pd.DataFrame:
    """Dodaje kolumny pochodne wspólne dla ramki powiatowej i szkolnej."""
    df = df.copy()

    # Wskaźnik ambicji: jaki odsetek zdających matematykę PP porywa się też na
    # rozszerzenie. PR nie ma zdawalności (brak progu), więc porównujemy
    # uczestnictwo, nie wyniki.
    # Pusta komórka w "liczba zdających" PR oznacza ZERO zdających, nie brak
    # danych — portal raportuje nawet n=1, a utajnia dopiero metryki wynikowe
    # przy małym n. Dlatego fillna(0): zero podchodzących do rozszerzenia to
    # realna informacja o (braku) ambicji, nie luka w danych.
    df["ambition_ratio"] = df["math_pr_n"].fillna(0) / df["math_pp_n"]

    # Wąskie gardło: różnica zdawalności języka polskiego/angielskiego i
    # matematyki (wszystko na poziomie podstawowym). Zdawalności OGÓLNEJ
    # (świadectwo) nie używamy do tego porównania — jest z konstrukcji niższa
    # od zdawalności pojedynczego przedmiotu (oblanie czegokolwiek = brak
    # świadectwa). Wartość dodatnia = matematyka wypada gorzej niż przedmiot
    # odniesienia, czyli jest wąskim gardłem matury.
    df["pol_math_gap"] = df["pol_pp_pass_rate"] - df["math_pp_pass_rate"]
    df["eng_math_gap"] = df["eng_pp_pass_rate"] - df["math_pp_pass_rate"]

    # Odchylenie od średniej krajowej (ważonej liczbą zdających) w danym roku —
    # pozwala porównywać powiaty/szkoły między latami mimo wahań trudności arkusza.
    for col, out in [
        ("math_pp_pass_rate", "math_pp_pass_rate_dev"),
        ("math_pp_mean", "math_pp_mean_dev"),
    ]:
        national = df.groupby("year").apply(
            lambda g: weighted_mean(g, col, "math_pp_n"), include_groups=False
        )
        df[out] = df[col] - df["year"].map(national)

    return df


def add_school_flags(df: pd.DataFrame) -> pd.DataFrame:
    """Kolumny pochodne specyficzne dla szkół: wymiary rozwarstwienia."""
    df = df.copy()

    # LO vs technikum — kluczowy wymiar narracji. Pozostałe typy placówek
    # (szkoły artystyczne itp.) zbieramy w 'inne', bo są nieliczne.
    kind = df["school_type_raw"].str.lower().fillna("")
    df["school_kind"] = "inne"
    df.loc[kind.str.contains("liceum"), "school_kind"] = "LO"
    df.loc[kind.str.contains("technikum"), "school_kind"] = "Technikum"

    # Miasto vs wieś na podstawie typu gminy (portal: miasto / wieś /
    # obszar miejsko-wiejski itd.). Flaga binarna: gmina zawierająca 'wie'
    # (wieś/wiejski) traktowana jako wiejska.
    gtype = df["gmina_type"].str.lower().fillna("")
    df["is_rural"] = gtype.str.contains("wie")

    # Publiczna / niepubliczna jako czytelna flaga.
    df["is_public"] = df["is_public_raw"].str.lower().str.startswith("tak")

    return df


# ---------------------------------------------------------------------------
# Interfejs publiczny
# ---------------------------------------------------------------------------
def _load_dataset(kind: str) -> pd.DataFrame:
    """Wczytuje i łączy wszystkie roczniki danego rodzaju ('powiaty'/'szkoly')."""
    paths = sorted(RAW_DIR.glob(f"*_{kind}_*.xlsx"))
    if not paths:
        raise FileNotFoundError(
            f"Nie znaleziono plików '*_{kind}_*.xlsx' w {RAW_DIR}. "
            f"Umieść eksporty z mapa.wyniki.edu.pl w data/raw/."
        )
    frames = [load_file(p) for p in paths]
    return pd.concat(frames, ignore_index=True)


def load_counties() -> pd.DataFrame:
    """Czysta ramka powiatowa: wiersz = powiat × rok."""
    df = _load_dataset("powiaty")
    # Wiersze bez kodu TERYT to artefakty eksportu (np. podsumowania) — precz.
    df = df.dropna(subset=["teryt_county"]).reset_index(drop=True)
    # Plik zawiera 8 pseudo-powiatów "OKRĘGOWA KOMISJA EGZAMINACYJNA W ..."
    # (zdający przypisani wprost do OKE, np. eksterniści — po kilkanaście do
    # kilkudziesięciu osób). Dublują kody TERYT miast-siedzib OKE i psułyby
    # mapę oraz rankingi, więc je usuwamy.
    df = df[~df["county"].str.contains("KOMISJA EGZAMINACYJNA", case=False, na=False)]
    df = df.reset_index(drop=True)
    return add_derived_columns(df)


def load_schools() -> pd.DataFrame:
    """Czysta ramka szkolna: wiersz = szkoła × rok."""
    df = _load_dataset("szkoly")
    df = df.dropna(subset=["rspo"]).reset_index(drop=True)
    df = add_derived_columns(df)
    return add_school_flags(df)


def partial_coverage_years(schools: pd.DataFrame, threshold: float = 0.10) -> set[int]:
    """Lata, w których Formuła 2023 nie obejmowała jeszcze pełnej populacji
    maturzystów. W 2023 r. zdawali ją niemal wyłącznie absolwenci LO (technika
    kończyły Formułę 2015): technika to ~0,7% szkół vs ~37% w kolejnych latach.

    Wykrywamy to DYNAMICZNIE (udział techników < threshold), zamiast
    hardcodować rok 2023 — dzięki temu dorzucenie pliku 2026 nie wymaga zmian,
    a porównania LO/technikum i miasto/wieś automatycznie pomijają lata
    niepełne. Wyniki z tych lat pokazujemy na trendach z adnotacją.
    """
    tech_share = (
        schools.assign(is_tech=schools["school_kind"].eq("Technikum"))
        .groupby("year")["is_tech"]
        .mean()
    )
    return set(tech_share[tech_share < threshold].index)


# ---------------------------------------------------------------------------
# Szybki raport kontrolny: `python data.py`
# ---------------------------------------------------------------------------
if __name__ == "__main__":
    pd.set_option("display.width", 200)
    pd.set_option("display.max_columns", 50)

    counties = load_counties()
    schools = load_schools()

    print("=== POWIATY ===")
    print("shape:", counties.shape)
    print("wiersze na rok:\n", counties["year"].value_counts().sort_index())
    print("kolumny:", list(counties.columns))
    print(counties.sample(5, random_state=1).to_string())

    print("\n=== SZKOŁY ===")
    print("shape:", schools.shape)
    print("wiersze na rok:\n", schools["year"].value_counts().sort_index())
    print("kolumny:", list(schools.columns))
    print(schools.sample(5, random_state=1).to_string())

    print("\n=== SANITY: średnia krajowa zdawalności matematyki PP (ważona liczbą zdających) ===")
    for year, group in counties.groupby("year"):
        wm = weighted_mean(group, "math_pp_pass_rate", "math_pp_n")
        n = group["math_pp_n"].sum()
        print(f"  {year}: {wm:.2f}%  (zdających: {n:,.0f})")

    print("\n=== SANITY: to samo z ramki szkolnej (powinno być zbliżone) ===")
    for year, group in schools.groupby("year"):
        wm = weighted_mean(group, "math_pp_pass_rate", "math_pp_n")
        print(f"  {year}: {wm:.2f}%")

    print("\n=== KONTROLA: duplikaty TERYT w powiatach (na rok) ===")
    dup = counties.groupby(["year", "teryt_county"]).size()
    print(dup[dup > 1] if (dup > 1).any() else "  brak duplikatów")

    print("\n=== KONTROLA: braki danych (powiaty, % pustych) ===")
    na = counties.isna().mean().mul(100).round(1)
    print(na[na > 0].to_string())

    print("\n=== KONTROLA: lata niepełnego pokrycia (Formuła 2023 bez techników) ===")
    print(" ", partial_coverage_years(schools) or "brak")

    print("\n=== KONTROLA: wartości wymiarów szkolnych ===")
    print("typ placówki:", schools["school_type_raw"].value_counts(dropna=False).to_dict())
    print("school_kind:", schools["school_kind"].value_counts().to_dict())
    print("typ gminy:", schools["gmina_type"].value_counts(dropna=False).to_dict())
    print("is_rural:", schools["is_rural"].value_counts().to_dict())
    print("czy publiczna:", schools["is_public_raw"].value_counts(dropna=False).to_dict())
