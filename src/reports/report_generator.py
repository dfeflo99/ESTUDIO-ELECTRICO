# =============================================================================
# src/reports/report_generator.py
# Generador de informe PDF con ReportLab
# Version: 2.0 — parametros dinamicos desde el dashboard
#
# El PDF se genera con el estado actual del dashboard:
#   - Potencia contratada P1 y P2 seleccionada por el usuario
#   - Umbral de picos seleccionado
#   - Meses filtrados (si los hay)
#
# Estructura del PDF:
#   Pagina 1 — Portada
#   Pagina 2 — Perfil de consumo general
#   Pagina 3 — Perfil de potencia real
#   Pagina 4 — Analisis de picos criticos
#   Pagina 5 — Optimizacion de potencia contratada
#   Pagina 6 — Conclusiones
# =============================================================================

import os
import io
from datetime import datetime

from reportlab.lib.pagesizes import A4
from reportlab.lib.units import mm
from reportlab.lib import colors
from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
from reportlab.lib.enums import TA_CENTER, TA_LEFT
from reportlab.platypus import (
    SimpleDocTemplate, Paragraph, Spacer, Image,
    PageBreak, Table, TableStyle, HRFlowable
)

import sys
sys.path.append('../..')
from src.models.internal_data_model import ElectricityAnalysis
from src.analysis.peaks_engine import run_peaks_analysis
from src.analysis.optimization_engine import run_optimization_analysis
from src.analysis.charts.consumption_charts import generate_consumption_charts
from src.analysis.charts.power_charts import generate_power_charts
from src.analysis.charts.peaks_charts import generate_peaks_charts
from src.analysis.charts.optimization_charts import generate_optimization_charts


# =============================================================================
# COLORES CORPORATIVOS F2 ENERGY CONSULTING
# =============================================================================

ROJO        = colors.HexColor('#CC1F1F')
NARANJA     = colors.HexColor('#F5A623')
GRIS_OSCURO = colors.HexColor('#1E293B')
GRIS_CLARO  = colors.HexColor('#64748B')
GRIS_FONDO  = colors.HexColor('#F8FAFF')
BLANCO      = colors.white

PAGE_W, PAGE_H = A4
MARGIN = 20 * mm


# =============================================================================
# ESTILOS
# =============================================================================

def get_styles():
    styles = getSampleStyleSheet()

    styles.add(ParagraphStyle(
        name='F2Title', fontName='Helvetica-Bold', fontSize=28,
        textColor=ROJO, alignment=TA_CENTER, spaceAfter=6,
    ))
    styles.add(ParagraphStyle(
        name='F2Subtitle', fontName='Helvetica', fontSize=14,
        textColor=GRIS_CLARO, alignment=TA_CENTER, spaceAfter=4,
    ))
    styles.add(ParagraphStyle(
        name='F2SectionTitle', fontName='Helvetica-Bold', fontSize=16,
        textColor=ROJO, spaceBefore=10, spaceAfter=6,
    ))
    styles.add(ParagraphStyle(
        name='F2Body', fontName='Helvetica', fontSize=10,
        textColor=GRIS_OSCURO, spaceAfter=4, leading=14,
    ))
    styles.add(ParagraphStyle(
        name='F2Small', fontName='Helvetica', fontSize=8,
        textColor=GRIS_CLARO, spaceAfter=2,
    ))
    styles.add(ParagraphStyle(
        name='F2KPI_Label', fontName='Helvetica', fontSize=9,
        textColor=GRIS_CLARO, alignment=TA_CENTER,
    ))
    styles.add(ParagraphStyle(
        name='F2KPI_Value', fontName='Helvetica-Bold', fontSize=18,
        textColor=ROJO, alignment=TA_CENTER,
    ))
    styles.add(ParagraphStyle(
        name='F2Conclusion', fontName='Helvetica', fontSize=10,
        textColor=GRIS_OSCURO, spaceAfter=6, leading=16, leftIndent=10,
    ))
    return styles


# =============================================================================
# CABECERA Y PIE DE PAGINA
# =============================================================================

def make_page_decorator(logo_path, seccion, cliente):
    """Devuelve una funcion de decoracion de pagina para ReportLab."""
    def decorator(canvas_obj, doc):
        if doc.page == 1:
            return  # Sin cabecera en la portada
        canvas_obj.saveState()
        w, h = A4

        # Barra roja superior
        canvas_obj.setFillColor(ROJO)
        canvas_obj.rect(0, h - 18*mm, w, 18*mm, fill=1, stroke=0)

        # Logo
        if logo_path and os.path.exists(logo_path):
            try:
                canvas_obj.drawImage(
                    logo_path, MARGIN, h - 16*mm,
                    width=40*mm, height=12*mm,
                    preserveAspectRatio=True, mask='auto'
                )
            except Exception:
                pass

        # Nombre seccion
        canvas_obj.setFillColor(BLANCO)
        canvas_obj.setFont('Helvetica-Bold', 11)
        canvas_obj.drawRightString(w - MARGIN, h - 11*mm, seccion)

        # Linea naranja
        canvas_obj.setStrokeColor(NARANJA)
        canvas_obj.setLineWidth(2)
        canvas_obj.line(MARGIN, h - 19*mm, w - MARGIN, h - 19*mm)

        # Pie de pagina
        canvas_obj.setFillColor(GRIS_CLARO)
        canvas_obj.setFont('Helvetica', 8)
        canvas_obj.drawString(MARGIN, 10*mm,
                               f"F2 Energy Consulting  |  {cliente}")
        canvas_obj.drawRightString(
            w - MARGIN, 10*mm,
            f"Pagina {doc.page}  |  {datetime.now().strftime('%d/%m/%Y')}"
        )
        canvas_obj.setStrokeColor(GRIS_CLARO)
        canvas_obj.setLineWidth(0.5)
        canvas_obj.line(MARGIN, 14*mm, w - MARGIN, 14*mm)

        canvas_obj.restoreState()
    return decorator


# =============================================================================
# HELPERS
# =============================================================================

def fig_to_image(fig, width=170*mm, height=85*mm) -> Image:
    """Exporta un grafico Plotly a imagen PNG para el PDF."""
    try:
        img_bytes = fig.to_image(
            format='png',
            width=int(width * 3.78),
            height=int(height * 3.78)
        )
        return Image(io.BytesIO(img_bytes), width=width, height=height)
    except Exception as e:
        print(f"  Advertencia grafico: {e}")
        return Spacer(1, height)


def kpi_table(kpis_data: list) -> Table:
    """Tabla de KPIs con estilo corporativo."""
    styles  = get_styles()
    col_w   = (PAGE_W - 2 * MARGIN) / len(kpis_data)

    data = [
        [Paragraph(v, styles['F2KPI_Value']) for _, v in kpis_data],
        [Paragraph(l, styles['F2KPI_Label']) for l, _ in kpis_data],
    ]
    t = Table(data, colWidths=[col_w] * len(kpis_data))
    t.setStyle(TableStyle([
        ('BACKGROUND',   (0,0), (-1,-1), GRIS_FONDO),
        ('TOPPADDING',   (0,0), (-1,-1), 8),
        ('BOTTOMPADDING',(0,0), (-1,-1), 8),
        ('LINEABOVE',    (0,0), (-1,0), 3, NARANJA),
    ]))
    return t


# =============================================================================
# PAGINAS
# =============================================================================

def build_portada(analysis, logo_path, styles, params):
    story = []
    s = analysis.consumption_summary

    story.append(Spacer(1, 40*mm))

    if logo_path and os.path.exists(logo_path):
        try:
            img = Image(logo_path, width=80*mm, height=30*mm, kind='proportional')
            img.hAlign = 'CENTER'
            story.append(img)
        except Exception:
            pass

    story.append(Spacer(1, 15*mm))
    story.append(HRFlowable(width='100%', thickness=3, color=NARANJA))
    story.append(Spacer(1, 8*mm))
    story.append(Paragraph('INFORME DE ANALISIS ELECTRICO', styles['F2Title']))
    story.append(Spacer(1, 4*mm))
    story.append(Paragraph(
        'Estudio de consumo, potencia y optimizacion tarifaria',
        styles['F2Subtitle']
    ))
    story.append(Spacer(1, 8*mm))
    story.append(HRFlowable(width='100%', thickness=3, color=NARANJA))
    story.append(Spacer(1, 15*mm))

    periodo = (
        f"{s.date_from.strftime('%d/%m/%Y')} — {s.date_to.strftime('%d/%m/%Y')}"
        if s else 'No disponible'
    )

    info = [
        ['Periodo analizado:',   periodo],
        ['Tipo de cliente:',     analysis.client.client_type.value.capitalize()],
        ['Provincia:',           analysis.client.province],
        ['Tipo de contrato:',    analysis.client.contract_type.value],
        ['Potencia contratada:', f"P1: {params['contracted_p1']} kW  |  P2: {params['contracted_p2']} kW"],
        ['Umbral de analisis:',  f"{params['umbral_kw']} kW"],
        ['Fecha del informe:',   datetime.now().strftime('%d/%m/%Y %H:%M')],
    ]

    if params.get('meses_filtro'):
        info.append(['Meses analizados:', ', '.join(
            [m.capitalize() for m in params['meses_filtro']]
        )])

    t = Table(info, colWidths=[60*mm, 100*mm])
    t.setStyle(TableStyle([
        ('FONTNAME',     (0,0), (0,-1), 'Helvetica-Bold'),
        ('FONTNAME',     (1,0), (1,-1), 'Helvetica'),
        ('FONTSIZE',     (0,0), (-1,-1), 11),
        ('TEXTCOLOR',    (0,0), (0,-1), GRIS_CLARO),
        ('TEXTCOLOR',    (1,0), (1,-1), GRIS_OSCURO),
        ('TOPPADDING',   (0,0), (-1,-1), 5),
        ('BOTTOMPADDING',(0,0), (-1,-1), 5),
        ('LINEBELOW',    (0,-1), (-1,-1), 0.5, GRIS_CLARO),
    ]))
    story.append(t)
    story.append(PageBreak())
    return story


def build_consumo(analysis, styles, params):
    story = []
    s = analysis.consumption_summary
    meses_filtro = params.get('meses_filtro') or None

    story.append(Spacer(1, 5*mm))
    story.append(Paragraph('Perfil de Consumo General', styles['F2SectionTitle']))
    story.append(HRFlowable(width='100%', thickness=1, color=NARANJA))
    story.append(Spacer(1, 5*mm))

    if not s:
        story.append(Paragraph('No hay datos de consumo.', styles['F2Body']))
        story.append(PageBreak())
        return story

    # Si hay filtro de meses, recalcular
    if meses_filtro:
        from src.analysis.consumption_engine import run_consumption_analysis
        import copy
        analysis_f = copy.copy(analysis)
        analysis_f.hourly_records = [
            r for r in analysis.hourly_records if r.month_name in meses_filtro
        ]
        analysis_f.consumption_summary = None
        analysis_f = run_consumption_analysis(analysis_f)
        s = analysis_f.consumption_summary
        story.append(Paragraph(
            f"Filtrado por: <b>{', '.join([m.capitalize() for m in meses_filtro])}</b>",
            styles['F2Small']
        ))
        story.append(Spacer(1, 3*mm))

    kpis = [
        ('Consumo Total',      f"{s.total_kwh:,.1f} kWh"),
        ('Promedio Diario',    f"{s.avg_daily_kwh:,.2f} kWh"),
        ('Promedio por Hora',  f"{s.avg_hourly_kwh:,.3f} kWh"),
    ]
    story.append(kpi_table(kpis))
    story.append(Spacer(1, 4*mm))

    # Periodos
    if s.by_energy_period:
        for p_key, p_val in s.by_energy_period.items():
            story.append(Paragraph(
                f"  <b>{p_key}:</b> {p_val.total_kwh:,.2f} kWh ({p_val.pct_of_total}%)",
                styles['F2Body']
            ))
        story.append(Spacer(1, 3*mm))

    # Graficos
    try:
        charts = generate_consumption_charts(s)
        story.append(Paragraph('Consumo por Mes:', styles['F2Small']))
        story.append(fig_to_image(charts['by_month'], height=75*mm))
        story.append(Spacer(1, 3*mm))
        story.append(Paragraph('Consumo Promedio por Hora:', styles['F2Small']))
        story.append(fig_to_image(charts['by_hour'], height=75*mm))
        story.append(Spacer(1, 3*mm))
        story.append(Paragraph('Distribucion por Periodo P1/P2/P3:', styles['F2Small']))
        story.append(fig_to_image(charts['by_period'], height=80*mm))
    except Exception as e:
        story.append(Paragraph(f'Graficos no disponibles: {e}', styles['F2Small']))

    story.append(PageBreak())
    return story


def build_potencia(analysis, styles, params):
    story = []
    p = analysis.power_analysis
    meses_filtro = params.get('meses_filtro_potencia') or None

    story.append(Spacer(1, 5*mm))
    story.append(Paragraph('Perfil de Potencia Real', styles['F2SectionTitle']))
    story.append(HRFlowable(width='100%', thickness=1, color=NARANJA))
    story.append(Spacer(1, 5*mm))

    if not p:
        story.append(Paragraph('No hay datos de potencia.', styles['F2Body']))
        story.append(PageBreak())
        return story

    kpis = [
        ('Maximo Real',       f"{p.max_power_kw:.3f} kW"),
        ('P99',               f"{p.p99_power_kw:.4f} kW"),
        ('Factor de Carga',   f"{p.load_factor:.3f}"),
        ('Horas sobre umbral',f"{p.hours_exceeds_2kw} h"),
        ('% sobre umbral',    f"{p.pct_exceeds_2kw}%"),
    ]
    story.append(kpi_table(kpis))
    story.append(Spacer(1, 4*mm))

    tipo        = getattr(p, 'perfil_tipo', '')
    descripcion = getattr(p, 'perfil_descripcion', '')
    if tipo:
        story.append(Paragraph(
            f'Perfil de consumo: <b>{tipo.upper()}</b>', styles['F2Body']
        ))
        story.append(Paragraph(descripcion, styles['F2Body']))
        story.append(Spacer(1, 3*mm))

    for obs in p.observations:
        story.append(Paragraph(f'• {obs}', styles['F2Body']))
    story.append(Spacer(1, 3*mm))

    try:
        charts = generate_power_charts(
            p,
            meses_filtro=meses_filtro,
            records=analysis.hourly_records
        )
        story.append(Paragraph('Potencia Maxima Dia a Dia:', styles['F2Small']))
        story.append(fig_to_image(charts['daily_max'], height=80*mm))
        story.append(Spacer(1, 3*mm))
        story.append(Paragraph('Picos Oficiales Mensuales:', styles['F2Small']))
        story.append(fig_to_image(charts['monthly_official'], height=80*mm))
    except Exception as e:
        story.append(Paragraph(f'Graficos no disponibles: {e}', styles['F2Small']))

    story.append(PageBreak())
    return story


def build_picos(analysis, styles, params):
    story = []
    umbral_kw = params.get('umbral_kw', 2.0)

    story.append(Spacer(1, 5*mm))
    story.append(Paragraph('Analisis de Picos Criticos', styles['F2SectionTitle']))
    story.append(HRFlowable(width='100%', thickness=1, color=NARANJA))
    story.append(Spacer(1, 4*mm))
    story.append(Paragraph(
        f"Umbral de analisis: <b>{umbral_kw} kW</b>",
        styles['F2Small']
    ))
    story.append(Spacer(1, 4*mm))

    data      = run_peaks_analysis(analysis, umbral_kw=umbral_kw)
    kpis_data = data.get('kpis', {})

    if not kpis_data or data.get('total_picos', 0) == 0:
        story.append(Paragraph(
            f'No hay horas con consumo superior a {umbral_kw} kW.',
            styles['F2Body']
        ))
        story.append(PageBreak())
        return story

    kpis = [
        ('Horas sobre umbral', f"{data['total_picos']} h"),
        ('% sobre umbral',     f"{kpis_data['pct_sobre_umbral']}%"),
        ('Pico maximo',        f"{kpis_data['pico_maximo_kwh']:.3f} kW"),
        ('Mes con mas picos',  kpis_data.get('mes_mas_picos','').capitalize()),
    ]
    story.append(kpi_table(kpis))
    story.append(Spacer(1, 4*mm))

    story.append(Paragraph(
        f"Franja horaria mas repetida: <b>{kpis_data.get('franja_mas_repetida','')}</b>",
        styles['F2Body']
    ))
    story.append(Spacer(1, 3*mm))

    # Top 10
    top10 = data.get('top10', [])
    if top10:
        story.append(Paragraph('Top 10 Picos mas Altos:', styles['F2Body']))
        headers = ['#', 'Fecha', 'Hora', 'Dia', 'kWh', 'Exceso', 'Periodo']
        rows = [[
            str(r['ranking']), r['fecha'], r['hora'],
            r['dia_semana'], str(r['kwh']),
            str(r['exceso_kwh']), r['periodo_potencia']
        ] for r in top10]

        t = Table([headers] + rows,
                  colWidths=[10*mm, 25*mm, 18*mm, 25*mm, 20*mm, 20*mm, 20*mm])
        t.setStyle(TableStyle([
            ('BACKGROUND',    (0,0), (-1,0), ROJO),
            ('TEXTCOLOR',     (0,0), (-1,0), BLANCO),
            ('FONTNAME',      (0,0), (-1,0), 'Helvetica-Bold'),
            ('FONTSIZE',      (0,0), (-1,-1), 8),
            ('ALIGN',         (0,0), (-1,-1), 'CENTER'),
            ('ROWBACKGROUNDS',(0,1), (-1,-1), [BLANCO, GRIS_FONDO]),
            ('GRID',          (0,0), (-1,-1), 0.3, GRIS_CLARO),
            ('TOPPADDING',    (0,0), (-1,-1), 4),
            ('BOTTOMPADDING', (0,0), (-1,-1), 4),
        ]))
        story.append(t)
        story.append(Spacer(1, 4*mm))

    try:
        charts = generate_peaks_charts(data)
        story.append(Paragraph('Evolucion Mensual de Picos:', styles['F2Small']))
        story.append(fig_to_image(charts['by_month'], height=75*mm))
        story.append(Spacer(1, 3*mm))
        story.append(Paragraph('Distribucion por Hora:', styles['F2Small']))
        story.append(fig_to_image(charts['by_hour'], height=75*mm))
    except Exception as e:
        story.append(Paragraph(f'Graficos no disponibles: {e}', styles['F2Small']))

    story.append(PageBreak())
    return story


def build_optimizacion(analysis, styles, params):
    story = []
    contracted_p1 = params.get('contracted_p1', 2.3)
    contracted_p2 = params.get('contracted_p2', 2.3)

    story.append(Spacer(1, 5*mm))
    story.append(Paragraph('Optimizacion de Potencia Contratada', styles['F2SectionTitle']))
    story.append(HRFlowable(width='100%', thickness=1, color=NARANJA))
    story.append(Spacer(1, 5*mm))

    data      = run_optimization_analysis(analysis, contracted_p1, contracted_p2)
    kpis_data = data.get('kpis', {})

    if not kpis_data:
        story.append(Paragraph('No hay datos.', styles['F2Body']))
        story.append(PageBreak())
        return story

    kpis = [
        ('P1 Actual',       f"{contracted_p1} kW"),
        ('P2 Actual',       f"{contracted_p2} kW"),
        ('Meses exceso P1', str(kpis_data['meses_exceso_p1'])),
        ('Meses exceso P2', str(kpis_data['meses_exceso_p2'])),
        ('Pico max Punta',  f"{kpis_data['max_pico_punta']:.3f} kW"),
        ('Pico max Valle',  f"{kpis_data['max_pico_valle']:.3f} kW"),
    ]
    story.append(kpi_table(kpis))
    story.append(Spacer(1, 4*mm))

    try:
        charts = generate_optimization_charts(data)
        story.append(Paragraph('Picos Mensuales vs Potencia Contratada:', styles['F2Small']))
        story.append(fig_to_image(charts['picos'], height=90*mm))
        story.append(Spacer(1, 4*mm))
    except Exception as e:
        story.append(Paragraph(f'Grafico no disponible: {e}', styles['F2Small']))

    opciones = data.get('opciones_sugeridas', {})
    if opciones:
        story.append(Paragraph('Opciones Sugeridas:', styles['F2SectionTitle']))
        for key in ['equilibrada', 'segura']:
            op = opciones.get(key, {})
            if op:
                story.append(Paragraph(f"<b>{op.get('titulo','')}</b>", styles['F2Body']))
                story.append(Paragraph(op.get('descripcion',''), styles['F2Conclusion']))
                story.append(Spacer(1, 3*mm))

    story.append(PageBreak())
    return story


def build_conclusiones(analysis, styles, params):
    story = []
    s  = analysis.consumption_summary
    p  = analysis.power_analysis
    contracted_p1 = params.get('contracted_p1', 2.3)
    contracted_p2 = params.get('contracted_p2', 2.3)
    umbral_kw     = params.get('umbral_kw', 2.0)

    story.append(Spacer(1, 5*mm))
    story.append(Paragraph('Conclusiones del Analisis', styles['F2SectionTitle']))
    story.append(HRFlowable(width='100%', thickness=1, color=NARANJA))
    story.append(Spacer(1, 8*mm))

    conclusiones = []

    if s:
        conclusiones.append(
            f"El consumo total analizado es de <b>{s.total_kwh:,.1f} kWh</b>, "
            f"con un promedio diario de <b>{s.avg_daily_kwh:,.2f} kWh</b>. "
            f"El valle (P3) concentra el "
            f"<b>{s.by_energy_period['P3'].pct_of_total}%</b> del consumo."
        )

    if p:
        conclusiones.append(
            f"El pico maximo registrado por la distribuidora es "
            f"<b>{p.max_power_kw:.3f} kW</b>. "
            f"El perfil de consumo es <b>{getattr(p,'perfil_tipo','')}</b>."
        )
        for obs in p.observations:
            conclusiones.append(obs)

    data_picos = run_peaks_analysis(analysis, umbral_kw=umbral_kw)
    if data_picos.get('total_picos', 0) > 0:
        kp = data_picos.get('kpis', {})
        conclusiones.append(
            f"Se han detectado <b>{data_picos['total_picos']} horas</b> "
            f"({kp.get('pct_sobre_umbral',0)}% del tiempo) con consumo "
            f"superior a {umbral_kw} kW. "
            f"Mayor concentracion en <b>{kp.get('mes_mas_picos','').capitalize()}</b>."
        )

    data_opt = run_optimization_analysis(analysis, contracted_p1, contracted_p2)
    opciones  = data_opt.get('opciones_sugeridas', {})
    if opciones:
        eq  = opciones.get('equilibrada', {})
        seg = opciones.get('segura', {})
        conclusiones.append(
            f"Para la potencia contratada se sugieren dos opciones: "
            f"<b>{eq.get('titulo','')}</b> o <b>{seg.get('titulo','')}</b>. "
            f"La decision final dependera del coste del termino de potencia, "
            f"que se analizara en el estudio de factura."
        )

    for i, c in enumerate(conclusiones):
        story.append(Paragraph(f"{i+1}. {c}", styles['F2Conclusion']))
        story.append(Spacer(1, 4*mm))

    story.append(Spacer(1, 10*mm))
    story.append(HRFlowable(width='100%', thickness=2, color=NARANJA))
    story.append(Spacer(1, 5*mm))
    story.append(Paragraph(
        'Este informe ha sido generado automaticamente por F2 Energy Consulting '
        'con los parametros seleccionados en el dashboard en el momento de la descarga.',
        styles['F2Small']
    ))

    return story


# =============================================================================
# FUNCION PRINCIPAL
# =============================================================================

def generate_report(
    analysis:    ElectricityAnalysis,
    output_path: str,
    logo_path:   str = None,
    params:      dict = None,
) -> str:
    """
    Genera el informe PDF con los parametros actuales del dashboard.

    Args:
        analysis:    ElectricityAnalysis con todos los analisis calculados
        output_path: Ruta donde guardar el PDF
        logo_path:   Ruta al logo PNG
        params:      Diccionario con los parametros actuales del dashboard:
                     {
                       'contracted_p1':         float,  # Potencia P1 seleccionada
                       'contracted_p2':         float,  # Potencia P2 seleccionada
                       'umbral_kw':             float,  # Umbral de picos seleccionado
                       'meses_filtro':          list,   # Meses filtrados en consumo
                       'meses_filtro_potencia': list,   # Meses filtrados en potencia
                     }

    Returns:
        Ruta del PDF generado
    """
    if params is None:
        params = {}

    # Valores por defecto si no se pasan
    params.setdefault('contracted_p1', 2.3)
    params.setdefault('contracted_p2', 2.3)
    params.setdefault('umbral_kw', 2.0)
    params.setdefault('meses_filtro', [])
    params.setdefault('meses_filtro_potencia', [])

    print(f"Generando PDF con parametros: {params}")
    styles  = get_styles()
    cliente = (analysis.client.name or 'Cliente') if analysis.client else 'Cliente'
    provincia = analysis.client.province if analysis.client else ''

    secciones_map = {
        2: 'Perfil de Consumo General',
        3: 'Perfil de Potencia Real',
        4: 'Analisis de Picos Criticos',
        5: 'Optimizacion de Potencia',
        6: 'Conclusiones',
    }

    story = []
    story += build_portada(analysis, logo_path, styles, params)
    story += build_consumo(analysis, styles, params)
    story += build_potencia(analysis, styles, params)
    story += build_picos(analysis, styles, params)
    story += build_optimizacion(analysis, styles, params)
    story += build_conclusiones(analysis, styles, params)

    # Contador de pagina para asignar seccion correcta
    _page_counter = [0]

    def on_page(canvas_obj, doc):
        _page_counter[0] += 1
        pg = _page_counter[0]
        if pg == 1:
            return
        seccion = secciones_map.get(pg, 'F2 Energy Consulting')
        decorator = make_page_decorator(
            logo_path, seccion,
            f"{cliente} — {provincia}"
        )
        decorator(canvas_obj, doc)

    doc = SimpleDocTemplate(
        output_path,
        pagesize     = A4,
        leftMargin   = MARGIN,
        rightMargin  = MARGIN,
        topMargin    = 25*mm,
        bottomMargin = 20*mm,
        title        = f"Informe Electrico — {cliente}",
        author       = 'F2 Energy Consulting',
    )

    doc.build(story, onFirstPage=on_page, onLaterPages=on_page)
    print(f"PDF generado: {output_path}")
    return output_path
