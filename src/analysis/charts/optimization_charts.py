# =============================================================================
# src/analysis/charts/optimization_charts.py
# Graficos de optimizacion de potencia — Version 3.0
# =============================================================================

import plotly.graph_objects as go
from plotly.subplots import make_subplots

COLORS = {
    'primary':     '#2563EB',
    'secondary':   '#3B82F6',
    'ok':          '#2563EB',
    'exceso':      '#EF4444',
    'equilibrada': '#F59E0B',
    'segura':      '#10B981',
    'background':  '#F8FAFF',
    'grid':        '#E2E8F0',
    'text':        '#1E293B',
    'text_light':  '#64748B',
}

BASE_LAYOUT = dict(
    font          = dict(family='Segoe UI, Arial, sans-serif', color='#1E293B'),
    paper_bgcolor = 'white',
    plot_bgcolor  = '#F8FAFF',
    margin        = dict(l=40, r=40, t=60, b=40),
    hoverlabel    = dict(bgcolor='white', font_size=13),
)


# =============================================================================
# 1. KPIs
# =============================================================================

def chart_optimization_kpis(data: dict) -> go.Figure:
    kpis = data.get('kpis', {})
    if not kpis:
        return go.Figure()

    fig = go.Figure()

    valores = [
        ('P1 Actual',           kpis['contracted_p1'],   ',.2f', ' kW', COLORS['primary']),
        ('P2 Actual',           kpis['contracted_p2'],   ',.2f', ' kW', COLORS['primary']),
        ('Meses exceso P1',     kpis['meses_exceso_p1'], '',     ' mes', COLORS['exceso']),
        ('Meses exceso P2',     kpis['meses_exceso_p2'], '',     ' mes', COLORS['exceso']),
        ('Pico maximo Punta',   kpis['max_pico_punta'],  ',.3f', ' kW', COLORS['secondary']),
        ('Pico maximo Valle',   kpis['max_pico_valle'],  ',.3f', ' kW', COLORS['secondary']),
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

    if kpis.get('tiene_exceso'):
        mes_p1 = kpis.get('mes_max_exceso_p1', '')
        mes_p2 = kpis.get('mes_max_exceso_p2', '')
        estado = f"⚠️ Con la potencia actual hay excesos"
        if mes_p1:
            estado += f" — Mayor exceso P1 en {mes_p1.capitalize()}"
        color_estado = COLORS['exceso']
    else:
        estado = "✅ Sin excesos registrados con la potencia actual"
        color_estado = COLORS['segura']

    fig.update_layout(
        **BASE_LAYOUT,
        height = 150,
        title  = dict(text=estado, font=dict(size=13, color=color_estado), x=0.5)
    )
    return fig


# =============================================================================
# 2. PICOS MENSUALES VS POTENCIA CONTRATADA
# =============================================================================

def chart_monthly_peaks(data: dict) -> go.Figure:
    """
    Grafico principal: picos reales de cada mes vs potencia contratada.
    Barras rojas = meses que superan la potencia contratada.
    Barras azules = meses dentro del limite.
    Dos subplots: Punta (P1) y Valle (P2).
    """
    picos = data.get('picos_mensuales', [])
    if not picos:
        return go.Figure()

    meses        = [p['mes'].capitalize() for p in picos]
    vals_punta   = [p['pico_punta'] for p in picos]
    vals_valle   = [p['pico_valle'] for p in picos]
    colores_punta = [COLORS['exceso'] if p['supera_p1'] else COLORS['ok'] for p in picos]
    colores_valle = [COLORS['exceso'] if p['supera_p2'] else COLORS['ok'] for p in picos]

    contracted_p1 = data.get('contracted_p1', 0)
    contracted_p2 = data.get('contracted_p2', 0)

    fig = make_subplots(
        rows=1, cols=2,
        subplot_titles=['Punta — Periodo P1 (Laborable 8h-24h)',
                        'Valle — Periodo P2 (Nocturno / Finde)'],
        horizontal_spacing=0.08
    )

    # Punta
    fig.add_trace(go.Bar(
        x             = meses,
        y             = vals_punta,
        name          = 'Pico Punta',
        marker_color  = colores_punta,
        hovertemplate = '<b>%{x}</b><br>Pico Punta: %{y:.3f} kW<extra></extra>',
        text          = [f"{v:.2f}" for v in vals_punta],
        textposition  = 'outside',
        textfont      = dict(size=10),
    ), row=1, col=1)

    if contracted_p1 > 0:
        fig.add_hline(
            y=contracted_p1, line_dash='dash', line_color=COLORS['exceso'],
            line_width=2,
            annotation_text=f'Contratada P1: {contracted_p1} kW',
            annotation_position='top right',
            annotation_font=dict(color=COLORS['exceso'], size=11),
            row=1, col=1
        )

    # Valle
    fig.add_trace(go.Bar(
        x             = meses,
        y             = vals_valle,
        name          = 'Pico Valle',
        marker_color  = colores_valle,
        hovertemplate = '<b>%{x}</b><br>Pico Valle: %{y:.3f} kW<extra></extra>',
        text          = [f"{v:.2f}" for v in vals_valle],
        textposition  = 'outside',
        textfont      = dict(size=10),
    ), row=1, col=2)

    if contracted_p2 > 0:
        fig.add_hline(
            y=contracted_p2, line_dash='dash', line_color=COLORS['exceso'],
            line_width=2,
            annotation_text=f'Contratada P2: {contracted_p2} kW',
            annotation_position='top right',
            annotation_font=dict(color=COLORS['exceso'], size=11),
            row=1, col=2
        )

    # Leyenda
    fig.add_trace(go.Bar(x=[None], y=[None], name='Dentro del limite',
                         marker_color=COLORS['ok'], showlegend=True))
    fig.add_trace(go.Bar(x=[None], y=[None], name='Supera potencia contratada',
                         marker_color=COLORS['exceso'], showlegend=True))

    fig.update_layout(
        **BASE_LAYOUT,
        title   = dict(text='Picos Mensuales vs Potencia Contratada',
                       font=dict(size=16)),
        height  = 450,
        barmode = 'group',
        legend  = dict(orientation='h', y=-0.15),
        showlegend = True,
    )
    fig.update_yaxes(title_text='kW', gridcolor=COLORS['grid'], row=1, col=1)
    fig.update_yaxes(title_text='kW', gridcolor=COLORS['grid'], row=1, col=2)
    return fig


# =============================================================================
# 3. TABLA DE MESES CON EXCESO
# =============================================================================

def chart_exceso_table(data: dict) -> go.Figure:
    """
    Tabla simple con solo los meses donde hubo exceso.
    """
    tabla = data.get('tabla_excesos', [])

    if not tabla:
        fig = go.Figure()
        fig.add_annotation(
            text="✅ No hay excesos con la potencia contratada actual",
            xref='paper', yref='paper', x=0.5, y=0.5,
            showarrow=False,
            font=dict(size=16, color=COLORS['segura'],
                      family='Segoe UI, Arial, sans-serif'),
            bgcolor='#ECFDF5', bordercolor=COLORS['segura'],
            borderwidth=2, borderpad=20,
        )
        fig.update_layout(**BASE_LAYOUT, height=150,
                          xaxis=dict(visible=False), yaxis=dict(visible=False))
        return fig

    colores_fila = []
    for row in tabla:
        if row['supera_p1'] and row['supera_p2']:
            colores_fila.append('#FEF2F2')
        elif row['supera_p1'] or row['supera_p2']:
            colores_fila.append('#FFF7ED')
        else:
            colores_fila.append('white')

    fig = go.Figure(go.Table(
        header=dict(
            values=['Mes', 'Pico Punta', 'Exceso P1', 'Pico Valle', 'Exceso P2'],
            fill_color=COLORS['exceso'],
            font=dict(color='white', size=13,
                      family='Segoe UI, Arial, sans-serif'),
            align='center', height=36,
        ),
        cells=dict(
            values=[
                [r['mes']        for r in tabla],
                [r['pico_punta'] for r in tabla],
                [r['exceso_p1']  for r in tabla],
                [r['pico_valle'] for r in tabla],
                [r['exceso_p2']  for r in tabla],
            ],
            fill_color=[colores_fila] * 5,
            font=dict(size=13, family='Segoe UI, Arial, sans-serif',
                      color=[
                          [COLORS['text']]  * len(tabla),
                          [COLORS['text']]  * len(tabla),
                          [COLORS['exceso'] if r['supera_p1'] else COLORS['text']
                           for r in tabla],
                          [COLORS['text']]  * len(tabla),
                          [COLORS['exceso'] if r['supera_p2'] else COLORS['text']
                           for r in tabla],
                      ]),
            align='center', height=32,
        )
    ))

    fig.update_layout(
        **BASE_LAYOUT,
        title=dict(text='Meses con Exceso sobre la Potencia Contratada',
                   font=dict(size=16)),
        height=80 + len(tabla) * 36,
    )
    return fig


# =============================================================================
# 4. OPCIONES SUGERIDAS — dos tarjetas claras
# =============================================================================

def chart_suggested_options(data: dict) -> go.Figure:
    opciones = data.get('opciones_sugeridas', {})
    if not opciones:
        return go.Figure()

    eq  = opciones.get('equilibrada', {})
    seg = opciones.get('segura', {})

    fig = go.Figure()

    # Opcion equilibrada
    fig.add_annotation(
        text=(
            f"<b>{eq.get('titulo','')}</b><br><br>"
            f"{eq.get('descripcion','')}"
        ),
        xref='paper', yref='paper', x=0.25, y=0.55,
        showarrow=False,
        font=dict(size=13, color='#78350F',
                  family='Segoe UI, Arial, sans-serif'),
        align='left',
        bgcolor='#FFFBEB', bordercolor='#F59E0B',
        borderwidth=2, borderpad=20,
        width=400,
    )

    # Opcion segura
    fig.add_annotation(
        text=(
            f"<b>{seg.get('titulo','')}</b><br><br>"
            f"{seg.get('descripcion','')}"
        ),
        xref='paper', yref='paper', x=0.75, y=0.55,
        showarrow=False,
        font=dict(size=13, color='#064E3B',
                  family='Segoe UI, Arial, sans-serif'),
        align='left',
        bgcolor='#ECFDF5', bordercolor='#10B981',
        borderwidth=2, borderpad=20,
        width=400,
    )

    fig.update_layout(
        **BASE_LAYOUT,
        title=dict(text='Opciones Sugeridas', font=dict(size=16)),
        height=280,
        xaxis=dict(visible=False),
        yaxis=dict(visible=False),
    )
    return fig


# =============================================================================
# FUNCION PRINCIPAL
# =============================================================================

def generate_optimization_charts(data: dict) -> dict:
    print("Generando graficos de optimizacion...")

    graficos = {
        'kpis':     chart_optimization_kpis(data),
        'picos':    chart_monthly_peaks(data),
        'excesos':  chart_exceso_table(data),
        'opciones': chart_suggested_options(data),
    }

    print(f"  {len(graficos)} graficos generados correctamente.")
    return graficos
