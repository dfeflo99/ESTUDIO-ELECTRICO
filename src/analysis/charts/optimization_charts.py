# =============================================================================
# src/analysis/charts/optimization_charts.py
# Graficos de optimizacion de potencia contratada
# Compatible con 2.0TD + 3.0TD
# Estructura original:
# 1. KPIs
# 2. Picos
# 3. Excesos
# 4. Opciones
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
COLOR_DARK = "#111827"
COLOR_GRAY = "#6B7280"


# =============================================================================
# HELPERS
# =============================================================================

def _is_3_0(opt_result: dict) -> bool:
    return opt_result.get("contract_type") == "3.0TD"


def _periodos(opt_result: dict):
    if _is_3_0(opt_result):
        return ["P1", "P2", "P3", "P4", "P5", "P6"]
    return ["P1", opt_result.get("alias_periodo_2", "P3")]


def _alias2(opt_result: dict) -> str:
    return opt_result.get("alias_periodo_2", "P3")


def _card_annotation(x0, x1, title, value, subtitle="", color=COLOR_BLUE, value_size=26, value_x=None):
    cx = (x0 + x1) / 2 if value_x is None else value_x

    ann = [
        dict(
            x=(x0 + x1) / 2,
            y=0.76,
            xref="paper",
            yref="paper",
            text=f"<b>{title}</b>",
            showarrow=False,
            font=dict(size=14, color=COLOR_DARK),
            align="center",
            xanchor="center",
        ),
        dict(
            x=cx,
            y=0.46,
            xref="paper",
            yref="paper",
            text=f"<span style='font-size:{value_size}px; color:{color}; white-space:normal'><b>{value}</b></span>",
            showarrow=False,
            align="center",
            xanchor="center",
        ),
    ]

    if subtitle:
        ann.append(
            dict(
                x=(x0 + x1) / 2,
                y=0.22,
                xref="paper",
                yref="paper",
                text=subtitle,
                showarrow=False,
                font=dict(size=12, color=COLOR_GRAY),
                align="center",
                xanchor="center",
            )
        )

    return ann


# =============================================================================
# 1. KPIs
# =============================================================================

def chart_optimization_kpis(opt_result: dict):
    kpis = opt_result["kpis"]
    es_3 = _is_3_0(opt_result)

    if not es_3:
        alias2 = _alias2(opt_result)

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

        estado = "Hay excesos registrados" if kpis.get("tiene_exceso") else "Potencia bien ajustada"
        estado_color = COLOR_RED if kpis.get("tiene_exceso") else COLOR_GREEN

        annotations = []
        annotations += _card_annotation(
            *boxes[0],
            "Potencias actuales",
            f"P1: {kpis['contracted_p1']} / {alias2}: {kpis['contracted_p2']}",
            color=COLOR_BLUE,
            value_size=22,
            value_x=0.125,
        )
        annotations += _card_annotation(
            *boxes[1],
            "Meses con exceso",
            f"P1: {kpis['meses_exceso_p1']} / {alias2}: {kpis['meses_exceso_p2']}",
            color=COLOR_ORANGE,
            value_size=22,
            value_x=0.375,
        )
        annotations += _card_annotation(
            *boxes[2],
            "Pico máximo",
            f"P1: {kpis['max_pico_punta']} / {alias2}: {kpis['max_pico_valle']}",
            color=COLOR_RED,
            value_size=20,
            value_x=0.625,
        )
        annotations += _card_annotation(
            *boxes[3],
            "Estado",
            estado,
            color=estado_color,
            value_size=12,
            value_x=0.89,
        )

        fig.update_layout(
            title="KPIs de optimización",
            template="plotly_white",
            height=260,
            margin=dict(l=20, r=20, t=60, b=20),
            xaxis=dict(visible=False),
            yaxis=dict(visible=False),
            annotations=annotations,
        )
        return fig

    # 3.0TD
    periodos = _periodos(opt_result)
    contracted = kpis.get("contracted_periods", {})
    meses_exceso = kpis.get("meses_exceso_por_periodo", {})
    maximos = kpis.get("max_picos_por_periodo", {})

    fig = make_subplots(
        rows=1,
        cols=3,
        subplot_titles=(
            "Contratada vs pico máximo",
            "Meses con exceso por periodo",
            "Estado",
        ),
        specs=[[{"type": "bar"}, {"type": "bar"}, {"type": "indicator"}]],
        column_widths=[0.42, 0.33, 0.25],
    )

    fig.add_trace(
        go.Bar(
            x=periodos,
            y=[contracted.get(p, 0.0) for p in periodos],
            name="Contratada",
            marker_color=COLOR_BLUE,
        ),
        row=1, col=1,
    )

    fig.add_trace(
        go.Bar(
            x=periodos,
            y=[maximos.get(p, 0.0) for p in periodos],
            name="Pico máximo",
            marker_color=COLOR_RED,
        ),
        row=1, col=1,
    )

    fig.add_trace(
        go.Bar(
            x=periodos,
            y=[meses_exceso.get(p, 0) for p in periodos],
            name="Meses con exceso",
            marker_color=COLOR_ORANGE,
            text=[meses_exceso.get(p, 0) for p in periodos],
            textposition="outside",
        ),
        row=1, col=2,
    )

    estado = "Hay periodos a revisar" if kpis.get("tiene_exceso") else "Potencia bien ajustada"
    estado_color = COLOR_RED if kpis.get("tiene_exceso") else COLOR_GREEN

    fig.add_trace(
        go.Indicator(
            mode="number",
            value=sum(meses_exceso.get(p, 0) for p in periodos),
            title={"text": f"<b>{estado}</b><br><span style='font-size:12px'>Suma meses con exceso</span>"},
            number={"font": {"size": 42, "color": estado_color}},
        ),
        row=1, col=3,
    )

    fig.update_layout(
        title="KPIs de optimización",
        template="plotly_white",
        height=420,
        barmode="group",
        legend_title_text="",
        margin=dict(l=20, r=20, t=70, b=40),
    )

    fig.update_yaxes(title_text="kW", row=1, col=1)
    fig.update_yaxes(title_text="Nº meses", row=1, col=2)

    return fig


# =============================================================================
# 2. PICOS
# =============================================================================

def chart_optimization_peaks(opt_result: dict):
    picos = opt_result["picos_mensuales"]
    periodos = _periodos(opt_result)
    contracted = opt_result["contracted_periods"]

    meses = [str(p["mes"]).capitalize() for p in picos]

    fig = go.Figure()

    for p in periodos:
        y = [row["periodos"].get(p, {}).get("pico_kw", 0.0) for row in picos]
        colors = []
        for row in picos:
            supera = row["periodos"].get(p, {}).get("supera", False)
            colors.append(COLOR_RED if supera else COLOR_BLUE)

        fig.add_trace(
            go.Bar(
                x=meses,
                y=y,
                name=f"Pico {p}",
                marker_color=colors,
            )
        )

    for p in periodos:
        fig.add_trace(
            go.Scatter(
                x=meses,
                y=[contracted.get(p, 0.0)] * len(meses),
                mode="lines",
                name=f"Contratada {p}",
                line=dict(dash="dash"),
            )
        )

    fig.update_layout(
        title="Picos mensuales vs potencia contratada",
        template="plotly_white",
        barmode="group",
        height=520,
        xaxis_title="Mes",
        yaxis_title="kW",
        legend_title_text="",
    )

    return fig


# =============================================================================
# 3. EXCESOS
# =============================================================================

def chart_optimization_excess(opt_result: dict):
    es_3 = _is_3_0(opt_result)

    if es_3:
        rows = opt_result.get("tabla_excesos_full", [])
        if not rows:
            fig = go.Figure()
            fig.add_annotation(
                text="<b>Sin excesos registrados</b>",
                x=0.5, y=0.5,
                xref="paper", yref="paper",
                showarrow=False,
                font=dict(size=20, color=COLOR_GREEN),
            )
            fig.update_layout(
                title="Excesos registrados",
                template="plotly_white",
                height=300,
                xaxis=dict(visible=False),
                yaxis=dict(visible=False),
            )
            return fig

        df = pd.DataFrame(rows)
        df = df.rename(columns={
            "mes": "Mes",
            "periodo": "Periodo",
            "pico_kw": "Pico (kW)",
            "contracted_kw": "Contratada (kW)",
            "exceso_kw": "Exceso (kW)",
        })

    else:
        rows = opt_result.get("tabla_excesos", [])
        if not rows:
            fig = go.Figure()
            fig.add_annotation(
                text="<b>Sin excesos registrados</b>",
                x=0.5, y=0.5,
                xref="paper", yref="paper",
                showarrow=False,
                font=dict(size=20, color=COLOR_GREEN),
            )
            fig.update_layout(
                title="Excesos registrados",
                template="plotly_white",
                height=300,
                xaxis=dict(visible=False),
                yaxis=dict(visible=False),
            )
            return fig

        alias2 = _alias2(opt_result)
        df = pd.DataFrame(rows)[["mes", "pico_punta", "exceso_p1", "pico_valle", "exceso_p2"]]
        df.columns = ["Mes", "Pico P1", "Exceso P1", f"Pico {alias2}", f"Exceso {alias2}"]

    fig = go.Figure(
        data=[
            go.Table(
                header=dict(
                    values=list(df.columns),
                    fill_color=COLOR_RED,
                    font=dict(color="white", size=12),
                    align="center",
                ),
                cells=dict(
                    values=[df[col] for col in df.columns],
                    fill_color="white",
                    align="center",
                    font=dict(size=11),
                    height=28,
                ),
            )
        ]
    )

    fig.update_layout(
        title="Excesos registrados",
        height=max(320, 90 + len(df) * 28),
    )

    return fig


# =============================================================================
# 4. OPCIONES
# =============================================================================

def chart_optimization_options(opt_result: dict):
    opciones = opt_result["opciones_sugeridas"]
    periodos = _periodos(opt_result)

    fig = make_subplots(
        rows=1,
        cols=2,
        subplot_titles=(
            opciones["equilibrada"]["titulo"],
            opciones["segura"]["titulo"],
        ),
        specs=[[{"type": "table"}, {"type": "table"}]],
    )

    def build_df(op):
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

    df_eq = build_df(opciones["equilibrada"])
    df_sg = build_df(opciones["segura"])

    fig.add_trace(
        go.Table(
            header=dict(
                values=list(df_eq.columns),
                fill_color=COLOR_ORANGE,
                font=dict(color="white", size=12),
                align="center",
            ),
            cells=dict(
                values=[df_eq[c] for c in df_eq.columns],
                fill_color="#FFF7ED",
                align="center",
                height=28,
            ),
        ),
        row=1, col=1,
    )

    fig.add_trace(
        go.Table(
            header=dict(
                values=list(df_sg.columns),
                fill_color=COLOR_GREEN,
                font=dict(color="white", size=12),
                align="center",
            ),
            cells=dict(
                values=[df_sg[c] for c in df_sg.columns],
                fill_color="#ECFDF5",
                align="center",
                height=28,
            ),
        ),
        row=1, col=2,
    )

    fig.update_layout(
        title="Opciones sugeridas",
        height=460,
    )

    return fig


# =============================================================================
# MAIN
# =============================================================================

def generate_optimization_charts(opt_result: dict):
    print("Generando gráficos de optimización...")

    charts = {
        "kpis": chart_optimization_kpis(opt_result),
        "picos": chart_optimization_peaks(opt_result),
        "excesos": chart_optimization_excess(opt_result),
        "opciones": chart_optimization_options(opt_result),
    }

    print("4 gráficos generados correctamente.")
    return charts
