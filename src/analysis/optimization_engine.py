# =============================================================================
# src/analysis/charts/optimization_charts.py
# Gráficos de optimización de potencia contratada
# Compatible con 2.0TD + 3.0TD
# =============================================================================

import pandas as pd
import plotly.graph_objects as go
from plotly.subplots import make_subplots


# =============================================================================
# CONFIG VISUAL
# =============================================================================

COLOR_RED = "#CC1F1F"
COLOR_ORANGE = "#F5A623"
COLOR_BLUE = "#2563EB"
COLOR_GREEN = "#16A34A"
COLOR_GRAY = "#6B7280"
COLOR_LIGHT = "#F3F4F6"
COLOR_DARK = "#111827"


# =============================================================================
# HELPERS
# =============================================================================

def _is_3_0(opt_result: dict) -> bool:
    return opt_result.get("contract_type") == "3.0TD"


def _alias_periodo_2(opt_result: dict) -> str:
    return opt_result.get("alias_periodo_2", "P3")


def _ordered_periods(opt_result: dict):
    if _is_3_0(opt_result):
        return ["P1", "P2", "P3", "P4", "P5", "P6"]
    return ["P1", _alias_periodo_2(opt_result)]


def _round2(x):
    return round(float(x), 2)


# =============================================================================
# 1. KPIs
# =============================================================================

def chart_optimization_kpis(opt_result: dict):
    kpis = opt_result["kpis"]
    periodos = _ordered_periods(opt_result)

    contracted = kpis.get("contracted_periods", {})
    maximos = kpis.get("max_picos_por_periodo", {})
    meses_exceso = kpis.get("meses_exceso_por_periodo", {})

    labels = []
    values_current = []
    values_max = []

    for p in periodos:
        labels.append(p)
        values_current.append(contracted.get(p, 0.0))
        values_max.append(maximos.get(p, 0.0))

    fig = make_subplots(
        rows=1,
        cols=2,
        subplot_titles=("Potencia contratada vs pico máximo", "Meses con exceso por periodo"),
        specs=[[{"type": "bar"}, {"type": "bar"}]]
    )

    fig.add_trace(
        go.Bar(
            x=labels,
            y=values_current,
            name="Contratada",
            marker_color=COLOR_BLUE,
        ),
        row=1, col=1
    )

    fig.add_trace(
        go.Bar(
            x=labels,
            y=values_max,
            name="Pico máximo",
            marker_color=COLOR_RED,
        ),
        row=1, col=1
    )

    fig.add_trace(
        go.Bar(
            x=labels,
            y=[meses_exceso.get(p, 0) for p in labels],
            name="Meses con exceso",
            marker_color=COLOR_ORANGE,
        ),
        row=1, col=2
    )

    fig.update_layout(
        title="KPIs de optimización de potencia",
        barmode="group",
        template="plotly_white",
        height=450,
        legend_title_text=""
    )

    fig.update_yaxes(title_text="kW", row=1, col=1)
    fig.update_yaxes(title_text="Nº meses", row=1, col=2)

    return fig


# =============================================================================
# 2. BARRAS MENSUALES
# =============================================================================

def chart_monthly_official_peaks(opt_result: dict):
    picos = opt_result["picos_mensuales"]
    periodos = _ordered_periods(opt_result)
    contracted = opt_result["contracted_periods"]

    meses = [p["mes"].capitalize() for p in picos]

    fig = go.Figure()

    # Barras por periodo
    for p in periodos:
        fig.add_trace(
            go.Bar(
                x=meses,
                y=[pico["periodos"].get(p, {}).get("pico_kw", 0.0) for pico in picos],
                name=f"Pico {p}",
            )
        )

    # Líneas contratadas
    for p in periodos:
        fig.add_trace(
            go.Scatter(
                x=meses,
                y=[contracted.get(p, 0.0)] * len(meses),
                mode="lines",
                name=f"Contratada {p}",
                line=dict(dash="dash")
            )
        )

    fig.update_layout(
        title="Picos oficiales mensuales por periodo",
        barmode="group",
        template="plotly_white",
        height=520,
        xaxis_title="Mes",
        yaxis_title="kW",
        legend_title_text=""
    )

    return fig


# =============================================================================
# 3. TABLA DE EXCESOS
# =============================================================================

def chart_excess_table(opt_result: dict):
    if _is_3_0(opt_result):
        rows = opt_result.get("tabla_excesos_full", [])
        if not rows:
            rows = [{
                "mes": "—",
                "periodo": "—",
                "pico_kw": "—",
                "contracted_kw": "—",
                "exceso_kw": "—",
            }]

        df = pd.DataFrame(rows)
        cols = ["mes", "periodo", "pico_kw", "contracted_kw", "exceso_kw"]
        headers = ["Mes", "Periodo", "Pico (kW)", "Contratada (kW)", "Exceso (kW)"]

    else:
        rows = opt_result.get("tabla_excesos", [])
        if not rows:
            rows = [{
                "mes": "—",
                "pico_punta": "—",
                "exceso_p1": "—",
                "pico_valle": "—",
                "exceso_p2": "—",
            }]

        alias2 = _alias_periodo_2(opt_result)
        df = pd.DataFrame(rows)
        cols = ["mes", "pico_punta", "exceso_p1", "pico_valle", "exceso_p2"]
        headers = ["Mes", "Pico P1", "Exceso P1", f"Pico {alias2}", f"Exceso {alias2}"]

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
                    fill_color="white",
                    align="center",
                    font=dict(size=11),
                    height=28
                )
            )
        ]
    )

    fig.update_layout(
        title="Meses con excesos registrados",
        height=max(350, 60 + len(df) * 28)
    )

    return fig


# =============================================================================
# 4. TARJETAS OPCIONES SUGERIDAS
# =============================================================================

def chart_suggested_options(opt_result: dict):
    opciones = opt_result["opciones_sugeridas"]
    periodos = _ordered_periods(opt_result)

    fig = make_subplots(
        rows=1,
        cols=2,
        subplot_titles=(
            opciones["equilibrada"]["titulo"],
            opciones["segura"]["titulo"],
        ),
        specs=[[{"type": "table"}, {"type": "table"}]]
    )

    def build_table_data(op):
        rows = []
        for p in periodos:
            info = op["periodos"].get(p, {})
            rows.append({
                "Periodo": p,
                "kW": info.get("kw", 0.0),
                "Horas exceso": info.get("horas_exceso", 0),
                "Meses exceso": info.get("meses_exceso", 0),
            })
        return pd.DataFrame(rows)

    df_eq = build_table_data(opciones["equilibrada"])
    df_sg = build_table_data(opciones["segura"])

    fig.add_trace(
        go.Table(
            header=dict(
                values=list(df_eq.columns),
                fill_color=COLOR_ORANGE,
                font=dict(color="white", size=12),
                align="center"
            ),
            cells=dict(
                values=[df_eq[c] for c in df_eq.columns],
                fill_color="white",
                align="center",
                height=28
            )
        ),
        row=1, col=1
    )

    fig.add_trace(
        go.Table(
            header=dict(
                values=list(df_sg.columns),
                fill_color=COLOR_GREEN,
                font=dict(color="white", size=12),
                align="center"
            ),
            cells=dict(
                values=[df_sg[c] for c in df_sg.columns],
                fill_color="white",
                align="center",
                height=28
            )
        ),
        row=1, col=2
    )

    fig.update_layout(
        title="Opciones sugeridas de potencia contratada",
        height=450
    )

    return fig


# =============================================================================
# 5. RESUMEN DE EXCESOS POR PERIODO
# =============================================================================

def chart_excess_summary(opt_result: dict):
    kpis = opt_result["kpis"]
    periodos = _ordered_periods(opt_result)
    meses_exceso = kpis.get("meses_exceso_por_periodo", {})

    fig = go.Figure()

    fig.add_trace(
        go.Bar(
            x=periodos,
            y=[meses_exceso.get(p, 0) for p in periodos],
            marker_color=COLOR_RED,
            text=[meses_exceso.get(p, 0) for p in periodos],
            textposition="outside",
            name="Meses con exceso"
        )
    )

    fig.update_layout(
        title="Resumen de meses con exceso por periodo",
        template="plotly_white",
        height=420,
        xaxis_title="Periodo",
        yaxis_title="Nº meses",
        showlegend=False
    )

    return fig


# =============================================================================
# MAIN
# =============================================================================

def generate_optimization_charts(opt_result: dict):
    return {
        "kpis": chart_optimization_kpis(opt_result),
        "monthly_official": chart_monthly_official_peaks(opt_result),
        "table_excess": chart_excess_table(opt_result),
        "suggested_options": chart_suggested_options(opt_result),
        "summary_excess": chart_excess_summary(opt_result),
    }
