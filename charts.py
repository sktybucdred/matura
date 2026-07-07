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
        legend=dict(orientation="h", yanchor="bottom", y=1.0, x=0, title=None),
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
        labels={"rok": "rok egzaminu", "zdawalność": "zdawalność (%)"},
    )
    fig.update_traces(hovertemplate="%{fullData.name}<br>rok %{x}: <b>%{y:.1f}%</b><extra></extra>")
    fig.update_yaxes(range=[70, 100])
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
) -> go.Figure:
    """df: kolumny [teryt_county, county, voivodeship, value_col, ...]."""
    plot_df = df.dropna(subset=[value_col])
    fig = px.choropleth(
        plot_df,
        geojson=geojson,
        locations="teryt_county",
        featureidkey=feature_key,
        color=value_col,
        color_continuous_scale=color_scale,
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
    styles = {
        "cała populacja": dict(color=COLOR_MATH, dash="solid", symbol="circle"),
        "tylko LO": dict(color=COLOR_POL, dash="dash", symbol="square"),
    }
    for col in trend.columns:
        st_ = styles.get(col, dict(color=COLOR_NEUTRAL, dash="dot", symbol="diamond"))
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
        if y in trend.index:
            first_col = trend.columns[0]
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
