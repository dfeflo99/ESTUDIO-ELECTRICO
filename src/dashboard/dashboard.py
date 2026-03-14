# =============================================================================
# src/dashboard/dashboard.py
# Dashboard interactivo de consumo con Dash
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
from src.analysis.consumption_engine import run_consumption_analysis
from src.analysis.charts.consumption_charts import (
    chart_kpis, chart_by_month, chart_by_hour, chart_by_day_of_week,
    chart_by_day_of_month, chart_by_hour_and_date, chart_by_period,
    chart_by_day_type, chart_by_season, chart_nocturno
)
from src.reports.report_generator import generate_report


COLORS = {
    'primary':    '#2563EB',
    'background': '#F0F4FF',
    'card':       '#FFFFFF',
    'text':       '#1E293B',
    'text_light': '#64748B',
    'border':     '#E2E8F0',
}

CARD_STYLE = {
    'backgroundColor': COLORS['card'],
    'borderRadius':    '12px',
    'padding':         '20px',
    'marginBottom':    '20px',
    'boxShadow':       '0 1px 4px rgba(0,0,0,0.08)',
    'border':          f"1px solid {COLORS['border']}",
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
    'fontFamily': 'Segoe UI, Arial, sans-serif', 'fontWeight': '600',
    'cursor': 'pointer',
}

MESES_ORDEN = [
    'enero', 'febrero', 'marzo', 'abril', 'mayo', 'junio',
    'julio', 'agosto', 'septiembre', 'octubre', 'noviembre', 'diciembre'
]


def filter_records_by_month(analysis, meses):
    import copy
    a = copy.copy(analysis)
    a.hourly_records = [r for r in analysis.hourly_records
                        if r.month_name in meses] if meses else analysis.hourly_records
    a.consumption_summary = None
    return a


def build_layout(analysis):
    meses_disponibles = sorted(
        {r.month_name for r in analysis.hourly_records},
        key=lambda m: MESES_ORDEN.index(m) if m in MESES_ORDEN else 99
    )
    opciones_meses = [{'label': m.capitalize(), 'value': m} for m in meses_disponibles]

    return html.Div(
        style={'backgroundColor': COLORS['background'], 'minHeight': '100vh', 'padding': '24px'},
        children=[

            # Cabecera
            html.Div(style={**CARD_STYLE, 'display': 'flex', 'justifyContent': 'space-between', 'alignItems': 'center'},
                children=[html.Div([
                    html.H1('Perfil de Consumo General', style=TITLE_STYLE),
                    html.P('Analisis de consumo electrico — Tarifa 2.0TD', style=SUBTITLE_STYLE),
                ])]
            ),

            # Filtro de meses
            html.Div(style=CARD_STYLE, children=[
                html.P('Filtrar por mes:', style=FILTER_LABEL_STYLE),
                html.P('Sin seleccion = año completo.', style={**SUBTITLE_STYLE, 'marginBottom': '12px'}),
                dcc.Checklist(
                    id='filtro-meses', options=opciones_meses, value=[], inline=True,
                    style={'fontFamily': 'Segoe UI, Arial', 'fontSize': '14px', 'color': COLORS['text']},
                    labelStyle={'marginRight': '16px', 'marginBottom': '8px', 'cursor': 'pointer'},
                    inputStyle={'marginRight': '6px', 'accentColor': COLORS['primary']}
                ),
            ]),

            # KPIs
            html.Div(style=CARD_STYLE, children=[
                html.P('Resumen', style=SECTION_TITLE_STYLE),
                dcc.Graph(id='graph-kpis', config={'displayModeBar': False}),
            ]),

            # Fila 1: Por mes + Por hora
            html.Div(style={'display': 'grid', 'gridTemplateColumns': '1fr 1fr', 'gap': '20px', 'marginBottom': '20px'},
                children=[
                    html.Div(style=CARD_STYLE, children=[
                        html.P('Consumo por Mes', style=SECTION_TITLE_STYLE),
                        dcc.Graph(id='graph-by-month', config={'displayModeBar': False}),
                    ]),
                    html.Div(style=CARD_STYLE, children=[
                        html.P('Promedio por Hora', style=SECTION_TITLE_STYLE),
                        dcc.Graph(id='graph-by-hour', config={'displayModeBar': False}),
                    ]),
                ]
            ),

            # Fila 2: Por dia semana + Por dia mes
            html.Div(style={'display': 'grid', 'gridTemplateColumns': '1fr 1fr', 'gap': '20px', 'marginBottom': '20px'},
                children=[
                    html.Div(style=CARD_STYLE, children=[
                        html.P('Consumo por Dia de la Semana', style=SECTION_TITLE_STYLE),
                        dcc.Graph(id='graph-by-dow', config={'displayModeBar': False}),
                    ]),
                    html.Div(style=CARD_STYLE, children=[
                        html.P('Promedio por Dia del Mes', style=SECTION_TITLE_STYLE),
                        dcc.Graph(id='graph-by-dom', config={'displayModeBar': False}),
                    ]),
                ]
            ),

            # Detalle horario
            html.Div(style=CARD_STYLE, children=[
                html.P('Consumo por Hora y Fecha', style=SECTION_TITLE_STYLE),
                dcc.Graph(id='graph-by-hour-date', config={'displayModeBar': True}),
            ]),

            # Fila 4: Periodos + Laborable + Nocturno
            html.Div(style={'display': 'grid', 'gridTemplateColumns': '1fr 1fr 1fr', 'gap': '20px', 'marginBottom': '20px'},
                children=[
                    html.Div(style=CARD_STYLE, children=[
                        html.P('Por Periodo P1/P2/P3', style=SECTION_TITLE_STYLE),
                        dcc.Graph(id='graph-by-period', config={'displayModeBar': False}),
                    ]),
                    html.Div(style=CARD_STYLE, children=[
                        html.P('Laborable vs Fin de Semana', style=SECTION_TITLE_STYLE),
                        dcc.Graph(id='graph-by-day-type', config={'displayModeBar': False}),
                    ]),
                    html.Div(style=CARD_STYLE, children=[
                        html.P('Nocturno vs Diurno', style=SECTION_TITLE_STYLE),
                        dcc.Graph(id='graph-nocturno', config={'displayModeBar': False}),
                    ]),
                ]
            ),

            # Temporada
            html.Div(style=CARD_STYLE, children=[
                html.P('Consumo por Temporada', style=SECTION_TITLE_STYLE),
                dcc.Graph(id='graph-by-season', config={'displayModeBar': False}),
            ]),

            # Boton descarga PDF
            html.Div(style={**CARD_STYLE, 'textAlign': 'center', 'padding': '24px'}, children=[
                html.P('Descarga el informe PDF con el estado actual del analisis.',
                       style={**SUBTITLE_STYLE, 'marginBottom': '16px'}),
                html.Button('Descargar Informe PDF', id='btn-download-pdf', style=BTN_PDF_STYLE),
                dcc.Download(id='download-pdf'),
            ]),

        ]
    )


def run_dashboard(analysis: ElectricityAnalysis, port: int = 8050):
    _analysis_global = analysis

    app = dash.Dash(__name__, external_stylesheets=[dbc.themes.BOOTSTRAP], title='Estudio Electrico')
    app.layout = build_layout(analysis)

    # Callback principal — actualiza graficos
    @app.callback(
        Output('graph-kpis', 'figure'), Output('graph-by-month', 'figure'),
        Output('graph-by-hour', 'figure'), Output('graph-by-dow', 'figure'),
        Output('graph-by-dom', 'figure'), Output('graph-by-hour-date', 'figure'),
        Output('graph-by-period', 'figure'), Output('graph-by-day-type', 'figure'),
        Output('graph-nocturno', 'figure'), Output('graph-by-season', 'figure'),
        Input('filtro-meses', 'value')
    )
    def update_all_charts(meses_seleccionados):
        af = filter_records_by_month(_analysis_global, meses_seleccionados)
        af = run_consumption_analysis(af)
        s  = af.consumption_summary
        return (
            chart_kpis(s), chart_by_month(s), chart_by_hour(s),
            chart_by_day_of_week(s), chart_by_day_of_month(s),
            chart_by_hour_and_date(s), chart_by_period(s),
            chart_by_day_type(s), chart_nocturno(s), chart_by_season(s),
        )

    # Callback descarga PDF
    @app.callback(
        Output('download-pdf', 'data'),
        Input('btn-download-pdf', 'n_clicks'),
        State('filtro-meses', 'value'),
        prevent_initial_call=True
    )
    def download_pdf(n_clicks, meses_seleccionados):
        p  = _analysis_global.power_analysis
        params = {
            'contracted_p1':  p.contracted_powers.p1 if p else 2.3,
            'contracted_p2':  p.contracted_powers.p2 if p else 2.3,
            'umbral_kw':      p.umbral_kw if p else 2.0,
            'meses_filtro':   meses_seleccionados or [],
        }
        with tempfile.NamedTemporaryFile(suffix='.pdf', delete=False) as tmp:
            tmp_path = tmp.name
        generate_report(_analysis_global, tmp_path, logo_path=None, params=params)
        with open(tmp_path, 'rb') as f:
            pdf_bytes = f.read()
        os.unlink(tmp_path)
        return dcc.send_bytes(pdf_bytes, 'informe_f2energy.pdf')

    print(f"Dashboard lanzado en http://localhost:{port}")
    app.run(debug=False, port=port)
