# =============================================================================
# src/reports/report_generator.py
# Generador de informe PDF con ReportLab
# Version: 1.0
#
# Estructura del PDF:
#   Pagina 1 — Portada
#   Pagina 2 — Perfil de consumo general
#   Pagina 3 — Perfil de potencia real
#   Pagina 4 — Analisis de picos criticos
#   Pagina 5 — Optimizacion de potencia contratada
#   Pagina 6 — Conclusiones
#
# Estilo: F2 Energy Consulting
#   Rojo corporativo: #CC1F1F
#   Naranja/amarillo: #F5A623
#   Fondo: blanco
# =============================================================================

import os
import io
import tempfile
from datetime import datetime

from reportlab.lib.pagesizes import A4
from reportlab.lib.units import mm
from reportlab.lib import colors
from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
from reportlab.lib.enums import TA_CENTER, TA_LEFT, TA_RIGHT
from reportlab.platypus import (
    SimpleDocTemplate, Paragraph, Spacer, Image,
    PageBreak, Table, TableStyle, HRFlowable
)
from reportlab.pdfgen import canvas
from reportlab.platypus.flowables import Flowable

import sys
sys.path.append('../..')
from src.models.internal_data_model import ElectricityAnalysis
from src.analysis.consumption_engine import run_consumption_analysis
from src.analysis.power_engine import run_power_analysis
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

# Dimensiones A4
PAGE_W, PAGE_H = A4
MARGIN = 20 * mm


# =============================================================================
# ESTILOS
# =============================================================================

def get_styles():
    styles = getSampleStyleSheet()

    styles.add(ParagraphStyle(
        name        = 'F2Title',
        fontName    = 'Helvetica-Bold',
        fontSize    = 28,
        textColor   = ROJO,
        alignment   = TA_CENTER,
        spaceAfter  = 6,
    ))

    styles.add(ParagraphStyle(
        name        = 'F2Subtitle',
        fontName    = 'Helvetica',
        fontSize    = 14,
        textColor   = GRIS_CLARO,
        alignment   = TA_CENTER,
        spaceAfter  = 4,
    ))

    styles.add(ParagraphStyle(
        name        = 'F2SectionTitle',
        fontName    = 'Helvetica-Bold',
        fontSize    = 16,
        textColor   = ROJO,
        spaceBefore = 10,
        spaceAfter  = 6,
    ))

    styles.add(ParagraphStyle(
        name        = 'F2Body',
        fontName    = 'Helvetica',
        fontSize    = 10,
        textColor   = GRIS_OSCURO,
        spaceAfter  = 4,
        leading     = 14,
    ))

    styles.add(ParagraphStyle(
        name        = 'F2Small',
        fontName    = 'Helvetica',
        fontSize    = 8,
        textColor   = GRIS_CLARO,
        spaceAfter  = 2,
    ))

    styles.add(ParagraphStyle(
        name        = 'F2KPI_Label',
        fontName    = 'Helvetica',
        fontSize    = 9,
        textColor   = GRIS_CLARO,
        alignment   = TA_CENTER,
    ))

    styles.add(ParagraphStyle(
        name        = 'F2KPI_Value',
        fontName    = 'Helvetica-Bold',
        fontSize    = 18,
        textColor   = ROJO,
        alignment   = TA_CENTER,
    ))

    styles.add(ParagraphStyle(
        name        = 'F2Conclusion',
        fontName    = 'Helvetica',
        fontSize    = 10,
        textColor   = GRIS_OSCURO,
        spaceAfter  = 6,
        leading     = 16,
        leftIndent  = 10,
    ))

    return styles


# =============================================================================
# CABECERA Y PIE DE PAGINA
# =============================================================================

class PageTemplate:
    """Cabecera y pie de pagina para todas las paginas excepto la portada."""

    def __init__(self, logo_path: str, seccion: str, cliente: str):
        self.logo_path = logo_path
        self.seccion   = seccion
        self.cliente   = cliente

    def __call__(self, canvas_obj, doc):
        canvas_obj.saveState()
        w, h = A4

        # Barra superior roja
        canvas_obj.setFillColor(ROJO)
        canvas_obj.rect(0, h - 18*mm, w, 18*mm, fill=1, stroke=0)

        # Logo en cabecera (si existe)
        if self.logo_path and os.path.exists(self.logo_path):
            try:
                canvas_obj.drawImage(
                    self.logo_path,
                    MARGIN, h - 16*mm,
                    width=40*mm, height=12*mm,
                    preserveAspectRatio=True, mask='auto'
                )
            except Exception:
                pass

        # Nombre seccion en cabecera
        canvas_obj.setFillColor(BLANCO)
        canvas_obj.setFont('Helvetica-Bold', 11)
        canvas_obj.drawRightString(w - MARGIN, h - 11*mm, self.seccion)

        # Linea naranja bajo la cabecera
        canvas_obj.setStrokeColor(NARANJA)
        canvas_obj.setLineWidth(2)
        canvas_obj.line(MARGIN, h - 19*mm, w - MARGIN, h - 19*mm)

        # Pie de pagina
        canvas_obj.setFillColor(GRIS_CLARO)
        canvas_obj.setFont('Helvetica', 8)
        canvas_obj.drawString(MARGIN, 10*mm, f"F2 Energy Consulting  |  {self.cliente}")
        canvas_obj.drawRightString(
            w - MARGIN, 10*mm,
            f"Pagina {doc.page}  |  {datetime.now().strftime('%d/%m/%Y')}"
        )

        # Linea gris sobre el pie
        canvas_obj.setStrokeColor(GRIS_CLARO)
        canvas_obj.setLineWidth(0.5)
        canvas_obj.line(MARGIN, 14*mm, w - MARGIN, 14*mm)

        canvas_obj.restoreState()


# =============================================================================
# EXPORTAR GRAFICOS PLOTLY A IMAGEN
# =============================================================================

def fig_to_image(fig, width=170*mm, height=90*mm) -> Image:
    """
    Convierte un grafico Plotly a imagen para insertar en el PDF.
    Requiere kaleido instalado: pip install kaleido
    """
    try:
        img_bytes = fig.to_image(format='png', width=int(width*3.78), height=int(height*3.78))
        buf = io.BytesIO(img_bytes)
        return Image(buf, width=width, height=height)
    except Exception as e:
        print(f"  Advertencia: no se pudo exportar grafico: {e}")
        return Spacer(1, height)


# =============================================================================
# BLOQUE KPI
# =============================================================================

def kpi_table(kpis_data: list) -> Table:
    """
    Genera una tabla de KPIs con formato corporativo.
    kpis_data = [(label, value), (label, value), ...]
    """
    styles = get_styles()
    col_w  = (PAGE_W - 2 * MARGIN) / len(kpis_data)

    data = [
        [Paragraph(v, styles['F2KPI_Value']) for _, v in kpis_data],
        [Paragraph(l, styles['F2KPI_Label']) for l, _ in kpis_data],
    ]

    t = Table(data, colWidths=[col_w] * len(kpis_data))
    t.setStyle(TableStyle([
        ('BACKGROUND',  (0,0), (-1,-1), GRIS_FONDO),
        ('ROUNDEDCORNERS', [4]),
        ('TOPPADDING',  (0,0), (-1,-1), 8),
        ('BOTTOMPADDING',(0,0), (-1,-1), 8),
        ('LEFTPADDING', (0,0), (-1,-1), 4),
        ('RIGHTPADDING',(0,0), (-1,-1), 4),
        ('LINEABOVE',   (0,0), (-1,0), 3, NARANJA),
    ]))
    return t


# =============================================================================
# PAGINA 1 — PORTADA
# =============================================================================

def build_portada(analysis: ElectricityAnalysis,
                  logo_path: str,
                  styles: dict) -> list:

    story = []
    s = analysis.consumption_summary
    p = analysis.power_analysis

    # Espacio superior
    story.append(Spacer(1, 40*mm))

    # Logo centrado
    if logo_path and os.path.exists(logo_path):
        try:
            img = Image(logo_path, width=80*mm, height=30*mm,
                        kind='proportional')
            img.hAlign = 'CENTER'
            story.append(img)
        except Exception:
            pass

    story.append(Spacer(1, 15*mm))

    # Linea naranja
    story.append(HRFlowable(width='100%', thickness=3, color=NARANJA))
    story.append(Spacer(1, 8*mm))

    # Titulo
    story.append(Paragraph('INFORME DE ANALISIS ELECTRICO', styles['F2Title']))
    story.append(Spacer(1, 4*mm))

    # Subtitulo
    story.append(Paragraph('Estudio de consumo, potencia y optimizacion tarifaria',
                            styles['F2Subtitle']))
    story.append(Spacer(1, 8*mm))
    story.append(HRFlowable(width='100%', thickness=3, color=NARANJA))
    story.append(Spacer(1, 15*mm))

    # Datos del informe
    if s:
        periodo = (f"{s.date_from.strftime('%d/%m/%Y')} — "
                   f"{s.date_to.strftime('%d/%m/%Y')}")
    else:
        periodo = 'Periodo no disponible'

    tipo_cliente = (analysis.client.client_type.value.capitalize()
                    if analysis.client else 'No especificado')
    provincia    = analysis.client.province if analysis.client else 'No especificada'
    contrato     = (analysis.client.contract_type.value
                    if analysis.client else 'No especificado')

    info_data = [
        ['Periodo analizado:', periodo],
        ['Tipo de cliente:',   tipo_cliente],
        ['Provincia:',         provincia],
        ['Tipo de contrato:',  contrato],
        ['Fecha del informe:', datetime.now().strftime('%d/%m/%Y')],
    ]

    t = Table(info_data, colWidths=[60*mm, 100*mm])
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


# =============================================================================
# PAGINA 2 — PERFIL DE CONSUMO
# =============================================================================

def build_consumo(analysis: ElectricityAnalysis,
                  styles: dict) -> list:
    story = []
    s = analysis.consumption_summary
    if not s:
        story.append(Paragraph('No hay datos de consumo disponibles.', styles['F2Body']))
        story.append(PageBreak())
        return story

    story.append(Spacer(1, 5*mm))
    story.append(Paragraph('Perfil de Consumo General', styles['F2SectionTitle']))
    story.append(HRFlowable(width='100%', thickness=1, color=NARANJA))
    story.append(Spacer(1, 5*mm))

    # KPIs
    kpis = [
        ('Consumo Total', f"{s.total_kwh:,.1f} kWh"),
        ('Promedio Diario', f"{s.avg_daily_kwh:,.2f} kWh"),
        ('Promedio por Hora', f"{s.avg_hourly_kwh:,.3f} kWh"),
    ]
    story.append(kpi_table(kpis))
    story.append(Spacer(1, 5*mm))

    # Periodos
    if s.by_energy_period:
        story.append(Paragraph('Distribucion por Periodo Energetico:', styles['F2Body']))
        for p, v in s.by_energy_period.items():
            story.append(Paragraph(
                f"  <b>{p}:</b> {v.total_kwh:,.2f} kWh ({v.pct_of_total}%)",
                styles['F2Body']
            ))
        story.append(Spacer(1, 3*mm))

    # Graficos
    try:
        charts = generate_consumption_charts(s)
        story.append(Paragraph('Consumo por Mes:', styles['F2Small']))
        story.append(fig_to_image(charts['by_month'], height=75*mm))
        story.append(Spacer(1, 3*mm))
        story.append(Paragraph('Consumo Promedio por Hora del Dia:', styles['F2Small']))
        story.append(fig_to_image(charts['by_hour'], height=75*mm))
        story.append(Spacer(1, 3*mm))
        story.append(Paragraph('Consumo por Periodo P1/P2/P3:', styles['F2Small']))
        story.append(fig_to_image(charts['by_period'], height=80*mm))
    except Exception as e:
        story.append(Paragraph(f'Graficos no disponibles: {e}', styles['F2Small']))

    story.append(PageBreak())
    return story


# =============================================================================
# PAGINA 3 — PERFIL DE POTENCIA
# =============================================================================

def build_potencia(analysis: ElectricityAnalysis,
                   styles: dict) -> list:
    story = []
    p = analysis.power_analysis
    if not p:
        story.append(Paragraph('No hay datos de potencia disponibles.', styles['F2Body']))
        story.append(PageBreak())
        return story

    story.append(Spacer(1, 5*mm))
    story.append(Paragraph('Perfil de Potencia Real', styles['F2SectionTitle']))
    story.append(HRFlowable(width='100%', thickness=1, color=NARANJA))
    story.append(Spacer(1, 5*mm))

    # KPIs
    kpis = [
        ('Maximo Real', f"{p.max_power_kw:.3f} kW"),
        ('P99', f"{p.p99_power_kw:.4f} kW"),
        ('Factor de Carga', f"{p.load_factor:.3f}"),
        ('Horas sobre umbral', f"{p.hours_exceeds_2kw} h"),
    ]
    story.append(kpi_table(kpis))
    story.append(Spacer(1, 4*mm))

    # Perfil
    tipo       = getattr(p, 'perfil_tipo', '')
    descripcion = getattr(p, 'perfil_descripcion', '')
    if tipo:
        story.append(Paragraph(f'<b>Perfil de consumo: {tipo.upper()}</b>',
                                styles['F2Body']))
        story.append(Paragraph(descripcion, styles['F2Body']))
        story.append(Spacer(1, 3*mm))

    # Observaciones
    for obs in p.observations:
        story.append(Paragraph(f'• {obs}', styles['F2Body']))
    story.append(Spacer(1, 3*mm))

    # Graficos
    try:
        charts = generate_power_charts(p)
        story.append(Paragraph('Potencia Maxima Dia a Dia:', styles['F2Small']))
        story.append(fig_to_image(charts['daily_max'], height=80*mm))
        story.append(Spacer(1, 3*mm))
        story.append(Paragraph('Picos Oficiales Mensuales por Periodo:', styles['F2Small']))
        story.append(fig_to_image(charts['monthly_official'], height=80*mm))
    except Exception as e:
        story.append(Paragraph(f'Graficos no disponibles: {e}', styles['F2Small']))

    story.append(PageBreak())
    return story


# =============================================================================
# PAGINA 4 — PICOS CRITICOS
# =============================================================================

def build_picos(analysis: ElectricityAnalysis,
                umbral_kw: float,
                styles: dict) -> list:
    story = []

    story.append(Spacer(1, 5*mm))
    story.append(Paragraph('Analisis de Picos Criticos', styles['F2SectionTitle']))
    story.append(HRFlowable(width='100%', thickness=1, color=NARANJA))
    story.append(Spacer(1, 5*mm))

    data = run_peaks_analysis(analysis, umbral_kw=umbral_kw)
    kpis_data = data.get('kpis', {})

    if not kpis_data:
        story.append(Paragraph('No hay picos sobre el umbral.', styles['F2Body']))
        story.append(PageBreak())
        return story

    # KPIs
    kpis = [
        ('Horas sobre umbral', f"{data['total_picos']} h"),
        ('% sobre umbral', f"{kpis_data['pct_sobre_umbral']}%"),
        ('Pico maximo', f"{kpis_data['pico_maximo_kwh']:.3f} kW"),
        ('Mes con mas picos', kpis_data.get('mes_mas_picos','').capitalize()),
    ]
    story.append(kpi_table(kpis))
    story.append(Spacer(1, 4*mm))

    story.append(Paragraph(
        f"Umbral de analisis: <b>{umbral_kw} kW</b>  |  "
        f"Franja mas repetida: <b>{kpis_data.get('franja_mas_repetida','')}</b>",
        styles['F2Body']
    ))
    story.append(Spacer(1, 3*mm))

    # Top 10 tabla
    top10 = data.get('top10', [])
    if top10:
        story.append(Paragraph('Top 10 Picos mas Altos:', styles['F2Body']))
        headers = ['#', 'Fecha', 'Hora', 'Dia', 'kWh', 'Exceso', 'Periodo']
        rows = [[
            str(r['ranking']), r['fecha'], r['hora'],
            r['dia_semana'], str(r['kwh']), str(r['exceso_kwh']),
            r['periodo_potencia']
        ] for r in top10]

        t_data = [headers] + rows
        col_ws = [10*mm, 25*mm, 18*mm, 25*mm, 20*mm, 20*mm, 20*mm]
        t = Table(t_data, colWidths=col_ws)
        t.setStyle(TableStyle([
            ('BACKGROUND',   (0,0), (-1,0), ROJO),
            ('TEXTCOLOR',    (0,0), (-1,0), BLANCO),
            ('FONTNAME',     (0,0), (-1,0), 'Helvetica-Bold'),
            ('FONTSIZE',     (0,0), (-1,-1), 8),
            ('ALIGN',        (0,0), (-1,-1), 'CENTER'),
            ('ROWBACKGROUNDS',(0,1), (-1,-1), [BLANCO, GRIS_FONDO]),
            ('GRID',         (0,0), (-1,-1), 0.3, GRIS_CLARO),
            ('TOPPADDING',   (0,0), (-1,-1), 4),
            ('BOTTOMPADDING',(0,0), (-1,-1), 4),
        ]))
        story.append(t)
        story.append(Spacer(1, 4*mm))

    # Graficos
    try:
        charts = generate_peaks_charts(data)
        story.append(Paragraph('Evolucion Mensual de Picos:', styles['F2Small']))
        story.append(fig_to_image(charts['by_month'], height=75*mm))
        story.append(Spacer(1, 3*mm))
        story.append(Paragraph('Distribucion por Hora del Dia:', styles['F2Small']))
        story.append(fig_to_image(charts['by_hour'], height=75*mm))
    except Exception as e:
        story.append(Paragraph(f'Graficos no disponibles: {e}', styles['F2Small']))

    story.append(PageBreak())
    return story


# =============================================================================
# PAGINA 5 — OPTIMIZACION DE POTENCIA
# =============================================================================

def build_optimizacion(analysis: ElectricityAnalysis,
                        contracted_p1: float,
                        contracted_p2: float,
                        styles: dict) -> list:
    story = []

    story.append(Spacer(1, 5*mm))
    story.append(Paragraph('Optimizacion de Potencia Contratada', styles['F2SectionTitle']))
    story.append(HRFlowable(width='100%', thickness=1, color=NARANJA))
    story.append(Spacer(1, 5*mm))

    data  = run_optimization_analysis(analysis, contracted_p1, contracted_p2)
    kpis_data = data.get('kpis', {})

    if not kpis_data:
        story.append(Paragraph('No hay datos de optimizacion disponibles.', styles['F2Body']))
        story.append(PageBreak())
        return story

    # KPIs
    kpis = [
        ('P1 Actual', f"{contracted_p1} kW"),
        ('P2 Actual', f"{contracted_p2} kW"),
        ('Meses exceso P1', f"{kpis_data['meses_exceso_p1']}"),
        ('Meses exceso P2', f"{kpis_data['meses_exceso_p2']}"),
        ('Pico max Punta', f"{kpis_data['max_pico_punta']:.3f} kW"),
        ('Pico max Valle', f"{kpis_data['max_pico_valle']:.3f} kW"),
    ]
    story.append(kpi_table(kpis))
    story.append(Spacer(1, 4*mm))

    # Grafico picos mensuales
    try:
        charts = generate_optimization_charts(data)
        story.append(Paragraph('Picos Mensuales vs Potencia Contratada:', styles['F2Small']))
        story.append(fig_to_image(charts['picos'], height=90*mm))
        story.append(Spacer(1, 4*mm))
    except Exception as e:
        story.append(Paragraph(f'Grafico no disponible: {e}', styles['F2Small']))

    # Opciones sugeridas
    opciones = data.get('opciones_sugeridas', {})
    if opciones:
        story.append(Paragraph('Opciones Sugeridas:', styles['F2SectionTitle']))
        for key in ['equilibrada', 'segura']:
            op = opciones.get(key, {})
            if op:
                color = NARANJA if key == 'equilibrada' else colors.HexColor('#10B981')
                story.append(Paragraph(f"<b>{op.get('titulo','')}</b>", styles['F2Body']))
                story.append(Paragraph(op.get('descripcion',''), styles['F2Conclusion']))
                story.append(Spacer(1, 3*mm))

    story.append(PageBreak())
    return story


# =============================================================================
# PAGINA 6 — CONCLUSIONES
# =============================================================================

def build_conclusiones(analysis: ElectricityAnalysis,
                        contracted_p1: float,
                        contracted_p2: float,
                        umbral_kw: float,
                        styles: dict) -> list:
    story = []
    s = analysis.consumption_summary
    p = analysis.power_analysis

    story.append(Spacer(1, 5*mm))
    story.append(Paragraph('Conclusiones del Analisis', styles['F2SectionTitle']))
    story.append(HRFlowable(width='100%', thickness=1, color=NARANJA))
    story.append(Spacer(1, 8*mm))

    conclusiones = []

    # Consumo
    if s:
        conclusiones.append(
            f"El consumo total analizado es de <b>{s.total_kwh:,.1f} kWh</b>, "
            f"con un promedio diario de <b>{s.avg_daily_kwh:,.2f} kWh</b>. "
            f"El periodo valle (P3) concentra el "
            f"<b>{s.by_energy_period['P3'].pct_of_total}%</b> del consumo total."
        )

    # Potencia
    if p:
        conclusiones.append(
            f"El pico de potencia maximo registrado por la distribuidora es de "
            f"<b>{p.max_power_kw:.3f} kW</b>. "
            f"El perfil de consumo es <b>{getattr(p,'perfil_tipo','')}</b>."
        )
        for obs in p.observations:
            conclusiones.append(obs)

    # Picos
    data_picos = run_peaks_analysis(analysis, umbral_kw=umbral_kw)
    if data_picos.get('total_picos', 0) > 0:
        kpis_picos = data_picos.get('kpis', {})
        conclusiones.append(
            f"Se han detectado <b>{data_picos['total_picos']} horas</b> "
            f"({kpis_picos.get('pct_sobre_umbral',0)}% del tiempo) "
            f"con consumo superior a {umbral_kw} kW. "
            f"El mes con mas picos es <b>{kpis_picos.get('mes_mas_picos','').capitalize()}</b>."
        )

    # Optimizacion
    data_opt = run_optimization_analysis(analysis, contracted_p1, contracted_p2)
    opciones = data_opt.get('opciones_sugeridas', {})
    if opciones:
        eq  = opciones.get('equilibrada', {})
        seg = opciones.get('segura', {})
        conclusiones.append(
            f"Para la potencia contratada, el sistema sugiere dos opciones: "
            f"<b>{eq.get('titulo','')}</b> o <b>{seg.get('titulo','')}</b>. "
            f"La decision depende de la tolerancia al riesgo y el coste del "
            f"termino de potencia (a analizar en el estudio de factura)."
        )

    for i, c in enumerate(conclusiones):
        story.append(Paragraph(f"{i+1}. {c}", styles['F2Conclusion']))
        story.append(Spacer(1, 4*mm))

    story.append(Spacer(1, 10*mm))
    story.append(HRFlowable(width='100%', thickness=2, color=NARANJA))
    story.append(Spacer(1, 5*mm))
    story.append(Paragraph(
        'Este informe ha sido generado automaticamente por F2 Energy Consulting. '
        'Los calculos se basan en los datos aportados por el cliente y en los '
        'registros oficiales de la distribuidora.',
        styles['F2Small']
    ))

    return story


# =============================================================================
# FUNCION PRINCIPAL
# =============================================================================

def generate_report(
    analysis:       ElectricityAnalysis,
    output_path:    str,
    logo_path:      str = None,
    contracted_p1:  float = 2.3,
    contracted_p2:  float = 2.3,
    umbral_kw:      float = 2.0,
) -> str:
    """
    Genera el informe PDF completo.

    Args:
        analysis:      ElectricityAnalysis con todos los analisis calculados
        output_path:   Ruta donde guardar el PDF
        logo_path:     Ruta al logo de F2 Energy Consulting (PNG)
        contracted_p1: Potencia contratada P1 en kW
        contracted_p2: Potencia contratada P2 en kW
        umbral_kw:     Umbral para analisis de picos

    Returns:
        Ruta del PDF generado
    """
    print("Generando informe PDF...")
    styles = get_styles()

    # Nombre del cliente
    cliente = (analysis.client.name or 'Cliente') if analysis.client else 'Cliente'
    provincia = analysis.client.province if analysis.client else ''

    secciones = [
        'Perfil de Consumo',
        'Perfil de Potencia',
        'Analisis de Picos',
        'Optimizacion',
        'Conclusiones',
    ]

    # Construir el PDF pagina a pagina
    story = []

    # Pagina 1 — Portada (sin cabecera)
    story += build_portada(analysis, logo_path, styles)

    # Paginas 2-6 con cabecera
    secciones_contenido = [
        ('Perfil de Consumo General',        build_consumo(analysis, styles)),
        ('Perfil de Potencia Real',           build_potencia(analysis, styles)),
        ('Analisis de Picos Criticos',        build_picos(analysis, umbral_kw, styles)),
        ('Optimizacion de Potencia',          build_optimizacion(analysis, contracted_p1, contracted_p2, styles)),
        ('Conclusiones',                      build_conclusiones(analysis, contracted_p1, contracted_p2, umbral_kw, styles)),
    ]

    for seccion, contenido in secciones_contenido:
        story += contenido

    # Crear documento
    doc = SimpleDocTemplate(
        output_path,
        pagesize    = A4,
        leftMargin  = MARGIN,
        rightMargin = MARGIN,
        topMargin   = 25*mm,
        bottomMargin= 20*mm,
        title       = f"Informe Electrico — {cliente}",
        author      = 'F2 Energy Consulting',
    )

    # Template de cabecera/pie (se aplica a todas las paginas excepto la portada)
    from reportlab.platypus import BaseDocTemplate, Frame, PageTemplate as RLPageTemplate

    def on_later_pages(canvas_obj, doc_obj):
        if doc_obj.page > 1:
            seccion_actual = secciones[min(doc_obj.page - 2, len(secciones)-1)]
            pt = PageTemplate(logo_path, seccion_actual, f"{cliente} — {provincia}")
            pt(canvas_obj, doc_obj)

    doc.build(story, onLaterPages=on_later_pages)

    print(f"Informe PDF generado: {output_path}")
    return output_path
