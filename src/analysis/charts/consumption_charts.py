# =============================================================================
# src/analysis/charts/consumption_charts.py
# Graficos de consumo electrico con Plotly
# Version: 1.0
#
# Pagina 1 del informe: Perfil de consumo general
#
# Estilo: Azul corporativo (inspirado en Power BI)
# Idioma: Espanol
#
# Graficos incluidos:
#   1. KPIs principales (tarjetas)
#   2. Consumo por mes (barras)
#   3. Consumo promedio por hora (barras)
#   4. Consumo por dia de la semana (barras)
#   5. Consumo promedio por dia del mes (linea)
#   6. Consumo por hora y fecha (linea detallada)
#   7. Desglose por periodo P1/P2/P3 (dona)
#   8. Laborable vs fin de semana (dona)
#   9. Por temporada (barras horizontales)
#  10. Consumo nocturno vs diurno (dona)
# =============================================================================

import plotly.graph_objects as go
import plotly.express as px
from plotly.subplots import make_subplots

import sys
sys.path.append('../..')
from src.models.internal_data_model import ConsumptionSummary


# =============================================================================
# PALETA DE COLORES CORPORATIVA
# =============================================================================

COLORS = {
    'primary':      '#2563EB',   # Azul principal
    'secondary':    '#3B82F6',   # Azul medio
    'light':        '#93C5FD',   # Azul claro
    'accent':       '#1D4ED8',   # Azul oscuro
    'p1':           '#1D4ED8',   # P1 Punta — azul oscuro
    'p2':           '#3B82F6',   # P2 Llano — azul medio
    'p3':           '#93C5FD',   # P3 Valle — azul claro
    'laborable':    '#2563EB',   # Laborable
    'finde':        '#93C5FD',   # Fin de semana
    'verano':       '#F59E0B',   # Verano — amarillo
    'invierno':     '#6366F1',   # Invierno — morado
    'entretiempo':  '#10B981',   # Entretiempo — verde
    'nocturno':     '#1E3A5F',   # Nocturno — azul muy oscuro
    'diurno':       '#60A5FA',   # Diurno — azul suave
    'background':   '#F8FAFF',   # Fondo
    'grid':         '#E2E8F0',   # Lineas de cuadricula
    'text':         '#1E293B',   # Texto principal
    'text_light':   '#64748B',   # Texto secundario
}

# Layout base reutilizable
BASE_LAYOUT = dict(
    font        = dict(family='Segoe UI, Arial, sans-serif', color=COLORS['text']),
    paper_bgcolor = 'white',
    plot_bgcolor  = COLORS['background'],
    margin        = dict(l=40, r=40, t=60, b=40),
    hoverlabel    = dict(bgcolor='white', font_size=13),
)


# =============================================================================
# 1. TARJETAS DE KPIs
# =============================================================================

def chart_kpis(summary: ConsumptionSummary) -> go.Figure:
    """
    Muestra los 3 KPIs principales como tarjetas numericas.
    """
    fig = go.Figure()

    kpis = [
        ('Consumo Total',          f"{summary.total_kwh:,.1f} kWh",   ''),
        ('Promedio Diario',        f"{summary.avg_daily_kwh:,.2f} kWh", ''),
        ('Promedio por Hora',      f"{summary.avg_hourly_kwh:,.3f} kWh", ''),
    ]

    for i, (titulo, valor, _) in enumerate(kpis):
        fig.add_trace(go.Indicator(
            mode   = "number",
            value  = float(valor.split()[0].replace(',', '').replace('.', '').replace(',', '.')),
            title  = dict(text=titulo, font=dict(size=14, color=COLORS['text_light'])),
            number = dict(
                suffix    = ' kWh',
                font      = dict(size=28, color=COLORS['primary']),
                valueformat = ',.2f'
            ),
            domain = dict(x=[i/3, (i+1)/3], y=[0, 1])
        ))

    fig.update_layout(
        **BASE_LAYOUT,
        height = 150,
        title  = dict(
            text     = f"Periodo analizado: {summary.date_from.strftime('%d/%m/%Y')} "
                       f"— {summary.date_to.strftime('%d/%m/%Y')}",
            font     = dict(size=13, color=COLORS['text_light']),
            x        = 0.5
        )
    )
    return fig


# =============================================================================
# 2. CONSUMO POR MES
# =============================================================================

def chart_by_month(summary: ConsumptionSummary) -> go.Figure:
    """
    Barras verticales con el consumo total por mes.
    """
    meses  = list(summary.by_month.keys())
    totals = [summary.by_month[m]['total_kwh'] for m in meses]

    fig = go.Figure(go.Bar(
        x           = meses,
        y           = totals,
        marker_color = COLORS['primary'],
        marker_line  = dict(color=COLORS['accent'], width=1),
        hovertemplate = '<b>%{x}</b><br>Consumo: %{y:.2f} kWh<extra></extra>',
        text         = [f"{v:.1f}" for v in totals],
        textposition = 'outside',
        textfont     = dict(size=11, color=COLORS['text'])
    ))

    fig.update_layout(
        **BASE_LAYOUT,
        title  = dict(text='Consumo Total por Mes', font=dict(size=16)),
        xaxis  = dict(title='Mes', gridcolor=COLORS['grid']),
        yaxis  = dict(title='kWh', gridcolor=COLORS['grid']),
        height = 380,
    )
    return fig


# =============================================================================
# 3. CONSUMO PROMEDIO POR HORA
# =============================================================================

def chart_by_hour(summary: ConsumptionSummary) -> go.Figure:
    """
    Barras con el consumo PROMEDIO por hora del dia (0-23).
    Incluye linea de promedio global para referencia.
    """
    horas  = sorted(summary.by_hour.keys())
    avgs   = [summary.by_hour[h]['avg_kwh'] for h in horas]
    avg_global = summary.avg_hourly_kwh

    fig = go.Figure()

    # Barras de promedio por hora
    fig.add_trace(go.Bar(
        x             = [f"{h:02d}:00" for h in horas],
        y             = avgs,
        name          = 'Promedio por hora',
        marker_color  = COLORS['secondary'],
        marker_line   = dict(color=COLORS['accent'], width=0.5),
        hovertemplate = '<b>%{x}</b><br>Promedio: %{y:.3f} kWh<extra></extra>',
    ))

    # Linea de promedio global
    fig.add_hline(
        y           = avg_global,
        line_dash   = 'dash',
        line_color  = COLORS['accent'],
        annotation_text = f'Promedio global: {avg_global:.3f} kWh',
        annotation_position = 'top right',
        annotation_font     = dict(color=COLORS['accent'], size=11)
    )

    fig.update_layout(
        **BASE_LAYOUT,
        title  = dict(text='Consumo Promedio por Hora del Dia', font=dict(size=16)),
        xaxis  = dict(title='Hora', gridcolor=COLORS['grid']),
        yaxis  = dict(title='kWh (promedio)', gridcolor=COLORS['grid']),
        height = 380,
    )
    return fig


# =============================================================================
# 4. CONSUMO POR DIA DE LA SEMANA
# =============================================================================

def chart_by_day_of_week(summary: ConsumptionSummary) -> go.Figure:
    """
    Barras con consumo total y promedio por dia de la semana.
    """
    dias   = list(summary.by_day_of_week.keys())
    totals = [summary.by_day_of_week[d]['total_kwh'] for d in dias]
    avgs   = [summary.by_day_of_week[d]['avg_kwh'] for d in dias]

    # Colores diferenciados para fin de semana
    colores = [
        COLORS['finde'] if d in ['sabado', 'domingo'] else COLORS['primary']
        for d in dias
    ]

    fig = make_subplots(specs=[[{"secondary_y": True}]])

    fig.add_trace(go.Bar(
        x             = dias,
        y             = totals,
        name          = 'Consumo total',
        marker_color  = colores,
        hovertemplate = '<b>%{x}</b><br>Total: %{y:.2f} kWh<extra></extra>',
    ), secondary_y=False)

    fig.add_trace(go.Scatter(
        x             = dias,
        y             = avgs,
        name          = 'Promedio por hora',
        mode          = 'lines+markers',
        line          = dict(color=COLORS['accent'], width=2),
        marker        = dict(size=7),
        hovertemplate = '<b>%{x}</b><br>Promedio: %{y:.3f} kWh/h<extra></extra>',
    ), secondary_y=True)

    fig.update_layout(
        **BASE_LAYOUT,
        title  = dict(text='Consumo por Dia de la Semana', font=dict(size=16)),
        height = 380,
        legend = dict(orientation='h', y=-0.2),
    )
    fig.update_yaxes(title_text='kWh total', gridcolor=COLORS['grid'],
                     secondary_y=False)
    fig.update_yaxes(title_text='kWh promedio/hora', secondary_y=True)
    return fig


# =============================================================================
# 5. CONSUMO PROMEDIO POR DIA DEL MES
# =============================================================================

def chart_by_day_of_month(summary: ConsumptionSummary) -> go.Figure:
    """
    Linea con el consumo promedio para cada dia del mes (1-31).
    """
    dias = sorted(summary.by_day_of_month.keys())
    avgs = [summary.by_day_of_month[d]['avg_kwh'] for d in dias]

    fig = go.Figure(go.Scatter(
        x             = dias,
        y             = avgs,
        mode          = 'lines+markers',
        line          = dict(color=COLORS['primary'], width=2),
        marker        = dict(size=5, color=COLORS['primary']),
        fill          = 'tozeroy',
        fillcolor     = 'rgba(37, 99, 235, 0.1)',
        hovertemplate = '<b>Dia %{x}</b><br>Promedio: %{y:.3f} kWh<extra></extra>',
    ))

    fig.update_layout(
        **BASE_LAYOUT,
        title  = dict(text='Consumo Promedio por Dia del Mes', font=dict(size=16)),
        xaxis  = dict(title='Dia del mes', dtick=1, gridcolor=COLORS['grid']),
        yaxis  = dict(title='kWh (promedio)', gridcolor=COLORS['grid']),
        height = 350,
    )
    return fig


# =============================================================================
# 6. CONSUMO POR HORA Y FECHA (detallado)
# =============================================================================

def chart_by_hour_and_date(summary: ConsumptionSummary,
                            fecha_inicio: str = None,
                            fecha_fin: str = None) -> go.Figure:
    """
    Grafico de linea con el consumo horario real.
    Filtrable por rango de fechas (interactivo en web).

    Args:
        fecha_inicio: 'YYYY-MM-DD' (opcional, filtra el rango)
        fecha_fin:    'YYYY-MM-DD' (opcional, filtra el rango)
    """
    datos = summary.by_hour_and_date
    fechas = sorted(datos.keys())
    valores = [datos[f] for f in fechas]

    # Filtrar por rango si se especifica
    if fecha_inicio:
        fechas  = [f for f in fechas if f >= fecha_inicio]
        valores = [datos[f] for f in fechas]
    if fecha_fin:
        fechas  = [f for f in fechas if f <= fecha_fin + ' 23:00']
        valores = [datos[f] for f in fechas]

    fig = go.Figure(go.Scatter(
        x             = fechas,
        y             = valores,
        mode          = 'lines',
        line          = dict(color=COLORS['primary'], width=1),
        fill          = 'tozeroy',
        fillcolor     = 'rgba(37, 99, 235, 0.08)',
        hovertemplate = '<b>%{x}</b><br>Consumo: %{y:.3f} kWh<extra></extra>',
    ))

    fig.update_layout(
        **BASE_LAYOUT,
        title  = dict(text='Consumo por Hora y Fecha', font=dict(size=16)),
        xaxis  = dict(
            title        = 'Fecha',
            gridcolor    = COLORS['grid'],
            rangeslider  = dict(visible=True),   # Slider para zoom interactivo
            type         = 'date'
        ),
        yaxis  = dict(title='kWh', gridcolor=COLORS['grid']),
        height = 420,
    )
    return fig


# =============================================================================
# 7. DESGLOSE POR PERIODO P1/P2/P3
# =============================================================================

def chart_by_period(summary: ConsumptionSummary) -> go.Figure:
    """
    Dona con el desglose de consumo por periodo energetico.
    """
    periodos = ['P1 Punta', 'P2 Llano', 'P3 Valle']
    valores  = [
        summary.by_energy_period['P1'].total_kwh,
        summary.by_energy_period['P2'].total_kwh,
        summary.by_energy_period['P3'].total_kwh,
    ]
    colores = [COLORS['p1'], COLORS['p2'], COLORS['p3']]

    fig = go.Figure(go.Pie(
        labels            = periodos,
        values            = valores,
        hole              = 0.55,
        marker            = dict(colors=colores,
                                 line=dict(color='white', width=2)),
        hovertemplate     = '<b>%{label}</b><br>%{value:.2f} kWh<br>%{percent}<extra></extra>',
        textinfo          = 'label+percent',
        textfont          = dict(size=12),
    ))

    fig.update_layout(
        **BASE_LAYOUT,
        title  = dict(text='Consumo por Periodo Energetico', font=dict(size=16)),
        height = 380,
        annotations = [dict(
            text      = f"{summary.total_kwh:.0f}<br>kWh",
            x=0.5, y=0.5,
            font_size = 18,
            font_color = COLORS['primary'],
            showarrow = False
        )]
    )
    return fig


# =============================================================================
# 8. LABORABLE VS FIN DE SEMANA
# =============================================================================

def chart_by_day_type(summary: ConsumptionSummary) -> go.Figure:
    """
    Dona comparando consumo en dias laborables vs fin de semana y festivos.
    """
    dt = summary.by_day_type
    labels  = ['Laborable', 'Fin de semana / Festivo']
    valores = [dt['laborable']['total_kwh'], dt['fin_de_semana']['total_kwh']]
    colores = [COLORS['laborable'], COLORS['finde']]

    fig = go.Figure(go.Pie(
        labels        = labels,
        values        = valores,
        hole          = 0.55,
        marker        = dict(colors=colores, line=dict(color='white', width=2)),
        hovertemplate = '<b>%{label}</b><br>%{value:.2f} kWh<br>%{percent}<extra></extra>',
        textinfo      = 'label+percent',
        textfont      = dict(size=12),
    ))

    fig.update_layout(
        **BASE_LAYOUT,
        title  = dict(text='Laborable vs Fin de Semana', font=dict(size=16)),
        height = 380,
    )
    return fig


# =============================================================================
# 9. CONSUMO POR TEMPORADA
# =============================================================================

def chart_by_season(summary: ConsumptionSummary) -> go.Figure:
    """
    Barras horizontales con consumo por temporada.
    """
    bs = summary.by_season
    temporadas = list(bs.keys())
    totals     = [bs[t]['total_kwh'] for t in temporadas]
    colores    = [
        COLORS.get(t, COLORS['primary']) for t in temporadas
    ]

    fig = go.Figure(go.Bar(
        x             = totals,
        y             = [t.capitalize() for t in temporadas],
        orientation   = 'h',
        marker_color  = colores,
        text          = [f"{v:.1f} kWh ({bs[t]['pct_of_total']}%)"
                         for t, v in zip(temporadas, totals)],
        textposition  = 'outside',
        hovertemplate = '<b>%{y}</b><br>%{x:.2f} kWh<extra></extra>',
    ))

    fig.update_layout(
        **BASE_LAYOUT,
        title  = dict(text='Consumo por Temporada', font=dict(size=16)),
        xaxis  = dict(title='kWh', gridcolor=COLORS['grid']),
        yaxis  = dict(title=''),
        height = 300,
    )
    return fig


# =============================================================================
# 10. CONSUMO NOCTURNO VS DIURNO
# =============================================================================

def chart_nocturno(summary: ConsumptionSummary) -> go.Figure:
    """
    Dona comparando consumo nocturno (0h-8h) vs diurno (8h-24h).
    """
    noc = summary.nocturno
    diurno_kwh = _round2(summary.total_kwh - noc['total_kwh'])

    fig = go.Figure(go.Pie(
        labels        = ['Nocturno (0h-8h)', 'Diurno (8h-24h)'],
        values        = [noc['total_kwh'], diurno_kwh],
        hole          = 0.55,
        marker        = dict(
            colors    = [COLORS['nocturno'], COLORS['diurno']],
            line      = dict(color='white', width=2)
        ),
        hovertemplate = '<b>%{label}</b><br>%{value:.2f} kWh<br>%{percent}<extra></extra>',
        textinfo      = 'label+percent',
        textfont      = dict(size=12),
    ))

    fig.update_layout(
        **BASE_LAYOUT,
        title  = dict(text='Consumo Nocturno vs Diurno', font=dict(size=16)),
        height = 380,
        annotations = [dict(
            text      = f"{noc['pct_of_total']}%<br>nocturno",
            x=0.5, y=0.5,
            font_size  = 16,
            font_color = COLORS['nocturno'],
            showarrow  = False
        )]
    )
    return fig


# =============================================================================
# HELPER
# =============================================================================

def _round2(val: float) -> float:
    return round(val, 2)


# =============================================================================
# FUNCION PRINCIPAL — genera todos los graficos de la pagina 1
# =============================================================================

def generate_consumption_charts(summary: ConsumptionSummary) -> dict:
    """
    Genera todos los graficos de la Pagina 1 (Perfil de consumo general).

    Returns:
        Diccionario con todos los objetos Figure de Plotly listos para
        mostrar en web (interactivos) o exportar a PDF (estaticos).

    Ejemplo de uso en Colab:
        charts = generate_consumption_charts(analysis.consumption_summary)
        charts['by_month'].show()
        charts['by_hour'].show()

    Ejemplo de uso en web (Flask/FastAPI):
        charts = generate_consumption_charts(summary)
        html = charts['by_month'].to_html(full_html=False)
    """
    print("Generando graficos de consumo...")

    graficos = {
        'kpis':            chart_kpis(summary),
        'by_month':        chart_by_month(summary),
        'by_hour':         chart_by_hour(summary),
        'by_day_of_week':  chart_by_day_of_week(summary),
        'by_day_of_month': chart_by_day_of_month(summary),
        'by_hour_and_date':chart_by_hour_and_date(summary),
        'by_period':       chart_by_period(summary),
        'by_day_type':     chart_by_day_type(summary),
        'by_season':       chart_by_season(summary),
        'nocturno':        chart_nocturno(summary),
    }

    print(f"  {len(graficos)} graficos generados correctamente.")
    return graficos
