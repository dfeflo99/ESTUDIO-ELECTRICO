# =============================================================================
# src/dashboard/dashboard_power.py
# Dashboard de analisis de potencia
# Compatible con 2.0TD + 3.0TD
# =============================================================================

import copy
import os
import sys
import tempfile

import dash
from dash import dcc, html, Input, Output, State
import dash_bootstrap_components as dbc
import plotly.graph_objects as go

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

INFO_BOX_STYLE = {
    "backgroundColor": "#EFF6FF",
    "border": "1px solid #BFDBFE",
    "borderRadius": "10px",
    "padding": "14px 16px",
    "color": COLORS["text"],
    "fontFamily": "Segoe UI, Arial, sans-serif",
    "fontSize": "13px",
    "marginTop": "14px",
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

MONTH_NUM_TO_NAME = {
    1: "Enero", 2: "Febrero", 3: "Marzo", 4: "Abril",
    5: "Mayo", 6: "Junio", 7: "Julio", 8: "Agosto",
    9: "Septiembre", 10: "Octubre", 11: "Noviembre", 12: "Diciembre"
}

MONTH_NAME_TO_NUM = {v: k for k, v in MONTH_NUM_TO_NAME.items()}


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


def _message_figure(title, text):
    fig = go.Figure()
    fig.add_annotation(
        text=f"<b>{text}</b>",
        x=0.5, y=0.5,
        xref="paper", yref="paper",
        showarrow=False,
        font=dict(size=18, color="#6B7280")
    )
    fig.update_layout(
        title=title,
        template="plotly_white",
        height=380,
        xaxis=dict(visible=False),
        yaxis=dict(visible=False),
    )
    return fig


def _extract_available_years(analysis: ElectricityAnalysis):
    years = sorted({r.timestamp.year for r in analysis.hourly_records})
    return years


def _extract_available_months(analysis: ElectricityAnalysis, selected_years=None):
    months = []
    for r in analysis.hourly_records:
        if selected_years and r.timestamp.year not in selected_years:
            continue
        months.append(r.timestamp.month)
    months = sorted(set(months))
    return [MONTH_NUM_TO_NAME[m] for m in months]


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


def _filter_analysis(analysis: ElectricityAnalysis, selected_years=None, selected_month=None):
    filtered = copy.deepcopy(analysis)

    selected_years = selected_years or []
    month_num = MONTH_NAME_TO_NUM.get(selected_month) if selected_month else None

    def keep_timestamp(ts):
        ok_year = (not selected_years) or (ts.year in selected_years)
        ok_month = (month_num is None) or (ts.month == month_num)
        return ok_year and ok_month

    filtered.hourly_records = [r for r in analysis.hourly_records if keep_timestamp(r.timestamp)]

    if hasattr(analysis, "monthly_max_power") and analysis.monthly_max_power:
        filtered.monthly_max_power = [
            r for r in analysis.monthly_max_power
            if keep_timestamp(r.date)
        ]
    else:
        filtered.monthly_max_power = []

    return filtered


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

    available_years = _extract_available_years(analysis)
    available_months = _extract_available_months(analysis, available_years)

    return html.Div(
        style={"backgroundColor": COLORS["background"], "minHeight": "100vh", "padding": "24px"},
        children=[
            html.Div(
                style={**CARD_STYLE, "display": "flex", "justifyContent": "space-between", "alignItems": "center"},
                children=[
                    html.Div([
                        html.H1("Análisis de Potencia", style=TITLE_STYLE),
                        html.P(
                            "Ajusta umbral, potencias, año y mes para analizar el comportamiento real.",
                            style=SUBTITLE_STYLE
                        ),
                        html.Div(
                            "Las potencias mostradas aquí son potencias medias de una hora calculadas a partir de la curva de consumo. No son picos instantáneos del momento.",
                            style=INFO_BOX_STYLE
                        ),
                    ])
                ]
            ),

            html.Div(
                style=CARD_STYLE,
                children=[
                    html.Div(
                        style={"display": "grid", "gridTemplateColumns": "1.3fr 1fr 1fr 1fr", "gap": "24px"},
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
                            html.Div([
                                html.P("Filtrar por año", style=FILTER_LABEL_STYLE),
                                dcc.Dropdown(
                                    id="pw-year-filter",
                                    options=[{"label": str(y), "value": y} for y in available_years],
                                    value=available_years,
                                    multi=True,
                                    placeholder="Todos los años",
                                ),
                            ]),
                            html.Div([
                                html.P("Filtrar por mes", style=FILTER_LABEL_STYLE),
                                dcc.Dropdown(
                                    id="pw-month-filter",
                                    options=[{"label": m, "value": m} for m in available_months],
                                    value=None,
                                    clearable=True,
                                    placeholder="Todos los meses",
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
                html.P("Distribución horaria estimada", style=SECTION_TITLE_STYLE),
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

            html.Div(style=CARD_STYLE, children=[
                html.P("Tabla de valores mensuales", style=SECTION_TITLE_STYLE),
                dcc.Graph(id="pw-monthly-official-table", config={"displayModeBar": False}),
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
        Output("pw-month-filter", "options"),
        Input("pw-year-filter", "value"),
    )
    def update_month_options(selected_years):
        months = _extract_available_months(_analysis_global, selected_years)
        return [{"label": m, "value": m} for m in months]

    @app.callback(
        Output("pw-kpis", "figure"),
        Output("pw-daily-max", "figure"),
        Output("pw-heatmap", "figure"),
        Output("pw-ranking", "figure"),
        Output("pw-profile", "figure"),
        Output("pw-monthly-official", "figure"),
        Output("pw-monthly-official-table", "figure"),
        Input("pw-p1-input", "value"),
        Input("pw-p3-input", "value"),
        Input("pw-umbral-slider", "value"),
        Input("pw-year-filter", "value"),
        Input("pw-month-filter", "value"),
        Input("pw-p2-input", "value") if es_3 else Input("pw-p1-input", "value"),
        Input("pw-p4-input", "value") if es_3 else Input("pw-p1-input", "value"),
        Input("pw-p5-input", "value") if es_3 else Input("pw-p1-input", "value"),
        Input("pw-p6-input", "value") if es_3 else Input("pw-p1-input", "value"),
    )
    def update_charts(p1, p3, umbral, selected_years, selected_month, p2_dummy_or_real, p4_dummy_or_real, p5_dummy_or_real, p6_dummy_or_real):
        filtered_analysis = _filter_analysis(
            _analysis_global,
            selected_years=selected_years or [],
            selected_month=selected_month,
        )

        if not filtered_analysis.hourly_records:
            empty = _message_figure("Sin datos", "No hay datos para los filtros seleccionados")
            return empty, empty, empty, empty, empty, empty, empty

        if es_3:
            data = run_power_analysis(
                filtered_analysis,
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
                filtered_analysis,
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
            charts["monthly_official_table"],
        )

    @app.callback(
        Output("pw-download-pdf", "data"),
        Input("pw-btn-download-pdf", "n_clicks"),
        State("pw-p1-input", "value"),
        State("pw-p3-input", "value"),
        State("pw-umbral-slider", "value"),
        State("pw-year-filter", "value"),
        State("pw-month-filter", "value"),
        State("pw-p2-input", "value") if es_3 else State("pw-p1-input", "value"),
        State("pw-p4-input", "value") if es_3 else State("pw-p1-input", "value"),
        State("pw-p5-input", "value") if es_3 else State("pw-p1-input", "value"),
        State("pw-p6-input", "value") if es_3 else State("pw-p1-input", "value"),
        prevent_initial_call=True
    )
    def download_pdf(n_clicks, p1, p3, umbral, selected_years, selected_month, p2_dummy_or_real, p4_dummy_or_real, p5_dummy_or_real, p6_dummy_or_real):
        params = {
            "contracted_p1": _default_value(p1, 10.0 if es_3 else 2.3),
            "contracted_p2": _default_value(p2_dummy_or_real, 8.0) if es_3 else _default_value(p3, 2.3),
            "contracted_p3": _default_value(p3, 7.0) if es_3 else None,
            "contracted_p4": _default_value(p4_dummy_or_real, 7.0) if es_3 else None,
            "contracted_p5": _default_value(p5_dummy_or_real, 5.0) if es_3 else None,
            "contracted_p6": _default_value(p6_dummy_or_real, 5.0) if es_3 else None,
            "umbral_kw": _default_value(umbral, 2.0),
            "meses_filtro": [selected_month] if selected_month else [],
            "years_filtro": selected_years or [],
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
