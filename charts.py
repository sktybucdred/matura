# -*- coding: utf-8 -*-
"""Wykresy Plotly dla dashboardu — każda funkcja zwraca gotową figurę.

Wspólne zasady:
- polska typografia liczb: przecinek dziesiętny, spacja tysięcy
  (plotly: separators=", "),
- tytuły i etykiety osi po polsku,
- funkcje dostają już PRZEFILTROWANE dane — logika filtrów żyje w app.py.
"""

from __future__ import annotations

import pandas as pd
import plotly.express as px
import plotly.graph_objects as go

# Pierwsze znaki: separator dziesiętny, separator tysięcy.
PL_SEPARATORS = ", "

COLOR_MATH = "#d62728"
COLOR_POL = "#1f77b4"
COLOR_ENG = "#2ca02c"
COLOR_NEUTRAL = "#7f7f7f"

SUBJECT_COLORS = {
    "matematyka": COLOR_MATH,
    "język polski": COLOR_POL,
    "język angielski": COLOR_ENG,
    "cała matura (świadectwo)": COLOR_NEUTRAL,
}

SPLIT_COLORS = {
    "LO": "#1f77b4",
    "Technikum": "#ff7f0e",
    "inne": "#7f7f7f",
    "publiczna": "#1f77b4",
    "niepubliczna": "#ff7f0e",
    "miasto": "#1f77b4",
    "wieś": "#ff7f0e",
}


def fmt_pl(value: float, decimals: int = 0) -> str:
    """Format liczby po polsku: 1 234 567,8 (spacja tysięcy, przecinek)."""
    if value is None or pd.isna(value):
        return "—"
    text = f"{value:,.{decimals}f}"
    return text.replace(",", " ").replace(".", ",")


def _base_layout(fig: go.Figure, title: str, height: int = 450) -> go.Figure:
    fig.update_layout(
        title=dict(text=title, font=dict(size=16)),
        separators=PL_SEPARATORS,
        height=height,
        margin=dict(l=10, r=10, t=60, b=10),
        # Legenda POD wykresem — na górze nachodziła na tytuł.
        legend=dict(orientation="h", yanchor="top", y=-0.18, x=0, title=None),
        plot_bgcolor="rgba(0,0,0,0)",
        paper_bgcolor="rgba(0,0,0,0)",
    )
    fig.update_xaxes(showgrid=False)
    fig.update_yaxes(gridcolor="rgba(128,128,128,0.2)")
    return fig


# ---------------------------------------------------------------------------
# 1. Słupkowy: zdawalność przedmiotów vs cała matura, per rok
# ---------------------------------------------------------------------------
def subject_pass_bar(tidy: pd.DataFrame, scope_label: str) -> go.Figure:
    """tidy: kolumny [rok, przedmiot, zdawalność]."""
    fig = px.bar(
        tidy,
        x="rok",
        y="zdawalność",
        color="przedmiot",
        barmode="group",
        color_discrete_map=SUBJECT_COLORS,
        category_orders={"przedmiot": list(SUBJECT_COLORS)},
        labels={"rok": "rok egzaminu", "zdawalność": "zdawalność (%)"},
    )
    fig.update_traces(hovertemplate="%{fullData.name}<br>rok %{x}: <b>%{y:.1f}%</b><extra></extra>")
    # Zakres osi dopasowany do danych (np. technika schodzą poniżej 70%),
    # ale nigdy nie zaczynamy wyżej niż 70, żeby nie dramatyzować różnic.
    y_floor = min(70, (tidy["zdawalność"].min() // 5) * 5 - 5)
    fig.update_yaxes(range=[y_floor, 100])
    fig.update_xaxes(tickvals=sorted(tidy["rok"].unique()), type="category")
    return _base_layout(
        fig, f"Zdawalność przedmiotów obowiązkowych (PP) vs cała matura — {scope_label}"
    )


# ---------------------------------------------------------------------------
# 2. Heatmapa: rok × województwo
# ---------------------------------------------------------------------------
def voivodeship_heatmap(pivot: pd.DataFrame, subject_label: str) -> go.Figure:
    """pivot: index = województwo, columns = lata, values = zdawalność (%)."""
    fig = px.imshow(
        pivot,
        text_auto=".1f",
        aspect="auto",
        color_continuous_scale="RdYlGn",
        labels=dict(x="rok egzaminu", y="", color="zdawalność (%)"),
    )
    fig.update_xaxes(side="bottom", tickvals=list(pivot.columns), type="category")
    fig.update_traces(
        hovertemplate="%{y}, rok %{x}: <b>%{z:.1f}%</b><extra></extra>"
    )
    fig = _base_layout(
        fig,
        f"Zdawalność: {subject_label} (PP) — województwa × lata (wagi: liczba zdających)",
        height=520,
    )
    fig.update_layout(coloraxis_colorbar=dict(title="%"))
    return fig


# ---------------------------------------------------------------------------
# 3. Mapa choropleth powiatów
# ---------------------------------------------------------------------------
def county_map(
    df: pd.DataFrame,
    geojson: dict,
    feature_key: str,
    value_col: str,
    value_label: str,
    title: str,
    color_scale: str = "RdYlGn",
    hover_extra: dict | None = None,
    clip_quantiles: tuple[float, float] | None = (0.02, 0.98),
) -> go.Figure:
    """df: kolumny [teryt_county, county, voivodeship, value_col, ...].

    clip_quantiles: przycięcie zakresu skali barw (kwantyle) — pojedynczy
    ekstremalny powiat (np. Warszawa wolumenem albo mikropowiaty odsetkiem)
    nie spłaszcza wtedy kolorów całej reszty mapy. Wartości poza zakresem
    dostają kolor krańcowy.
    """
    plot_df = df.dropna(subset=[value_col])
    range_color = None
    if clip_quantiles and len(plot_df) > 20:
        lo = float(plot_df[value_col].quantile(clip_quantiles[0]))
        hi = float(plot_df[value_col].quantile(clip_quantiles[1]))
        if hi > lo:
            range_color = (lo, hi)
    fig = px.choropleth(
        plot_df,
        geojson=geojson,
        locations="teryt_county",
        featureidkey=feature_key,
        color=value_col,
        color_continuous_scale=color_scale,
        range_color=range_color,
        hover_name="county",
        hover_data={
            "teryt_county": False,
            "voivodeship": True,
            value_col: ":.1f",
            **(hover_extra or {}),
        },
        labels={value_col: value_label, "voivodeship": "województwo"},
        fitbounds="locations",
        basemap_visible=False,
    )
    fig.update_geos(projection_type="mercator", bgcolor="rgba(0,0,0,0)")
    fig = _base_layout(fig, title, height=560)
    fig.update_layout(
        coloraxis_colorbar=dict(title=value_label, len=0.8),
        margin=dict(l=0, r=0, t=60, b=0),
        dragmode=False,
    )
    return fig


# ---------------------------------------------------------------------------
# 4. Histogram rozkładu szkół
# ---------------------------------------------------------------------------
def school_histogram(
    df: pd.DataFrame, value_col: str, split_col: str, subject_label: str, year: int
) -> go.Figure:
    """df: szkoły (przefiltrowane, n>=10), split_col: kolumna kategorii."""
    fig = px.histogram(
        df.dropna(subset=[value_col, split_col]),
        x=value_col,
        color=split_col,
        barmode="overlay",
        histnorm="percent",
        nbins=20,
        opacity=0.65,
        color_discrete_map=SPLIT_COLORS,
        labels={value_col: f"zdawalność: {subject_label} PP w szkole (%)"},
    )
    fig.update_traces(
        hovertemplate="%{fullData.name}: %{y:.1f}% szkół w przedziale %{x}<extra></extra>"
    )
    fig.update_yaxes(title="odsetek szkół w grupie (%)")
    return _base_layout(
        fig,
        f"Rozkład zdawalności ({subject_label} PP) po szkołach — {year}, szkoły z ≥ 10 zdających",
    )


# ---------------------------------------------------------------------------
# 5. Boxplot rozkładu szkół
# ---------------------------------------------------------------------------
def school_box(
    df: pd.DataFrame, value_col: str, split_col: str, subject_label: str, year: int
) -> go.Figure:
    fig = px.box(
        df.dropna(subset=[value_col, split_col]),
        x=split_col,
        y=value_col,
        color=split_col,
        color_discrete_map=SPLIT_COLORS,
        labels={value_col: f"zdawalność: {subject_label} PP (%)", split_col: ""},
    )
    fig.update_traces(boxmean=True)
    fig = _base_layout(
        fig,
        f"Zdawalność ({subject_label} PP) w szkołach — mediana i rozrzut, {year}",
    )
    fig.update_layout(showlegend=False)
    return fig


# ---------------------------------------------------------------------------
# 6. Scatter: ambicje × skuteczność
# ---------------------------------------------------------------------------
def ambition_scatter(df: pd.DataFrame, year: int) -> go.Figure:
    """df: powiaty (jeden rok), wymagane kolumny math_pp_pass_rate,
    ambition_ratio, math_pp_n, county, voivodeship. Braki jawnie pomijamy."""
    plot_df = df.dropna(subset=["math_pp_pass_rate", "ambition_ratio", "math_pp_n"]).copy()
    plot_df["ambition_pct"] = plot_df["ambition_ratio"] * 100
    fig = px.scatter(
        plot_df,
        x="math_pp_pass_rate",
        y="ambition_pct",
        size="math_pp_n",
        size_max=42,
        hover_name="county",
        hover_data={
            "voivodeship": True,
            "math_pp_pass_rate": ":.1f",
            "ambition_pct": ":.1f",
            "math_pp_n": ":,",
        },
        opacity=0.55,
        color_discrete_sequence=[COLOR_MATH],
        labels={
            "math_pp_pass_rate": "zdawalność matematyki PP (%)",
            "ambition_pct": "podchodzący do PR jako % zdających PP",
            "math_pp_n": "liczba zdających PP",
            "voivodeship": "województwo",
        },
    )
    return _base_layout(
        fig,
        f"Ambicje vs skuteczność po powiatach — {year} (rozmiar kropki = liczba zdających)",
        height=520,
    )


# ---------------------------------------------------------------------------
# 6b. Scatter: rynek — oblewający × zamożność powiatu
# ---------------------------------------------------------------------------
def wage_scatter(df: pd.DataFrame, exam_year: int, wage_year: int) -> go.Figure:
    """df: powiaty (jeden rok) z kolumnami failers, wage, math_pp_n, county,
    voivodeship. Oś X logarytmiczna (Warszawa vs powiaty to 3 rzędy wielkości).
    Linie referencyjne na medianach dzielą rynek na ćwiartki."""
    import math

    plot_df = df.dropna(subset=["failers", "wage", "math_pp_n"])
    plot_df = plot_df[plot_df["failers"] >= 1]  # log(0) — powiaty bez oblewających

    fig = px.scatter(
        plot_df,
        x="failers",
        y="wage",
        size="math_pp_n",
        size_max=40,
        color="voivodeship",
        log_x=True,
        opacity=0.75,
        hover_name="county",
        hover_data={
            "voivodeship": True,
            "failers": ":.0f",
            "wage": ":.0f",
            "math_pp_n": ":,",
        },
        labels={
            "failers": f"szacowana liczba oblewających matematykę PP ({exam_year}, skala log)",
            "wage": f"przeciętne wynagrodzenie brutto, zł ({wage_year})",
            "math_pp_n": "liczba zdających PP",
            "voivodeship": "województwo",
        },
    )
    med_x = float(plot_df["failers"].median())
    med_y = float(plot_df["wage"].median())
    # Pułapka plotly na osi log: kształt add_vline przyjmuje wartość SUROWĄ,
    # ale adnotacje wymagają log10 — wbudowany annotation_text vline'a ląduje
    # w 10^x i rozsadza zakres osi. Dlatego linia i podpis idą osobno.
    fig.add_vline(x=med_x, line_dash="dot", line_color="#999")
    fig.add_annotation(
        x=math.log10(med_x), y=1.0, yref="paper", yanchor="bottom",
        text="mediana", showarrow=False, font=dict(size=10, color="#777"),
    )
    fig.add_hline(y=med_y, line_dash="dot", line_color="#999",
                  annotation_text="mediana", annotation_font_size=10)

    # Etykiety skrajnych powiatów (największy wolumen, skraje zamożności
    # i największy rynek w tańszej połowie kraju).
    picks: dict[str, pd.Series] = {}
    for _, row in plot_df.nlargest(2, "failers").iterrows():
        picks[row["county"]] = row
    picks.setdefault(
        plot_df.loc[plot_df["wage"].idxmax(), "county"],
        plot_df.loc[plot_df["wage"].idxmax()],
    )
    picks.setdefault(
        plot_df.loc[plot_df["wage"].idxmin(), "county"],
        plot_df.loc[plot_df["wage"].idxmin()],
    )
    cheap_big = plot_df[(plot_df["wage"] < med_y) & (plot_df["failers"] > med_x)]
    if not cheap_big.empty:
        row = cheap_big.nlargest(1, "failers").iloc[0]
        picks.setdefault(row["county"], row)
    for county, row in picks.items():
        fig.add_annotation(
            x=math.log10(float(row["failers"])),  # oś log: współrzędna = log10
            y=float(row["wage"]),
            text=county,
            showarrow=True,
            arrowhead=0,
            arrowcolor="#888",
            ax=0,
            ay=-22,
            font=dict(size=10, color="#444"),
        )

    fig = _base_layout(
        fig,
        f"Rynek korepetycji: wolumen × zamożność powiatu — matura {exam_year}, płace {wage_year}",
        height=560,
    )
    fig.update_layout(legend=dict(font=dict(size=10)))
    return fig


# ---------------------------------------------------------------------------
# 7. Liniowy: trend zdawalności
# ---------------------------------------------------------------------------
def trend_line(
    trend: pd.DataFrame,
    subject_label: str,
    scope_label: str,
    partial_years: set[int],
) -> go.Figure:
    """trend: index = lata, kolumny = serie (np. 'cała populacja', 'tylko LO')."""
    fig = go.Figure()
    # Style pozycyjne: pierwsza seria = główna (czerwona ciągła),
    # druga = odniesienie (niebieska przerywana) — nazwy serii bywają różne
    # w zależności od filtra typu szkoły.
    positional_styles = [
        dict(color=COLOR_MATH, dash="solid", symbol="circle"),
        dict(color=COLOR_POL, dash="dash", symbol="square"),
        dict(color=COLOR_NEUTRAL, dash="dot", symbol="diamond"),
    ]
    for idx, col in enumerate(trend.columns):
        st_ = positional_styles[min(idx, len(positional_styles) - 1)]
        fig.add_trace(
            go.Scatter(
                x=trend.index,
                y=trend[col],
                mode="lines+markers",
                name=col,
                line=dict(color=st_["color"], dash=st_["dash"], width=2.5),
                marker=dict(symbol=st_["symbol"], size=9),
                hovertemplate="%{fullData.name}, rok %{x}: <b>%{y:.1f}%</b><extra></extra>",
            )
        )
    # Adnotacja o latach niepełnego pokrycia — wprost na wykresie, nie tylko
    # w tekście (w 2023 r. Formuła 2023 obejmowała niemal wyłącznie LO).
    for y in sorted(partial_years):
        if y not in trend.index:
            continue
        # Kotwiczymy adnotację w pierwszej serii, która ma wartość w tym roku
        # (seria przefiltrowana po typie szkoły może nie mieć roku 2023).
        anchor_cols = [c for c in trend.columns if pd.notna(trend.loc[y, c])]
        if anchor_cols:
            first_col = anchor_cols[0]
            fig.add_annotation(
                x=y,
                y=float(trend.loc[y, first_col]),
                text=f"{y}: tylko LO<br>(technika od {y + 1})",
                showarrow=True,
                arrowhead=2,
                ax=45,
                ay=45,
                font=dict(size=11, color="#666"),
                arrowcolor="#999",
            )
    fig.update_xaxes(tickvals=list(trend.index), title="rok egzaminu")
    fig.update_yaxes(title=f"zdawalność: {subject_label} PP (%)")
    return _base_layout(
        fig,
        f"Trend zdawalności: {subject_label} (PP) — {scope_label} (wagi: liczba zdających)",
    )
