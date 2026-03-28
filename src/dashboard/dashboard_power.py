# =============================================================================
# src/dashboard/dashboard_power.py
# Dashboard de analisis de potencia
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
from src.analysis.power_engine import run_power_analysis
from src.analysis.charts.power_charts import generate_power_charts
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
    "color": COLORS["primary"],
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
    "borderLeft": f"4px solid {COLORS['primary']}",
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
                    dcc.Input(id="pw-p1-input", type="number", value=init_vals["P1"], step=0.1,
                              style={"width": "100%", "padding": "10px"}),
                ]),
                html.Div([
                    html.P("P2 (kW)", style=FILTER_LABEL_STYLE),
                    dcc.Input(id="pw-p2-input", type="number", value=init_vals["P2"], step=0.1,
                              style={"width": "100%", "padding": "10px"}),
                ]),
                html.Div([
                    html.P("P3 (kW)", style=FILTER_LABEL_STYLE),
                    dcc.Input(id="pw-p3-input", type="number", value=init_vals["P3"], step=0.1,
                              style={"width": "100%", "padding": "10px"}),
                ]),
                html.Div([
                    html.P("P4 (kW)", style=FILTER_LABEL_STYLE),
                    dcc.Input(id="pw-p4-input", type="number", value=init_vals["P4"], step=0.1,
                              style={"width": "100%", "padding": "10px"}),
                ]),
                html.Div([
                    html.P("P5 (kW)", style=FILTER_LABEL_STYLE),
                    dcc.Input(id="pw-p5-input", type="number", value=init_vals["P5"], step=0.1,
                              style={"width": "100%", "padding": "10px"}),
                ]),
                html.Div([
                    html.P("P6 (kW)", style=FILTER_LABEL_STYLE),
                    dcc.Input(id="pw-p6-input", type="number", value=init_vals["P6"], step=0.1,
                              style={"width": "100%", "padding": "10px"}),
                ]),
            ]
        )

    return html.Div(
        style={"display": "grid", "gridTemplateColumns": "1fr 1fr", "gap": "24px"},
        children=[
            html.Div([
                html.P("P1 (kW) — Laborable diurno", style=FILTER_LABEL_STYLE),
                dcc.Input(id="pw-p1-input", type="number", value=init_vals["P1"], step=0.1,
                          style={"width": "100%", "padding": "10px"}),
            ]),
            html.Div([
                html.P("P3 (kW) — Nocturno / Finde", style=FILTER_LABEL_STYLE),
                dcc.Input(id="pw-p3-input", type="number", value=init_vals["P3"], step=0.1,
                          style={"width": "100%", "padding": "10px"}),
            ]),
        ]
    )


def _initial_umbral(analysis: ElectricityAnalysis, umbral_kw=None):
    if umbral_kw is not None:
        return umbral_kw
    if getattr(analysis, "power_analysis", None) is not None:
        pa = analysis.power_analysis
        if getattr(pa, "umbral_kw", None) is not None:
            return pa.umbral_kw
    return 2.0


# =============================================================================
# LAYOUT
# =============================================================================

def build_power_layout(
    analysis: ElectricityAnalysis,
    contracted_p1=None,
    contracted_p2=None,
    contracted_p3=None,
    contracted_p4=None,
    contracted_p5=None,
    contracted_p6=None,
    umbral_kw=None,
):
    init_vals = _initial_power_values(
        analysis,
        contracted_p1, contracted_p2, contracted_p3,
        contracted_p4, contracted_p5, contracted_p6
    )
    init_umbral = _initial_umbral(analysis, umbral_kw)

    subtitulo = (
        "Ajusta el umbral y las potencias contratadas para analizar el perfil real."
        if _is_3_0(analysis)
        else "Ajusta umbral y potencias contratadas para ver el perfil y los máximos reales."
    )

    return html.Div(
        style={"backgroundColor": COLORS["background"], "minHeight": "100vh", "padding": "24px"},
        children=[
            html.Div(
                style={**CARD_STYLE, "display": "flex", "justifyContent": "space-between", "alignItems": "center"},
                children=[
                    html.Div([
                        html.H1("Análisis de Potencia", style=TITLE_STYLE),
                        html.P(subtitulo, style=SUBTITLE_STYLE),
                    ])
                ]
            ),

            html.Div(
                style=CARD_STYLE,
                children=[
                    html.Div(
                        style={"display": "grid", "gridTemplateColumns": "1.5fr 1fr", "gap": "24px"},
                        children=[
                            html.Div([
                                html.P("Potencias contratadas actuales / simuladas", style=FILTER_LABEL_STYLE),
                                _build_power_controls(analysis, init_vals),
                            ]),
                            html.Div([
                                html.P("Umbral de análisis (kW)", style=FILTER_LABEL_STYLE),
                                dcc.Slider(
                                    id="pw-umbral-slider",
                                    min=0.5,
                                    max=12.0 if _is_3_0(analysis) else 6.0,
                                    step=0.1,
                                    value=init_umbral,
                                    marks={i: str(i) for i in range(1, 13 if _is_3_0(analysis) else 7)},
                                    tooltip={"placement": "bottom", "always_visible": True},
                                ),
                            ]),
                        ]
                    )
                ]
            ),

            html.Div(style=CARD_STYLE, children=[
                html.P("KPIs", style=SECTION_TITLE_STYLE),
                dcc.Graph(id="pw-kpis", config={"displayModeBar": False}),
            ]),

            html.Div(style=CARD_STYLE, children=[
                html.P("Máximo diario", style=SECTION_TITLE_STYLE),
                dcc.Graph(id="pw-daily-max", config={"displayModeBar": False}),
            ]),

            html.Div(style=CARD_STYLE, children=[
                html.P("Heatmap hora × día", style=SECTION_TITLE_STYLE),
                dcc.Graph(id="pw-heatmap", config={"displayModeBar": False}),
            ]),

            html.Div(style=CARD_STYLE, children=[
                html.P("Curva de duración", style=SECTION_TITLE_STYLE),
                dcc.Graph(id="pw-ranking", config={"displayModeBar": False}),
            ]),

            html.Div(style=CARD_STYLE, children=[
                html.P("Perfil", style=SECTION_TITLE_STYLE),
                dcc.Graph(id="pw-profile", config={"displayModeBar": False}),
            ]),

            html.Div(style=CARD_STYLE, children=[
                html.P("Picos oficiales mensuales", style=SECTION_TITLE_STYLE),
                dcc.Graph(id="pw-monthly-official", config={"displayModeBar": False}),
            ]),

            html.Div(style={**CARD_STYLE, "textAlign": "center", "padding": "24px"}, children=[
                html.P(
                    "Descarga el informe PDF con el estado actual del análisis.",
                    style={**SUBTITLE_STYLE, "marginBottom": "16px"}
                ),
                html.Button("Descargar Informe PDF", id="pw-btn-download-pdf", style=BTN_PDF_STYLE),
                dcc.Download(id="pw-download-pdf"),
            ]),
        ]
    )


# =============================================================================
# DASHBOARD
# =============================================================================

def run_power_dashboard(
    analysis: ElectricityAnalysis,
    contracted_p1: float = None,
    contracted_p2: float = None,
    contracted_p3: float = None,
    contracted_p4: float = None,
    contracted_p5: float = None,
    contracted_p6: float = None,
    umbral_kw: float = None,
    port: int = 8051,
):
    _analysis_global = analysis
    es_3 = _is_3_0(analysis)

    app = dash.Dash(
        __name__,
        external_stylesheets=[dbc.themes.BOOTSTRAP],
        title="Estudio Electrico — Potencia"
    )

    app.layout = build_power_layout(
        analysis,
        contracted_p1, contracted_p2, contracted_p3,
        contracted_p4, contracted_p5, contracted_p6,
        umbral_kw,
    )

    @app.callback(
        Output("pw-kpis", "figure"),
        Output("pw-daily-max", "figure"),
        Output("pw-heatmap", "figure"),
        Output("pw-ranking", "figure"),
        Output("pw-profile", "figure"),
        Output("pw-monthly-official", "figure"),
        Input("pw-p1-input", "value"),
        Input("pw-p3-input", "value"),
        Input("pw-umbral-slider", "value"),
        Input("pw-p2-input", "value") if es_3 else Input("pw-p1-input", "value"),
        Input("pw-p4-input", "value") if es_3 else Input("pw-p1-input", "value"),
        Input("pw-p5-input", "value") if es_3 else Input("pw-p1-input", "value"),
        Input("pw-p6-input", "value") if es_3 else Input("pw-p1-input", "value"),
    )
    def update_charts(p1, p3, umbral, p2_dummy_or_real, p4_dummy_or_real, p5_dummy_or_real, p6_dummy_or_real):
        if es_3:
            data = run_power_analysis(
                _analysis_global,
                contracted_p1=_default_value(p1, 10.0),
                contracted_p2=_default_value(p2_dummy_or_real, 8.0),
                contracted_p3=_default_value(p3, 7.0),
                contracted_p4=_default_value(p4_dummy_or_real, 7.0),
                contracted_p5=_default_value(p5_dummy_or_real, 5.0),
                contracted_p6=_default_value(p6_dummy_or_real, 5.0),
                umbral_kw=_default_value(umbral, 2.0),
            )
        else:
            data = run_power_analysis(
                _analysis_global,
                contracted_p1=_default_value(p1, 2.3),
                contracted_p2=_default_value(p3, 2.3),
                umbral_kw=_default_value(umbral, 2.0),
            )

        charts = generate_power_charts(data.power_analysis)

        return (
            charts["kpis"],
            charts["daily_max"],
            charts["heatmap"],
            charts["ranking"],
            charts["profile"],
            charts["monthly_official"],
        )

    @app.callback(
        Output("pw-download-pdf", "data"),
        Input("pw-btn-download-pdf", "n_clicks"),
        State("pw-p1-input", "value"),
        State("pw-p3-input", "value"),
        State("pw-umbral-slider", "value"),
        State("pw-p2-input", "value") if es_3 else State("pw-p1-input", "value"),
        State("pw-p4-input", "value") if es_3 else State("pw-p1-input", "value"),
        State("pw-p5-input", "value") if es_3 else State("pw-p1-input", "value"),
        State("pw-p6-input", "value") if es_3 else State("pw-p1-input", "value"),
        prevent_initial_call=True
    )
    def download_pdf(n_clicks, p1, p3, umbral, p2_dummy_or_real, p4_dummy_or_real, p5_dummy_or_real, p6_dummy_or_real):
        params = {
            "contracted_p1": _default_value(p1, 10.0 if es_3 else 2.3),
            "contracted_p2": _default_value(p2_dummy_or_real, 8.0) if es_3 else _default_value(p3, 2.3),
            "contracted_p3": _default_value(p3, 7.0) if es_3 else None,
            "contracted_p4": _default_value(p4_dummy_or_real, 7.0) if es_3 else None,
            "contracted_p5": _default_value(p5_dummy_or_real, 5.0) if es_3 else None,
            "contracted_p6": _default_value(p6_dummy_or_real, 5.0) if es_3 else None,
            "umbral_kw": _default_value(umbral, 2.0),
            "meses_filtro": [],
        }

        with tempfile.NamedTemporaryFile(suffix=".pdf", delete=False) as tmp:
            tmp_path = tmp.name

        generate_report(_analysis_global, tmp_path, logo_path=None, params=params)

        with open(tmp_path, "rb") as f:
            pdf_bytes = f.read()

        os.unlink(tmp_path)
        return dcc.send_bytes(pdf_bytes, "informe_f2energy_potencia.pdf")

    print(f"Dashboard de potencia lanzado en http://localhost:{port}")
    app.run(debug=False, port=port)
