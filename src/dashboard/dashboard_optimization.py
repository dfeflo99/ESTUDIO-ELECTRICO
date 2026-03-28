# =============================================================================
# src/dashboard/dashboard_optimization.py
# Dashboard de optimizacion de potencia
# Compatible con 2.0TD + 3.0TD
# =============================================================================

import os
import sys
import tempfile

import dash
from dash import dcc, html, Input, Output, State
import dash_bootstrap_components as dbc

sys.path.append("../..")

from src.models.internal_data_model import ElectricityAnalysis, ContractType
from src.analysis.optimization_engine import run_optimization_analysis
from src.analysis.charts.optimization_charts import (
    chart_optimization_kpis,
    chart_optimization_peaks,
    chart_optimization_excess,
    chart_optimization_options,
)
from src.reports.report_generator import generate_report


# =============================================================================
# ESTILOS
# =============================================================================

COLORS = {
    "primary": "#2563EB",
    "success": "#10B981",
    "warning": "#F59E0B",
    "danger": "#CC1F1F",
    "background": "#F0F4FF",
    "card": "#FFFFFF",
    "text": "#1E293B",
    "text_light": "#64748B",
    "border": "#E2E8F0",
}

CARD_STYLE = {
    "backgroundColor": COLORS["card"],
    "borderRadius": "12px",
    "padding": "20px",
    "marginBottom": "20px",
    "boxShadow": "0 1px 4px rgba(0,0,0,0.08)",
    "border": f"1px solid {COLORS['border']}",
}

TITLE_STYLE = {
    "color": COLORS["success"],
    "fontFamily": "Segoe UI, Arial, sans-serif",
    "fontWeight": "700",
    "fontSize": "24px",
    "margin": "0",
}

SUBTITLE_STYLE = {
    "color": COLORS["text_light"],
    "fontFamily": "Segoe UI, Arial, sans-serif",
    "fontSize": "14px",
    "marginTop": "4px",
}

SECTION_TITLE_STYLE = {
    "color": COLORS["text"],
    "fontFamily": "Segoe UI, Arial, sans-serif",
    "fontWeight": "600",
    "fontSize": "16px",
    "marginBottom": "12px",
    "borderLeft": f"4px solid {COLORS['success']}",
    "paddingLeft": "10px",
}

FILTER_LABEL_STYLE = {
    "color": COLORS["text"],
    "fontFamily": "Segoe UI, Arial, sans-serif",
    "fontWeight": "600",
    "fontSize": "13px",
    "marginBottom": "8px",
}

BTN_PDF_STYLE = {
    "backgroundColor": "#CC1F1F",
    "color": "white",
    "border": "none",
    "padding": "12px 32px",
    "borderRadius": "8px",
    "fontSize": "14px",
    "fontFamily": "Segoe UI, Arial, sans-serif",
    "fontWeight": "600",
    "cursor": "pointer",
}


# =============================================================================
# HELPERS
# =============================================================================

def _is_3_0(analysis: ElectricityAnalysis) -> bool:
    return analysis.client.contract_type == ContractType.TD_3_0


def _default_value(value, fallback):
    try:
        if value is None or value == "":
            return fallback
        return float(value)
    except Exception:
        return fallback


def _initial_power_values(
    analysis: ElectricityAnalysis,
    contracted_p1=None,
    contracted_p2=None,
    contracted_p3=None,
    contracted_p4=None,
    contracted_p5=None,
    contracted_p6=None,
):
    base = analysis.contract.contracted_powers if analysis.contract else None

    def pick(attr, explicit, fallback):
        if explicit is not None:
            return explicit
        if base is not None:
            val = getattr(base, attr, None)
            if val not in (None, 0):
                return val
        return fallback

    if _is_3_0(analysis):
        return {
            "P1": pick("p1", contracted_p1, 10.0),
            "P2": pick("p2", contracted_p2, 8.0),
            "P3": pick("p3", contracted_p3, 7.0),
            "P4": pick("p4", contracted_p4, 7.0),
            "P5": pick("p5", contracted_p5, 5.0),
            "P6": pick("p6", contracted_p6, 5.0),
        }

    return {
        "P1": pick("p1", contracted_p1, 2.3),
        "P3": pick("p3", contracted_p3 if contracted_p3 is not None else contracted_p2, 2.3),
    }


def _build_power_controls(analysis: ElectricityAnalysis, init_vals: dict):
    if _is_3_0(analysis):
        return html.Div(
            style={"display": "grid", "gridTemplateColumns": "repeat(3, 1fr)", "gap": "20px"},
            children=[
                html.Div([
                    html.P("P1 (kW)", style=FILTER_LABEL_STYLE),
                    dcc.Input(
                        id="opt-p1-input",
                        type="number",
                        value=init_vals["P1"],
                        step=0.1,
                        style={"width": "100%", "padding": "10px"},
                    ),
                ]),
                html.Div([
                    html.P("P2 (kW)", style=FILTER_LABEL_STYLE),
                    dcc.Input(
                        id="opt-p2-input",
                        type="number",
                        value=init_vals["P2"],
                        step=0.1,
                        style={"width": "100%", "padding": "10px"},
                    ),
                ]),
                html.Div([
                    html.P("P3 (kW)", style=FILTER_LABEL_STYLE),
                    dcc.Input(
                        id="opt-p3-input",
                        type="number",
                        value=init_vals["P3"],
                        step=0.1,
                        style={"width": "100%", "padding": "10px"},
                    ),
                ]),
                html.Div([
                    html.P("P4 (kW)", style=FILTER_LABEL_STYLE),
                    dcc.Input(
                        id="opt-p4-input",
                        type="number",
                        value=init_vals["P4"],
                        step=0.1,
                        style={"width": "100%", "padding": "10px"},
                    ),
                ]),
                html.Div([
                    html.P("P5 (kW)", style=FILTER_LABEL_STYLE),
                    dcc.Input(
                        id="opt-p5-input",
                        type="number",
                        value=init_vals["P5"],
                        step=0.1,
                        style={"width": "100%", "padding": "10px"},
                    ),
                ]),
                html.Div([
                    html.P("P6 (kW)", style=FILTER_LABEL_STYLE),
                    dcc.Input(
                        id="opt-p6-input",
                        type="number",
                        value=init_vals["P6"],
                        step=0.1,
                        style={"width": "100%", "padding": "10px"},
                    ),
                ]),
            ],
        )

    # 2.0TD: input libre, no dropdown
    return html.Div(
        style={"display": "grid", "gridTemplateColumns": "1fr 1fr", "gap": "24px"},
        children=[
            html.Div([
                html.P("P1 (kW) — Laborable diurno", style=FILTER_LABEL_STYLE),
                dcc.Input(
                    id="opt-p1-input",
                    type="number",
                    value=init_vals["P1"],
                    step=0.1,
                    style={"width": "100%", "padding": "10px"},
                ),
            ]),
            html.Div([
                html.P("P3 (kW) — Nocturno / Finde", style=FILTER_LABEL_STYLE),
                dcc.Input(
                    id="opt-p3-input",
                    type="number",
                    value=init_vals["P3"],
                    step=0.1,
                    style={"width": "100%", "padding": "10px"},
                ),
            ]),
        ],
    )


# =============================================================================
# LAYOUT
# =============================================================================

def build_optimization_layout(
    analysis: ElectricityAnalysis,
    contracted_p1=None,
    contracted_p2=None,
    contracted_p3=None,
    contracted_p4=None,
    contracted_p5=None,
    contracted_p6=None,
):
    init_vals = _initial_power_values(
        analysis,
        contracted_p1, contracted_p2, contracted_p3,
        contracted_p4, contracted_p5, contracted_p6,
    )

    subtitulo = (
        "Analiza picos reales, excesos y opciones sugeridas."
        if _is_3_0(analysis)
        else "Analiza picos reales y ajusta P1/P3 para simular escenarios."
    )

    return html.Div(
        style={"backgroundColor": COLORS["background"], "minHeight": "100vh", "padding": "24px"},
        children=[
            html.Div(
                style={**CARD_STYLE, "display": "flex", "justifyContent": "space-between", "alignItems": "center"},
                children=[
                    html.Div([
                        html.H1("Optimización de Potencia Contratada", style=TITLE_STYLE),
                        html.P(subtitulo, style=SUBTITLE_STYLE),
                    ])
                ],
            ),

            html.Div(
                style=CARD_STYLE,
                children=[
                    html.P("Potencias contratadas actuales / simuladas", style=FILTER_LABEL_STYLE),
                    _build_power_controls(analysis, init_vals),
                ],
            ),

            html.Div(style=CARD_STYLE, children=[
                html.P("Resumen", style=SECTION_TITLE_STYLE),
                dcc.Graph(id="opt-kpis", config={"displayModeBar": False}),
            ]),

            html.Div(style=CARD_STYLE, children=[
                html.P("Picos mensuales vs potencia contratada", style=SECTION_TITLE_STYLE),
                html.P(
                    "Rojo = supera la potencia contratada. Azul = dentro del límite.",
                    style={**SUBTITLE_STYLE, "marginBottom": "12px"},
                ),
                dcc.Graph(id="opt-picos", config={"displayModeBar": False}),
            ]),

            html.Div(style=CARD_STYLE, children=[
                html.P("Detalle de excesos", style=SECTION_TITLE_STYLE),
                dcc.Graph(id="opt-excesos", config={"displayModeBar": False}),
            ]),

            html.Div(style=CARD_STYLE, children=[
                html.P("Opciones sugeridas", style=SECTION_TITLE_STYLE),
                html.P(
                    "Puedes usar estas opciones como referencia y después ajustar manualmente.",
                    style={**SUBTITLE_STYLE, "marginBottom": "12px"},
                ),
                dcc.Graph(id="opt-opciones", config={"displayModeBar": False}),
            ]),

            html.Div(style={**CARD_STYLE, "textAlign": "center", "padding": "24px"}, children=[
                html.P(
                    "Descarga el informe PDF con el estado actual del análisis.",
                    style={**SUBTITLE_STYLE, "marginBottom": "16px"},
                ),
                html.Button("Descargar Informe PDF", id="opt-btn-download-pdf", style=BTN_PDF_STYLE),
                dcc.Download(id="opt-download-pdf"),
            ]),
        ],
    )


# =============================================================================
# DASHBOARD
# =============================================================================

def run_optimization_dashboard(
    analysis: ElectricityAnalysis,
    contracted_p1: float = None,
    contracted_p2: float = None,
    contracted_p3: float = None,
    contracted_p4: float = None,
    contracted_p5: float = None,
    contracted_p6: float = None,
    port: int = 8053,
):
    _analysis_global = analysis
    es_3 = _is_3_0(analysis)

    app = dash.Dash(
        __name__,
        external_stylesheets=[dbc.themes.BOOTSTRAP],
        title="Estudio Electrico — Optimización",
    )

    app.layout = build_optimization_layout(
        analysis,
        contracted_p1, contracted_p2, contracted_p3,
        contracted_p4, contracted_p5, contracted_p6,
    )

    @app.callback(
        Output("opt-kpis", "figure"),
        Output("opt-picos", "figure"),
        Output("opt-excesos", "figure"),
        Output("opt-opciones", "figure"),
        Input("opt-p1-input", "value"),
        Input("opt-p3-input", "value"),
        Input("opt-p2-input", "value") if es_3 else Input("opt-p1-input", "value"),
        Input("opt-p4-input", "value") if es_3 else Input("opt-p1-input", "value"),
        Input("opt-p5-input", "value") if es_3 else Input("opt-p1-input", "value"),
        Input("opt-p6-input", "value") if es_3 else Input("opt-p1-input", "value"),
    )
    def update_charts(p1, p3, p2_dummy_or_real, p4_dummy_or_real, p5_dummy_or_real, p6_dummy_or_real):
        if es_3:
            p2 = _default_value(p2_dummy_or_real, 8.0)
            p4 = _default_value(p4_dummy_or_real, 7.0)
            p5 = _default_value(p5_dummy_or_real, 5.0)
            p6 = _default_value(p6_dummy_or_real, 5.0)

            data = run_optimization_analysis(
                _analysis_global,
                contracted_p1=_default_value(p1, 10.0),
                contracted_p2=p2,
                contracted_p3=_default_value(p3, 7.0),
                contracted_p4=p4,
                contracted_p5=p5,
                contracted_p6=p6,
            )
        else:
            data = run_optimization_analysis(
                _analysis_global,
                contracted_p1=_default_value(p1, 2.3),
                contracted_p2=_default_value(p3, 2.3),
            )

        return (
            chart_optimization_kpis(data),
            chart_optimization_peaks(data),
            chart_optimization_excess(data),
            chart_optimization_options(data),
        )

    @app.callback(
        Output("opt-download-pdf", "data"),
        Input("opt-btn-download-pdf", "n_clicks"),
        State("opt-p1-input", "value"),
        State("opt-p3-input", "value"),
        State("opt-p2-input", "value") if es_3 else State("opt-p1-input", "value"),
        State("opt-p4-input", "value") if es_3 else State("opt-p1-input", "value"),
        State("opt-p5-input", "value") if es_3 else State("opt-p1-input", "value"),
        State("opt-p6-input", "value") if es_3 else State("opt-p1-input", "value"),
        prevent_initial_call=True,
    )
    def download_pdf(n_clicks, p1, p3, p2_dummy_or_real, p4_dummy_or_real, p5_dummy_or_real, p6_dummy_or_real):
        pw = _analysis_global.power_analysis

        params = {
            "contracted_p1": _default_value(p1, 10.0 if es_3 else 2.3),
            "contracted_p2": _default_value(p2_dummy_or_real, 8.0) if es_3 else _default_value(p3, 2.3),
            "contracted_p3": _default_value(p3, 7.0) if es_3 else None,
            "contracted_p4": _default_value(p4_dummy_or_real, 7.0) if es_3 else None,
            "contracted_p5": _default_value(p5_dummy_or_real, 5.0) if es_3 else None,
            "contracted_p6": _default_value(p6_dummy_or_real, 5.0) if es_3 else None,
            "umbral_kw": pw.umbral_kw if pw else 2.0,
            "meses_filtro": [],
        }

        with tempfile.NamedTemporaryFile(suffix=".pdf", delete=False) as tmp:
            tmp_path = tmp.name

        generate_report(_analysis_global, tmp_path, logo_path=None, params=params)

        with open(tmp_path, "rb") as f:
            pdf_bytes = f.read()

        os.unlink(tmp_path)
        return dcc.send_bytes(pdf_bytes, "informe_f2energy.pdf")

    print(f"Dashboard de optimización lanzado en http://localhost:{port}")
    app.run(debug=False, port=port)
