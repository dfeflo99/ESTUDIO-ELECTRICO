# =============================================================================
# src/dashboard/dashboard_optimization.py
# Dashboard de optimizacion de potencia — Version 3.0
# =============================================================================

import dash
from dash import dcc, html, Input, Output
import dash_bootstrap_components as dbc

import sys
sys.path.append('../..')
from src.models.internal_data_model import ElectricityAnalysis
from src.analysis.optimization_engine import run_optimization_analysis, POTENCIAS_COMERCIALES
from src.analysis.charts.optimization_charts import (
    chart_optimization_kpis,
    chart_monthly_peaks,
    chart_exceso_table,
    chart_suggested_options,
)

COLORS = {
    'primary':    '#2563EB',
    'success':    '#10B981',
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
    'color':      COLORS['success'],
    'fontFamily': 'Segoe UI, Arial, sans-serif',
    'fontWeight': '700',
    'fontSize':   '24px',
    'margin':     '0',
}

SUBTITLE_STYLE = {
    'color':      COLORS['text_light'],
    'fontFamily': 'Segoe UI, Arial, sans-serif',
    'fontSize':   '14px',
    'marginTop':  '4px',
}

SECTION_TITLE_STYLE = {
    'color':        COLORS['text'],
    'fontFamily':   'Segoe UI, Arial, sans-serif',
    'fontWeight':   '600',
    'fontSize':     '16px',
    'marginBottom': '12px',
    'borderLeft':   f"4px solid {COLORS['success']}",
    'paddingLeft':  '10px',
}

FILTER_LABEL_STYLE = {
    'color':        COLORS['text'],
    'fontFamily':   'Segoe UI, Arial, sans-serif',
    'fontWeight':   '600',
    'fontSize':     '13px',
    'marginBottom': '8px',
}


def build_optimization_layout(analysis, contracted_p1=2.3, contracted_p2=2.3):
    opciones = [{'label': f"{p} kW", 'value': p} for p in POTENCIAS_COMERCIALES]

    return html.Div(
        style={'backgroundColor': COLORS['background'],
               'minHeight': '100vh', 'padding': '24px'},
        children=[

            # Cabecera
            html.Div(
                style={**CARD_STYLE, 'display': 'flex',
                       'justifyContent': 'space-between',
                       'alignItems': 'center'},
                children=[html.Div([
                    html.H1('Optimizacion de Potencia Contratada', style=TITLE_STYLE),
                    html.P(
                        'Analisis de picos reales vs potencia contratada. '
                        'Cambia la potencia actual para simular distintos escenarios.',
                        style=SUBTITLE_STYLE
                    ),
                ])]
            ),

            # Controles
            html.Div(style=CARD_STYLE, children=[
                html.P('Potencia contratada actual:', style=FILTER_LABEL_STYLE),
                html.Div(
                    style={'display': 'grid',
                           'gridTemplateColumns': '1fr 1fr',
                           'gap': '24px'},
                    children=[
                        html.Div([
                            html.P('P1 (kW) — Laborable 8h-24h:',
                                   style=FILTER_LABEL_STYLE),
                            dcc.Dropdown(
                                id='opt-p1-dropdown', options=opciones,
                                value=contracted_p1, clearable=False,
                                style={'fontFamily': 'Segoe UI, Arial', 'fontSize': '14px'}
                            ),
                        ]),
                        html.Div([
                            html.P('P2 (kW) — Nocturno / Finde:',
                                   style=FILTER_LABEL_STYLE),
                            dcc.Dropdown(
                                id='opt-p2-dropdown', options=opciones,
                                value=contracted_p2, clearable=False,
                                style={'fontFamily': 'Segoe UI, Arial', 'fontSize': '14px'}
                            ),
                        ]),
                    ]
                ),
            ]),

            # KPIs
            html.Div(style=CARD_STYLE, children=[
                html.P('Resumen', style=SECTION_TITLE_STYLE),
                dcc.Graph(id='opt-kpis', config={'displayModeBar': False}),
            ]),

            # Picos mensuales
            html.Div(style=CARD_STYLE, children=[
                html.P('Picos Mensuales vs Potencia Contratada',
                       style=SECTION_TITLE_STYLE),
                html.P(
                    'Rojo = mes que supera la potencia contratada. '
                    'Azul = dentro del limite.',
                    style={**SUBTITLE_STYLE, 'marginBottom': '12px'}
                ),
                dcc.Graph(id='opt-picos', config={'displayModeBar': False}),
            ]),

            # Tabla de excesos
            html.Div(style=CARD_STYLE, children=[
                html.P('Detalle de Meses con Exceso', style=SECTION_TITLE_STYLE),
                dcc.Graph(id='opt-excesos', config={'displayModeBar': False}),
            ]),

            # Opciones sugeridas
            html.Div(style=CARD_STYLE, children=[
                html.P('Opciones Sugeridas', style=SECTION_TITLE_STYLE),
                html.P(
                    'El sistema te presenta dos opciones. Tu decides segun '
                    'tu tolerancia al riesgo y lo que quieras pagar.',
                    style={**SUBTITLE_STYLE, 'marginBottom': '12px'}
                ),
                dcc.Graph(id='opt-opciones', config={'displayModeBar': False}),
            ]),

        ]
    )


def run_optimization_dashboard(analysis: ElectricityAnalysis,
                                contracted_p1: float = 2.3,
                                contracted_p2: float = 2.3,
                                port: int = 8053):

    _analysis_global = analysis

    app = dash.Dash(
        __name__,
        external_stylesheets=[dbc.themes.BOOTSTRAP],
        title='Estudio Electrico — Optimizacion'
    )

    app.layout = build_optimization_layout(analysis, contracted_p1, contracted_p2)

    @app.callback(
        Output('opt-kpis',    'figure'),
        Output('opt-picos',   'figure'),
        Output('opt-excesos', 'figure'),
        Output('opt-opciones','figure'),
        Input('opt-p1-dropdown', 'value'),
        Input('opt-p2-dropdown', 'value'),
    )
    def update_charts(p1, p2):
        data = run_optimization_analysis(
            _analysis_global,
            contracted_p1 = float(p1) if p1 else 2.3,
            contracted_p2 = float(p2) if p2 else 2.3,
        )
        return (
            chart_optimization_kpis(data),
            chart_monthly_peaks(data),
            chart_exceso_table(data),
            chart_suggested_options(data),
        )

    print(f"Dashboard de optimizacion lanzado en http://localhost:{port}")
    app.run(debug=False, port=port)
