# =============================================================================
# src/analysis/charts/power_charts.py
# Gráficos de análisis de potencia
# Compatible con 2.0TD + 3.0TD
# =============================================================================

import pandas as pd
import plotly.graph_objects as go
from plotly.subplots import make_subplots


# =============================================================================
# CONFIG VISUAL
# =============================================================================

COLOR_RED = "#CC1F1F"
COLOR_ORANGE = "#F59E0B"
COLOR_BLUE = "#2563EB"
COLOR_GREEN = "#16A34A"
COLOR_GRAY = "#6B7280"
COLOR_LIGHT = "#F3F4F6"
COLOR_DARK = "#111827"


# =============================================================================
# HELPERS
# =============================================================================

def _is_3_0(power_analysis) -> bool:
    return getattr(power_analysis, "contract_type", "") == "3.0TD"


def _periods_for_contract(power_analysis):
    if _is_3_0(power_analysis):
        return ["P1", "P2", "P3", "P4", "P5", "P6"]
    return ["P1", "P3"]


def _alias_period_2(power_analysis):
    return "P6" if _is_3_0(power_analysis) else "P3"


def _card_annotation(x0, x1, title, value, subtitle="", color=COLOR_BLUE, value_size=24):
    anns = [
        dict(
            x=(x0 + x1) / 2,
            y=0.74,
            xref="paper",
            yref="paper",
            text=f"<b>{title}</b>",
            showarrow=False,
            font=dict(size=13, color=COLOR_DARK),
            align="center",
        ),
        dict(
            x=(x0 + x1) / 2,
            y=0.47,
            xref="paper",
            yref="paper",
            text=f"<span style='font-size:{value_size}px; color:{color}'><b>{value}</b></span>",
            showarrow=False,
            align="center",
        ),
    ]
    if subtitle:
        anns.append(
            dict(
                x=(x0 + x1) / 2,
                y=0.22,
                xref="paper",
                yref="paper",
                text=subtitle,
                showarrow=False,
                font=dict(size=11, color=COLOR_GRAY),
                align="center",
            )
        )
    return anns


# =============================================================================
# 1. KPIs
# =============================================================================

def chart_power_kpis(power_analysis):
    fig = go.Figure()

    boxes = [
        (0.00, 0.18),
        (0.205, 0.385),
        (0.41, 0.59),
        (0.615, 0.795),
        (0.82, 1.00),
    ]

    for x0, x1 in boxes:
        fig.add_shape(
            type="rect",
            xref="paper",
            yref="paper",
            x0=x0,
            x1=x1,
            y0=0.02,
            y1=0.98,
            line=dict(color="#E5E7EB", width=1),
            fillcolor="white",
        )

    annotations = []
    annotations += _card_annotation(*boxes[0], "Máx. potencia", f"{power_analysis.max_power_kw} kW", color=COLOR_RED)
    annotations += _card_annotation(*boxes[1], "P99", f"{power_analysis.p99_power_kw} kW", color=COLOR_ORANGE)
    annotations += _card_annotation(*boxes[2], "Factor de carga", f"{power_analysis.load_factor}", color=COLOR_BLUE)
    annotations += _card_annotation(*boxes[3], "Horas > umbral", f"{power_analysis.hours_exceeds_2kw}", color=COLOR_RED)
    annotations += _card_annotation(*boxes[4], "% > umbral", f"{power_analysis.pct_exceeds_2kw}%", color=COLOR_ORANGE)

    fig.update_layout(
        title="KPIs de potencia",
        template="plotly_white",
        height=250,
        margin=dict(l=20, r=20, t=60, b=20),
        xaxis=dict(visible=False),
        yaxis=dict(visible=False),
        annotations=annotations,
    )

    return fig


# =============================================================================
# 2. DAILY MAX
# =============================================================================

def chart_daily_max(power_analysis):
    daily = power_analysis.daily_max_power

    fechas = list(daily.keys())
    valores = [daily[f]["max_kw"] for f in fechas]

    fig = go.Figure()

    fig.add_trace(
        go.Scatter(
            x=fechas,
            y=valores,
            mode="lines+markers",
            name="Máx diario",
            line=dict(color=COLOR_BLUE),
        )
    )

    contracted = power_analysis.contracted_powers
    periods = _periods_for_contract(power_analysis)

    for p in periods:
        kw = getattr(contracted, p.lower(), 0.0) or 0.0
        if kw > 0:
            fig.add_trace(
                go.Scatter(
                    x=fechas,
                    y=[kw] * len(fechas),
                    mode="lines",
                    name=f"Contratada {p}",
                    line=dict(dash="dash"),
                )
            )

    fig.update_layout(
        title="Potencia máxima diaria",
        template="plotly_white",
        height=420,
        xaxis_title="Fecha",
        yaxis_title="kW",
        legend_title_text="",
    )

    return fig


# =============================================================================
# 3. HEATMAP
# =============================================================================

def chart_power_heatmap(power_analysis):
    heat = power_analysis.hourly_power_heatmap
    horas = heat["horas"]
    dias = heat["dias"]

    z = []
    for hora in horas:
        fila = []
        for dia in dias:
            fila.append(heat["valores"][hora][dia])
        z.append(fila)

    fig = go.Figure(
        data=go.Heatmap(
            z=z,
            x=dias,
            y=horas,
            colorscale="YlOrRd",
            colorbar_title="kW"
        )
    )

    fig.update_layout(
        title="Heatmap potencia hora × día del mes",
        template="plotly_white",
        height=500,
        xaxis_title="Día del mes",
        yaxis_title="Hora",
    )

    return fig


# =============================================================================
# 4. RANKING / CURVA DE DURACIÓN
# =============================================================================

def chart_power_ranking(power_analysis):
    ranking = power_analysis.power_ranking
    x = list(range(1, len(ranking) + 1))

    fig = go.Figure()

    fig.add_trace(
        go.Scatter(
            x=x,
            y=ranking,
            mode="lines",
            name="Curva de duración",
            line=dict(color=COLOR_BLUE),
        )
    )

    fig.add_trace(
        go.Scatter(
            x=[1, len(ranking)],
            y=[power_analysis.p99_power_kw, power_analysis.p99_power_kw],
            mode="lines",
            name="P99",
            line=dict(color=COLOR_ORANGE, dash="dash"),
        )
    )

    fig.add_trace(
        go.Scatter(
            x=[1, len(ranking)],
            y=[power_analysis.umbral_kw, power_analysis.umbral_kw],
            mode="lines",
            name="Umbral",
            line=dict(color=COLOR_RED, dash="dot"),
        )
    )

    fig.update_layout(
        title="Curva de duración de potencia",
        template="plotly_white",
        height=420,
        xaxis_title="Horas ordenadas",
        yaxis_title="kW",
        legend_title_text="",
    )

    return fig


# =============================================================================
# 5. PROFILE
# =============================================================================

def chart_power_profile(power_analysis):
    perfil = getattr(power_analysis, "perfil_tipo", "sin clasificar")
    descripcion = getattr(power_analysis, "perfil_descripcion", "")

    color = COLOR_BLUE
    if "estable" in perfil:
        color = COLOR_GREEN
    elif "moderadamente" in perfil:
        color = COLOR_ORANGE
    elif "muy variable" in perfil:
        color = COLOR_RED

    fig = go.Figure()

    fig.add_shape(
        type="rect",
        xref="paper",
        yref="paper",
        x0=0.05,
        x1=0.95,
        y0=0.1,
        y1=0.9,
        line=dict(color="#E5E7EB", width=1),
        fillcolor="white",
    )

    fig.add_annotation(
        x=0.5, y=0.72,
        xref="paper", yref="paper",
        text="<b>Perfil de consumo</b>",
        showarrow=False,
        font=dict(size=16, color=COLOR_DARK)
    )

    fig.add_annotation(
        x=0.5, y=0.5,
        xref="paper", yref="paper",
        text=f"<span style='font-size:30px; color:{color}'><b>{perfil}</b></span>",
        showarrow=False,
    )

    fig.add_annotation(
        x=0.5, y=0.25,
        xref="paper", yref="paper",
        text=descripcion,
        showarrow=False,
        font=dict(size=12, color=COLOR_GRAY),
        align="center"
    )

    fig.update_layout(
        title="Perfil de potencia",
        template="plotly_white",
        height=280,
        xaxis=dict(visible=False),
        yaxis=dict(visible=False),
        margin=dict(l=20, r=20, t=60, b=20),
    )

    return fig


# =============================================================================
# 6. MONTHLY OFFICIAL
# =============================================================================

def chart_monthly_official(power_analysis):
    max_by_month = power_analysis.max_by_month
    meses = list(max_by_month.keys())

    fig = go.Figure()

    if _is_3_0(power_analysis):
        for p in ["P1", "P2", "P3", "P4", "P5", "P6"]:
            fig.add_trace(
                go.Bar(
                    x=meses,
                    y=[max_by_month[m].get(p, 0.0) for m in meses],
                    name=f"Pico {p}",
                )
            )
    else:
        fig.add_trace(
            go.Bar(
                x=meses,
                y=[max_by_month[m].get("P1", 0.0) for m in meses],
                name="Pico P1",
                marker_color=COLOR_RED,
            )
        )
        fig.add_trace(
            go.Bar(
                x=meses,
                y=[max_by_month[m].get("P3", 0.0) for m in meses],
                name="Pico P3",
                marker_color=COLOR_BLUE,
            )
        )

    fig.add_trace(
        go.Bar(
            x=meses,
            y=[max_by_month[m].get("Pot.Max", 0.0) for m in meses],
            name="Pot.Max",
            marker_color=COLOR_ORANGE,
            opacity=0.45,
        )
    )

    contracted = power_analysis.contracted_powers
    for p in _periods_for_contract(power_analysis):
        kw = getattr(contracted, p.lower(), 0.0) or 0.0
        if kw > 0:
            fig.add_trace(
                go.Scatter(
                    x=meses,
                    y=[kw] * len(meses),
                    mode="lines",
                    name=f"Contratada {p}",
                    line=dict(dash="dash"),
                )
            )

    # Líneas recomendadas visibles
    recs = {
        "P1": power_analysis.recommended_p1_kw,
        "P2": power_analysis.recommended_p2_kw,
        "P3": power_analysis.recommended_p3_kw,
        "P4": power_analysis.recommended_p4_kw,
        "P5": power_analysis.recommended_p5_kw,
        "P6": power_analysis.recommended_p6_kw,
    }
    for p in _periods_for_contract(power_analysis):
        kw = recs.get(p, 0.0)
        if kw > 0:
            fig.add_trace(
                go.Scatter(
                    x=meses,
                    y=[kw] * len(meses),
                    mode="lines",
                    name=f"Recomendada {p}",
                    line=dict(dash="dot"),
                )
            )

    fig.update_layout(
        title="Picos oficiales mensuales",
        template="plotly_white",
        height=520,
        barmode="group",
        xaxis_title="Mes",
        yaxis_title="kW",
        legend_title_text="",
    )

    return fig


# =============================================================================
# MAIN
# =============================================================================

def generate_power_charts(power_analysis):
    return {
        "kpis": chart_power_kpis(power_analysis),
        "daily_max": chart_daily_max(power_analysis),
        "heatmap": chart_power_heatmap(power_analysis),
        "ranking": chart_power_ranking(power_analysis),
        "profile": chart_power_profile(power_analysis),
        "monthly_official": chart_monthly_official(power_analysis),
    }
