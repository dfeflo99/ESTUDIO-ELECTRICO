# =============================================================================
# src/dashboard/dashboard_power.py
# Dashboard interactivo de potencia con Dash
# Version: 1.0
#
# Pagina 2: Perfil de potencia real
#
# Controles interactivos:
#   - Filtro de meses     -> afecta daily_max y heatmap
#   - Slider de umbral    -> afecta KPIs de horas y % sobre umbral
#   - Inputs P1 y P2      -> afecta KPIs, daily_max y recomendacion
# =============================================================================

import dash
from dash import dcc, html, Input, Output
import dash_bootstrap_components as dbc

import sys
sys.path.append('../..')
from src.models.internal_data_model import ElectricityAnalysis
from src.analysis.power_engine import run_power_analysis
from src.analysis.charts.power_charts import (
    chart_power_kpis,
    chart_daily_max_power,
    chart_heatmap,
    chart_power_ranking,
    chart_profile_interpretation,
    chart_monthly_official_peaks,
)


# =============================================================================
# ESTILOS
# =============================================================================

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
    'color':      COLORS['primary'],
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
    'borderLeft':   f"4px solid {COLORS['primary']}",
    'paddingLeft':  '10px',
}

FILTER_LABEL_STYLE = {
    'color':        COLORS['text'],
    'fontFamily':   'Segoe UI, Arial, sans-serif',
    'fontWeight':   '600',
    'fontSize':     '13px',
    'marginBottom': '8px',
}

INPUT_STYLE = {
    'width':        '100px',
    'padding':      '6px 10px',
    'borderRadius': '6px',
    'border':       f"1px solid {COLORS['border']}",
    'fontFamily':   'Segoe UI, Arial, sans-serif',
    'fontSize':     '14px',
    'color':        COLORS['text'],
}

# Orden de meses
MESES_ORDEN = [
    'enero', 'febrero', 'marzo', 'abril', 'mayo', 'junio',
    'julio', 'agosto', 'septiembre', 'octubre', 'noviembre', 'diciembre'
]

# Potencias comerciales disponibles 2.0TD
POTENCIAS_COMERCIALES = [2.3, 3.45, 4.6, 5.75, 6.9, 8.05, 9.2, 10.35, 11.5, 14.49]


# =============================================================================
# LAYOUT
# =============================================================================

def build_power_layout(analysis: ElectricityAnalysis) -> html.Div:

    # Meses disponibles en los datos
    meses_disponibles = sorted(
        {r.month_name for r in analysis.hourly_records},
        key=lambda m: MESES_ORDEN.index(m) if m in MESES_ORDEN else 99
    )
    opciones_meses = [
        {'label': m.capitalize(), 'value': m}
        for m in meses_disponibles
    ]

    # Potencia contratada inicial
    p1_inicial = analysis.power_analysis.contracted_powers.p1 if analysis.power_analysis else 2.3
    p2_inicial = analysis.power_analysis.contracted_powers.p2 if analysis.power_analysis else 2.3
    umbral_inicial = analysis.power_analysis.umbral_kw if analysis.power_analysis else 2.0

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
                        html.H1('Perfil de Potencia Real', style=TITLE_STYLE),
                        html.P('Analisis de potencia electrica — Tarifa 2.0TD',
                               style=SUBTITLE_STYLE),
                    ]),
                ]
            ),

            # --- PANEL DE CONTROLES ---
            html.Div(
                style=CARD_STYLE,
                children=[
                    html.P('Controles del analisis', style=SECTION_TITLE_STYLE),

                    # Fila de controles
                    html.Div(
                        style={'display': 'grid',
                               'gridTemplateColumns': '2fr 1fr 1fr 1fr',
                               'gap': '24px',
                               'alignItems': 'start'},
                        children=[

                            # Filtro de meses
                            html.Div([
                                html.P('Filtrar graficos de dia a dia y heatmap por mes:',
                                       style=FILTER_LABEL_STYLE),
                                html.P(
                                    'Sin seleccion = año completo.',
                                    style={**SUBTITLE_STYLE, 'marginBottom': '8px'}
                                ),
                                dcc.Checklist(
                                    id      = 'power-filtro-meses',
                                    options = opciones_meses,
                                    value   = [],
                                    inline  = True,
                                    style   = {'fontFamily': 'Segoe UI, Arial',
                                               'fontSize': '13px'},
                                    labelStyle = {'marginRight': '12px',
                                                  'marginBottom': '6px',
                                                  'cursor': 'pointer'},
                                    inputStyle = {'marginRight': '5px',
                                                  'accentColor': COLORS['primary']}
                                ),
                            ]),

                            # Slider umbral
                            html.Div([
                                html.P('Umbral de analisis (kW):',
                                       style=FILTER_LABEL_STYLE),
                                html.P(
                                    'Afecta a horas y % sobre umbral.',
                                    style={**SUBTITLE_STYLE, 'marginBottom': '8px'}
                                ),
                                dcc.Slider(
                                    id    = 'power-umbral-slider',
                                    min   = 0.5,
                                    max   = 6.0,
                                    step  = 0.1,
                                    value = umbral_inicial,
                                    marks = {
                                        0.5: '0.5',
                                        1.0: '1.0',
                                        2.0: '2.0',
                                        3.0: '3.0',
                                        4.0: '4.0',
                                        6.0: '6.0',
                                    },
                                    tooltip = {'placement': 'bottom',
                                               'always_visible': True}
                                ),
                            ]),

                            # Input P1
                            html.Div([
                                html.P('Potencia contratada P1 (kW):',
                                       style=FILTER_LABEL_STYLE),
                                html.P('Afecta a KPIs y grafico dia a dia.',
                                       style={**SUBTITLE_STYLE, 'marginBottom': '8px'}),
                                dcc.Dropdown(
                                    id      = 'power-p1-input',
                                    options = [{'label': str(p), 'value': p}
                                               for p in POTENCIAS_COMERCIALES],
                                    value   = p1_inicial,
                                    clearable = False,
                                    style   = {'fontFamily': 'Segoe UI, Arial',
                                               'fontSize': '14px'}
                                ),
                            ]),

                            # Input P2
                            html.Div([
                                html.P('Potencia contratada P2 (kW):',
                                       style=FILTER_LABEL_STYLE),
                                html.P('Afecta a KPIs y grafico dia a dia.',
                                       style={**SUBTITLE_STYLE, 'marginBottom': '8px'}),
                                dcc.Dropdown(
                                    id      = 'power-p2-input',
                                    options = [{'label': str(p), 'value': p}
                                               for p in POTENCIAS_COMERCIALES],
                                    value   = p2_inicial,
                                    clearable = False,
                                    style   = {'fontFamily': 'Segoe UI, Arial',
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
                    html.P('Resumen de potencia', style=SECTION_TITLE_STYLE),
                    dcc.Graph(id='power-graph-kpis',
                              config={'displayModeBar': False}),
                ]
            ),

            # --- FILA 1: Dia a dia + Heatmap (filtrables) ---
            html.Div(
                style={'display': 'grid',
                       'gridTemplateColumns': '1fr 1fr',
                       'gap': '20px',
                       'marginBottom': '20px'},
                children=[
                    html.Div(style=CARD_STYLE, children=[
                        html.P('Potencia Maxima Dia a Dia',
                               style=SECTION_TITLE_STYLE),
                        html.P('Filtrable por mes',
                               style={**SUBTITLE_STYLE, 'marginBottom': '8px'}),
                        dcc.Graph(id='power-graph-daily',
                                  config={'displayModeBar': True}),
                    ]),
                    html.Div(style=CARD_STYLE, children=[
                        html.P('Mapa de Calor: Hora x Dia del Mes',
                               style=SECTION_TITLE_STYLE),
                        html.P('Filtrable por mes',
                               style={**SUBTITLE_STYLE, 'marginBottom': '8px'}),
                        dcc.Graph(id='power-graph-heatmap',
                                  config={'displayModeBar': True}),
                    ]),
                ]
            ),

            # --- FILA 2: Ranking + Perfil ---
            html.Div(
                style={'display': 'grid',
                       'gridTemplateColumns': '3fr 2fr',
                       'gap': '20px',
                       'marginBottom': '20px'},
                children=[
                    html.Div(style=CARD_STYLE, children=[
                        html.P('Curva de Ranking de Potencia',
                               style=SECTION_TITLE_STYLE),
                        dcc.Graph(id='power-graph-ranking',
                                  config={'displayModeBar': False}),
                    ]),
                    html.Div(style=CARD_STYLE, children=[
                        html.P('Interpretacion del Perfil',
                               style=SECTION_TITLE_STYLE),
                        dcc.Graph(id='power-graph-profile',
                                  config={'displayModeBar': False}),
                    ]),
                ]
            ),

            # --- FILA 3: Evolucion mensual oficial ---
            html.Div(
                style=CARD_STYLE,
                children=[
                    html.P('Pico Oficial Mensual por Periodo (CSV Distribuidora)',
                           style=SECTION_TITLE_STYLE),
                    html.P(
                        'Datos reales registrados por tu distribuidora. '
                        'El maximo real puede ser superior a la media horaria '
                        'mostrada en los graficos anteriores.',
                        style={**SUBTITLE_STYLE, 'marginBottom': '12px'}
                    ),
                    dcc.Graph(id='power-graph-monthly',
                              config={'displayModeBar': False}),
                ]
            ),

            # --- NOTA METODOLOGICA ---
            html.Div(
                style={**CARD_STYLE,
                       'backgroundColor': '#EFF6FF',
                       'borderLeft': f"4px solid {COLORS['primary']}"},
                children=[
                    html.P('Nota sobre la metodologia:', style=FILTER_LABEL_STYLE),
                    html.P(
                        analysis.power_analysis.nota_metodologia
                        if analysis.power_analysis else '',
                        style={**SUBTITLE_STYLE, 'color': COLORS['text']}
                    )
                ]
            ),

        ]
    )


# =============================================================================
# FUNCION PRINCIPAL
# =============================================================================

def run_power_dashboard(analysis: ElectricityAnalysis, port: int = 8051):
    """
    Lanza el dashboard interactivo de potencia.

    Args:
        analysis: ElectricityAnalysis con power_analysis ya calculado
        port:     Puerto (por defecto 8051 para no chocar con el de consumo)

    Uso en Colab:
        from src.dashboard.dashboard_power import run_power_dashboard
        run_power_dashboard(analysis)
    """

    _analysis_global = analysis

    app = dash.Dash(
        __name__,
        external_stylesheets=[dbc.themes.BOOTSTRAP],
        title='Estudio Electrico — Potencia'
    )

    app.layout = build_power_layout(analysis)

    # ----------------------------------------------------------------
    # CALLBACK PRINCIPAL
    # ----------------------------------------------------------------

    @app.callback(
        Output('power-graph-kpis',     'figure'),
        Output('power-graph-daily',    'figure'),
        Output('power-graph-heatmap',  'figure'),
        Output('power-graph-ranking',  'figure'),
        Output('power-graph-profile',  'figure'),
        Output('power-graph-monthly',  'figure'),
        Input('power-filtro-meses',    'value'),
        Input('power-umbral-slider',   'value'),
        Input('power-p1-input',        'value'),
        Input('power-p2-input',        'value'),
    )
    def update_power_charts(meses_seleccionados, umbral_kw, p1, p2):

        # Recalcular el motor con los nuevos parametros
        analysis_nuevo = run_power_analysis(
            _analysis_global,
            contracted_p1 = float(p1) if p1 else 2.3,
            contracted_p2 = float(p2) if p2 else 2.3,
            umbral_kw     = float(umbral_kw) if umbral_kw else 2.0,
        )
        power = analysis_nuevo.power_analysis

        # Filtro de meses solo para daily_max y heatmap
        meses = meses_seleccionados if meses_seleccionados else None

        return (
            chart_power_kpis(power),
            chart_daily_max_power(power, meses),
            chart_heatmap(power, meses),
            chart_power_ranking(power),
            chart_profile_interpretation(power),
            chart_monthly_official_peaks(power),
        )

    print(f"Dashboard de potencia lanzado en http://localhost:{port}")
    app.run(debug=False, port=port)
