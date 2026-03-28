# =============================================================================
# src/dashboard/dashboard_peaks.py
# Dashboard de analisis de picos
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
from src.analysis.peaks_engine import run_peaks_analysis
from src.analysis.charts.peaks_charts import generate_peaks_charts
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
    return sorted({r.timestamp.year for r in analysis.hourly_records})


def _extract_available_months(analysis: ElectricityAnalysis, selected_years=None):
    months = []
    for r in analysis.hourly_records:
        if selected_years and r.timestamp.year not in selected_years:
            continue
        months.append(r.timestamp.month)
    months = sorted(set(months))
    return [MONTH_NUM_TO_NAME[m] for m in months]


def _initial_umbral(analysis: ElectricityAnalysis, umbral_kw=None):
    if umbral_kw is not None:
        return umbral_kw
    if getattr(analysis, "peaks_analysis", None) is not None:
        pa = analysis.peaks_analysis
        if isinstance(pa, dict) and pa.get("umbral_kw") is not None:
            return pa["umbral_kw"]
    if getattr(analysis, "power_analysis", None) is not None:
        pw = analysis.power_analysis
        if getattr(pw, "umbral_kw", None) is not None:
            return pw.umbral_kw
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

def build_peaks_layout(
    analysis: ElectricityAnalysis,
    umbral_kw=None,
):
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
                        html.H1("Análisis de Picos", style=TITLE_STYLE),
                        html.P(
                            "Ajusta umbral, año y mes para ver cuándo se concentran los excesos horarios.",
                            style=SUBTITLE_STYLE
                        ),
                        html.Div(
                            "Los picos analizados aquí se basan en potencias medias de una hora calculadas a partir de la curva de consumo. No son picos instantáneos oficiales.",
                            style=INFO_BOX_STYLE
                        ),
                    ])
                ]
            ),

            html.Div(
                style=CARD_STYLE,
                children=[
                    html.Div(
                        style={"display": "grid", "gridTemplateColumns": "1fr 1fr 1fr", "gap": "24px"},
                        children=[
                            html.Div([
                                html.P("Umbral de análisis (kW)", style=FILTER_LABEL_STYLE),
                                dcc.Slider(
                                    id="pk-umbral-slider",
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
                                    id="pk-year-filter",
                                    options=[{"label": str(y), "value": y} for y in available_years],
                                    value=available_years,
                                    multi=True,
                                    placeholder="Todos los años",
                                ),
                            ]),
                            html.Div([
                                html.P("Filtrar por mes", style=FILTER_LABEL_STYLE),
                                dcc.Dropdown(
                                    id="pk-month-filter",
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
                dcc.Graph(id="pk-kpis", config={"displayModeBar": False}),
            ]),

            html.Div(style=CARD_STYLE, children=[
                html.P("Top 10 picos", style=SECTION_TITLE_STYLE),
                dcc.Graph(id="pk-top10", config={"displayModeBar": False}),
            ]),

            html.Div(style=CARD_STYLE, children=[
                html.P("Picos por mes", style=SECTION_TITLE_STYLE),
                dcc.Graph(id="pk-by-month", config={"displayModeBar": False}),
            ]),

            html.Div(style=CARD_STYLE, children=[
                html.P("Picos por hora", style=SECTION_TITLE_STYLE),
                dcc.Graph(id="pk-by-hour", config={"displayModeBar": False}),
            ]),

            html.Div(style=CARD_STYLE, children=[
                html.P("Heatmap mes × hora", style=SECTION_TITLE_STYLE),
                dcc.Graph(id="pk-heatmap", config={"displayModeBar": False}),
            ]),

            html.Div(style=CARD_STYLE, children=[
                html.P("Tipo de día", style=SECTION_TITLE_STYLE),
                dcc.Graph(id="pk-day-type", config={"displayModeBar": False}),
            ]),

            html.Div(style=CARD_STYLE, children=[
                html.P("Periodo de potencia", style=SECTION_TITLE_STYLE),
                dcc.Graph(id="pk-by-period", config={"displayModeBar": False}),
            ]),

            html.Div(style={**CARD_STYLE, "textAlign": "center", "padding": "24px"}, children=[
                html.P(
                    "Descarga el informe PDF con el estado actual del análisis.",
                    style={**SUBTITLE_STYLE, "marginBottom": "16px"}
                ),
                html.Button("Descargar Informe PDF", id="pk-btn-download-pdf", style=BTN_PDF_STYLE),
                dcc.Download(id="pk-download-pdf"),
            ]),
        ]
    )


# =============================================================================
# DASHBOARD
# =============================================================================

def run_peaks_dashboard(
    analysis: ElectricityAnalysis,
    umbral_kw: float = None,
    port: int = 8052,
):
    _analysis_global = analysis
    es_3 = _is_3_0(analysis)

    app = dash.Dash(
        __name__,
        external_stylesheets=[dbc.themes.BOOTSTRAP],
        title="Estudio Electrico — Picos"
    )

    app.layout = build_peaks_layout(analysis, umbral_kw)

    @app.callback(
        Output("pk-month-filter", "options"),
        Input("pk-year-filter", "value"),
    )
    def update_month_options(selected_years):
        months = _extract_available_months(_analysis_global, selected_years)
        return [{"label": m, "value": m} for m in months]

    @app.callback(
        Output("pk-kpis", "figure"),
        Output("pk-top10", "figure"),
        Output("pk-by-month", "figure"),
        Output("pk-by-hour", "figure"),
        Output("pk-heatmap", "figure"),
        Output("pk-day-type", "figure"),
        Output("pk-by-period", "figure"),
        Input("pk-umbral-slider", "value"),
        Input("pk-year-filter", "value"),
        Input("pk-month-filter", "value"),
    )
    def update_charts(umbral, selected_years, selected_month):
        filtered_analysis = _filter_analysis(
            _analysis_global,
            selected_years=selected_years or [],
            selected_month=selected_month,
        )

        if not filtered_analysis.hourly_records:
            empty = _message_figure("Sin datos", "No hay datos para los filtros seleccionados")
            return empty, empty, empty, empty, empty, empty, empty

        result = run_peaks_analysis(
            filtered_analysis,
            umbral_kw=_default_value(umbral, 2.0),
        )

        charts = generate_peaks_charts(result)

        return (
            charts["kpis"],
            charts["top10"],
            charts["by_month"],
            charts["by_hour"],
            charts["heatmap"],
            charts["day_type"],
            charts["by_period"],
        )

    @app.callback(
        Output("pk-download-pdf", "data"),
        Input("pk-btn-download-pdf", "n_clicks"),
        State("pk-umbral-slider", "value"),
        State("pk-year-filter", "value"),
        State("pk-month-filter", "value"),
        prevent_initial_call=True
    )
    def download_pdf(n_clicks, umbral, selected_years, selected_month):
        params = {
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
        return dcc.send_bytes(pdf_bytes, "informe_f2energy_picos.pdf")

    print(f"Dashboard de picos lanzado en http://localhost:{port}")
    app.run(debug=False, port=port)
