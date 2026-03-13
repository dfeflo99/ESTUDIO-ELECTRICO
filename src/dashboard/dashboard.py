# =============================================================================
# src/dashboard/dashboard.py
# Dashboard interactivo con Dash
# Version: 1.0
#
# Pagina 1: Perfil de consumo general
#
# Funcionalidad:
#   - Filtro de meses (segmentador) que actualiza todos los graficos
#   - Si no se selecciona ningun mes se muestran todos (ano completo)
#   - Todos los graficos de consumption_charts.py integrados
# =============================================================================

import dash
from dash import dcc, html, Input, Output, callback
import dash_bootstrap_components as dbc

import sys
sys.path.append('../..')
from src.models.internal_data_model import ElectricityAnalysis
from src.analysis.consumption_engine import run_consumption_analysis
from src.analysis.charts.consumption_charts import (
    chart_kpis,
    chart_by_month,
    chart_by_hour,
    chart_by_day_of_week,
    chart_by_day_of_month,
    chart_by_hour_and_date,
    chart_by_period,
    chart_by_day_type,
    chart_by_season,
    chart_nocturno
)


# =============================================================================
# COLORES Y ESTILOS
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

# Orden de los meses
MESES_ORDEN = [
    'enero', 'febrero', 'marzo', 'abril', 'mayo', 'junio',
    'julio', 'agosto', 'septiembre', 'octubre', 'noviembre', 'diciembre'
]


# =============================================================================
# FUNCION PARA FILTRAR REGISTROS POR MES
# =============================================================================

def filter_records_by_month(analysis: ElectricityAnalysis,
                             meses_seleccionados: list) -> ElectricityAnalysis:
    """
    Filtra los registros horarios por los meses seleccionados.
    Si no se selecciona ningun mes devuelve todos los registros.
    """
    import copy
    analysis_filtrado = copy.copy(analysis)

    if not meses_seleccionados:
        # Sin filtro -> todos los registros
        analysis_filtrado.hourly_records = analysis.hourly_records
    else:
        analysis_filtrado.hourly_records = [
            r for r in analysis.hourly_records
            if r.month_name in meses_seleccionados
        ]

    # Resetear el summary para que se recalcule
    analysis_filtrado.consumption_summary = None
    return analysis_filtrado


# =============================================================================
# FUNCION PARA CONSTRUIR EL LAYOUT
# =============================================================================

def build_layout(analysis: ElectricityAnalysis) -> html.Div:
    """
    Construye el layout completo del dashboard.
    """
    # Obtener los meses disponibles en los datos
    meses_disponibles = sorted(
        {r.month_name for r in analysis.hourly_records},
        key=lambda m: MESES_ORDEN.index(m) if m in MESES_ORDEN else 99
    )

    opciones_meses = [
        {'label': m.capitalize(), 'value': m}
        for m in meses_disponibles
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
                        html.H1('Perfil de Consumo General', style=TITLE_STYLE),
                        html.P('Analisis de consumo electrico — Tarifa 2.0TD',
                               style=SUBTITLE_STYLE),
                    ]),
                    html.Div([
                        html.P('Datos reales de tu vivienda',
                               style={**SUBTITLE_STYLE, 'textAlign': 'right'}),
                    ])
                ]
            ),

            # --- FILTRO DE MESES ---
            html.Div(
                style=CARD_STYLE,
                children=[
                    html.P('Filtrar por mes:', style=FILTER_LABEL_STYLE),
                    html.P(
                        'Selecciona uno o varios meses. '
                        'Si no seleccionas ninguno se muestra el año completo.',
                        style={**SUBTITLE_STYLE, 'marginBottom': '12px'}
                    ),
                    dcc.Checklist(
                        id      = 'filtro-meses',
                        options = opciones_meses,
                        value   = [],   # Por defecto sin filtro = año completo
                        inline  = True,
                        style   = {'fontFamily': 'Segoe UI, Arial, sans-serif',
                                   'fontSize': '14px', 'color': COLORS['text']},
                        labelStyle = {
                            'marginRight':    '16px',
                            'marginBottom':   '8px',
                            'cursor':         'pointer',
                        },
                        inputStyle = {
                            'marginRight':    '6px',
                            'accentColor':    COLORS['primary'],
                        }
                    ),
                ]
            ),

            # --- KPIs ---
            html.Div(
                style=CARD_STYLE,
                children=[
                    html.P('Resumen', style=SECTION_TITLE_STYLE),
                    dcc.Graph(id='graph-kpis', config={'displayModeBar': False}),
                ]
            ),

            # --- FILA 1: Por mes + Por hora ---
            html.Div(
                style={'display': 'grid',
                       'gridTemplateColumns': '1fr 1fr',
                       'gap': '20px',
                       'marginBottom': '20px'},
                children=[
                    html.Div(style=CARD_STYLE, children=[
                        html.P('Consumo por Mes', style=SECTION_TITLE_STYLE),
                        dcc.Graph(id='graph-by-month',
                                  config={'displayModeBar': False}),
                    ]),
                    html.Div(style=CARD_STYLE, children=[
                        html.P('Promedio por Hora', style=SECTION_TITLE_STYLE),
                        dcc.Graph(id='graph-by-hour',
                                  config={'displayModeBar': False}),
                    ]),
                ]
            ),

            # --- FILA 2: Por dia semana + Por dia mes ---
            html.Div(
                style={'display': 'grid',
                       'gridTemplateColumns': '1fr 1fr',
                       'gap': '20px',
                       'marginBottom': '20px'},
                children=[
                    html.Div(style=CARD_STYLE, children=[
                        html.P('Consumo por Dia de la Semana',
                               style=SECTION_TITLE_STYLE),
                        dcc.Graph(id='graph-by-dow',
                                  config={'displayModeBar': False}),
                    ]),
                    html.Div(style=CARD_STYLE, children=[
                        html.P('Promedio por Dia del Mes',
                               style=SECTION_TITLE_STYLE),
                        dcc.Graph(id='graph-by-dom',
                                  config={'displayModeBar': False}),
                    ]),
                ]
            ),

            # --- FILA 3: Detalle horario (ancho completo) ---
            html.Div(
                style=CARD_STYLE,
                children=[
                    html.P('Consumo por Hora y Fecha', style=SECTION_TITLE_STYLE),
                    dcc.Graph(id='graph-by-hour-date',
                              config={'displayModeBar': True}),
                ]
            ),

            # --- FILA 4: Periodos + Laborable/Finde ---
            html.Div(
                style={'display': 'grid',
                       'gridTemplateColumns': '1fr 1fr 1fr',
                       'gap': '20px',
                       'marginBottom': '20px'},
                children=[
                    html.Div(style=CARD_STYLE, children=[
                        html.P('Por Periodo P1/P2/P3', style=SECTION_TITLE_STYLE),
                        dcc.Graph(id='graph-by-period',
                                  config={'displayModeBar': False}),
                    ]),
                    html.Div(style=CARD_STYLE, children=[
                        html.P('Laborable vs Fin de Semana',
                               style=SECTION_TITLE_STYLE),
                        dcc.Graph(id='graph-by-day-type',
                                  config={'displayModeBar': False}),
                    ]),
                    html.Div(style=CARD_STYLE, children=[
                        html.P('Nocturno vs Diurno', style=SECTION_TITLE_STYLE),
                        dcc.Graph(id='graph-nocturno',
                                  config={'displayModeBar': False}),
                    ]),
                ]
            ),

            # --- FILA 5: Temporada (ancho completo) ---
            html.Div(
                style=CARD_STYLE,
                children=[
                    html.P('Consumo por Temporada', style=SECTION_TITLE_STYLE),
                    dcc.Graph(id='graph-by-season',
                              config={'displayModeBar': False}),
                ]
            ),

        ]
    )


# =============================================================================
# FUNCION PRINCIPAL — lanza el dashboard
# =============================================================================

def run_dashboard(analysis: ElectricityAnalysis, port: int = 8050):
    """
    Lanza el dashboard interactivo en el navegador.

    Args:
        analysis: ElectricityAnalysis con hourly_records validados
        port:     Puerto donde se lanza (por defecto 8050)

    Uso en Colab:
        from src.dashboard.dashboard import run_dashboard
        run_dashboard(analysis)
        # Luego abrir el enlace que aparece en el output
    """

    # Guardar el analysis en una variable accesible por los callbacks
    _analysis_global = analysis

    # Inicializar la app Dash con tema Bootstrap
    app = dash.Dash(
        __name__,
        external_stylesheets=[dbc.themes.BOOTSTRAP],
        title='Estudio Electrico'
    )

    # Layout
    app.layout = build_layout(analysis)

    # ----------------------------------------------------------------
    # CALLBACK PRINCIPAL
    # Cuando cambia el filtro de meses -> actualiza todos los graficos
    # ----------------------------------------------------------------

    @app.callback(
        Output('graph-kpis',          'figure'),
        Output('graph-by-month',      'figure'),
        Output('graph-by-hour',       'figure'),
        Output('graph-by-dow',        'figure'),
        Output('graph-by-dom',        'figure'),
        Output('graph-by-hour-date',  'figure'),
        Output('graph-by-period',     'figure'),
        Output('graph-by-day-type',   'figure'),
        Output('graph-nocturno',      'figure'),
        Output('graph-by-season',     'figure'),
        Input('filtro-meses', 'value')
    )
    def update_all_charts(meses_seleccionados):
        # 1. Filtrar registros por meses seleccionados
        analysis_filtrado = filter_records_by_month(
            _analysis_global, meses_seleccionados
        )

        # 2. Recalcular el summary con los datos filtrados
        analysis_filtrado = run_consumption_analysis(analysis_filtrado)
        s = analysis_filtrado.consumption_summary

        # 3. Regenerar todos los graficos
        return (
            chart_kpis(s),
            chart_by_month(s),
            chart_by_hour(s),
            chart_by_day_of_week(s),
            chart_by_day_of_month(s),
            chart_by_hour_and_date(s),
            chart_by_period(s),
            chart_by_day_type(s),
            chart_nocturno(s),
            chart_by_season(s),
        )

    # Lanzar
    print(f"Dashboard lanzado en http://localhost:{port}")
    print("En Colab: haz clic en el enlace que aparece abajo")
    app.run(debug=False, port=port)
