# -*- coding: utf-8 -*-
"""Mapa maturalnej matematyki — dashboard Streamlit.

app.py jest tylko orkiestratorem: wczytanie danych (data.py, cache),
filtry w sidebarze, KPI i zakładki. Definicje wykresów żyją w charts.py,
logika danych w data.py.
"""

from __future__ import annotations

import pandas as pd
import streamlit as st

import charts
import data
from charts import fmt_pl

st.set_page_config(
    page_title="Mapa maturalnej matematyki",
    page_icon="📐",
    layout="wide",
)

SUBJECTS = {"matematyka": "math", "język polski": "pol", "język angielski": "eng"}


# ---------------------------------------------------------------------------
# Dane (st.cache_data — parsowanie/parquet płaci tylko pierwsze wejście)
# ---------------------------------------------------------------------------
@st.cache_data(show_spinner="Wczytuję dane powiatowe…")
def get_counties() -> pd.DataFrame:
    return data.load_counties()


@st.cache_data(show_spinner="Wczytuję dane szkół…")
def get_schools() -> pd.DataFrame:
    return data.load_schools()


@st.cache_data(show_spinner="Wczytuję granice powiatów…")
def get_geojson() -> dict:
    return data.load_county_geojson()


counties = get_counties()
schools = get_schools()
partial_years = data.partial_coverage_years(schools)

YEARS = sorted(int(y) for y in counties["year"].unique())
LATEST = YEARS[-1]
ALL_VOIS = sorted(counties["voivodeship"].dropna().unique())


# ---------------------------------------------------------------------------
# Sidebar: filtry
# ---------------------------------------------------------------------------
with st.sidebar:
    st.header("🎛️ Filtry")
    year = st.selectbox(
        "Rok egzaminu", YEARS, index=len(YEARS) - 1,
        help="Domyślnie najnowszy dostępny rocznik.",
    )
    vois = st.multiselect("Województwa", ALL_VOIS, placeholder="puste = cała Polska")
    subject_label = st.selectbox("Przedmiot (poziom podstawowy)", list(SUBJECTS))
    kind = st.radio("Typ szkoły", ["wszystkie", "LO", "Technikum"], horizontal=True)
    st.caption(
        "Każdy filtr przelicza KPI, wykresy i tabele. Przy typie szkoły "
        "innym niż „wszystkie” wskaźniki powiatowe liczone są z agregacji "
        "danych szkolnych (mogą się minimalnie różnić od oficjalnych sum "
        "powiatowych CKE)."
    )
    st.divider()
    st.caption(
        "**Dane:** CKE / [mapa.wyniki.edu.pl](https://mapa.wyniki.edu.pl), "
        "Formuła 2023, aktualizacja wrześniowa (sesja główna + poprawkowa), "
        f"lata {YEARS[0]}–{LATEST}."
    )

prefix = SUBJECTS[subject_label]
pass_col = f"{prefix}_pp_pass_rate"
n_col = f"{prefix}_pp_n"

# Zakresy danych po filtrach
c_scope = counties[counties["voivodeship"].isin(vois)] if vois else counties
c_year = c_scope[c_scope["year"] == year]

s_scope = schools[schools["voivodeship"].isin(vois)] if vois else schools
s_year = s_scope[s_scope["year"] == year]
if kind != "wszystkie":
    s_year = s_year[s_year["school_kind"] == kind]


# Wspólny "widok powiatowy" dla mapy, rankingów, scattera i trendów:
# oficjalne dane powiatowe CKE, a przy filtrze typu szkoły — agregacja
# ze szkół (oficjalne dane powiatowe nie mają podziału LO/technikum).
@st.cache_data(show_spinner=False)
def county_level_for_kind(vois_key: tuple[str, ...], kind_key: str) -> pd.DataFrame:
    base = schools
    if vois_key:
        base = base[base["voivodeship"].isin(list(vois_key))]
    return data.aggregate_schools_to_counties(base[base["school_kind"] == kind_key])


if kind == "wszystkie":
    cc_scope = c_scope
else:
    cc_scope = county_level_for_kind(tuple(vois), kind)
cc_year = cc_scope[cc_scope["year"] == year]

if len(vois) == 0:
    scope_label = "Polska"
elif len(vois) <= 3:
    scope_label = ", ".join(vois)
else:
    scope_label = f"{len(vois)} województw"

if c_year.empty or s_year.empty or cc_year.empty:
    st.warning(
        "Brak danych dla wybranej kombinacji filtrów — poszerz zakres "
        "(np. inny rok lub typ szkoły; w 2023 r. Formuła 2023 obejmowała "
        "niemal wyłącznie licea)."
    )
    st.stop()


# ---------------------------------------------------------------------------
# Nagłówek + KPI
# ---------------------------------------------------------------------------
st.title("📐 Mapa maturalnej matematyki")
st.markdown(
    "**Gdzie w Polsce matura z matematyki idzie najgorzej — i gdzie rynek "
    "wsparcia edukacyjnego jest największy.** Wyniki egzaminu maturalnego "
    "z matematyki na tle języka polskiego i angielskiego, per powiat "
    "i per szkoła."
)

kind_note = "" if kind == "wszystkie" else f", {kind}"


def kpi_pass_rate(frame: pd.DataFrame) -> float:
    return data.weighted_mean(frame, pass_col, n_col)


cur_pass = kpi_pass_rate(s_year)
prev_year = year - 1
delta_text = None
if prev_year in YEARS:
    s_prev = s_scope[s_scope["year"] == prev_year]
    if kind != "wszystkie":
        s_prev = s_prev[s_prev["school_kind"] == kind]
    prev_pass = kpi_pass_rate(s_prev)
    if pd.notna(prev_pass) and pd.notna(cur_pass):
        diff = cur_pass - prev_pass
        delta_text = f"{fmt_pl(diff, 1)} p.p. vs {prev_year}"

n_takers = s_year[n_col].sum()
pr_share = (
    s_year["math_pr_n"].fillna(0).sum() / s_year["math_pp_n"].sum()
    if s_year["math_pp_n"].sum() > 0
    else float("nan")
)

# Najsłabszy powiat w bieżącym filtrze (widok powiatowy reaguje też na typ
# szkoły); próg ≥100 zdających odsiewa niestabilne odsetki.
county_big = cc_year[(cc_year[n_col] >= 100) & cc_year[pass_col].notna()]
worst = county_big.nsmallest(1, pass_col)

k1, k2, k3, k4 = st.columns(4)
k1.metric(
    f"Zdawalność: {subject_label} PP ({scope_label}{kind_note})",
    f"{fmt_pl(cur_pass, 1)}%",
    delta=delta_text,
    help="Średnia ważona liczbą zdających w wybranym zakresie.",
)
k2.metric(
    f"Zdający: {subject_label} PP",
    fmt_pl(n_takers),
    help="Suma zdających w wybranym zakresie (rok, województwa, typ szkoły).",
)
k3.metric(
    "Podchodzący do rozszerzenia z matematyki",
    f"{fmt_pl(pr_share * 100, 1)}%" if pd.notna(pr_share) else "—",
    help="Zdający matematykę PR jako odsetek zdających matematykę PP "
    "(wskaźnik ambicji). Zawsze dotyczy matematyki.",
)
if not worst.empty:
    w = worst.iloc[0]
    k4.metric(
        "Najsłabszy powiat (≥ 100 zdających)",
        str(w["county"]),
        delta=f"{fmt_pl(w[pass_col], 1)}% — {w['voivodeship']}",
        delta_color="off",
    )
else:
    k4.metric("Najsłabszy powiat (≥ 100 zdających)", "—")

st.divider()


# ---------------------------------------------------------------------------
# Zakładki
# ---------------------------------------------------------------------------
tab_gap, tab_map, tab_split, tab_trend, tab_about = st.tabs(
    ["📊 Wąskie gardło", "🗺️ Mapa powiatów", "🏫 Rozwarstwienie", "🎯 Ambicje i trendy", "ℹ️ O danych"]
)

# --- 1. Wąskie gardło -------------------------------------------------------
with tab_gap:
    col_bar, col_heat = st.columns(2)

    # W latach niepełnych Formułę 2023 zdawały niemal wyłącznie licea, więc
    # rocznik jest miarodajny dla "wszystkie" (z zastrzeżeniem) i dla "LO",
    # ale dla techników (16 szkół w 2023) to szum — pomijamy zamiast pokazywać
    # mylące słupki.
    years_shown = [
        y for y in YEARS if kind in ("wszystkie", "LO") or y not in partial_years
    ]

    with col_bar:
        rows = []
        for y in years_shown:
            g = cc_scope[cc_scope["year"] == y]
            rows += [
                {"rok": y, "przedmiot": "matematyka",
                 "zdawalność": data.weighted_mean(g, "math_pp_pass_rate", "math_pp_n")},
                {"rok": y, "przedmiot": "język polski",
                 "zdawalność": data.weighted_mean(g, "pol_pp_pass_rate", "pol_pp_n")},
                {"rok": y, "przedmiot": "język angielski",
                 "zdawalność": data.weighted_mean(g, "eng_pp_pass_rate", "eng_pp_n")},
                {"rok": y, "przedmiot": "cała matura (świadectwo)",
                 "zdawalność": data.weighted_mean(g, "overall_pass_rate", "overall_taken")},
            ]
        tidy = pd.DataFrame(rows).dropna(subset=["zdawalność"])
        st.plotly_chart(
            charts.subject_pass_bar(tidy, f"{scope_label}{kind_note}"), width="stretch"
        )
        # dropna(how="all"): wiersze bez żadnej zdawalności (np. powiaty z samymi
        # utajnionymi metrykami przy filtrze typu szkoły) wywalają idxmin
        # w nowszych wersjach pandas ("Encountered all NA values").
        subj_mat = (
            cc_scope[["math_pp_pass_rate", "pol_pp_pass_rate", "eng_pp_pass_rate"]]
            .dropna(how="all")
        )
        share_math_worst = (
            (subj_mat.idxmin(axis=1) == "math_pp_pass_rate").mean()
            if not subj_mat.empty
            else float("nan")
        )
        st.caption(
            f"💡 **Wniosek:** matematyka jest najsłabszym z trzech przedmiotów "
            f"obowiązkowych w {fmt_pl(share_math_worst * 100, 0)}% powiato-lat "
            f"w wybranym zakresie — to ona generuje rynek „ratowania matury”. "
            f"Zdawalność ogólna (świadectwo) jest z konstrukcji najniższa: "
            f"oblanie dowolnego przedmiotu odbiera świadectwo."
        )

    with col_heat:
        heat = (
            cc_scope[cc_scope["year"].isin(years_shown)]
            .groupby(["voivodeship", "year"])
            .apply(lambda g: data.weighted_mean(g, pass_col, n_col), include_groups=False)
            .unstack("year")
            .sort_index(ascending=False)
        )
        st.plotly_chart(
            charts.voivodeship_heatmap(heat, subject_label), width="stretch"
        )
        st.caption(
            "💡 **Wniosek:** spadek zdawalności między latami to w dużej mierze "
            "efekt dochodzenia techników do Formuły 2023 (2023 = niemal same "
            "licea) — ale różnice MIĘDZY województwami utrzymują się co roku, "
            "niezależnie od formuły."
        )

# --- 2. Mapa powiatów -------------------------------------------------------
with tab_map:
    metric_label = st.radio(
        "Pokaż na mapie",
        ["zdawalność (%)", "liczba oblewających", "podchodzący do PR (%)"],
        horizontal=True,
        help="Liczba oblewających = zdający × (1 − zdawalność). "
        "Wskaźnik PR zawsze dotyczy matematyki.",
    )

    map_df = cc_year.copy()
    if metric_label == "zdawalność (%)":
        map_df["value"] = map_df[pass_col]
        cfg = dict(
            value_label="%", color_scale="RdYlGn",
            title=f"Zdawalność: {subject_label} PP po powiatach — {year}{kind_note}",
            caption=f"💡 **Wniosek:** rozstrzał między powiatami sięga "
            f"kilkudziesięciu p.p. i jest trwały między latami — w najsłabszych "
            f"powiatach nawet co trzeci maturzysta oblewa. Lokalizacja to "
            f"pierwszy filtr przy planowaniu oferty korepetycji.",
            ascending_is_bad=True,
        )
    elif metric_label == "liczba oblewających":
        map_df["value"] = map_df[n_col] * (1 - map_df[pass_col] / 100)
        cfg = dict(
            value_label="osoby", color_scale="Reds",
            title=f"Szacowana liczba oblewających: {subject_label} PP — {year}{kind_note}",
            caption="💡 **Wniosek:** wolumen rynku siedzi w metropoliach — "
            "Warszawa, Wrocław, Kraków czy Poznań mają zdawalność powyżej "
            "średniej, ale to tam mieszka najwięcej osób do uratowania. "
            "Drugi biegun: powiaty o niskiej zdawalności i małej podaży "
            "korepetytorów — naturalny rynek dla nauki online.",
            ascending_is_bad=False,
        )
    else:
        map_df["value"] = map_df["ambition_ratio"] * 100
        cfg = dict(
            value_label="% PP", color_scale="Blues",
            title=f"Podchodzący do matematyki PR jako % zdających PP — {year}{kind_note}",
            caption="💡 **Wniosek:** ambicje koncentrują się w metropoliach "
            "i na południowym wschodzie; są powiaty, gdzie do rozszerzenia "
            "nie podchodzi nikt. Tam, gdzie podstawa kuleje, znika też rynek "
            "przygotowania do PR — podwójne wykluczenie edukacyjne.",
            ascending_is_bad=False,
        )
        if subject_label != "matematyka":
            st.info("Wskaźnik rozszerzenia dotyczy matematyki — mapa pokazuje "
                    "matematykę niezależnie od filtra przedmiotu.")

    st.plotly_chart(
        charts.county_map(
            map_df,
            get_geojson(),
            data.GEOJSON_FEATURE_KEY,
            "value",
            cfg["value_label"],
            cfg["title"],
            cfg["color_scale"],
            hover_extra={n_col: ":,"},
        ),
        width="stretch",
    )
    st.caption(cfg["caption"])

    rank_df = (
        map_df.dropna(subset=["value"])
        .loc[map_df[n_col] >= 100, ["county", "voivodeship", "value", n_col]]
    )
    col_lo, col_hi = st.columns(2)
    bad_first = rank_df.sort_values("value", ascending=cfg["ascending_is_bad"])
    col_cfg = {
        "county": st.column_config.TextColumn("powiat"),
        "voivodeship": st.column_config.TextColumn("województwo"),
        "value": st.column_config.NumberColumn(cfg["value_label"], format="%.1f"),
        n_col: st.column_config.NumberColumn("zdający", format="%d"),
    }
    with col_lo:
        st.markdown("**🔴 Największa potrzeba wsparcia** (powiaty ≥ 100 zdających)")
        st.dataframe(bad_first.head(10), hide_index=True, column_config=col_cfg,
                     width="stretch")
    with col_hi:
        st.markdown("**🟢 Najlepsze wyniki**")
        st.dataframe(bad_first.tail(10).iloc[::-1], hide_index=True,
                     column_config=col_cfg, width="stretch")

# --- 3. Rozwarstwienie ------------------------------------------------------
with tab_split:
    if year in partial_years:
        st.warning(
            f"⚠️ W {year} r. Formułę 2023 zdawali niemal wyłącznie absolwenci "
            f"liceów (technika kończyły Formułę 2015). Porównania LO vs "
            f"technikum są dla tego rocznika niemiarodajne — wybierz "
            f"{min(y for y in YEARS if y not in partial_years)} lub później."
        )

    split_choice = st.radio(
        "Porównaj szkoły według",
        ["LO vs technikum", "publiczne vs niepubliczne", "miasto vs wieś"],
        horizontal=True,
    )

    sh = s_year[(s_year[n_col] >= 10)].dropna(subset=[pass_col]).copy()
    if split_choice == "LO vs technikum":
        sh = sh[sh["school_kind"].isin(["LO", "Technikum"])]
        sh["grupa"] = sh["school_kind"]
        split_caption = (
            "💡 **Wniosek:** dwa różne światy — znaczna część LO ma komplet "
            "zdanych matur z matematyki, technika są przesunięte o kilkanaście "
            "punktów w lewo, a luka rośnie z roku na rok. Uczeń technikum to "
            "niedoceniany segment rynku: matematyka na maturze ta sama, "
            "wsparcia wokół mniej."
        )
    elif split_choice == "publiczne vs niepubliczne":
        sh = sh[sh["is_public"].notna()]
        sh["grupa"] = sh["is_public"].map({True: "publiczna", False: "niepubliczna"})
        split_caption = (
            "💡 **Uwaga interpretacyjna:** niższe wyniki części szkół "
            "niepublicznych nie oznaczają „gorszych szkół” — wśród "
            "niepublicznych dużo jest liceów dla dorosłych i szkół zaocznych, "
            "czyli zupełnie innej populacji zdających (powroty do matury po "
            "latach). To osobny, specyficzny segment rynku wsparcia."
        )
    else:
        sh["grupa"] = sh["is_rural"].map({True: "wieś", False: "miasto"})
        split_caption = (
            "💡 **Wniosek:** szkoły w gminach wiejskich wypadają słabiej nawet "
            "po rozdzieleniu LO i techników — to nie tylko efekt struktury "
            "typów szkół. Nauka zdalna/online może docierać tam, gdzie podaż "
            "stacjonarnych korepetycji jest najmniejsza."
        )

    if sh.empty or sh["grupa"].nunique() < 1:
        st.info("Za mało danych w wybranym zakresie — poszerz filtry.")
    else:
        col_h, col_b = st.columns(2)
        with col_h:
            st.plotly_chart(
                charts.school_histogram(sh, pass_col, "grupa", subject_label, year),
                width="stretch",
            )
        with col_b:
            st.plotly_chart(
                charts.school_box(sh, pass_col, "grupa", subject_label, year),
                width="stretch",
            )
        st.caption(split_caption)

        summary = (
            sh.groupby("grupa")
            .apply(
                lambda g: pd.Series({
                    "zdawalność ważona (%)": data.weighted_mean(g, pass_col, n_col),
                    "liczba zdających": g[n_col].sum(),
                    "liczba szkół": len(g),
                }),
                include_groups=False,
            )
            .reset_index()
        )
        st.dataframe(
            summary,
            hide_index=True,
            column_config={
                "grupa": st.column_config.TextColumn("grupa"),
                "zdawalność ważona (%)": st.column_config.NumberColumn(
                    "zdawalność ważona (%)", format="%.1f"),
                "liczba zdających": st.column_config.NumberColumn(
                    "liczba zdających", format="%d"),
                "liczba szkół": st.column_config.NumberColumn(
                    "liczba szkół", format="%d"),
            },
            width="stretch",
        )
        st.caption(
            "Tabela: szkoły z ≥ 10 zdającymi w wybranym zakresie filtrów. "
            "Zdawalność ważona liczbą zdających."
        )

# --- 4. Ambicje i trendy ----------------------------------------------------
with tab_trend:
    col_sc, col_tr = st.columns(2)

    with col_sc:
        if subject_label != "matematyka":
            st.info("Wskaźnik ambicji (PR/PP) dotyczy matematyki — wykres "
                    "pokazuje matematykę niezależnie od filtra przedmiotu.")
        st.plotly_chart(charts.ambition_scatter(cc_year, year), width="stretch")
        sc_df = cc_year.dropna(subset=["math_pp_pass_rate", "ambition_ratio"])
        corr_txt = ""
        if len(sc_df) >= 10:
            corr = sc_df["math_pp_pass_rate"].corr(sc_df["ambition_ratio"])
            corr_txt = f" (korelacja {fmt_pl(corr, 2)})"
        st.caption(
            f"💡 **Wniosek:** ambicje idą w parze ze skutecznością{corr_txt} — "
            f"gdzie zdawalność podstawy niska, tam do rozszerzenia podchodzi "
            f"garstka. To **współwystępowanie, nie przyczynowość**: oba "
            f"zjawiska mogą wynikać z tego samego zaplecza "
            f"społeczno-ekonomicznego. Dla rynku wniosek jest praktyczny: "
            f"przygotowanie do PR sprzedaje się tam, gdzie podstawa stoi mocno."
        )

    with col_tr:
        if kind == "wszystkie":
            # Linia "tylko LO" to metodologiczne odniesienie — jedyna populacja
            # porównywalna przez wszystkie lata (2023 = niemal same licea).
            lo_scope = s_scope[s_scope["school_kind"] == "LO"]
            trend = pd.DataFrame(
                {
                    "cała populacja": [
                        data.weighted_mean(c_scope[c_scope["year"] == y], pass_col, n_col)
                        for y in YEARS
                    ],
                    "tylko LO": [
                        data.weighted_mean(lo_scope[lo_scope["year"] == y], pass_col, n_col)
                        for y in YEARS
                    ],
                },
                index=YEARS,
            )
        else:
            # Przy filtrze typu szkoły: wybrany typ + odniesienie do wszystkich.
            # Lata niemiarodajne dla wybranego typu → NaN (2023 = 16 techników;
            # dla LO rok 2023 jest pełnoprawny).
            trend = pd.DataFrame(
                {
                    f"tylko {kind}": [
                        data.weighted_mean(cc_scope[cc_scope["year"] == y], pass_col, n_col)
                        if (kind == "LO" or y not in partial_years)
                        else float("nan")
                        for y in YEARS
                    ],
                    "wszystkie szkoły": [
                        data.weighted_mean(c_scope[c_scope["year"] == y], pass_col, n_col)
                        for y in YEARS
                    ],
                },
                index=YEARS,
            )
        st.plotly_chart(
            charts.trend_line(trend, subject_label, scope_label, partial_years),
            width="stretch",
        )
        st.caption(
            "💡 **Wniosek:** zdawalność spada nawet w porównywalnej populacji "
            "liceów — to nie tylko efekt dojścia techników do formuły, ale też "
            "zaostrzania wymagań po pandemii. Rynek wsparcia nie maleje: "
            "z każdym rokiem przybywa maturzystów z problemem z matematyką. "
            "Linia „tylko LO” jest porównywalna przez wszystkie lata; linia "
            "pełnej populacji obejmuje szkoły objęte Formułą 2023 w danym roku."
        )

# --- 5. O danych ------------------------------------------------------------
with tab_about:
    n_schools = schools.groupby("year")["rspo"].nunique()
    st.markdown(
        f"""
### Źródło danych

- **CKE / [mapa.wyniki.edu.pl](https://mapa.wyniki.edu.pl)** — wyniki egzaminu
  maturalnego w **Formule 2023**, eksporty XLSX per powiat i per szkoła.
- Aktualizacja **wrześniowa (09)** = sesja główna **+ poprawkowa** — stąd
  zdawalność wyższa niż w lipcowych komunikatach prasowych CKE.
- Lata: **{YEARS[0]}–{LATEST}**; {fmt_pl(len(counties))} wierszy powiatowych,
  {fmt_pl(len(schools))} szkolnych ({fmt_pl(n_schools.max())} szkół w {int(n_schools.idxmax())} r.).
- Granice powiatów: **Państwowy Rejestr Granic (PRG)** — dane publiczne
  GUGiK udostępniane nieodpłatnie przez [Geoportal](https://www.geoportal.gov.pl)
  (art. 40a ust. 2 pkt 1 ustawy Prawo geodezyjne i kartograficzne).
  Konwersja do GeoJSON/WGS84 i uproszczenie geometrii:
  [github.com/waszkiewiczja/GeoJSON-Polska-Wojewodztwa-Powiaty-Gminy](https://github.com/waszkiewiczja/GeoJSON-Polska-Wojewodztwa-Powiaty-Gminy)
  (stan granic: sierpień 2025). Dopasowanie do danych CKE po kodach TERYT.

### Decyzje przy czyszczeniu danych

- **Trzyrzędowy nagłówek** (pasmo → przedmiot+poziom → metryka) składany
  przez forward-fill scalonych komórek; normalizacja nazw (prefiks `* `,
  białe znaki, wielkość liter).
- Używamy **wyłącznie wariantów przedmiotów z sufiksem „(M)”** — bliźniacze
  kolumny bez „(M)” są w plikach źródłowych puste.
- Z ~75 wariantów przedmiot×poziom zawężamy do: **matematyka PP i PR**,
  **język polski PP**, **język angielski PP** + **zdawalność ogólna**.
- Kody **TERYT jako tekst** (wiodące zera); rok z nazwy pliku.
- Usunięte **pseudo-powiaty „OKRĘGOWA KOMISJA EGZAMINACYJNA…”** (po 8 na rok,
  kilkunastu–kilkudziesięciu zdających przypisanych wprost do OKE) — dublowały
  kody TERYT miast-siedzib komisji.
- Puste metryki małych szkół/powiatów zostają jako braki (NaN) — **wyjątek:**
  pusta liczba zdających PR oznacza **0 zdających** (portal raportuje nawet
  n=1, utajnia dopiero wyniki), więc wskaźnik ambicji traktuje ją jako zero.
- Średnie krajowe/wojewódzkie zawsze **ważone liczbą zdających**.

### Zastrzeżenia metodologiczne

- **Rok 2023 obejmuje niemal wyłącznie licea** — technika kończyły wtedy
  jeszcze Formułę 2015. Porównania LO/technikum liczymy od 2024 r., a trend
  2023→{LATEST} ma adnotację na wykresie.
- **Poziom rozszerzony nie ma zdawalności** (brak progu zdania dla przedmiotów
  dodatkowych) — porównujemy uczestnictwo (wskaźnik ambicji = zdający PR /
  zdający PP) i średnie wyniki.
- Dane są **zagregowane per lokalizacja** (powiat/szkoła) — wnioski dotyczą
  jednostek terytorialnych, nie pojedynczych uczniów (ryzyko błędu ekologicznego).
- „Liczba oblewających” to szacunek: zdający × (1 − zdawalność).

### Po co ten dashboard

Prowadzę korepetycje z matematyki dla licealistów i buduję aplikację do
treningu matematyki (12–18 lat). Ten dashboard to research rynkowy: **gdzie
popyt na wsparcie z matematyki jest największy** — geograficznie (mapa),
strukturalnie (LO/technikum, miasto/wieś) i w czasie (trendy).
"""
    )
