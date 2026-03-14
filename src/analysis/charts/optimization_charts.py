# =============================================================================
# src/analysis/charts/optimization_charts.py
# Graficos de optimizacion de potencia contratada con Plotly
# Version: 1.1
# =============================================================================

import plotly.graph_objects as go
from plotly.subplots import make_subplots

import sys
sys.path.append('../..')


COLORS = {
    'primary':      '#2563EB',
    'secondary':    '#3B82F6',
    'light':        '#93C5FD',
    'actual':       '#EF4444',
    'equilibrada':  '#F59E0B',
    'segura':       '#10B981',
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
    'Ninguno':  '#10B981',
    'Muy bajo': '#6EE7B7',
    'Bajo':     '#A3E635',
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
        ('P1 Actual',      kpis['contracted_p1'],  ',.2f', ' kW', COLORS['actual']),
        ('P2 Actual',      kpis['contracted_p2'],  ',.2f', ' kW', COLORS['actual']),
        ('Excesos P1',     kpis['horas_exceso_p1'],'',     ' h',  COLORS['equilibrada']),
        ('Excesos P2',     kpis['horas_exceso_p2'],'',     ' h',  COLORS['equilibrada']),
        ('Max real P1',    kpis['max_real_p1'],    ',.3f', ' kW', COLORS['primary']),
        ('P95 consumo P1', kpis['p95_p1'],         ',.4f', ' kW', COLORS['primary']),
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

    estado = "⚠️ Has superado la potencia contratada" if kpis.get('tiene_exceso') else "✅ Sin excesos registrados con la potencia actual"
    color_estado = COLORS['actual'] if kpis.get('tiene_exceso') else COLORS['segura']

    fig.update_layout(
        **BASE_LAYOUT,
        height = 150,
        title  = dict(text=estado, font=dict(size=14, color=color_estado), x=0.5)
    )
    return fig


# =============================================================================
# 2. TARJETAS DE OPCIONES SUGERIDAS
# =============================================================================

def chart_suggested_options(data: dict) -> go.Figure:
    """
    Muestra las dos opciones sugeridas (equilibrada y segura)
    como tarjetas explicativas con sus datos clave.
    """
    opciones = data.get('opciones_sugeridas', {})
    if not opciones:
        return go.Figure()

    eq   = opciones.get('equilibrada', {})
    seg  = opciones.get('segura', {})

    fig = go.Figure()

    # Opcion equilibrada (izquierda)
    fig.add_annotation(
        text = (
            f"<b>{eq.get('titulo','').upper()}</b><br><br>"
            f"P1: <b>{eq.get('p1', 0)} kW</b>  |  P2: <b>{eq.get('p2', 0)} kW</b><br><br>"
            f"Horas exceso P1: {eq.get('horas_exceso_p1', 0)}h  |  "
            f"Riesgo: {eq.get('riesgo_p1','')}<br><br>"
            f"{eq.get('descripcion','')}<br><br>"
            f"<i>Base: {eq.get('base_calculo','')}</i>"
        ),
        xref='paper', yref='paper',
        x=0.25, y=0.5,
        showarrow  = False,
        font       = dict(size=12, color='#92400E',
                          family='Segoe UI, Arial, sans-serif'),
        align      = 'left',
        bgcolor    = '#FFFBEB',
        bordercolor= '#F59E0B',
        borderwidth= 2,
        borderpad  = 16,
    )

    # Opcion segura (derecha)
    fig.add_annotation(
        text = (
            f"<b>{seg.get('titulo','').upper()}</b><br><br>"
            f"P1: <b>{seg.get('p1', 0)} kW</b>  |  P2: <b>{seg.get('p2', 0)} kW</b><br><br>"
            f"Horas exceso P1: {seg.get('horas_exceso_p1', 0)}h  |  "
            f"Riesgo: {seg.get('riesgo_p1','')}<br><br>"
            f"{seg.get('descripcion','')}<br><br>"
            f"<i>Base: {seg.get('base_calculo','')}</i>"
        ),
        xref='paper', yref='paper',
        x=0.75, y=0.5,
        showarrow  = False,
        font       = dict(size=12, color='#065F46',
                          family='Segoe UI, Arial, sans-serif'),
        align      = 'left',
        bgcolor    = '#ECFDF5',
        bordercolor= '#10B981',
        borderwidth= 2,
        borderpad  = 16,
    )

    fig.update_layout(
        **BASE_LAYOUT,
        title  = dict(text='Opciones Sugeridas', font=dict(size=16)),
        height = 320,
        xaxis  = dict(visible=False),
        yaxis  = dict(visible=False),
    )
    return fig


# =============================================================================
# 3. CURVA DE HORAS SUPERADAS VS POTENCIA
# =============================================================================

def chart_exceedance_curve(data: dict) -> go.Figure:
    curva_p1 = data.get('curva_p1', [])
    curva_p2 = data.get('curva_p2', [])

    if not curva_p1 and not curva_p2:
        return go.Figure()

    potencias = [e['potencia'] for e in curva_p1]
    horas_p1  = [e['horas_exceso'] for e in curva_p1]
    horas_p2  = [e['horas_exceso'] for e in curva_p2]

    fig = go.Figure()

    fig.add_trace(go.Scatter(
        x=potencias, y=horas_p1,
        name='P1 (Laborable 8h-24h)',
        mode='lines+markers',
        line=dict(color=COLORS['primary'], width=2),
        marker=dict(size=8, color=COLORS['primary']),
        hovertemplate='<b>P1: %{x} kW</b><br>Horas exceso: %{y}<extra></extra>',
    ))

    fig.add_trace(go.Scatter(
        x=potencias, y=horas_p2,
        name='P2 (Nocturno / Finde)',
        mode='lines+markers',
        line=dict(color=COLORS['secondary'], width=2, dash='dot'),
        marker=dict(size=8, color=COLORS['secondary']),
        hovertemplate='<b>P2: %{x} kW</b><br>Horas exceso: %{y}<extra></extra>',
    ))

    # Linea potencia actual
    contracted_p1 = data.get('contracted_p1', 0)
    if contracted_p1 > 0:
        fig.add_vline(x=contracted_p1, line_dash='dash',
                      line_color=COLORS['actual'],
                      annotation_text=f'Actual: {contracted_p1} kW',
                      annotation_position='top right',
                      annotation_font=dict(color=COLORS['actual'], size=11))

    # Linea opcion equilibrada
    eq_p1 = data.get('opciones_sugeridas', {}).get('equilibrada', {}).get('p1', 0)
    if eq_p1 > 0 and eq_p1 != contracted_p1:
        fig.add_vline(x=eq_p1, line_dash='dash',
                      line_color=COLORS['equilibrada'],
                      annotation_text=f'Equilibrada: {eq_p1} kW',
                      annotation_position='top left',
                      annotation_font=dict(color=COLORS['equilibrada'], size=11))

    # Linea opcion segura
    seg_p1 = data.get('opciones_sugeridas', {}).get('segura', {}).get('p1', 0)
    if seg_p1 > 0 and seg_p1 != eq_p1:
        fig.add_vline(x=seg_p1, line_dash='dot',
                      line_color=COLORS['segura'],
                      annotation_text=f'Segura: {seg_p1} kW',
                      annotation_position='bottom right',
                      annotation_font=dict(color=COLORS['segura'], size=11))

    fig.update_layout(
        **BASE_LAYOUT,
        title  = dict(text='Horas de Exceso por Nivel de Potencia Contratada',
                      font=dict(size=16)),
        xaxis  = dict(title='Potencia contratada (kW)',
                      tickvals=potencias, gridcolor=COLORS['grid']),
        yaxis  = dict(title='Horas de exceso al año', gridcolor=COLORS['grid']),
        height = 420,
        legend = dict(orientation='h', y=-0.2),
    )
    return fig


# =============================================================================
# 4. TABLA COMPARATIVA P1
# =============================================================================

def chart_options_table_p1(data: dict) -> go.Figure:
    tabla = data.get('tabla_p1', [])
    if not tabla:
        return go.Figure()

    colores_fila = []
    for row in tabla:
        if row['es_actual']:
            colores_fila.append('#FEF2F2')
        elif row['es_equilibrada']:
            colores_fila.append('#FFFBEB')
        elif row['es_segura']:
            colores_fila.append('#ECFDF5')
        else:
            colores_fila.append('white')

    etiqueta = []
    for row in tabla:
        if row['es_actual']:
            etiqueta.append('← Actual')
        elif row['es_equilibrada'] and row['es_segura']:
            etiqueta.append('← Equilibrada / Segura')
        elif row['es_equilibrada']:
            etiqueta.append('← Equilibrada')
        elif row['es_segura']:
            etiqueta.append('← Segura')
        else:
            etiqueta.append('')

    color_etiqueta = []
    for row in tabla:
        if row['es_actual']:
            color_etiqueta.append(COLORS['actual'])
        elif row['es_equilibrada']:
            color_etiqueta.append(COLORS['equilibrada'])
        elif row['es_segura']:
            color_etiqueta.append(COLORS['segura'])
        else:
            color_etiqueta.append(COLORS['text'])

    fig = go.Figure(go.Table(
        header=dict(
            values=['Potencia (kW)', 'Horas exceso', '% exceso',
                    'Margen vs max real', 'Riesgo', ''],
            fill_color=COLORS['primary'],
            font=dict(color='white', size=12,
                      family='Segoe UI, Arial, sans-serif'),
            align='center', height=32,
        ),
        cells=dict(
            values=[
                [f"{r['potencia']} kW"        for r in tabla],
                [r['horas_exceso']             for r in tabla],
                [f"{r['pct_exceso']}%"         for r in tabla],
                [f"+{r['margen_kw']} kW" if r['margen_kw'] >= 0
                 else f"{r['margen_kw']} kW"   for r in tabla],
                [r['riesgo']                   for r in tabla],
                etiqueta,
            ],
            fill_color=[colores_fila] * 6,
            font=dict(size=12, family='Segoe UI, Arial, sans-serif',
                      color=[
                          [COLORS['text']] * len(tabla),
                          [COLORS['text']] * len(tabla),
                          [COLORS['text']] * len(tabla),
                          [COLORS['text']] * len(tabla),
                          [RIESGO_COLORES.get(r['riesgo'], COLORS['text']) for r in tabla],
                          color_etiqueta,
                      ]),
            align='center', height=28,
        )
    ))

    fig.update_layout(
        **BASE_LAYOUT,
        title=dict(text='Comparativa de Opciones — P1 (Punta)', font=dict(size=16)),
        height=420,
    )
    return fig


# =============================================================================
# 5. TABLA COMPARATIVA P2
# =============================================================================

def chart_options_table_p2(data: dict) -> go.Figure:
    tabla = data.get('tabla_p2', [])
    if not tabla:
        return go.Figure()

    colores_fila = []
    for row in tabla:
        if row['es_actual']:
            colores_fila.append('#FEF2F2')
        elif row['es_equilibrada']:
            colores_fila.append('#FFFBEB')
        elif row['es_segura']:
            colores_fila.append('#ECFDF5')
        else:
            colores_fila.append('white')

    etiqueta = []
    for row in tabla:
        if row['es_actual']:
            etiqueta.append('← Actual')
        elif row['es_equilibrada'] and row['es_segura']:
            etiqueta.append('← Equilibrada / Segura')
        elif row['es_equilibrada']:
            etiqueta.append('← Equilibrada')
        elif row['es_segura']:
            etiqueta.append('← Segura')
        else:
            etiqueta.append('')

    color_etiqueta = []
    for row in tabla:
        if row['es_actual']:
            color_etiqueta.append(COLORS['actual'])
        elif row['es_equilibrada']:
            color_etiqueta.append(COLORS['equilibrada'])
        elif row['es_segura']:
            color_etiqueta.append(COLORS['segura'])
        else:
            color_etiqueta.append(COLORS['text'])

    fig = go.Figure(go.Table(
        header=dict(
            values=['Potencia (kW)', 'Horas exceso', '% exceso',
                    'Margen vs max real', 'Riesgo', ''],
            fill_color=COLORS['secondary'],
            font=dict(color='white', size=12,
                      family='Segoe UI, Arial, sans-serif'),
            align='center', height=32,
        ),
        cells=dict(
            values=[
                [f"{r['potencia']} kW"        for r in tabla],
                [r['horas_exceso']             for r in tabla],
                [f"{r['pct_exceso']}%"         for r in tabla],
                [f"+{r['margen_kw']} kW" if r['margen_kw'] >= 0
                 else f"{r['margen_kw']} kW"   for r in tabla],
                [r['riesgo']                   for r in tabla],
                etiqueta,
            ],
            fill_color=[colores_fila] * 6,
            font=dict(size=12, family='Segoe UI, Arial, sans-serif',
                      color=[
                          [COLORS['text']] * len(tabla),
                          [COLORS['text']] * len(tabla),
                          [COLORS['text']] * len(tabla),
                          [COLORS['text']] * len(tabla),
                          [RIESGO_COLORES.get(r['riesgo'], COLORS['text']) for r in tabla],
                          color_etiqueta,
                      ]),
            align='center', height=28,
        )
    ))

    fig.update_layout(
        **BASE_LAYOUT,
        title=dict(text='Comparativa de Opciones — P2 (Valle)', font=dict(size=16)),
        height=420,
    )
    return fig


# =============================================================================
# FUNCION PRINCIPAL
# =============================================================================

def generate_optimization_charts(data: dict) -> dict:
    print("Generando graficos de optimizacion...")

    graficos = {
        'kpis':        chart_optimization_kpis(data),
        'opciones':    chart_suggested_options(data),
        'curva':       chart_exceedance_curve(data),
        'tabla_p1':    chart_options_table_p1(data),
        'tabla_p2':    chart_options_table_p2(data),
    }

    print(f"  {len(graficos)} graficos generados correctamente.")
    return graficos
