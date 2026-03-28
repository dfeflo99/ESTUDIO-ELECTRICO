# =============================================================================
# src/analysis/charts/peaks_charts.py
# Gráficos de análisis de picos
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
COLOR_DARK = "#111827"


# =============================================================================
# HELPERS
# =============================================================================

def _is_3_0(peaks_analysis: dict) -> bool:
    return peaks_analysis.get("contract_type") == "3.0TD"


def _periods(peaks_analysis: dict):
    if _is_3_0(peaks_analysis):
        return ["P1", "P2", "P3", "P4", "P5", "P6"]
    return ["P1", "P3"]


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
                y=0.20,
                xref="paper",
                yref="paper",
                text=subtitle,
                showarrow=False,
                font=dict(size=11, color=COLOR_GRAY),
                align="center",
            )
        )
    return anns


def _franja_color(franja: str):
    mapping = {
        "00-08": "#1D4ED8",
        "08-12": "#10B981",
        "12-16": "#F59E0B",
        "16-20": "#F97316",
        "20-24": "#DC2626",
    }
    return mapping.get(franja, COLOR_BLUE)


# =============================================================================
# 1. KPIs
# =============================================================================

def chart_peaks_kpis(peaks_analysis: dict):
    total_peaks = peaks_analysis["total_peaks"]
    pct_peaks = peaks_analysis["pct_peaks"]
    top10 = peaks_analysis["top10"]
    by_month = peaks_analysis["by_month"]
    by_franja = peaks_analysis["by_franja"]

    pico_max = max([r["consumption_kwh"] for r in top10], default=0.0)

    if by_month:
        mes_mas_picos = max(by_month.items(), key=lambda x: x[1]["num_picos"])[0].capitalize()
    else:
        mes_mas_picos = "—"

    if by_franja:
        franja_mas = max(by_franja.items(), key=lambda x: x[1]["num_picos"])[0]
    else:
        franja_mas = "—"

    fig = go.Figure()

    boxes = [
        (0.00, 0.23),
        (0.26, 0.49),
        (0.52, 0.75),
        (0.78, 1.00),
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
    annotations += _card_annotation(*boxes[0], "Horas sobre umbral", f"{total_peaks}", color=COLOR_RED)
    annotations += _card_annotation(*boxes[1], "% sobre umbral", f"{pct_peaks}%", color=COLOR_ORANGE)
    annotations += _card_annotation(
        *boxes[2],
        "Pico máximo",
        f"{pico_max} kW",
        f"Mes con más picos: {mes_mas_picos}",
        COLOR_RED,
        24
    )
    annotations += _card_annotation(
        *boxes[3],
        "Franja más repetida",
        franja_mas,
        "",
        COLOR_BLUE,
        22
    )

    fig.update_layout(
        title="KPIs de picos",
        template="plotly_white",
        height=260,
        margin=dict(l=20, r=20, t=60, b=20),
        xaxis=dict(visible=False),
        yaxis=dict(visible=False),
        annotations=annotations,
    )

    return fig


# =============================================================================
# 2. TOP 10
# =============================================================================

def chart_peaks_top10(peaks_analysis: dict):
    rows = peaks_analysis["top10"]

    if not rows:
        rows = [{
            "fecha": "—",
            "hora": "—",
            "consumption_kwh": "—",
            "exceso_kwh": "—",
            "power_period": "—",
            "energy_period": "—",
        }]

    df = pd.DataFrame(rows)

    cols = ["fecha", "hora", "consumption_kwh", "exceso_kwh", "power_period", "energy_period"]
    headers = ["Fecha", "Hora", "kW", "Exceso", "Periodo potencia", "Periodo energía"]

    fill_colors = []
    for i in range(len(df)):
        if i == 0:
            fill_colors.append("#FEE2E2")
        elif i < 3:
            fill_colors.append("#FEF3C7")
        else:
            fill_colors.append("white")

    fig = go.Figure(
        data=[
            go.Table(
                header=dict(
                    values=headers,
                    fill_color=COLOR_RED,
                    font=dict(color="white", size=12),
                    align="center"
                ),
                cells=dict(
                    values=[df[c] for c in cols],
                    fill_color=[fill_colors] * len(cols),
                    align="center",
                    font=dict(size=11),
                    height=28
                )
            )
        ]
    )

    fig.update_layout(
        title="Top 10 picos",
        height=max(360, 90 + len(df) * 28)
    )

    return fig


# =============================================================================
# 3. BY MONTH
# =============================================================================

def chart_peaks_by_month(peaks_analysis: dict):
    by_month = peaks_analysis["by_month"]

    meses = [m.capitalize() for m in by_month.keys()]
    num_picos = [v["num_picos"] for v in by_month.values()]
    max_kw = [v["max_kw"] for v in by_month.values()]

    fig = make_subplots(specs=[[{"secondary_y": True}]])

    fig.add_trace(
        go.Bar(
            x=meses,
            y=num_picos,
            name="Horas sobre umbral",
            marker_color=COLOR_RED,
        ),
        secondary_y=False
    )

    fig.add_trace(
        go.Scatter(
            x=meses,
            y=max_kw,
            mode="lines+markers",
            name="Pico máximo",
            line=dict(color=COLOR_BLUE),
        ),
        secondary_y=True
    )

    fig.update_layout(
        title="Picos por mes",
        template="plotly_white",
        height=420,
        legend_title_text="",
    )

    fig.update_yaxes(title_text="Nº horas", secondary_y=False)
    fig.update_yaxes(title_text="kW", secondary_y=True)

    return fig


# =============================================================================
# 4. BY HOUR
# =============================================================================

def chart_peaks_by_hour(peaks_analysis: dict):
    by_hour = peaks_analysis["by_hour"]

    horas = list(by_hour.keys())
    num_picos = [by_hour[h]["num_picos"] for h in horas]

    colors = []
    for h in horas:
        if 0 <= h < 8:
            colors.append(_franja_color("00-08"))
        elif 8 <= h < 12:
            colors.append(_franja_color("08-12"))
        elif 12 <= h < 16:
            colors.append(_franja_color("12-16"))
        elif 16 <= h < 20:
            colors.append(_franja_color("16-20"))
        else:
            colors.append(_franja_color("20-24"))

    fig = go.Figure()

    fig.add_trace(
        go.Bar(
            x=horas,
            y=num_picos,
            marker_color=colors,
            name="Picos"
        )
    )

    fig.update_layout(
        title="Picos por hora",
        template="plotly_white",
        height=420,
        xaxis_title="Hora",
        yaxis_title="Nº picos",
        showlegend=False
    )

    return fig


# =============================================================================
# 5. HEATMAP
# =============================================================================

def chart_peaks_heatmap(peaks_analysis: dict):
    heat = peaks_analysis["heatmap"]
    meses = heat["meses"]
    horas = heat["horas"]

    z = []
    for hora in horas:
        fila = []
        for mes in meses:
            fila.append(heat["valores"][mes][hora])
        z.append(fila)

    fig = go.Figure(
        data=go.Heatmap(
            z=z,
            x=meses,
            y=horas,
            colorscale="Reds",
            colorbar_title="kW"
        )
    )

    fig.update_layout(
        title="Heatmap mes × hora",
        template="plotly_white",
        height=500,
        xaxis_title="Mes",
        yaxis_title="Hora"
    )

    return fig


# =============================================================================
# 6. DAY TYPE
# =============================================================================

def chart_peaks_day_type(peaks_analysis: dict):
    by_day_type = peaks_analysis["by_day_type"]

    labels = ["Laborable", "Fin de semana/Festivo"]
    values = [
        by_day_type["laborable"]["num_picos"],
        by_day_type["fin_de_semana"]["num_picos"],
    ]

    fig = go.Figure(
        data=[
            go.Pie(
                labels=labels,
                values=values,
                hole=0.55,
                marker=dict(colors=[COLOR_BLUE, COLOR_ORANGE]),
                textinfo="label+percent"
            )
        ]
    )

    fig.update_layout(
        title="Picos por tipo de día",
        template="plotly_white",
        height=420,
        annotations=[dict(text=f"{sum(values)}", x=0.5, y=0.5, showarrow=False, font=dict(size=24))]
    )

    return fig


# =============================================================================
# 7. BY PERIOD
# =============================================================================

def chart_peaks_by_period(peaks_analysis: dict):
    by_period = peaks_analysis["by_period"]
    periodos = _periods(peaks_analysis)

    labels = periodos
    values = [by_period[p]["num_picos"] for p in periodos]

    fig = go.Figure(
        data=[
            go.Pie(
                labels=labels,
                values=values,
                hole=0.55,
                textinfo="label+percent"
            )
        ]
    )

    fig.update_layout(
        title="Picos por periodo de potencia",
        template="plotly_white",
        height=420,
        annotations=[dict(text=f"{sum(values)}", x=0.5, y=0.5, showarrow=False, font=dict(size=24))]
    )

    return fig


# =============================================================================
# MAIN
# =============================================================================

def generate_peaks_charts(peaks_analysis: dict):
    return {
        "kpis": chart_peaks_kpis(peaks_analysis),
        "top10": chart_peaks_top10(peaks_analysis),
        "by_month": chart_peaks_by_month(peaks_analysis),
        "by_hour": chart_peaks_by_hour(peaks_analysis),
        "heatmap": chart_peaks_heatmap(peaks_analysis),
        "day_type": chart_peaks_day_type(peaks_analysis),
        "by_period": chart_peaks_by_period(peaks_analysis),
    }
