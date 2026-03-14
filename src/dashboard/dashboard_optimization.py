# =============================================================================
# src/dashboard/dashboard_optimization.py
# Dashboard interactivo de optimizacion de potencia con Dash
# Version: 1.0
#
# Pagina 4: Optimizacion de potencia contratada
#
# Controles interactivos:
#   - Dropdowns P1 y P2 -> actualiza todos los graficos
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
    chart_exceedance_curve,
    chart_options_table_p1,
    chart_options_table_p2,
)


# =============================================================================
# ESTILOS
# =============================================================================

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


# =============================================================================
# LAYOUT
# =============================================================================

def build_optimization_layout(analysis: ElectricityAnalysis,
                               contracted_p1: float = 2.3,
                               contracted_p2: float = 2.3) -> html.Div:

    opciones_potencias = [
        {'label': f"{p} kW", 'value': p}
        for p in POTENCIAS_COMERCIALES
    ]

    return html.Div(
        style={'backgroundColor': COLORS['background'],
               'minHeight': '100vh', 'padding': '24px'},
        children=[

            # --- CABECERA ---
            html.Div(
                style={**CARD_STYLE, 'display': 'flex',
                       'justifyContent': 'space-between',
                       'alignItems': 'center'},
                children=[
                    html.Div([
                        html.H1('Optimizacion de Potencia Contratada',
                                style=TITLE_STYLE),
                        html.P(
                            'Analisis tecnico para encontrar la potencia optima. '
                            'Sin calculos economicos — el estudio de costes se realiza '
                            'en el apartado de factura.',
                            style=SUBTITLE_STYLE
                        ),
                    ]),
                ]
            ),

            # --- CONTROLES ---
            html.Div(
                style=CARD_STYLE,
                children=[
                    html.P('Ajusta la potencia contratada para simular:',
                           style=FILTER_LABEL_STYLE),
                    html.P(
                        'Cambia P1 y P2 para ver cuantas horas superarias '
                        'cada nivel de potencia. La curva y las tablas se '
                        'actualizan automaticamente.',
                        style={**SUBTITLE_STYLE, 'marginBottom': '16px'}
                    ),
                    html.Div(
                        style={'display': 'grid',
                               'gridTemplateColumns': '1fr 1fr',
                               'gap': '24px'},
                        children=[
                            html.Div([
                                html.P('Potencia contratada P1 (kW):',
                                       style=FILTER_LABEL_STYLE),
                                html.P('Periodo laboral 8h-24h',
                                       style={**SUBTITLE_STYLE, 'marginBottom': '8px'}),
                                dcc.Dropdown(
                                    id        = 'opt-p1-dropdown',
                                    options   = opciones_potencias,
                                    value     = contracted_p1,
                                    clearable = False,
                                    style     = {'fontFamily': 'Segoe UI, Arial',
                                                 'fontSize': '14px'}
                                ),
                            ]),
                            html.Div([
                                html.P('Potencia contratada P2 (kW):',
                                       style=FILTER_LABEL_STYLE),
                                html.P('Periodo nocturno y fines de semana',
                                       style={**SUBTITLE_STYLE, 'marginBottom': '8px'}),
                                dcc.Dropdown(
                                    id        = 'opt-p2-dropdown',
                                    options   = opciones_potencias,
                                    value     = contracted_p2,
                                    clearable = False,
                                    style     = {'fontFamily': 'Segoe UI, Arial',
                                                 'fontSize': '14px'}
                                ),
                            ]),
                        ]
                    ),
                ]
            ),

            # --- KPIs ---
            html.Div(
                style=CARD_STYLE,
                children=[
                    html.P('Resumen de optimizacion', style=SECTION_TITLE_STYLE),
                    dcc.Graph(id='opt-graph-kpis',
                              config={'displayModeBar': False}),
                ]
            ),

            # --- CURVA DE HORAS SUPERADAS ---
            html.Div(
                style=CARD_STYLE,
                children=[
                    html.P('Curva de Horas de Exceso por Nivel de Potencia',
                           style=SECTION_TITLE_STYLE),
                    html.P(
                        'Cada punto muestra cuantas horas al ano superarias '
                        'si contratases esa potencia. El punto optimo equilibra '
                        'seguridad y coste.',
                        style={**SUBTITLE_STYLE, 'marginBottom': '12px'}
                    ),
                    dcc.Graph(id='opt-graph-curva',
                              config={'displayModeBar': False}),
                ]
            ),

            # --- TABLAS COMPARATIVAS ---
            html.Div(
                style={'display': 'grid',
                       'gridTemplateColumns': '1fr 1fr',
                       'gap': '20px',
                       'marginBottom': '20px'},
                children=[
                    html.Div(style=CARD_STYLE, children=[
                        html.P('Opciones disponibles — P1 (Punta)',
                               style=SECTION_TITLE_STYLE),
                        html.P(
                            'Rojo = opcion actual | Verde = opcion recomendada',
                            style={**SUBTITLE_STYLE, 'marginBottom': '8px'}
                        ),
                        dcc.Graph(id='opt-graph-tabla-p1',
                                  config={'displayModeBar': False}),
                    ]),
                    html.Div(style=CARD_STYLE, children=[
                        html.P('Opciones disponibles — P2 (Valle)',
                               style=SECTION_TITLE_STYLE),
                        html.P(
                            'Rojo = opcion actual | Verde = opcion recomendada',
                            style={**SUBTITLE_STYLE, 'marginBottom': '8px'}
                        ),
                        dcc.Graph(id='opt-graph-tabla-p2',
                                  config={'displayModeBar': False}),
                    ]),
                ]
            ),

        ]
    )


# =============================================================================
# FUNCION PRINCIPAL
# =============================================================================

def run_optimization_dashboard(analysis: ElectricityAnalysis,
                                contracted_p1: float = 2.3,
                                contracted_p2: float = 2.3,
                                port: int = 8053):
    """
    Lanza el dashboard interactivo de optimizacion de potencia.

    Args:
        analysis:      ElectricityAnalysis con datos validados
        contracted_p1: Potencia contratada P1 inicial
        contracted_p2: Potencia contratada P2 inicial
        port:          Puerto (default: 8053)
    """
    _analysis_global = analysis

    app = dash.Dash(
        __name__,
        external_stylesheets=[dbc.themes.BOOTSTRAP],
        title='Estudio Electrico — Optimizacion'
    )

    app.layout = build_optimization_layout(
        analysis, contracted_p1, contracted_p2
    )

    # ----------------------------------------------------------------
    # CALLBACK PRINCIPAL
    # ----------------------------------------------------------------

    @app.callback(
        Output('opt-graph-kpis',     'figure'),
        Output('opt-graph-curva',    'figure'),
        Output('opt-graph-tabla-p1', 'figure'),
        Output('opt-graph-tabla-p2', 'figure'),
        Input('opt-p1-dropdown',     'value'),
        Input('opt-p2-dropdown',     'value'),
    )
    def update_optimization_charts(p1, p2):
        data = run_optimization_analysis(
            _analysis_global,
            contracted_p1 = float(p1) if p1 else 2.3,
            contracted_p2 = float(p2) if p2 else 2.3,
        )
        return (
            chart_optimization_kpis(data),
            chart_exceedance_curve(data),
            chart_options_table_p1(data),
            chart_options_table_p2(data),
        )

    print(f"Dashboard de optimizacion lanzado en http://localhost:{port}")
    app.run(debug=False, port=port)
