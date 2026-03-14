# =============================================================================
# src/analysis/charts/optimization_charts.py
# Graficos de optimizacion de potencia contratada con Plotly
# Version: 2.0
# =============================================================================

import plotly.graph_objects as go
from plotly.subplots import make_subplots

COLORS = {
    'primary':      '#2563EB',
    'secondary':    '#3B82F6',
    'light':        '#93C5FD',
    'actual':       '#EF4444',
    'equilibrada':  '#F59E0B',
    'segura':       '#10B981',
    'puntual':      '#10B981',
    'ocasional':    '#F59E0B',
    'recurrente':   '#EF4444',
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

PATRON_COLORES = {
    'puntual':    '#10B981',
    'ocasional':  '#F59E0B',
    'recurrente': '#EF4444',
    'sin datos':  '#94A3B8',
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
        ('P1 Actual',        kpis['contracted_p1'],  ',.2f', ' kW', COLORS['actual']),
        ('P2 Actual',        kpis['contracted_p2'],  ',.2f', ' kW', COLORS['actual']),
        ('Max real P1',      kpis['max_real_p1'],    ',.3f', ' kW', COLORS['primary']),
        ('Mediana picos P1', kpis['mediana_p1'],     ',.3f', ' kW', COLORS['secondary']),
        ('Excesos P1',       kpis['horas_exceso_p1'],'',     ' h',  COLORS['equilibrada']),
        ('Excesos P2',       kpis['horas_exceso_p2'],'',     ' h',  COLORS['equilibrada']),
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

    patron_p1 = kpis.get('patron_global_p1', '')
    patron_p2 = kpis.get('patron_global_p2', '')
    estado = (
        f"Patron global — P1 (Punta): {patron_p1.upper()}  |  "
        f"P2 (Valle): {patron_p2.upper()}"
    )

    fig.update_layout(
        **BASE_LAYOUT,
        height = 150,
        title  = dict(text=estado, font=dict(size=13, color=COLORS['text_light']), x=0.5)
    )
    return fig


# =============================================================================
# 2. ANALISIS DE PATRON POR MES (tabla con colores)
# =============================================================================

def chart_pattern_analysis(data: dict) -> go.Figure:
    """
    Tabla que muestra para cada mes y periodo:
    - Pico oficial
    - Horas que superaron el 75% del pico
    - Patron detectado (puntual / ocasional / recurrente)
    - Descripcion
    """
    analisis = data.get('analisis_por_mes', {})
    if not analisis:
        return go.Figure()

    meses       = list(analisis.keys())
    pico_punta  = []
    umbral_punta = []
    horas_punta = []
    patron_punta = []
    pico_valle  = []
    horas_valle = []
    patron_valle = []

    for mes in meses:
        datos = analisis[mes]

        p = datos.get('punta', {})
        pico_punta.append(f"{p.get('pico_oficial', '-')} kW")
        umbral_punta.append(f"{p.get('umbral_75pct', '-')} kW")
        horas_punta.append(p.get('horas_sobre_umbral', '-'))
        patron_punta.append(p.get('patron', '-'))

        v = datos.get('valle', {})
        pico_valle.append(f"{v.get('pico_oficial', '-')} kW")
        horas_valle.append(v.get('horas_sobre_umbral', '-'))
        patron_valle.append(v.get('patron', '-'))

    color_patron = lambda p: PATRON_COLORES.get(p, COLORS['text_light'])

    fig = go.Figure(go.Table(
        header=dict(
            values=[
                'Mes',
                'Pico Punta (oficial)', 'Umbral 75%', 'Horas sobre umbral', 'Patron Punta',
                'Pico Valle (oficial)', 'Horas sobre umbral', 'Patron Valle',
            ],
            fill_color = COLORS['primary'],
            font       = dict(color='white', size=11,
                              family='Segoe UI, Arial, sans-serif'),
            align      = 'center',
            height     = 32,
        ),
        cells=dict(
            values=[
                [m.capitalize() for m in meses],
                pico_punta,
                umbral_punta,
                horas_punta,
                patron_punta,
                pico_valle,
                horas_valle,
                patron_valle,
            ],
            fill_color = 'white',
            font       = dict(
                size   = 12,
                family = 'Segoe UI, Arial, sans-serif',
                color  = [
                    [COLORS['text']]       * len(meses),
                    [COLORS['text']]       * len(meses),
                    [COLORS['text']]       * len(meses),
                    [COLORS['text']]       * len(meses),
                    [color_patron(p) for p in patron_punta],
                    [COLORS['text']]       * len(meses),
                    [COLORS['text']]       * len(meses),
                    [color_patron(p) for p in patron_valle],
                ]
            ),
            align  = 'center',
            height = 28,
        )
    ))

    fig.update_layout(
        **BASE_LAYOUT,
        title  = dict(
            text = 'Analisis de Patron por Mes — Cruce CSV Oficial + CSV Consumo',
            font = dict(size=16)
        ),
        height = 80 + len(meses) * 32,
    )
    return fig


# =============================================================================
# 3. GRAFICO DE BARRAS — PICOS MENSUALES CON PATRON
# =============================================================================

def chart_monthly_peaks_pattern(data: dict) -> go.Figure:
    """
    Barras con los picos mensuales de Punta y Valle coloreadas
    segun el patron detectado (puntual/ocasional/recurrente).
    """
    analisis = data.get('analisis_por_mes', {})
    if not analisis:
        return go.Figure()

    meses        = list(analisis.keys())
    picos_punta  = []
    colores_punta = []
    picos_valle  = []
    colores_valle = []

    for mes in meses:
        p = analisis[mes].get('punta', {})
        v = analisis[mes].get('valle', {})

        picos_punta.append(p.get('pico_oficial', 0))
        colores_punta.append(PATRON_COLORES.get(p.get('patron', ''), COLORS['primary']))

        picos_valle.append(v.get('pico_oficial', 0))
        colores_valle.append(PATRON_COLORES.get(v.get('patron', ''), COLORS['secondary']))

    contracted_p1 = data.get('contracted_p1', 0)
    contracted_p2 = data.get('contracted_p2', 0)

    fig = make_subplots(rows=1, cols=2,
                        subplot_titles=['Punta (P1)', 'Valle (P2)'])

    # Punta
    fig.add_trace(go.Bar(
        x             = [m.capitalize() for m in meses],
        y             = picos_punta,
        name          = 'Pico Punta',
        marker_color  = colores_punta,
        hovertemplate = '<b>%{x}</b><br>Pico: %{y:.3f} kW<extra></extra>',
    ), row=1, col=1)

    if contracted_p1 > 0:
        fig.add_hline(y=contracted_p1, line_dash='dash',
                      line_color=COLORS['actual'],
                      annotation_text=f'Contratada P1: {contracted_p1} kW',
                      annotation_font=dict(color=COLORS['actual'], size=10),
                      row=1, col=1)

    # Valle
    fig.add_trace(go.Bar(
        x             = [m.capitalize() for m in meses],
        y             = picos_valle,
        name          = 'Pico Valle',
        marker_color  = colores_valle,
        hovertemplate = '<b>%{x}</b><br>Pico: %{y:.3f} kW<extra></extra>',
    ), row=1, col=2)

    if contracted_p2 > 0:
        fig.add_hline(y=contracted_p2, line_dash='dash',
                      line_color=COLORS['actual'],
                      annotation_text=f'Contratada P2: {contracted_p2} kW',
                      annotation_font=dict(color=COLORS['actual'], size=10),
                      row=1, col=2)

    # Leyenda de patrones
    for patron, color in PATRON_COLORES.items():
        if patron != 'sin datos':
            fig.add_trace(go.Bar(
                x=[None], y=[None], name=patron.capitalize(),
                marker_color=color, showlegend=True
            ))

    fig.update_layout(
        **BASE_LAYOUT,
        title   = dict(
            text = 'Picos Mensuales por Periodo — Color segun Patron',
            font = dict(size=16)
        ),
        height  = 420,
        barmode = 'group',
        legend  = dict(orientation='h', y=-0.2),
    )
    return fig


# =============================================================================
# 4. OPCIONES SUGERIDAS
# =============================================================================

def chart_suggested_options(data: dict) -> go.Figure:
    opciones = data.get('opciones_sugeridas', {})
    if not opciones:
        return go.Figure()

    eq  = opciones.get('equilibrada', {})
    seg = opciones.get('segura', {})

    fig = go.Figure()

    fig.add_annotation(
        text=(
            f"<b>{eq.get('titulo','').upper()}</b><br><br>"
            f"P1: <b>{eq.get('p1',0)} kW</b>  |  P2: <b>{eq.get('p2',0)} kW</b><br><br>"
            f"{eq.get('descripcion','')}<br><br>"
            f"<i>Base: {eq.get('base_calculo','')}</i>"
        ),
        xref='paper', yref='paper', x=0.25, y=0.5,
        showarrow=False,
        font=dict(size=12, color='#92400E', family='Segoe UI, Arial, sans-serif'),
        align='left',
        bgcolor='#FFFBEB', bordercolor='#F59E0B',
        borderwidth=2, borderpad=16,
    )

    fig.add_annotation(
        text=(
            f"<b>{seg.get('titulo','').upper()}</b><br><br>"
            f"P1: <b>{seg.get('p1',0)} kW</b>  |  P2: <b>{seg.get('p2',0)} kW</b><br><br>"
            f"{seg.get('descripcion','')}<br><br>"
            f"<i>Base: {seg.get('base_calculo','')}</i>"
        ),
        xref='paper', yref='paper', x=0.75, y=0.5,
        showarrow=False,
        font=dict(size=12, color='#065F46', family='Segoe UI, Arial, sans-serif'),
        align='left',
        bgcolor='#ECFDF5', bordercolor='#10B981',
        borderwidth=2, borderpad=16,
    )

    fig.update_layout(
        **BASE_LAYOUT,
        title=dict(text='Opciones Sugeridas', font=dict(size=16)),
        height=300,
        xaxis=dict(visible=False),
        yaxis=dict(visible=False),
    )
    return fig


# =============================================================================
# 5. CURVA DE HORAS SUPERADAS
# =============================================================================

def chart_exceedance_curve(data: dict) -> go.Figure:
    curva_p1 = data.get('curva_p1', [])
    curva_p2 = data.get('curva_p2', [])

    if not curva_p1:
        return go.Figure()

    potencias = [e['potencia'] for e in curva_p1]
    horas_p1  = [e['horas_exceso'] for e in curva_p1]
    horas_p2  = [e['horas_exceso'] for e in curva_p2]

    fig = go.Figure()

    fig.add_trace(go.Scatter(
        x=potencias, y=horas_p1, name='P1 (Punta)',
        mode='lines+markers',
        line=dict(color=COLORS['primary'], width=2),
        marker=dict(size=8),
        hovertemplate='<b>P1: %{x} kW</b><br>Horas exceso: %{y}<extra></extra>',
    ))

    fig.add_trace(go.Scatter(
        x=potencias, y=horas_p2, name='P2 (Valle)',
        mode='lines+markers',
        line=dict(color=COLORS['secondary'], width=2, dash='dot'),
        marker=dict(size=8),
        hovertemplate='<b>P2: %{x} kW</b><br>Horas exceso: %{y}<extra></extra>',
    ))

    contracted_p1 = data.get('contracted_p1', 0)
    eq_p1 = data.get('opciones_sugeridas', {}).get('equilibrada', {}).get('p1', 0)
    seg_p1 = data.get('opciones_sugeridas', {}).get('segura', {}).get('p1', 0)

    if contracted_p1 > 0:
        fig.add_vline(x=contracted_p1, line_dash='dash', line_color=COLORS['actual'],
                      annotation_text=f'Actual: {contracted_p1} kW',
                      annotation_position='top right',
                      annotation_font=dict(color=COLORS['actual'], size=11))

    if eq_p1 > 0 and eq_p1 != contracted_p1:
        fig.add_vline(x=eq_p1, line_dash='dash', line_color=COLORS['equilibrada'],
                      annotation_text=f'Equilibrada: {eq_p1} kW',
                      annotation_position='top left',
                      annotation_font=dict(color=COLORS['equilibrada'], size=11))

    if seg_p1 > 0 and seg_p1 != eq_p1:
        fig.add_vline(x=seg_p1, line_dash='dot', line_color=COLORS['segura'],
                      annotation_text=f'Segura: {seg_p1} kW',
                      annotation_position='bottom right',
                      annotation_font=dict(color=COLORS['segura'], size=11))

    fig.update_layout(
        **BASE_LAYOUT,
        title=dict(text='Horas de Exceso por Nivel de Potencia Contratada',
                   font=dict(size=16)),
        xaxis=dict(title='Potencia contratada (kW)',
                   tickvals=potencias, gridcolor=COLORS['grid']),
        yaxis=dict(title='Horas de exceso al año', gridcolor=COLORS['grid']),
        height=420,
        legend=dict(orientation='h', y=-0.2),
    )
    return fig


# =============================================================================
# 6. TABLAS COMPARATIVAS
# =============================================================================

def _build_table(tabla, titulo, header_color):
    if not tabla:
        return go.Figure()

    colores_fila = []
    etiqueta = []
    color_etiqueta = []

    for row in tabla:
        if row['es_actual']:
            colores_fila.append('#FEF2F2')
            etiqueta.append('← Actual')
            color_etiqueta.append(COLORS['actual'])
        elif row['es_equilibrada'] and row['es_segura']:
            colores_fila.append('#ECFDF5')
            etiqueta.append('← Equilibrada / Segura')
            color_etiqueta.append(COLORS['segura'])
        elif row['es_equilibrada']:
            colores_fila.append('#FFFBEB')
            etiqueta.append('← Equilibrada')
            color_etiqueta.append(COLORS['equilibrada'])
        elif row['es_segura']:
            colores_fila.append('#ECFDF5')
            etiqueta.append('← Segura')
            color_etiqueta.append(COLORS['segura'])
        else:
            colores_fila.append('white')
            etiqueta.append('')
            color_etiqueta.append(COLORS['text'])

    fig = go.Figure(go.Table(
        header=dict(
            values=['Potencia (kW)', 'Horas exceso', '% exceso',
                    'Margen vs max', 'Riesgo', ''],
            fill_color=header_color,
            font=dict(color='white', size=12,
                      family='Segoe UI, Arial, sans-serif'),
            align='center', height=32,
        ),
        cells=dict(
            values=[
                [f"{r['potencia']} kW" for r in tabla],
                [r['horas_exceso']     for r in tabla],
                [f"{r['pct_exceso']}%" for r in tabla],
                [f"+{r['margen_kw']} kW" if r['margen_kw'] >= 0
                 else f"{r['margen_kw']} kW" for r in tabla],
                [r['riesgo']           for r in tabla],
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
        title=dict(text=titulo, font=dict(size=16)),
        height=420,
    )
    return fig


def chart_options_table_p1(data: dict) -> go.Figure:
    return _build_table(
        data.get('tabla_p1', []),
        'Comparativa de Opciones — P1 (Punta)',
        COLORS['primary']
    )

def chart_options_table_p2(data: dict) -> go.Figure:
    return _build_table(
        data.get('tabla_p2', []),
        'Comparativa de Opciones — P2 (Valle)',
        COLORS['secondary']
    )


# =============================================================================
# FUNCION PRINCIPAL
# =============================================================================

def generate_optimization_charts(data: dict) -> dict:
    print("Generando graficos de optimizacion...")

    graficos = {
        'kpis':           chart_optimization_kpis(data),
        'patron_tabla':   chart_pattern_analysis(data),
        'patron_barras':  chart_monthly_peaks_pattern(data),
        'opciones':       chart_suggested_options(data),
        'curva':          chart_exceedance_curve(data),
        'tabla_p1':       chart_options_table_p1(data),
        'tabla_p2':       chart_options_table_p2(data),
    }

    print(f"  {len(graficos)} graficos generados correctamente.")
    return graficos
