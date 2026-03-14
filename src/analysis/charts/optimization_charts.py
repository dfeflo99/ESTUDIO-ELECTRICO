# =============================================================================
# src/analysis/charts/optimization_charts.py
# Graficos de optimizacion de potencia contratada con Plotly
# Version: 1.0
#
# Pagina 4 del informe: Optimizacion de potencia contratada
# =============================================================================

import plotly.graph_objects as go
from plotly.subplots import make_subplots

import sys
sys.path.append('../..')


COLORS = {
    'primary':      '#2563EB',
    'secondary':    '#3B82F6',
    'light':        '#93C5FD',
    'accent':       '#1D4ED8',
    'danger':       '#EF4444',
    'warning':      '#F59E0B',
    'success':      '#10B981',
    'actual':       '#EF4444',
    'recomendada':  '#10B981',
    'background':   '#F8FAFF',
    'grid':         '#E2E8F0',
    'text':         '#1E293B',
    'text_light':   '#64748B',
}

BASE_LAYOUT = dict(
    font          = dict(family='Segoe UI, Arial, sans-serif', color='#1E293B'),
    paper_bgcolor = 'white',
    plot_bgcolor  = '#F8FAFF',
    margin        = dict(l=40, r=40, t=60, b=40),
    hoverlabel    = dict(bgcolor='white', font_size=13),
)

RIESGO_COLORES = {
    'Seguro':   '#10B981',
    'Bajo':     '#6EE7B7',
    'Moderado': '#F59E0B',
    'Alto':     '#EF4444',
}


# =============================================================================
# 1. KPIs
# =============================================================================

def chart_optimization_kpis(data: dict) -> go.Figure:
    kpis = data.get('kpis', {})
    if not kpis:
        return go.Figure()

    fig = go.Figure()

    valores = [
        ('P1 Actual',       kpis['contracted_p1'],   ',.2f', ' kW', COLORS['actual']),
        ('P1 Recomendada',  kpis['recommended_p1'],  ',.2f', ' kW', COLORS['recomendada']),
        ('P2 Actual',       kpis['contracted_p2'],   ',.2f', ' kW', COLORS['actual']),
        ('P2 Recomendada',  kpis['recommended_p2'],  ',.2f', ' kW', COLORS['recomendada']),
        ('Excesos P1',      kpis['horas_exceso_p1'], ',d',   ' h',  COLORS['warning']),
        ('Excesos P2',      kpis['horas_exceso_p2'], ',d',   ' h',  COLORS['warning']),
    ]

    for i, (titulo, valor, fmt, sufijo, color) in enumerate(valores):
        fig.add_trace(go.Indicator(
            mode   = "number",
            value  = float(valor),
            title  = dict(text=titulo, font=dict(size=12, color=COLORS['text_light'])),
            number = dict(suffix=sufijo, font=dict(size=22, color=color),
                          valueformat=fmt),
            domain = dict(x=[i/6, (i+1)/6], y=[0, 1])
        ))

    # Mensaje de estado
    if kpis.get('tiene_exceso'):
        estado = "⚠️ Has superado la potencia contratada"
        color_estado = COLORS['danger']
    elif kpis.get('tiene_sobredimension'):
        estado = "💡 Tienes potencia contratada de mas — podrias ahorrar bajandola"
        color_estado = COLORS['warning']
    else:
        estado = "✅ Tu potencia contratada es adecuada"
        color_estado = COLORS['success']

    fig.update_layout(
        **BASE_LAYOUT,
        height = 150,
        title  = dict(
            text  = estado,
            font  = dict(size=14, color=color_estado),
            x     = 0.5
        )
    )
    return fig


# =============================================================================
# 2. CURVA DE HORAS SUPERADAS VS POTENCIA
# =============================================================================

def chart_exceedance_curve(data: dict) -> go.Figure:
    """
    Muestra para cada potencia comercial cuantas horas se superaria.
    Permite ver el punto optimo entre seguridad y ahorro.
    Incluye P1 y P2 en el mismo grafico.
    """
    curva_p1 = data.get('curva_p1', [])
    curva_p2 = data.get('curva_p2', [])

    if not curva_p1 and not curva_p2:
        return go.Figure()

    potencias = [e['potencia'] for e in curva_p1]
    horas_p1  = [e['horas_exceso'] for e in curva_p1]
    horas_p2  = [e['horas_exceso'] for e in curva_p2]

    fig = go.Figure()

    # Curva P1
    fig.add_trace(go.Scatter(
        x             = potencias,
        y             = horas_p1,
        name          = 'P1 (Laborable 8h-24h)',
        mode          = 'lines+markers',
        line          = dict(color=COLORS['primary'], width=2),
        marker        = dict(size=8, color=COLORS['primary']),
        hovertemplate = '<b>P1: %{x} kW</b><br>Horas exceso: %{y}<extra></extra>',
    ))

    # Curva P2
    fig.add_trace(go.Scatter(
        x             = potencias,
        y             = horas_p2,
        name          = 'P2 (Nocturno / Finde)',
        mode          = 'lines+markers',
        line          = dict(color=COLORS['secondary'], width=2, dash='dot'),
        marker        = dict(size=8, color=COLORS['secondary']),
        hovertemplate = '<b>P2: %{x} kW</b><br>Horas exceso: %{y}<extra></extra>',
    ))

    # Linea potencia actual P1
    contracted_p1 = data.get('contracted_p1', 0)
    if contracted_p1 > 0:
        fig.add_vline(
            x                   = contracted_p1,
            line_dash           = 'dash',
            line_color          = COLORS['actual'],
            annotation_text     = f'Actual P1: {contracted_p1} kW',
            annotation_position = 'top right',
            annotation_font     = dict(color=COLORS['actual'], size=11)
        )

    # Linea potencia recomendada P1
    recommended_p1 = data['kpis'].get('recommended_p1', 0)
    if recommended_p1 > 0:
        fig.add_vline(
            x                   = recommended_p1,
            line_dash           = 'dash',
            line_color          = COLORS['recomendada'],
            annotation_text     = f'Recomendada P1: {recommended_p1} kW',
            annotation_position = 'top left',
            annotation_font     = dict(color=COLORS['recomendada'], size=11)
        )

    fig.update_layout(
        **BASE_LAYOUT,
        title   = dict(text='Horas de Exceso por Nivel de Potencia Contratada',
                       font=dict(size=16)),
        xaxis   = dict(
            title     = 'Potencia contratada (kW)',
            tickvals  = potencias,
            gridcolor = COLORS['grid']
        ),
        yaxis   = dict(title='Horas de exceso al año', gridcolor=COLORS['grid']),
        height  = 420,
        legend  = dict(orientation='h', y=-0.2),
    )
    return fig


# =============================================================================
# 3. TABLA COMPARATIVA DE OPCIONES P1
# =============================================================================

def chart_options_table_p1(data: dict) -> go.Figure:
    tabla = data.get('tabla_opciones_p1', [])
    if not tabla:
        return go.Figure()

    colores_fila = []
    for row in tabla:
        if row['es_actual']:
            colores_fila.append('#FEF2F2')
        elif row['es_recomendada']:
            colores_fila.append('#ECFDF5')
        else:
            colores_fila.append('white')

    fig = go.Figure(go.Table(
        header = dict(
            values    = ['Potencia (kW)', 'Horas exceso', '% exceso',
                         'Margen (kW)', 'Riesgo', ''],
            fill_color = COLORS['primary'],
            font       = dict(color='white', size=12,
                              family='Segoe UI, Arial, sans-serif'),
            align      = 'center',
            height     = 32,
        ),
        cells = dict(
            values = [
                [f"{r['potencia']} kW" for r in tabla],
                [r['horas_exceso']     for r in tabla],
                [f"{r['pct_exceso']}%" for r in tabla],
                [f"+{r['margen_kw']} kW" if r['margen_kw'] >= 0
                 else f"{r['margen_kw']} kW" for r in tabla],
                [r['riesgo']           for r in tabla],
                ['← Actual' if r['es_actual'] else
                 '← Recomendada' if r['es_recomendada'] else ''
                 for r in tabla],
            ],
            fill_color = [colores_fila] * 6,
            font       = dict(size=12, family='Segoe UI, Arial, sans-serif',
                              color=[
                                  [COLORS['text']] * len(tabla),
                                  [COLORS['text']] * len(tabla),
                                  [COLORS['text']] * len(tabla),
                                  [COLORS['text']] * len(tabla),
                                  [RIESGO_COLORES.get(r['riesgo'], COLORS['text'])
                                   for r in tabla],
                                  [COLORS['actual'] if r['es_actual'] else
                                   COLORS['recomendada'] if r['es_recomendada']
                                   else COLORS['text'] for r in tabla],
                              ]),
            align      = 'center',
            height     = 28,
        )
    ))

    fig.update_layout(
        **BASE_LAYOUT,
        title  = dict(text='Comparativa de Opciones — Periodo P1 (Punta)',
                      font=dict(size=16)),
        height = 420,
    )
    return fig


# =============================================================================
# 4. TABLA COMPARATIVA DE OPCIONES P2
# =============================================================================

def chart_options_table_p2(data: dict) -> go.Figure:
    tabla = data.get('tabla_opciones_p2', [])
    if not tabla:
        return go.Figure()

    colores_fila = []
    for row in tabla:
        if row['es_actual']:
            colores_fila.append('#FEF2F2')
        elif row['es_recomendada']:
            colores_fila.append('#ECFDF5')
        else:
            colores_fila.append('white')

    fig = go.Figure(go.Table(
        header = dict(
            values    = ['Potencia (kW)', 'Horas exceso', '% exceso',
                         'Margen (kW)', 'Riesgo', ''],
            fill_color = COLORS['secondary'],
            font       = dict(color='white', size=12,
                              family='Segoe UI, Arial, sans-serif'),
            align      = 'center',
            height     = 32,
        ),
        cells = dict(
            values = [
                [f"{r['potencia']} kW" for r in tabla],
                [r['horas_exceso']     for r in tabla],
                [f"{r['pct_exceso']}%" for r in tabla],
                [f"+{r['margen_kw']} kW" if r['margen_kw'] >= 0
                 else f"{r['margen_kw']} kW" for r in tabla],
                [r['riesgo']           for r in tabla],
                ['← Actual' if r['es_actual'] else
                 '← Recomendada' if r['es_recomendada'] else ''
                 for r in tabla],
            ],
            fill_color = [colores_fila] * 6,
            font       = dict(size=12, family='Segoe UI, Arial, sans-serif',
                              color=[
                                  [COLORS['text']] * len(tabla),
                                  [COLORS['text']] * len(tabla),
                                  [COLORS['text']] * len(tabla),
                                  [COLORS['text']] * len(tabla),
                                  [RIESGO_COLORES.get(r['riesgo'], COLORS['text'])
                                   for r in tabla],
                                  [COLORS['actual'] if r['es_actual'] else
                                   COLORS['recomendada'] if r['es_recomendada']
                                   else COLORS['text'] for r in tabla],
                              ]),
            align      = 'center',
            height     = 28,
        )
    ))

    fig.update_layout(
        **BASE_LAYOUT,
        title  = dict(text='Comparativa de Opciones — Periodo P2 (Valle)',
                      font=dict(size=16)),
        height = 420,
    )
    return fig


# =============================================================================
# FUNCION PRINCIPAL
# =============================================================================

def generate_optimization_charts(data: dict) -> dict:
    """
    Genera todos los graficos de la Pagina 4.

    Args:
        data: Resultado de run_optimization_analysis()

    Returns:
        Diccionario con todos los Figure de Plotly
    """
    print("Generando graficos de optimizacion...")

    graficos = {
        'kpis':        chart_optimization_kpis(data),
        'curva':       chart_exceedance_curve(data),
        'tabla_p1':    chart_options_table_p1(data),
        'tabla_p2':    chart_options_table_p2(data),
    }

    print(f"  {len(graficos)} graficos generados correctamente.")
    return graficos
