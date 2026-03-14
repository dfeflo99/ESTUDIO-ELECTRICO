# =============================================================================
# src/dashboard/dashboard_peaks.py
# Dashboard interactivo de picos criticos con Dash
# Version: 1.0
#
# Pagina 3: Analisis de picos criticos
#
# Controles interactivos:
#   - Slider de umbral -> actualiza todos los graficos y tablas
# =============================================================================

import dash
from dash import dcc, html, Input, Output
import dash_bootstrap_components as dbc

import sys
sys.path.append('../..')
from src.models.internal_data_model import ElectricityAnalysis
from src.analysis.peaks_engine import run_peaks_analysis
from src.analysis.charts.peaks_charts import (
    chart_peaks_kpis,
    chart_top10_table,
    chart_peaks_by_month,
    chart_peaks_by_hour,
    chart_peaks_heatmap,
    chart_peaks_day_type,
    chart_peaks_by_period,
)


# =============================================================================
# ESTILOS
# =============================================================================

COLORS = {
    'primary':    '#2563EB',
    'danger':     '#EF4444',
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
    'color':      COLORS['danger'],
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
    'borderLeft':   f"4px solid {COLORS['danger']}",
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

def build_peaks_layout(analysis: ElectricityAnalysis,
                        umbral_inicial: float = 2.0) -> html.Div:

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
                        html.H1('Analisis de Picos Criticos', style=TITLE_STYLE),
                        html.P('Identificacion y clasificacion de horas con consumo elevado',
                               style=SUBTITLE_STYLE),
                    ]),
                ]
            ),

            # --- CONTROL: SLIDER DE UMBRAL ---
            html.Div(
                style=CARD_STYLE,
                children=[
                    html.P('Umbral de analisis (kW):', style=FILTER_LABEL_STYLE),
                    html.P(
                        'Ajusta el umbral para ver que horas lo superan. '
                        'Todos los graficos y la tabla se actualizan automaticamente.',
                        style={**SUBTITLE_STYLE, 'marginBottom': '16px'}
                    ),
                    dcc.Slider(
                        id    = 'peaks-umbral-slider',
                        min   = 0.5,
                        max   = 6.0,
                        step  = 0.1,
                        value = umbral_inicial,
                        marks = {
                            0.5: '0.5 kW',
                            1.0: '1.0 kW',
                            2.0: '2.0 kW',
                            3.0: '3.0 kW',
                            4.0: '4.0 kW',
                            6.0: '6.0 kW',
                        },
                        tooltip = {'placement': 'bottom', 'always_visible': True}
                    ),
                ]
            ),

            # --- KPIs ---
            html.Div(
                style=CARD_STYLE,
                children=[
                    html.P('Resumen de picos', style=SECTION_TITLE_STYLE),
                    dcc.Graph(id='peaks-graph-kpis',
                              config={'displayModeBar': False}),
                ]
            ),

            # --- TOP 10 TABLA ---
            html.Div(
                style=CARD_STYLE,
                children=[
                    html.P('Top 10 Picos mas Altos', style=SECTION_TITLE_STYLE),
                    dcc.Graph(id='peaks-graph-top10',
                              config={'displayModeBar': False}),
                ]
            ),

            # --- FILA 1: Evolucion mensual + Por hora ---
            html.Div(
                style={'display': 'grid',
                       'gridTemplateColumns': '1fr 1fr',
                       'gap': '20px',
                       'marginBottom': '20px'},
                children=[
                    html.Div(style=CARD_STYLE, children=[
                        html.P('Evolucion Mensual de Picos',
                               style=SECTION_TITLE_STYLE),
                        dcc.Graph(id='peaks-graph-by-month',
                                  config={'displayModeBar': False}),
                    ]),
                    html.Div(style=CARD_STYLE, children=[
                        html.P('Distribucion por Hora del Dia',
                               style=SECTION_TITLE_STYLE),
                        dcc.Graph(id='peaks-graph-by-hour',
                                  config={'displayModeBar': False}),
                    ]),
                ]
            ),

            # --- MAPA DE CALOR ---
            html.Div(
                style=CARD_STYLE,
                children=[
                    html.P('Mapa de Calor: Picos por Mes y Hora',
                           style=SECTION_TITLE_STYLE),
                    dcc.Graph(id='peaks-graph-heatmap',
                              config={'displayModeBar': True}),
                ]
            ),

            # --- FILA 2: Laborable/Finde + Por periodo ---
            html.Div(
                style={'display': 'grid',
                       'gridTemplateColumns': '1fr 1fr',
                       'gap': '20px',
                       'marginBottom': '20px'},
                children=[
                    html.Div(style=CARD_STYLE, children=[
                        html.P('Picos: Laborable vs Fin de Semana',
                               style=SECTION_TITLE_STYLE),
                        dcc.Graph(id='peaks-graph-day-type',
                                  config={'displayModeBar': False}),
                    ]),
                    html.Div(style=CARD_STYLE, children=[
                        html.P('Picos por Periodo de Potencia',
                               style=SECTION_TITLE_STYLE),
                        dcc.Graph(id='peaks-graph-by-period',
                                  config={'displayModeBar': False}),
                    ]),
                ]
            ),

        ]
    )


# =============================================================================
# FUNCION PRINCIPAL
# =============================================================================

def run_peaks_dashboard(analysis: ElectricityAnalysis,
                         umbral_inicial: float = 2.0,
                         port: int = 8052):
    """
    Lanza el dashboard interactivo de picos criticos.

    Args:
        analysis:       ElectricityAnalysis con hourly_records validados
        umbral_inicial: Umbral inicial del slider (default: 2.0 kW)
        port:           Puerto (default: 8052)
    """
    _analysis_global = analysis

    app = dash.Dash(
        __name__,
        external_stylesheets=[dbc.themes.BOOTSTRAP],
        title='Estudio Electrico — Picos Criticos'
    )

    app.layout = build_peaks_layout(analysis, umbral_inicial)

    # ----------------------------------------------------------------
    # CALLBACK PRINCIPAL — slider de umbral actualiza todo
    # ----------------------------------------------------------------

    @app.callback(
        Output('peaks-graph-kpis',      'figure'),
        Output('peaks-graph-top10',     'figure'),
        Output('peaks-graph-by-month',  'figure'),
        Output('peaks-graph-by-hour',   'figure'),
        Output('peaks-graph-heatmap',   'figure'),
        Output('peaks-graph-day-type',  'figure'),
        Output('peaks-graph-by-period', 'figure'),
        Input('peaks-umbral-slider',    'value'),
    )
    def update_peaks_charts(umbral_kw):
        # Recalcular con el nuevo umbral
        data = run_peaks_analysis(
            _analysis_global,
            umbral_kw = float(umbral_kw) if umbral_kw else 2.0
        )

        return (
            chart_peaks_kpis(data),
            chart_top10_table(data),
            chart_peaks_by_month(data),
            chart_peaks_by_hour(data),
            chart_peaks_heatmap(data),
            chart_peaks_day_type(data),
            chart_peaks_by_period(data),
        )

    print(f"Dashboard de picos criticos lanzado en http://localhost:{port}")
    app.run(debug=False, port=port)
