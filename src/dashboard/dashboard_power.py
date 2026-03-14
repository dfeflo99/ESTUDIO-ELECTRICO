# =============================================================================
# src/dashboard/dashboard_power.py
# Dashboard interactivo de potencia con Dash
# Version: 2.0 — boton de descarga PDF con parametros actuales
# =============================================================================

import dash
from dash import dcc, html, Input, Output, State
import dash_bootstrap_components as dbc
import tempfile
import os

import sys
sys.path.append('../..')
from src.models.internal_data_model import ElectricityAnalysis
from src.analysis.power_engine import run_power_analysis
from src.analysis.charts.power_charts import (
    chart_power_kpis, chart_daily_max_power, chart_heatmap,
    chart_power_ranking, chart_profile_interpretation, chart_monthly_official_peaks,
)
from src.reports.report_generator import generate_report

COLORS = {
    'primary': '#2563EB', 'background': '#F0F4FF', 'card': '#FFFFFF',
    'text': '#1E293B', 'text_light': '#64748B', 'border': '#E2E8F0',
}
CARD_STYLE = {
    'backgroundColor': COLORS['card'], 'borderRadius': '12px', 'padding': '20px',
    'marginBottom': '20px', 'boxShadow': '0 1px 4px rgba(0,0,0,0.08)',
    'border': f"1px solid {COLORS['border']}",
}
TITLE_STYLE = {
    'color': COLORS['primary'], 'fontFamily': 'Segoe UI, Arial, sans-serif',
    'fontWeight': '700', 'fontSize': '24px', 'margin': '0',
}
SUBTITLE_STYLE = {
    'color': COLORS['text_light'], 'fontFamily': 'Segoe UI, Arial, sans-serif',
    'fontSize': '14px', 'marginTop': '4px',
}
SECTION_TITLE_STYLE = {
    'color': COLORS['text'], 'fontFamily': 'Segoe UI, Arial, sans-serif',
    'fontWeight': '600', 'fontSize': '16px', 'marginBottom': '12px',
    'borderLeft': f"4px solid {COLORS['primary']}", 'paddingLeft': '10px',
}
FILTER_LABEL_STYLE = {
    'color': COLORS['text'], 'fontFamily': 'Segoe UI, Arial, sans-serif',
    'fontWeight': '600', 'fontSize': '13px', 'marginBottom': '8px',
}
BTN_PDF_STYLE = {
    'backgroundColor': '#CC1F1F', 'color': 'white', 'border': 'none',
    'padding': '12px 32px', 'borderRadius': '8px', 'fontSize': '14px',
    'fontFamily': 'Segoe UI, Arial, sans-serif', 'fontWeight': '600', 'cursor': 'pointer',
}
MESES_ORDEN = [
    'enero', 'febrero', 'marzo', 'abril', 'mayo', 'junio',
    'julio', 'agosto', 'septiembre', 'octubre', 'noviembre', 'diciembre'
]
POTENCIAS_COMERCIALES = [2.3, 3.45, 4.6, 5.75, 6.9, 8.05, 9.2, 10.35, 11.5, 14.49]


def build_power_layout(analysis, contracted_p1=2.3, contracted_p2=2.3, umbral_inicial=2.0):
    meses_disponibles = sorted(
        {r.month_name for r in analysis.hourly_records},
        key=lambda m: MESES_ORDEN.index(m) if m in MESES_ORDEN else 99
    )
    opciones_meses = [{'label': m.capitalize(), 'value': m} for m in meses_disponibles]
    opciones_pot   = [{'label': str(p), 'value': p} for p in POTENCIAS_COMERCIALES]

    return html.Div(
        style={'backgroundColor': COLORS['background'], 'minHeight': '100vh', 'padding': '24px'},
        children=[

            # Cabecera
            html.Div(style={**CARD_STYLE, 'display': 'flex', 'justifyContent': 'space-between', 'alignItems': 'center'},
                children=[html.Div([
                    html.H1('Perfil de Potencia Real', style=TITLE_STYLE),
                    html.P('Analisis de potencia electrica — Tarifa 2.0TD', style=SUBTITLE_STYLE),
                ])]
            ),

            # Panel de controles
            html.Div(style=CARD_STYLE, children=[
                html.P('Controles del analisis', style=FILTER_LABEL_STYLE),
                html.Div(style={'display': 'grid', 'gridTemplateColumns': '2fr 1fr 1fr 1fr', 'gap': '24px', 'alignItems': 'start'},
                    children=[
                        html.Div([
                            html.P('Filtrar dia a dia y heatmap por mes:', style=FILTER_LABEL_STYLE),
                            html.P('Sin seleccion = año completo.', style={**SUBTITLE_STYLE, 'marginBottom': '8px'}),
                            dcc.Checklist(
                                id='power-filtro-meses', options=opciones_meses, value=[], inline=True,
                                style={'fontFamily': 'Segoe UI, Arial', 'fontSize': '13px'},
                                labelStyle={'marginRight': '12px', 'marginBottom': '6px', 'cursor': 'pointer'},
                                inputStyle={'marginRight': '5px', 'accentColor': COLORS['primary']}
                            ),
                        ]),
                        html.Div([
                            html.P('Umbral de analisis (kW):', style=FILTER_LABEL_STYLE),
                            html.P('Afecta a horas y % sobre umbral.', style={**SUBTITLE_STYLE, 'marginBottom': '8px'}),
                            dcc.Slider(
                                id='power-umbral-slider', min=0.5, max=6.0, step=0.1, value=umbral_inicial,
                                marks={0.5: '0.5', 1.0: '1.0', 2.0: '2.0', 3.0: '3.0', 4.0: '4.0', 6.0: '6.0'},
                                tooltip={'placement': 'bottom', 'always_visible': True}
                            ),
                        ]),
                        html.Div([
                            html.P('Potencia contratada P1 (kW):', style=FILTER_LABEL_STYLE),
                            dcc.Dropdown(id='power-p1-input', options=opciones_pot, value=contracted_p1, clearable=False,
                                         style={'fontFamily': 'Segoe UI, Arial', 'fontSize': '14px'}),
                        ]),
                        html.Div([
                            html.P('Potencia contratada P2 (kW):', style=FILTER_LABEL_STYLE),
                            dcc.Dropdown(id='power-p2-input', options=opciones_pot, value=contracted_p2, clearable=False,
                                         style={'fontFamily': 'Segoe UI, Arial', 'fontSize': '14px'}),
                        ]),
                    ]
                ),
            ]),

            # KPIs
            html.Div(style=CARD_STYLE, children=[
                html.P('Resumen de potencia', style=SECTION_TITLE_STYLE),
                dcc.Graph(id='power-graph-kpis', config={'displayModeBar': False}),
            ]),

            # Fila 1: Dia a dia + Heatmap
            html.Div(style={'display': 'grid', 'gridTemplateColumns': '1fr 1fr', 'gap': '20px', 'marginBottom': '20px'},
                children=[
                    html.Div(style=CARD_STYLE, children=[
                        html.P('Potencia Maxima Dia a Dia', style=SECTION_TITLE_STYLE),
                        html.P('Filtrable por mes', style={**SUBTITLE_STYLE, 'marginBottom': '8px'}),
                        dcc.Graph(id='power-graph-daily', config={'displayModeBar': True}),
                    ]),
                    html.Div(style=CARD_STYLE, children=[
                        html.P('Mapa de Calor: Hora x Dia del Mes', style=SECTION_TITLE_STYLE),
                        html.P('Filtrable por mes', style={**SUBTITLE_STYLE, 'marginBottom': '8px'}),
                        dcc.Graph(id='power-graph-heatmap', config={'displayModeBar': True}),
                    ]),
                ]
            ),

            # Fila 2: Ranking + Perfil
            html.Div(style={'display': 'grid', 'gridTemplateColumns': '3fr 2fr', 'gap': '20px', 'marginBottom': '20px'},
                children=[
                    html.Div(style=CARD_STYLE, children=[
                        html.P('Curva de Ranking de Potencia', style=SECTION_TITLE_STYLE),
                        dcc.Graph(id='power-graph-ranking', config={'displayModeBar': False}),
                    ]),
                    html.Div(style=CARD_STYLE, children=[
                        html.P('Interpretacion del Perfil', style=SECTION_TITLE_STYLE),
                        dcc.Graph(id='power-graph-profile', config={'displayModeBar': False}),
                    ]),
                ]
            ),

            # Evolucion mensual oficial
            html.Div(style=CARD_STYLE, children=[
                html.P('Pico Oficial Mensual por Periodo (CSV Distribuidora)', style=SECTION_TITLE_STYLE),
                dcc.Graph(id='power-graph-monthly', config={'displayModeBar': False}),
            ]),

            # Nota metodologica
            html.Div(style={**CARD_STYLE, 'backgroundColor': '#EFF6FF', 'borderLeft': f"4px solid {COLORS['primary']}"},
                children=[
                    html.P('Nota sobre la metodologia:', style=FILTER_LABEL_STYLE),
                    html.P(
                        analysis.power_analysis.nota_metodologia if analysis.power_analysis else '',
                        style={**SUBTITLE_STYLE, 'color': COLORS['text']}
                    )
                ]
            ),

            # Boton descarga PDF
            html.Div(style={**CARD_STYLE, 'textAlign': 'center', 'padding': '24px'}, children=[
                html.P('Descarga el informe PDF con el estado actual del analisis.',
                       style={**SUBTITLE_STYLE, 'marginBottom': '16px'}),
                html.Button('Descargar Informe PDF', id='power-btn-download-pdf', style=BTN_PDF_STYLE),
                dcc.Download(id='power-download-pdf'),
            ]),

        ]
    )


def run_power_dashboard(analysis: ElectricityAnalysis, port: int = 8051):
    _analysis_global = analysis

    app = dash.Dash(__name__, external_stylesheets=[dbc.themes.BOOTSTRAP], title='Estudio Electrico — Potencia')

    p1_inicial = analysis.power_analysis.contracted_powers.p1 if analysis.power_analysis else 2.3
    p2_inicial = analysis.power_analysis.contracted_powers.p2 if analysis.power_analysis else 2.3
    umbral_ini = analysis.power_analysis.umbral_kw if analysis.power_analysis else 2.0

    app.layout = build_power_layout(analysis, p1_inicial, p2_inicial, umbral_ini)

    @app.callback(
        Output('power-graph-kpis', 'figure'), Output('power-graph-daily', 'figure'),
        Output('power-graph-heatmap', 'figure'), Output('power-graph-ranking', 'figure'),
        Output('power-graph-profile', 'figure'), Output('power-graph-monthly', 'figure'),
        Input('power-filtro-meses', 'value'), Input('power-umbral-slider', 'value'),
        Input('power-p1-input', 'value'), Input('power-p2-input', 'value'),
    )
    def update_power_charts(meses, umbral_kw, p1, p2):
        an = run_power_analysis(
            _analysis_global,
            contracted_p1=float(p1) if p1 else 2.3,
            contracted_p2=float(p2) if p2 else 2.3,
            umbral_kw=float(umbral_kw) if umbral_kw else 2.0,
        )
        pw   = an.power_analysis
        mf   = meses if meses else None
        return (
            chart_power_kpis(pw),
            chart_daily_max_power(pw, mf),
            chart_heatmap(pw, mf, _analysis_global.hourly_records),
            chart_power_ranking(pw),
            chart_profile_interpretation(pw),
            chart_monthly_official_peaks(pw),
        )

    @app.callback(
        Output('power-download-pdf', 'data'),
        Input('power-btn-download-pdf', 'n_clicks'),
        State('power-filtro-meses', 'value'),
        State('power-umbral-slider', 'value'),
        State('power-p1-input', 'value'),
        State('power-p2-input', 'value'),
        prevent_initial_call=True
    )
    def download_pdf(n_clicks, meses, umbral_kw, p1, p2):
        params = {
            'contracted_p1':         float(p1) if p1 else 2.3,
            'contracted_p2':         float(p2) if p2 else 2.3,
            'umbral_kw':             float(umbral_kw) if umbral_kw else 2.0,
            'meses_filtro_potencia': meses or [],
            'meses_filtro':          [],
        }
        with tempfile.NamedTemporaryFile(suffix='.pdf', delete=False) as tmp:
            tmp_path = tmp.name
        generate_report(_analysis_global, tmp_path, logo_path=None, params=params)
        with open(tmp_path, 'rb') as f:
            pdf_bytes = f.read()
        os.unlink(tmp_path)
        return dcc.send_bytes(pdf_bytes, 'informe_f2energy.pdf')

    print(f"Dashboard de potencia lanzado en http://localhost:{port}")
    app.run(debug=False, port=port)
