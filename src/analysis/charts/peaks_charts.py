# =============================================================================
# src/analysis/charts/peaks_charts.py
# Graficos de analisis de picos criticos con Plotly
# Version: 1.0
#
# Pagina 3 del informe: Analisis de picos criticos
# =============================================================================

import plotly.graph_objects as go
from plotly.subplots import make_subplots

import sys
sys.path.append('../..')


COLORS = {
    'primary':    '#2563EB',
    'secondary':  '#3B82F6',
    'light':      '#93C5FD',
    'accent':     '#1D4ED8',
    'danger':     '#EF4444',
    'warning':    '#F59E0B',
    'success':    '#10B981',
    'background': '#F8FAFF',
    'grid':       '#E2E8F0',
    'text':       '#1E293B',
    'text_light': '#64748B',
    'p1':         '#1D4ED8',
    'p2':         '#93C5FD',
    'laborable':  '#2563EB',
    'finde':      '#93C5FD',
    'madrugada':  '#1E3A5F',
    'manana':     '#3B82F6',
    'tarde':      '#F59E0B',
    'noche':      '#6366F1',
}

BASE_LAYOUT = dict(
    font          = dict(family='Segoe UI, Arial, sans-serif', color='#1E293B'),
    paper_bgcolor = 'white',
    plot_bgcolor  = '#F8FAFF',
    margin        = dict(l=40, r=40, t=60, b=40),
    hoverlabel    = dict(bgcolor='white', font_size=13),
)

FRANJAS_COLORES = {
    'Madrugada (0h-6h)': COLORS['madrugada'],
    'Manana (6h-12h)':   COLORS['manana'],
    'Tarde (12h-18h)':   COLORS['tarde'],
    'Noche (18h-24h)':   COLORS['noche'],
}


# =============================================================================
# 1. KPIs
# =============================================================================

def chart_peaks_kpis(data: dict) -> go.Figure:
    kpis = data.get('kpis', {})
    if not kpis:
        return go.Figure()

    fig = go.Figure()

    valores = [
        ('Horas sobre umbral',  data['total_picos'],              ',d',   ' h'),
        ('% sobre umbral',      kpis['pct_sobre_umbral'],         ',.2f', '%'),
        ('Pico maximo',         kpis['pico_maximo_kwh'],          ',.3f', ' kW'),
    ]

    for i, (titulo, valor, fmt, sufijo) in enumerate(valores):
        fig.add_trace(go.Indicator(
            mode   = "number",
            value  = float(valor),
            title  = dict(text=titulo, font=dict(size=13, color=COLORS['text_light'])),
            number = dict(suffix=sufijo, font=dict(size=26, color=COLORS['danger']),
                          valueformat=fmt),
            domain = dict(x=[i/3, (i+1)/3], y=[0, 1])
        ))

    fig.update_layout(
        **BASE_LAYOUT,
        height = 130,
        title  = dict(
            text  = f"Umbral: {data['umbral_kw']} kW  |  "
                    f"Mes con mas picos: {kpis.get('mes_mas_picos','').capitalize()} "
                    f"({kpis.get('picos_en_mes_mas', 0)} horas)  |  "
                    f"Franja mas repetida: {kpis.get('franja_mas_repetida','')}",
            font  = dict(size=12, color=COLORS['text_light']),
            x     = 0.5
        )
    )
    return fig


# =============================================================================
# 2. TOP 10 PICOS (tabla interactiva)
# =============================================================================

def chart_top10_table(data: dict) -> go.Figure:
    top10 = data.get('top10', [])
    if not top10:
        fig = go.Figure()
        fig.add_annotation(text="No hay picos sobre el umbral",
                           xref='paper', yref='paper', x=0.5, y=0.5,
                           showarrow=False,
                           font=dict(size=14, color=COLORS['text_light']))
        fig.update_layout(**BASE_LAYOUT, height=200)
        return fig

    fig = go.Figure(go.Table(
        header = dict(
            values    = ['#', 'Fecha', 'Hora', 'Dia', 'Mes',
                         'kWh', 'Exceso kWh', 'Festivo', 'Finde',
                         'Periodo Pot.', 'Franja'],
            fill_color = COLORS['primary'],
            font       = dict(color='white', size=12,
                              family='Segoe UI, Arial, sans-serif'),
            align      = 'center',
            height     = 32,
        ),
        cells = dict(
            values = [
                [r['ranking']          for r in top10],
                [r['fecha']            for r in top10],
                [r['hora']             for r in top10],
                [r['dia_semana']       for r in top10],
                [r['mes']              for r in top10],
                [r['kwh']              for r in top10],
                [r['exceso_kwh']       for r in top10],
                [r['es_festivo']       for r in top10],
                [r['es_finde']         for r in top10],
                [r['periodo_potencia'] for r in top10],
                [r['franja']           for r in top10],
            ],
            fill_color = [
                ['#FEF2F2' if i == 0 else
                 '#FFF7ED' if i == 1 else
                 '#FFFBEB' if i == 2 else
                 'white'
                 for i in range(len(top10))]
            ] * 11,
            font       = dict(size=12, family='Segoe UI, Arial, sans-serif',
                              color=COLORS['text']),
            align      = ['center'] * 11,
            height     = 28,
        )
    ))

    fig.update_layout(
        **BASE_LAYOUT,
        title  = dict(text='Top 10 Picos mas Altos', font=dict(size=16)),
        height = 420,
    )
    return fig


# =============================================================================
# 3. EVOLUCION MENSUAL DE PICOS
# =============================================================================

def chart_peaks_by_month(data: dict) -> go.Figure:
    by_month = data.get('by_month', {})
    if not by_month:
        return go.Figure()

    meses    = list(by_month.keys())
    num_picos = [by_month[m]['num_picos'] for m in meses]
    max_kwh   = [by_month[m]['max_kwh']   for m in meses]

    fig = make_subplots(specs=[[{"secondary_y": True}]])

    fig.add_trace(go.Bar(
        x             = [m.capitalize() for m in meses],
        y             = num_picos,
        name          = 'Horas sobre umbral',
        marker_color  = COLORS['danger'],
        marker_line   = dict(color='#B91C1C', width=1),
        hovertemplate = '<b>%{x}</b><br>Horas: %{y}<extra></extra>',
    ), secondary_y=False)

    fig.add_trace(go.Scatter(
        x             = [m.capitalize() for m in meses],
        y             = max_kwh,
        name          = 'Pico maximo del mes',
        mode          = 'lines+markers',
        line          = dict(color=COLORS['warning'], width=2),
        marker        = dict(size=7),
        hovertemplate = '<b>%{x}</b><br>Pico max: %{y:.3f} kW<extra></extra>',
    ), secondary_y=True)

    fig.update_layout(
        **BASE_LAYOUT,
        title   = dict(text='Evolucion Mensual de Picos', font=dict(size=16)),
        height  = 380,
        legend  = dict(orientation='h', y=-0.2),
    )
    fig.update_yaxes(title_text='Horas sobre umbral',
                     gridcolor=COLORS['grid'], secondary_y=False)
    fig.update_yaxes(title_text='kW (pico maximo)', secondary_y=True)
    return fig


# =============================================================================
# 4. DISTRIBUCION POR HORA EXACTA
# =============================================================================

def chart_peaks_by_hour(data: dict) -> go.Figure:
    by_hora = data.get('by_hora', {})
    if not by_hora:
        return go.Figure()

    horas     = sorted(by_hora.keys())
    num_picos = [by_hora[h]['num_picos'] for h in horas]

    # Color por franja
    def color_hora(h):
        if h < 6:    return COLORS['madrugada']
        elif h < 12: return COLORS['manana']
        elif h < 18: return COLORS['tarde']
        else:        return COLORS['noche']

    colores = [color_hora(h) for h in horas]

    fig = go.Figure(go.Bar(
        x             = [f"{h:02d}:00" for h in horas],
        y             = num_picos,
        marker_color  = colores,
        hovertemplate = '<b>%{x}</b><br>Picos: %{y}<extra></extra>',
        text          = [str(v) if v > 0 else '' for v in num_picos],
        textposition  = 'outside',
        textfont      = dict(size=10),
    ))

    # Leyenda de franjas
    for franja, color in FRANJAS_COLORES.items():
        fig.add_trace(go.Bar(
            x=[None], y=[None], name=franja,
            marker_color=color, showlegend=True
        ))

    fig.update_layout(
        **BASE_LAYOUT,
        title   = dict(text='Distribucion de Picos por Hora del Dia',
                       font=dict(size=16)),
        xaxis   = dict(title='Hora', gridcolor=COLORS['grid']),
        yaxis   = dict(title='Numero de picos', gridcolor=COLORS['grid']),
        height  = 380,
        barmode = 'overlay',
        legend  = dict(orientation='h', y=-0.25),
    )
    return fig


# =============================================================================
# 5. MAPA DE CALOR: MES x HORA
# =============================================================================

def chart_peaks_heatmap(data: dict) -> go.Figure:
    heatmap = data.get('heatmap', {})
    if not heatmap or not heatmap.get('meses'):
        fig = go.Figure()
        fig.add_annotation(text="No hay suficientes datos para el mapa de calor",
                           xref='paper', yref='paper', x=0.5, y=0.5,
                           showarrow=False,
                           font=dict(size=14, color=COLORS['text_light']))
        fig.update_layout(**BASE_LAYOUT, height=300)
        return fig

    meses          = heatmap['meses']
    horas          = heatmap['horas']
    etiquetas_hora = [f"{h:02d}:00" for h in horas]

    # Construir matriz Z (meses x horas)
    z = []
    for mes in meses:
        fila = [heatmap['valores'].get(mes, {}).get(hora, 0) for hora in horas]
        z.append(fila)

    fig = go.Figure(go.Heatmap(
        z              = z,
        x              = etiquetas_hora,
        y              = [m.capitalize() for m in meses],
        colorscale     = [
            [0.0,  'white'],
            [0.01, '#FEF2F2'],
            [0.3,  '#FCA5A5'],
            [0.6,  '#F87171'],
            [0.8,  '#EF4444'],
            [1.0,  '#B91C1C'],
        ],
        colorbar       = dict(title='Picos', titleside='right', thickness=15),
        hovertemplate  = '<b>%{y} — %{x}</b><br>Picos: %{z}<extra></extra>',
        zsmooth        = False,
    ))

    fig.update_layout(
        **BASE_LAYOUT,
        title  = dict(text='Mapa de Calor: Picos por Mes y Hora',
                      font=dict(size=16)),
        xaxis  = dict(title='Hora del dia', gridcolor=COLORS['grid']),
        yaxis  = dict(title='Mes', gridcolor=COLORS['grid']),
        height = 420,
    )
    return fig


# =============================================================================
# 6. LABORABLE VS FIN DE SEMANA
# =============================================================================

def chart_peaks_day_type(data: dict) -> go.Figure:
    dt = data.get('by_day_type', {})
    if not dt:
        return go.Figure()

    labels  = ['Laborable', 'Fin de semana / Festivo']
    valores = [dt['laborable']['num_picos'], dt['fin_de_semana']['num_picos']]
    colores = [COLORS['laborable'], COLORS['finde']]

    fig = go.Figure(go.Pie(
        labels        = labels,
        values        = valores,
        hole          = 0.55,
        marker        = dict(colors=colores, line=dict(color='white', width=2)),
        hovertemplate = '<b>%{label}</b><br>%{value} picos<br>%{percent}<extra></extra>',
        textinfo      = 'label+percent',
        textfont      = dict(size=12),
    ))

    fig.update_layout(
        **BASE_LAYOUT,
        title  = dict(text='Picos: Laborable vs Fin de Semana',
                      font=dict(size=16)),
        height = 360,
    )
    return fig


# =============================================================================
# 7. POR PERIODO DE POTENCIA P1/P2
# =============================================================================

def chart_peaks_by_period(data: dict) -> go.Figure:
    bp = data.get('by_period', {})
    if not bp:
        return go.Figure()

    labels  = ['P1 (Laborable 8h-24h)', 'P2 (Nocturno / Finde)']
    valores = [bp['P1']['num_picos'], bp['P2']['num_picos']]
    colores = [COLORS['p1'], COLORS['p2']]

    fig = go.Figure(go.Pie(
        labels        = labels,
        values        = valores,
        hole          = 0.55,
        marker        = dict(colors=colores, line=dict(color='white', width=2)),
        hovertemplate = '<b>%{label}</b><br>%{value} picos<br>%{percent}<extra></extra>',
        textinfo      = 'label+percent',
        textfont      = dict(size=12),
    ))

    fig.update_layout(
        **BASE_LAYOUT,
        title  = dict(text='Picos por Periodo de Potencia',
                      font=dict(size=16)),
        height = 360,
    )
    return fig


# =============================================================================
# FUNCION PRINCIPAL
# =============================================================================

def generate_peaks_charts(data: dict) -> dict:
    """
    Genera todos los graficos de la Pagina 3 (Analisis de picos criticos).

    Args:
        data: Resultado de run_peaks_analysis()

    Returns:
        Diccionario con todos los Figure de Plotly
    """
    print("Generando graficos de picos criticos...")

    graficos = {
        'kpis':       chart_peaks_kpis(data),
        'top10':      chart_top10_table(data),
        'by_month':   chart_peaks_by_month(data),
        'by_hour':    chart_peaks_by_hour(data),
        'heatmap':    chart_peaks_heatmap(data),
        'day_type':   chart_peaks_day_type(data),
        'by_period':  chart_peaks_by_period(data),
    }

    print(f"  {len(graficos)} graficos generados correctamente.")
    return graficos
