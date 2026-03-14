# =============================================================================
# src/analysis/charts/power_charts.py
# Graficos de potencia electrica con Plotly
# Version: 1.1
# =============================================================================

import plotly.graph_objects as go
from plotly.subplots import make_subplots
import numpy as np

import sys
sys.path.append('../..')
from src.models.internal_data_model import PowerAnalysis


COLORS = {
    'primary':      '#2563EB',
    'secondary':    '#3B82F6',
    'light':        '#93C5FD',
    'accent':       '#1D4ED8',
    'danger':       '#EF4444',
    'warning':      '#F59E0B',
    'success':      '#10B981',
    'punta':        '#1D4ED8',
    'valle':        '#93C5FD',
    'potmax':       '#EF4444',
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

def _round2(val):
    return round(val, 2)


def chart_power_kpis(power: PowerAnalysis) -> go.Figure:
    fig = go.Figure()
    kpis = [
        ('Maximo Real',        power.max_power_kw,      ',.3f', ' kW'),
        ('P99',                power.p99_power_kw,      ',.4f', ' kW'),
        ('Factor de Carga',    power.load_factor,       ',.3f', ''),
        ('Horas sobre umbral', power.hours_exceeds_2kw, ',d',   ' h'),
        ('% sobre umbral',     power.pct_exceeds_2kw,   ',.2f', '%'),
    ]
    for i, (titulo, valor, fmt, sufijo) in enumerate(kpis):
        fig.add_trace(go.Indicator(
            mode   = "number",
            value  = float(valor),
            title  = dict(text=titulo, font=dict(size=13, color=COLORS['text_light'])),
            number = dict(suffix=sufijo, font=dict(size=24, color=COLORS['primary']),
                          valueformat=fmt),
            domain = dict(x=[i/5, (i+1)/5], y=[0, 1])
        ))
    fig.update_layout(
        **BASE_LAYOUT,
        height = 140,
        title  = dict(
            text  = f"Potencia contratada: P1={power.contracted_powers.p1} kW / "
                    f"P2={power.contracted_powers.p2} kW  |  "
                    f"Umbral analisis: {power.umbral_kw} kW",
            font  = dict(size=12, color=COLORS['text_light']),
            x     = 0.5
        )
    )
    return fig


def chart_daily_max_power(power: PowerAnalysis,
                           meses_filtro: list = None) -> go.Figure:
    datos = power.daily_max_power
    if meses_filtro:
        datos = {f: v for f, v in datos.items() if v['month_name'] in meses_filtro}

    fechas    = sorted(datos.keys())
    potencias = [datos[f]['max_kw'] for f in fechas]
    colores   = [
        COLORS['warning'] if datos[f]['is_holiday']
        else COLORS['light'] if datos[f]['is_weekend']
        else COLORS['primary']
        for f in fechas
    ]

    fig = go.Figure()
    fig.add_trace(go.Scatter(
        x=fechas, y=potencias, mode='lines+markers',
        name='Potencia maxima diaria',
        line=dict(color=COLORS['primary'], width=1.5),
        marker=dict(size=5, color=colores,
                    line=dict(color=COLORS['accent'], width=0.5)),
        hovertemplate='<b>%{x}</b><br>Potencia max: %{y:.3f} kW<extra></extra>',
    ))

    if power.contracted_powers.p1 > 0:
        fig.add_hline(y=power.contracted_powers.p1, line_dash='dash',
                      line_color=COLORS['danger'], line_width=1.5,
                      annotation_text=f'P1 contratada: {power.contracted_powers.p1} kW',
                      annotation_position='top right',
                      annotation_font=dict(color=COLORS['danger'], size=11))

    if power.contracted_powers.p2 > 0 and power.contracted_powers.p2 != power.contracted_powers.p1:
        fig.add_hline(y=power.contracted_powers.p2, line_dash='dot',
                      line_color=COLORS['warning'], line_width=1.5,
                      annotation_text=f'P2 contratada: {power.contracted_powers.p2} kW',
                      annotation_position='bottom right',
                      annotation_font=dict(color=COLORS['warning'], size=11))

    titulo_filtro = f" — {', '.join(meses_filtro)}" if meses_filtro else " — Año completo"
    fig.update_layout(
        **BASE_LAYOUT,
        title=dict(text=f'Potencia Maxima Dia a Dia{titulo_filtro}', font=dict(size=16)),
        xaxis=dict(title='Fecha', gridcolor=COLORS['grid'],
                   rangeslider=dict(visible=True), type='date'),
        yaxis=dict(title='kW (potencia media horaria)', gridcolor=COLORS['grid']),
        height=420,
    )
    return fig


def chart_heatmap(power: PowerAnalysis,
                  meses_filtro: list = None,
                  records: list = None) -> go.Figure:
    """
    Sin filtro o varios meses -> hora x dia 1-31
    Un solo mes               -> hora x fechas reales del mes
    """
    horas          = list(range(0, 24))
    etiquetas_hora = [f"{h:02d}:00" for h in horas]

    if meses_filtro and records:
        from src.analysis.power_engine import calculate_heatmap_filtered
        datos        = calculate_heatmap_filtered(records, meses_filtro)
        eje_x        = datos.get('eje_x', list(range(1, 32)))
        tipo         = datos.get('tipo', 'dia_mes')
        valores_dict = datos.get('valores', {})
    else:
        heatmap      = power.hourly_power_heatmap
        eje_x        = list(range(1, 32))
        tipo         = 'dia_mes'
        valores_dict = heatmap.get('valores', {})

    # Construir matriz Z
    z = []
    for hora in horas:
        fila = []
        for x in eje_x:
            val = valores_dict.get(hora, {}).get(x, None)
            fila.append(val)
        z.append(fila)

    # Etiquetas eje X
    if tipo == 'fecha_real':
        etiquetas_x = [x[8:] for x in eje_x]  # solo DD de YYYY-MM-DD
        titulo_x    = 'Dia del mes'
    else:
        etiquetas_x = eje_x
        titulo_x    = 'Dia del mes'

    # Titulo
    if meses_filtro and len(meses_filtro) == 1:
        titulo_filtro = f" — {meses_filtro[0].capitalize()} (fechas reales)"
    elif meses_filtro:
        titulo_filtro = f" — {', '.join(meses_filtro)}"
    else:
        titulo_filtro = " — Año completo"

    fig = go.Figure(go.Heatmap(
        z             = z,
        x             = etiquetas_x,
        y             = etiquetas_hora,
        colorscale    = [
            [0.0, '#EFF6FF'],
            [0.3, '#93C5FD'],
            [0.6, '#3B82F6'],
            [0.8, '#F97316'],
            [1.0, '#EF4444'],
        ],
        colorbar      = dict(title='kW', titleside='right', thickness=15),
        hovertemplate = '<b>Hora %{y} — Dia %{x}</b><br>Potencia media: %{z:.3f} kW<extra></extra>',
        zsmooth       = False,
    ))

    fig.update_layout(
        **BASE_LAYOUT,
        title  = dict(text=f'Mapa de Calor: Potencia por Hora y Dia{titulo_filtro}',
                      font=dict(size=16)),
        xaxis  = dict(title=titulo_x, gridcolor=COLORS['grid']),
        yaxis  = dict(title='Hora del dia', autorange='reversed',
                      gridcolor=COLORS['grid']),
        height = 550,
    )
    return fig


def chart_power_ranking(power: PowerAnalysis) -> go.Figure:
    ranking    = power.power_ranking
    n          = len(ranking)
    posiciones = list(range(1, n + 1))
    p99_idx    = int(n * 0.01)

    fig = go.Figure()
    fig.add_trace(go.Scatter(
        x=posiciones, y=ranking, mode='lines',
        name='Potencia',
        line=dict(color=COLORS['primary'], width=2),
        fill='tozeroy', fillcolor='rgba(37, 99, 235, 0.08)',
        hovertemplate='Ranking %{x}<br>Potencia: %{y:.3f} kW<extra></extra>',
    ))
    fig.add_vline(x=p99_idx, line_dash='dash', line_color=COLORS['danger'],
                  annotation_text=f'P99: {power.p99_power_kw:.3f} kW',
                  annotation_position='top right',
                  annotation_font=dict(color=COLORS['danger'], size=11))
    fig.add_hline(y=power.umbral_kw, line_dash='dot', line_color=COLORS['warning'],
                  annotation_text=f'Umbral: {power.umbral_kw} kW ({power.hours_exceeds_2kw}h)',
                  annotation_position='top left',
                  annotation_font=dict(color=COLORS['warning'], size=11))
    fig.update_layout(
        **BASE_LAYOUT,
        title=dict(text='Curva de Ranking de Potencia', font=dict(size=16)),
        xaxis=dict(title='Ranking (horas de mayor a menor potencia)',
                   gridcolor=COLORS['grid']),
        yaxis=dict(title='kW (potencia media horaria)', gridcolor=COLORS['grid']),
        height=380,
    )
    return fig


def chart_profile_interpretation(power: PowerAnalysis) -> go.Figure:
    color_map = {
        'estable':                ('#10B981', '#ECFDF5'),
        'moderadamente variable': ('#F59E0B', '#FFFBEB'),
        'muy variable':           ('#EF4444', '#FEF2F2'),
    }
    tipo        = getattr(power, 'perfil_tipo', 'estable')
    descripcion = getattr(power, 'perfil_descripcion', '')
    color_text, color_bg = color_map.get(tipo, (COLORS['primary'], COLORS['background']))

    fig = go.Figure()
    fig.add_annotation(
        text      = f"<b>Perfil: {tipo.upper()}</b><br><br>{descripcion}",
        xref='paper', yref='paper', x=0.5, y=0.6,
        showarrow = False,
        font      = dict(size=13, color=color_text,
                         family='Segoe UI, Arial, sans-serif'),
        align     = 'center',
        bgcolor   = color_bg,
        bordercolor = color_text,
        borderwidth = 2,
        borderpad   = 16,
    )
    for i, obs in enumerate(power.observations):
        fig.add_annotation(
            text=f"• {obs}", xref='paper', yref='paper',
            x=0.5, y=0.15 - (i * 0.12),
            showarrow=False,
            font=dict(size=11, color=COLORS['text'],
                      family='Segoe UI, Arial, sans-serif'),
            align='left',
        )
    fig.update_layout(
        **BASE_LAYOUT,
        title=dict(text='Interpretacion del Perfil de Potencia', font=dict(size=16)),
        height=300,
        xaxis=dict(visible=False),
        yaxis=dict(visible=False),
    )
    return fig


def chart_monthly_official_peaks(power: PowerAnalysis) -> go.Figure:
    max_by_month = getattr(power, 'max_by_month', {})

    if not max_by_month:
        fig = go.Figure()
        fig.add_annotation(text="No hay datos del CSV oficial",
                           xref='paper', yref='paper', x=0.5, y=0.5,
                           showarrow=False,
                           font=dict(size=14, color=COLORS['text_light']))
        fig.update_layout(**BASE_LAYOUT, height=300)
        return fig

    meses   = list(max_by_month.keys())
    punta   = [max_by_month[m].get('Punta',   0) for m in meses]
    valle   = [max_by_month[m].get('Valle',   0) for m in meses]
    pot_max = [max_by_month[m].get('Pot.Max', 0) for m in meses]

    fig = go.Figure()
    fig.add_trace(go.Bar(name='Punta', x=meses, y=punta,
                         marker_color=COLORS['punta'],
                         hovertemplate='<b>%{x} — Punta</b><br>%{y:.3f} kW<extra></extra>'))
    fig.add_trace(go.Bar(name='Valle', x=meses, y=valle,
                         marker_color=COLORS['valle'],
                         hovertemplate='<b>%{x} — Valle</b><br>%{y:.3f} kW<extra></extra>'))
    fig.add_trace(go.Bar(name='Pot.Max', x=meses, y=pot_max,
                         marker_color=COLORS['potmax'],
                         hovertemplate='<b>%{x} — Pot.Max</b><br>%{y:.3f} kW<extra></extra>'))

    fig.add_hline(y=power.recommended_p1_kw, line_dash='dash',
                  line_color=COLORS['success'],
                  annotation_text=f'Recomendada P1: {power.recommended_p1_kw} kW',
                  annotation_position='top left',
                  annotation_font=dict(color=COLORS['success'], size=11))

    if power.contracted_powers.p1 > 0:
        fig.add_hline(y=power.contracted_powers.p1, line_dash='dot',
                      line_color=COLORS['danger'],
                      annotation_text=f'Contratada P1: {power.contracted_powers.p1} kW',
                      annotation_position='top right',
                      annotation_font=dict(color=COLORS['danger'], size=11))

    fig.update_layout(
        **BASE_LAYOUT,
        title=dict(text='Pico Oficial Mensual por Periodo (CSV Distribuidora)',
                   font=dict(size=16)),
        barmode='group',
        xaxis=dict(title='Mes', gridcolor=COLORS['grid']),
        yaxis=dict(title='kW (pico real)', gridcolor=COLORS['grid']),
        height=420,
        legend=dict(orientation='h', y=-0.2),
    )
    return fig


def generate_power_charts(power: PowerAnalysis,
                           meses_filtro: list = None,
                           records: list = None) -> dict:
    print("Generando graficos de potencia...")
    graficos = {
        'kpis':             chart_power_kpis(power),
        'daily_max':        chart_daily_max_power(power, meses_filtro),
        'heatmap':          chart_heatmap(power, meses_filtro, records),
        'ranking':          chart_power_ranking(power),
        'profile':          chart_profile_interpretation(power),
        'monthly_official': chart_monthly_official_peaks(power),
    }
    print(f"  {len(graficos)} graficos generados correctamente.")
    return graficos
