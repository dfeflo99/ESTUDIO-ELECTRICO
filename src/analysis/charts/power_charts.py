# =============================================================================
# src/analysis/charts/power_charts.py
# Gráficos de análisis de potencia
# Compatible con 2.0TD + 3.0TD
# =============================================================================

import pandas as pd
import plotly.graph_objects as go


# =============================================================================
# CONFIG VISUAL
# =============================================================================

COLOR_RED = "#CC1F1F"
COLOR_ORANGE = "#F59E0B"
COLOR_BLUE = "#2563EB"
COLOR_GREEN = "#16A34A"
COLOR_GRAY = "#6B7280"
COLOR_DARK = "#111827"

MONTH_NUM_TO_NAME = {
    1: "Enero", 2: "Febrero", 3: "Marzo", 4: "Abril",
    5: "Mayo", 6: "Junio", 7: "Julio", 8: "Agosto",
    9: "Septiembre", 10: "Octubre", 11: "Noviembre", 12: "Diciembre"
}


# =============================================================================
# HELPERS
# =============================================================================

def _is_3_0(power_analysis) -> bool:
    return getattr(power_analysis, "contract_type", "") == "3.0TD"


def _month_name_from_any(x):
    if isinstance(x, int):
        return MONTH_NUM_TO_NAME.get(x, str(x))

    text = str(x).strip().lower()

    mapping = {
        "ene": "Enero", "enero": "Enero",
        "feb": "Febrero", "febrero": "Febrero",
        "mar": "Marzo", "marzo": "Marzo",
        "abr": "Abril", "abril": "Abril",
        "may": "Mayo", "mayo": "Mayo",
        "jun": "Junio", "junio": "Junio",
        "jul": "Julio", "julio": "Julio",
        "ago": "Agosto", "agosto": "Agosto",
        "sep": "Septiembre", "septiembre": "Septiembre",
        "oct": "Octubre", "octubre": "Octubre",
        "nov": "Noviembre", "noviembre": "Noviembre",
        "dic": "Diciembre", "diciembre": "Diciembre",
        "01": "Enero", "02": "Febrero", "03": "Marzo", "04": "Abril",
        "05": "Mayo", "06": "Junio", "07": "Julio", "08": "Agosto",
        "09": "Septiembre", "10": "Octubre", "11": "Noviembre", "12": "Diciembre",
    }

    if text[:3] in mapping:
        return mapping[text[:3]]
    if text[:2] in mapping:
        return mapping[text[:2]]

    return text.capitalize()


def _card_annotation(x0, x1, title, value, subtitle="", color=COLOR_BLUE, value_size=20):
    anns = [
        dict(
            x=(x0 + x1) / 2,
            y=0.76,
            xref="paper",
            yref="paper",
            text=f"<b>{title}</b>",
            showarrow=False,
            font=dict(size=13, color=COLOR_DARK),
            align="center",
            xanchor="center",
        ),
        dict(
            x=(x0 + x1) / 2,
            y=0.46,
            xref="paper",
            yref="paper",
            text=f"<span style='font-size:{value_size}px; color:{color}'><b>{value}</b></span>",
            showarrow=False,
            align="center",
            xanchor="center",
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
                xanchor="center",
            )
        )

    return anns


def _message_figure(title, text):
    fig = go.Figure()
    fig.add_annotation(
        text=f"<b>{text}</b>",
        x=0.5, y=0.5,
        xref="paper", yref="paper",
        showarrow=False,
        font=dict(size=18, color=COLOR_GRAY)
    )
    fig.update_layout(
        title=title,
        template="plotly_white",
        height=380,
        xaxis=dict(visible=False),
        yaxis=dict(visible=False),
    )
    return fig


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

    rows = []
    for fecha, info in daily.items():
        rows.append({
            "fecha": fecha,
            "max_kw": info["max_kw"],
        })

    df = pd.DataFrame(rows)
    if df.empty:
        return _message_figure("Potencia máxima diaria", "No hay datos para los filtros seleccionados")

    df = df.sort_values("fecha")

    fig = go.Figure()
    fig.add_trace(
        go.Scatter(
            x=df["fecha"],
            y=df["max_kw"],
            mode="lines+markers",
            name="Máx diario",
            line=dict(color=COLOR_BLUE),
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
    horas = heat.get("horas", [])
    dias = heat.get("dias", [])

    if not horas or not dias:
        return _message_figure("Heatmap potencia hora × día", "No hay datos para los filtros seleccionados")

    z = []
    for hora in horas:
        fila = []
        for dia in dias:
            fila.append(heat["valores"][hora][dia])
        z.append(fila)

    month_name = _month_name_from_any(heat.get("month_name", heat.get("month_num", "")))
    year_val = heat.get("year", "")

    title = "Heatmap potencia hora × día"
    if month_name:
        title += f" — {month_name}"
    if year_val:
        title += f" {year_val}"

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
        title=title,
        template="plotly_white",
        height=500,
        xaxis_title="Día del mes",
        yaxis_title="Hora",
    )

    return fig


# =============================================================================
# 4. DISTRIBUCIÓN HORARIA ESTIMADA
# =============================================================================

def chart_power_ranking(power_analysis):
    ranking = power_analysis.power_ranking
    if not ranking:
        return _message_figure("Distribución de potencia horaria estimada", "No hay datos para los filtros seleccionados")

    x = list(range(1, len(ranking) + 1))

    fig = go.Figure()

    fig.add_trace(
        go.Scatter(
            x=x,
            y=ranking,
            mode="lines",
            name="Distribución horaria estimada",
            line=dict(color=COLOR_BLUE, width=2),
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

    fig.add_annotation(
        x=0.01,
        y=1.10,
        xref="paper",
        yref="paper",
        showarrow=False,
        align="left",
        text="Potencia horaria estimada a partir de la curva de consumo. No representa picos instantáneos oficiales.",
        font=dict(size=11, color=COLOR_GRAY),
    )

    fig.update_layout(
        title="Distribución de potencia horaria estimada",
        template="plotly_white",
        height=440,
        xaxis_title="Horas ordenadas",
        yaxis_title="kW",
        legend_title_text="",
        margin=dict(l=60, r=40, t=90, b=60),
    )

    return fig


# =============================================================================
# 5. PROFILE
# =============================================================================

def chart_power_profile(power_analysis):
    perfil = getattr(power_analysis, "perfil_tipo", "sin clasificar")
    descripcion = getattr(power_analysis, "perfil_descripcion", "")

    color = COLOR_BLUE
    perfil_lower = perfil.lower()
    if "estable" in perfil_lower and "muy" not in perfil_lower:
        color = COLOR_GREEN
    elif "moderado" in perfil_lower:
        color = COLOR_ORANGE
    elif "muy variable" in perfil_lower:
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
        text="<b>Perfil de potencia</b>",
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

def chart_monthly_official_bars(power_analysis):
    max_by_month = power_analysis.max_by_month
    meses_raw = list(max_by_month.keys())
    meses = [_month_name_from_any(m) for m in meses_raw]

    if not meses_raw:
        return _message_figure("Picos oficiales mensuales", "No hay datos para los filtros seleccionados")

    fig = go.Figure()

    if _is_3_0(power_analysis):
        for p in ["P1", "P2", "P3", "P4", "P5", "P6"]:
            fig.add_trace(
                go.Bar(
                    x=meses,
                    y=[max_by_month[m].get(p, 0.0) for m in meses_raw],
                    name=f"Pico {p}",
                )
            )
    else:
        fig.add_trace(
            go.Bar(
                x=meses,
                y=[max_by_month[m].get("P1", 0.0) for m in meses_raw],
                name="Pico P1",
                marker_color=COLOR_RED,
            )
        )
        fig.add_trace(
            go.Bar(
                x=meses,
                y=[max_by_month[m].get("P3", 0.0) for m in meses_raw],
                name="Pico P3",
                marker_color=COLOR_BLUE,
            )
        )

    fig.add_trace(
        go.Bar(
            x=meses,
            y=[max_by_month[m].get("Pot.Max", 0.0) for m in meses_raw],
            name="Pot.Max",
            marker_color=COLOR_ORANGE,
            opacity=0.45,
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


def chart_monthly_official_table(power_analysis):
    max_by_month = power_analysis.max_by_month
    meses_raw = list(max_by_month.keys())

    if not meses_raw:
        return _message_figure("Tabla de picos oficiales mensuales", "No hay datos para los filtros seleccionados")

    rows = []
    for m in meses_raw:
        row = {"Mes": _month_name_from_any(m)}
        values = max_by_month[m]
        if _is_3_0(power_analysis):
            for p in ["P1", "P2", "P3", "P4", "P5", "P6"]:
                row[p] = values.get(p, 0.0)
        else:
            row["P1"] = values.get("P1", 0.0)
            row["P3"] = values.get("P3", 0.0)
        row["Pot.Max"] = values.get("Pot.Max", 0.0)
        rows.append(row)

    df = pd.DataFrame(rows)

    fig = go.Figure(
        data=[
            go.Table(
                header=dict(
                    values=list(df.columns),
                    fill_color=COLOR_BLUE,
                    font=dict(color="white", size=12),
                    align="center"
                ),
                cells=dict(
                    values=[df[col] for col in df.columns],
                    fill_color="white",
                    align="center",
                    font=dict(size=11),
                    height=28
                )
            )
        ]
    )

    fig.update_layout(
        title="Tabla de picos oficiales mensuales",
        height=max(320, 90 + len(df) * 28)
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
        "monthly_official": chart_monthly_official_bars(power_analysis),
        "monthly_official_table": chart_monthly_official_table(power_analysis),
    }
