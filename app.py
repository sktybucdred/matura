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


@st.cache_data(show_spinner=False)
def get_wages() -> pd.DataFrame:
    return data.load_wages()


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
    kind = st.radio(
        "Typ szkoły", ["wszystkie", "LO", "Technikum"], horizontal=True,
        help="Technika zdają Formułę 2023 dopiero od 2024 r. — dla roku 2023 "
        "dane techników to tylko 16 szkół (wyniki utajnione).",
    )
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
    "i per szkoła. Zakładki czytaj od lewej do prawej: **co** jest wąskim "
    "gardłem matury → **gdzie** boli najbardziej → **kogo** dotyczy → "
    "**dokąd** zmierzają ambicje i trendy → **jaki** rynek się w tym "
    "kryje → **wnioski** dla biznesu."
)

# Rocznik niepełnego pokrycia (2023 = niemal same licea) potrafi wyglądać jak
# zepsuta aplikacja (KPI „—”, pusta mapa dla techników) — ostrzegamy na górze
# strony, nie dopiero w zakładce Rozwarstwienie.
if year in partial_years:
    if kind == "Technikum":
        st.warning(
            f"⚠️ W {year} r. Formułę 2023 zdawali niemal wyłącznie absolwenci "
            f"liceów — technika to w tym roczniku margines (w wybranym "
            f"zakresie szkoły: {len(s_year)}, zdający: "
            f"{fmt_pl(s_year[n_col].sum())}), a wyniki tak małych prób CKE "
            f"utajnia (stąd „—” w KPI i pusta mapa zdawalności). Wybierz rok "
            f"{min(y for y in YEARS if y not in partial_years)} lub nowszy."
        )
    elif kind == "wszystkie":
        st.info(
            f"ℹ️ W {year} r. Formułę 2023 zdawały niemal wyłącznie licea "
            f"(technika kończyły Formułę 2015) — wskaźniki opisują de facto "
            f"populację LO i nie są porównywalne 1:1 z późniejszymi latami."
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
        # Delta względem rocznika niepełnego pokrycia porównuje różne
        # populacje (2023 = niemal same LO) — zastrzegamy to wprost.
        if prev_year in partial_years and kind == "wszystkie":
            delta_text += " (wtedy: niemal same LO)"

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
tab_gap, tab_map, tab_split, tab_trend, tab_market, tab_summary, tab_about = st.tabs(
    ["📊 Wąskie gardło", "🗺️ Mapa powiatów", "🏫 Rozwarstwienie",
     "🎯 Ambicje i trendy", "💰 Rynek", "📌 Wnioski", "ℹ️ O danych"]
)

# --- 1. Wąskie gardło -------------------------------------------------------
with tab_gap:
    # W latach niepełnych Formułę 2023 zdawały niemal wyłącznie licea, więc
    # rocznik jest miarodajny dla "wszystkie" (z zastrzeżeniem) i dla "LO",
    # ale dla techników (16 szkół w 2023) to szum — pomijamy zamiast pokazywać
    # mylące słupki. Nota MUSI iść przed st.columns, żeby wyrenderować się
    # nad wykresami.
    years_shown = [
        y for y in YEARS if kind in ("wszystkie", "LO") or y not in partial_years
    ]
    skipped = [y for y in YEARS if y not in years_shown]
    if skipped:
        skipped_txt = ", ".join(map(str, skipped))
        word = "rok" if len(skipped) == 1 else "lata"
        st.caption(
            f"ℹ️ Wykresy pomijają {word} {skipped_txt} dla techników — "
            f"Formuła 2023 obejmowała wtedy pojedyncze technika "
            f"(16 szkół w 2023 r.); słupki byłyby szumem, nie trendem."
        )

    col_bar, col_heat = st.columns(2)

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
            f"oblanie dowolnego przedmiotu odbiera świadectwo. "
            f"*Uwaga: oś Y jest ucięta (zaczyna się od ~70%, nie od zera) — "
            f"pełna skala 0–100 ukryłaby różnice rzędu kilku p.p.; proporcje "
            f"długości słupków nie odpowiadają więc proporcjom wartości.*"
        )

    with col_heat:
        heat = (
            cc_scope[cc_scope["year"].isin(years_shown)]
            .groupby(["voivodeship", "year"])
            .apply(lambda g: data.weighted_mean(g, pass_col, n_col), include_groups=False)
            .unstack("year")
        )
        # Sortowanie po najnowszym roku zamienia heatmapę w ranking:
        # najsłabsze województwa na górze (px.imshow rysuje pierwszy wiersz
        # na górze) — spójnie z narracją "wąskiego gardła". Porządek
        # alfabetyczny nie niósł żadnej informacji.
        heat = heat.sort_values(by=heat.columns[-1], ascending=True)
        st.plotly_chart(
            charts.voivodeship_heatmap(heat, subject_label), width="stretch"
        )
        st.caption(
            "💡 **Wniosek:** dojście techników do Formuły 2023 (2023 = niemal "
            "same licea) tłumaczy tylko część spadku między latami — dla "
            "matematyki w skali kraju z ~7 p.p. spadku 2023→2025 ok. 4 p.p. "
            "dzieje się w samych LO (szczegóły: zakładka „Ambicje i trendy”). "
            "Trwalsze od trendu są różnice MIĘDZY województwami: kilkupunktowy "
            "rozrzut między regionami powtarza się w każdym roku, niezależnie "
            "od formuły."
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
            value_label="%", color_scale="RdYlBu",
            title=f"Zdawalność: {subject_label} PP po powiatach — {year}{kind_note}",
            caption="💡 **Wniosek:** to w matematyce różnice między powiatami "
            "są największe — w 2025 r. w skali kraju rozstrzał sięga ~35 p.p. "
            "(polski: ~17 p.p., angielski: ~20 p.p.; powiaty ≥ 100 zdających), "
            "a w najsłabszych powiatach matematykę oblewa co trzeci maturzysta. "
            "Ranking powiatów jest przy tym stabilny rok do roku (korelacja "
            "~0,7), więc to cecha strukturalna, nie losowość arkusza — "
            "lokalizacja to pierwszy filtr przy planowaniu oferty korepetycji.",
            ascending_is_bad=True,
        )
    elif metric_label == "liczba oblewających":
        map_df["value"] = map_df[n_col] * (1 - map_df[pass_col] / 100)
        cfg = dict(
            value_label="osoby", color_scale="Reds", value_fmt=":.0f",
            title=f"Szacowana liczba oblewających: {subject_label} PP — {year}{kind_note}",
            caption="💡 **Wniosek:** wolumen rynku siedzi w metropoliach — "
            "Warszawa, Wrocław, Kraków czy Poznań mają zdawalność powyżej "
            "średniej, ale to tam mieszka najwięcej osób do uratowania "
            "(sama Warszawa: ~2,2 tys. oblewających matematykę w 2025 r.). "
            "Drugi biegun: powiaty o niskiej zdawalności, gdzie podaż "
            "stacjonarnych korepetycji jest przypuszczalnie najmniejsza "
            "(wniosek z zamożności i gęstości zaludnienia, nie z danych "
            "o korepetytorach — patrz „Wnioski”) — naturalny rynek dla "
            "nauki online.",
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

    # Guard pustego widoku: przy skrajnych filtrach (np. 2023 + Technikum)
    # wszystkie wartości są utajnione — zamiast szarej mapy z wnioskiem
    # i pustych rankingów pokazujemy komunikat.
    if map_df["value"].notna().sum() == 0:
        st.info(
            "Brak danych do pokazania na mapie dla tej kombinacji filtrów "
            "(wyniki utajnione przy małych próbach) — zmień rok lub typ szkoły."
        )
    else:
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
                value_fmt=cfg.get("value_fmt", ":.1f"),
            ),
            width="stretch",
        )
        st.caption(cfg["caption"])
        st.caption(
            "🎨 Skala barw przycięta do 2.–98. percentyla powiatów, żeby "
            "pojedyncze skrajne wartości (np. Warszawa wolumenem) nie "
            "spłaszczały kolorów reszty mapy; powiaty poza zakresem dostają "
            "kolor krańcowy. Dokładne wartości zawsze w dymku po najechaniu."
        )

        # format="localized" nie kontroluje miejsc po przecinku — zaokrąglamy
        # przed wyświetleniem (oblewający do całości, odsetki do 0,1).
        rank_decimals = 1 if cfg.get("value_fmt", ":.1f") == ":.1f" else 0
        rank_df = (
            map_df.dropna(subset=["value"])
            .loc[map_df[n_col] >= 100, ["county", "voivodeship", "value", n_col]]
            .assign(value=lambda d: d["value"].round(rank_decimals))
        )
        col_lo, col_hi = st.columns(2)
        bad_first = rank_df.sort_values("value", ascending=cfg["ascending_is_bad"])
        col_cfg = {
            "county": st.column_config.TextColumn("powiat"),
            "voivodeship": st.column_config.TextColumn("województwo"),
            "value": st.column_config.NumberColumn(cfg["value_label"], format="localized"),
            n_col: st.column_config.NumberColumn("zdający", format="localized"),
        }
        with col_lo:
            st.markdown("**🔴 Największa potrzeba wsparcia** (powiaty ≥ 100 zdających)")
            st.dataframe(bad_first.head(10), hide_index=True, column_config=col_cfg,
                         width="stretch")
        with col_hi:
            st.markdown("**🟢 Najlepsze wyniki** (powiaty ≥ 100 zdających)")
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
            "zdanych matur z matematyki (w 2025 r. 30% liceów ze 100% "
            "zdawalnością), technika są przesunięte o kilkanaście punktów "
            "w lewo, a luka w skali kraju wzrosła z 5,0 p.p. (2024) do "
            "8,0 p.p. (2025). Uczeń technikum to niedoceniany segment rynku: "
            "matematyka na maturze ta sama, wsparcia wokół mniej."
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
                    # round: format="localized" nie kontroluje liczby miejsc.
                    "zdawalność ważona (%)": round(
                        data.weighted_mean(g, pass_col, n_col), 1
                    ),
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
                # "localized": przecinek dziesiętny i spacja tysięcy jak na
                # wykresach (printf-owe "%.1f" dawało kropkę i 19073).
                "zdawalność ważona (%)": st.column_config.NumberColumn(
                    "zdawalność ważona (%)", format="localized"),
                "liczba zdających": st.column_config.NumberColumn(
                    "liczba zdających", format="localized"),
                "liczba szkół": st.column_config.NumberColumn(
                    "liczba szkół", format="localized"),
            },
            width="stretch",
        )
        st.caption(
            "Tabela: szkoły z ≥ 10 zdającymi w wybranym zakresie filtrów. "
            "Zdawalność ważona liczbą zdających. Na boxplocie linia ciągła "
            "w pudełku = mediana, linia przerywana = średnia arytmetyczna "
            "szkół w grupie."
        )

# --- 4. Ambicje i trendy ----------------------------------------------------
with tab_trend:
    col_sc, col_tr = st.columns(2)

    with col_sc:
        if subject_label != "matematyka":
            st.info("Wskaźnik ambicji (PR/PP) dotyczy matematyki — wykres "
                    "pokazuje matematykę niezależnie od filtra przedmiotu.")
        st.plotly_chart(charts.ambition_scatter(cc_year, year), width="stretch")
        sc_df = cc_year.dropna(
            subset=["math_pp_pass_rate", "ambition_ratio", "math_pp_n"]
        )
        corr_txt = ""
        if len(sc_df) >= 10:
            # Ważona liczbą zdających — spójnie z metodologią zakładki
            # Wnioski (mikropowiaty to głównie szum małych prób).
            corr = data.weighted_corr(
                sc_df, "math_pp_pass_rate", "ambition_ratio", "math_pp_n"
            )
            corr_txt = f" (korelacja ważona liczbą zdających: {fmt_pl(corr, 2)})"
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
        # Caption zależny od filtra typu szkoły — statyczny opisywałby linię
        # "tylko LO", której przy filtrze Technikum nie ma na wykresie.
        if kind == "wszystkie":
            trend_caption = (
                "💡 **Wniosek:** zdawalność spada nawet w porównywalnej "
                "populacji liceów — trend nie sprowadza się więc do dojścia "
                "techników do Formuły 2023. Możliwym kontekstem zewnętrznym "
                "jest stopniowe odchodzenie od pandemicznych ułatwień "
                "egzaminacyjnych (dane CKE pokazują sam spadek, nie jego "
                "przyczynę). Rynek wsparcia nie maleje: z każdym rokiem "
                "przybywa maturzystów z problemem z matematyką. Linia "
                "„tylko LO” jest porównywalna przez wszystkie lata; linia "
                "pełnej populacji obejmuje szkoły objęte Formułą 2023 "
                "w danym roku."
            )
        elif kind == "LO":
            trend_caption = (
                "💡 **Wniosek:** zdawalność spada nawet w samych liceach — "
                "to nie tylko efekt dojścia techników do Formuły 2023. Linia "
                "„wszystkie szkoły” spada szybciej, bo od 2024 r. obejmuje "
                "również słabsze technika."
            )
        else:
            trend_caption = (
                "💡 **Wniosek:** technika tracą zdawalność szybciej niż cała "
                "populacja — luka do liceów urosła między 2024 a 2025 r., "
                "a technika już dziś generują więcej oblewających niż licea. "
                "Rok 2023 na linii techników pominięty: Formułę 2023 zdawało "
                "wtedy tylko 16 techników (szum, nie trend)."
            )
        st.caption(trend_caption)

# --- 5. Rynek: wolumen × zamożność -------------------------------------------
with tab_market:
    if subject_label != "matematyka":
        st.info("Ta sekcja dotyczy matematyki — wykres nie zmienia się z filtrem "
                "przedmiotu.")

    wages = get_wages()
    wage_year = int(wages["wage_year"].iloc[0])
    market_df = cc_year.merge(wages, on="teryt_county", how="inner").copy()
    market_df["failers"] = market_df["math_pp_n"] * (
        1 - market_df["math_pp_pass_rate"] / 100
    )
    market_df = market_df.dropna(subset=["failers", "wage"])

    if len(market_df) < 5:
        st.info("Za mało powiatów w wybranym zakresie — poszerz filtry.")
    else:
        st.plotly_chart(
            charts.wage_scatter(market_df, year, wage_year), width="stretch"
        )
        st.caption(
            "💡 **Wniosek:** mediany dzielą rynek na cztery segmenty. Prawy górny "
            "róg (dużo oblewających + wysokie płace: metropolie) to naturalny "
            "rynek korepetycji premium 1:1. Prawy dolny (dużo oblewających + "
            "niższe płace) to segment, gdzie stacjonarne korki przegrywają "
            "z ceną — tu najlepiej pozycjonuje się tania aplikacja do "
            "samodzielnego treningu. To **współwystępowanie, nie "
            "przyczynowość** — zamożność i wyniki mają wspólne zaplecze "
            "społeczno-ekonomiczne. Uwaga: GUS liczy płace wg miejsca pracy, "
            "nie zamieszkania — powiaty sypialniane wokół metropolii wyglądają "
            "na uboższe, niż są."
        )

# --- 6. Wnioski: synteza na pełnych danych ------------------------------------
with tab_summary:
    st.caption(
        f"Ta zakładka podsumowuje **pełne dane za {LATEST} r.** (cała Polska, "
        f"wszystkie typy szkół) — celowo nie reaguje na filtry w sidebarze."
    )

    # Wszystko liczone na żywo — po dorzuceniu pliku za nowy rok wnioski
    # przeliczą się same.
    c_last = counties[counties["year"] == LATEST].copy()
    s_last = schools[schools["year"] == LATEST]
    wages_full = get_wages()
    wage_year_full = int(wages_full["wage_year"].iloc[0])

    c_last["failers"] = c_last["math_pp_n"] * (1 - c_last["math_pp_pass_rate"] / 100)
    c_last = c_last.merge(wages_full, on="teryt_county", how="left")

    total_failers = c_last["failers"].sum()
    math_pass = data.weighted_mean(c_last, "math_pp_pass_rate", "math_pp_n")
    pol_pass = data.weighted_mean(c_last, "pol_pp_pass_rate", "pol_pp_n")
    eng_pass = data.weighted_mean(c_last, "eng_pp_pass_rate", "eng_pp_n")
    share_worst = (
        c_last[["math_pp_pass_rate", "pol_pp_pass_rate", "eng_pp_pass_rate"]]
        .dropna(how="all")
        .idxmin(axis=1)
        .eq("math_pp_pass_rate")
        .mean()
    )

    def kind_failers(kind_name: str) -> float:
        g = s_last[s_last["school_kind"] == kind_name].dropna(
            subset=["math_pp_pass_rate", "math_pp_n"]
        )
        return (g["math_pp_n"] * (1 - g["math_pp_pass_rate"] / 100)).sum()

    tech_failers = kind_failers("Technikum")
    lo_failers = kind_failers("LO")
    tech_n = s_last.loc[s_last["school_kind"] == "Technikum", "math_pp_n"].sum()
    lo_n = s_last.loc[s_last["school_kind"] == "LO", "math_pp_n"].sum()

    corr_wage_pass = data.weighted_corr(
        c_last, "wage", "math_pp_pass_rate", "math_pp_n"
    )
    corr_wage_amb = data.weighted_corr(c_last, "wage", "ambition_ratio", "math_pp_n")

    # Rozstrzał i korelacja rok-do-roku liczone na żywo (jak reszta sekcji) —
    # zahardcodowane wartości rozjechałyby się po dorzuceniu nowego rocznika.
    big_last = c_last[c_last["math_pp_n"] >= 100]
    spread_pp = (
        big_last["math_pp_pass_rate"].max() - big_last["math_pp_pass_rate"].min()
    )
    piv = counties.pivot_table(
        index="teryt_county", columns="year", values="math_pp_pass_rate"
    ).dropna()
    yoy_corr = (
        piv[LATEST - 1].corr(piv[LATEST])
        if (LATEST - 1) in piv.columns
        else float("nan")
    )

    st.markdown(
        f"""
### Co mówią dane ({LATEST})

1. **Matematyka to wąskie gardło matury.** Zdawalność {fmt_pl(math_pass, 1)}%
   wobec {fmt_pl(pol_pass, 1)}% z polskiego i {fmt_pl(eng_pass, 1)}%
   z angielskiego; najsłabszy przedmiot w {fmt_pl(share_worst * 100, 0)}%
   powiatów. Rynek „ratowania matury z matematyki” to
   **~{fmt_pl(total_failers / 1000, 1)} tys. osób rocznie** — i rośnie
   (trend zniżkowy zdawalności nawet w samych LO).
2. **Geografia ma znaczenie i jest trwała.** Rozstrzał między powiatami sięga
   ~{fmt_pl(spread_pp, 0)} p.p., a korelacja wyników rok-do-roku
   {fmt_pl(yoy_corr, 2)} — słabe powiaty nie są przypadkiem statystycznym,
   tylko strukturalną cechą lokalną.
3. **Technika to (ponad) połowa rynku.** Przy {fmt_pl(tech_n)} zdających
   (wobec {fmt_pl(lo_n)} w LO) technika generują
   **{fmt_pl(tech_failers / 1000, 1)} tys. oblewających** —
   {fmt_pl(100 * tech_failers / (tech_failers + lo_failers), 0)}% sumy
   LO+technika, czyli w liczbach bezwzględnych więcej niż licea —
   a luka do LO rośnie z roku na rok.
4. **Zamożność silniej wiąże się z ambicjami niż ze zdawalnością.** Korelacja
   ważona płac ze zdawalnością to ledwie {fmt_pl(corr_wage_pass, 2)}, ale
   z odsetkiem podchodzących do rozszerzenia — już {fmt_pl(corr_wage_amb, 2)}.
   Bogatszy powiat niekoniecznie lepiej zdaje podstawę, ale znacznie częściej
   celuje w studia techniczne. (Współwystępowanie, nie przyczynowość.)
5. **Dwa produkty, dwie geografie.** Korepetycje premium 1:1 mają rynek tam,
   gdzie wolumen spotyka zamożność (metropolie). Tania aplikacja do
   samodzielnego treningu wygrywa tam, gdzie oblewających dużo, a płace
   poniżej mediany — oraz na wsi, gdzie podaż stacjonarnych korepetycji
   jest najmniejsza (szkoły wiejskie słabsze nawet w ramach tego samego
   typu szkoły).
"""
    )

    # Wizualny dowód dla wniosku nr 4 — bez niego korelacje wisiałyby
    # w powietrzu jako gołe liczby.
    corr_unweighted = float(
        c_last[["wage", "math_pp_pass_rate"]].dropna().corr().iloc[0, 1]
    )
    st.plotly_chart(
        charts.wage_relation_panels(
            c_last, LATEST, wage_year_full, corr_wage_pass, corr_wage_amb
        ),
        width="stretch",
    )
    st.caption(
        f"📐 **Metodologia:** korelacje ważone liczbą zdających — mikropowiaty "
        f"to głównie szum małych prób; bez ważenia korelacja płace↔zdawalność "
        f"spada do {fmt_pl(corr_unweighted, 2)} (podajemy to wprost, dobór "
        f"metody to nie cherry-picking). Płace GUS za {wage_year_full} r., "
        f"wyniki matury za {LATEST} r. — najnowsze dostępne roczniki obu "
        f"źródeł; roczne przesunięcie nie wpływa na wniosek, bo struktura płac "
        f"między powiatami zmienia się powoli. Jak wszędzie w tym dashboardzie: "
        f"**współwystępowanie, nie przyczynowość**."
    )

    st.markdown(f"### Gdzie targetować (powiaty, {LATEST})")

    with_wage = c_last.dropna(subset=["failers", "wage"])
    med_fail = float(with_wage["failers"].median())
    med_wage = float(with_wage["wage"].median())

    seg_premium = (
        with_wage[(with_wage["failers"] > med_fail) & (with_wage["wage"] >= med_wage)]
        .nlargest(8, "failers")
    )
    seg_value = (
        with_wage[(with_wage["failers"] > med_fail) & (with_wage["wage"] < med_wage)]
        .nlargest(8, "failers")
    )
    seg_urgent = (
        c_last[c_last["math_pp_n"] >= 100].dropna(subset=["math_pp_pass_rate"])
        .nsmallest(8, "math_pp_pass_rate")
    )

    seg_cols = {
        "county": st.column_config.TextColumn("powiat"),
        "voivodeship": st.column_config.TextColumn("województwo"),
        # "localized": polska typografia liczb (przecinek, spacja tysięcy) —
        # spójnie z KPI i wykresami.
        "failers": st.column_config.NumberColumn("oblewający", format="localized"),
        "wage": st.column_config.NumberColumn(f"płace {wage_year_full} (zł)", format="localized"),
        "math_pp_pass_rate": st.column_config.NumberColumn("zdawalność (%)", format="localized"),
    }
    show = ["county", "voivodeship", "failers", "wage", "math_pp_pass_rate"]

    def seg_view(seg: pd.DataFrame) -> pd.DataFrame:
        # format="localized" nie kontroluje miejsc po przecinku — zaokrąglamy
        # przed wyświetleniem (oblewający/płace do całości, zdawalność do 0,1).
        return seg[show].assign(
            failers=seg["failers"].round(),
            wage=seg["wage"].round(),
            math_pp_pass_rate=seg["math_pp_pass_rate"].round(1),
        )

    col_a, col_b = st.columns(2)
    with col_a:
        st.markdown("**🏙️ Korepetycje premium / stacjonarne** — duży wolumen, "
                    "płace ≥ mediany")
        st.dataframe(seg_view(seg_premium), hide_index=True, column_config=seg_cols,
                     width="stretch")
        st.caption(
            "Metropolie: najwięcej klientów o największej sile nabywczej — "
            "i najwięcej konkurencji. Reklama lokalna (osiedla, szkoły) "
            "zamiast szerokiego zasięgu."
        )
    with col_b:
        st.markdown("**📱 Aplikacja online / niska cena** — duży wolumen, "
                    "płace < mediany")
        st.dataframe(seg_view(seg_value), hide_index=True, column_config=seg_cols,
                     width="stretch")
        st.caption(
            "Duże rynki o niższej sile nabywczej: stacjonarne korki przegrywają "
            "tu z ceną — naturalny target kampanii online (geotargeting "
            "na powiat, komunikat cenowy)."
        )

    st.markdown("**🚨 Największa pilność** — najniższa zdawalność (powiaty ≥ 100 zdających)")
    st.dataframe(seg_view(seg_urgent), hide_index=True, column_config=seg_cols,
                 width="stretch")
    st.caption(
        "Tu problem jest najostrzejszy: co trzeci–czwarty maturzysta oblewa. "
        "Mały wolumen bezwzględny, ale minimalna podaż korepetytorów i duża "
        "potrzeba — dobre miejsce na pilotaż darmowej wersji aplikacji "
        "(budowanie marki tam, gdzie nikt inny nie dociera)."
    )

    st.markdown(
        """
### Czego te dane NIE mówią (uczciwe ograniczenia)

- **Nie widzimy podaży korepetycji** — "mała podaż stacjonarna" na wsi i w
  słabszych powiatach to wniosek z zamożności i gęstości zaludnienia (proxy),
  nie z danych o liczbie korepetytorów.
- **Dane są zagregowane** per powiat/szkoła — wnioski dotyczą rynków, nie
  pojedynczych uczniów (błąd ekologiczny).
- **Płace GUS liczone wg miejsca pracy** — powiaty sypialniane wokół
  metropolii są w rzeczywistości zamożniejsze, niż pokazuje oś Y.
- **Brak cen korepetycji i danych o sezonowości** — timing kampanii (np.
  wrzesień/poprawki, luty/studniówki) trzeba oprzeć na wiedzy branżowej.
"""
    )

# --- 7. O danych ------------------------------------------------------------
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
- Wynagrodzenia: **GUS Bank Danych Lokalnych** ([bdl.stat.gov.pl](https://bdl.stat.gov.pl),
  API, zmienna 64428 „przeciętne miesięczne wynagrodzenia brutto”, rok 2024,
  dane publiczne GUS). **Zastrzeżenie:** GUS liczy wynagrodzenia wg **miejsca
  pracy**, nie zamieszkania (powiaty „sypialniane” wokół metropolii mają
  zaniżone wartości); dane obejmują podmioty o więcej niż 9 pracujących.
  Pobrane jednorazowo skryptem `scripts/fetch_bdl_wages.py` — aplikacja nie
  odpytuje API przy starcie.
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
- **W danych jest 379 z 380 powiatów** — w eksportach CKE (wszystkie lata)
  nie występuje powiat siedlecki (ziemski, TERYT 1426): na jego terenie nie
  działa żadna szkoła zdająca maturę w Formule 2023, a tamtejsi maturzyści
  uczą się w szkołach miasta Siedlce (osobnego powiatu grodzkiego). Na mapie
  powiat siedlecki widnieje jako „brak danych”.
- „Liczba oblewających” to szacunek: zdający × (1 − zdawalność).

### Po co ten dashboard

Prowadzę korepetycje z matematyki dla licealistów i buduję aplikację do
treningu matematyki (12–18 lat). Ten dashboard to research rynkowy: **gdzie
popyt na wsparcie z matematyki jest największy** — geograficznie (mapa),
strukturalnie (LO/technikum, miasto/wieś) i w czasie (trendy).
"""
    )
