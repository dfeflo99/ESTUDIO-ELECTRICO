# =============================================================================
# src/analysis/peaks_engine.py
# Motor de analisis de picos criticos
# Version: 1.0
#
# Pagina 3 del informe: Analisis de picos criticos
#
# Calcula:
#   - KPIs: total horas sobre umbral, pico maximo, mes con mas picos,
#           franja horaria mas repetida
#   - Top 10 picos mas altos
#   - Evolucion mensual de picos
#   - Distribucion por franja horaria
#   - Mapa de calor picos por mes y hora
#   - Laborable vs fin de semana
#   - Por periodo P1/P2
# =============================================================================

from collections import defaultdict
from typing import Optional

import sys
sys.path.append('..')
from src.models.internal_data_model import ElectricityAnalysis

# Orden natural de meses
MESES_ORDEN = [
    'enero', 'febrero', 'marzo', 'abril', 'mayo', 'junio',
    'julio', 'agosto', 'septiembre', 'octubre', 'noviembre', 'diciembre'
]

def _round4(val: float) -> float:
    return round(val, 4)

def _round2(val: float) -> float:
    return round(val, 2)

def _franja_horaria(hora: int) -> str:
    """Clasifica una hora en franja horaria."""
    if 0 <= hora < 6:
        return 'Madrugada (0h-6h)'
    elif 6 <= hora < 12:
        return 'Manana (6h-12h)'
    elif 12 <= hora < 18:
        return 'Tarde (12h-18h)'
    else:
        return 'Noche (18h-24h)'


# =============================================================================
# FUNCION PRINCIPAL
# =============================================================================

def run_peaks_analysis(analysis: ElectricityAnalysis,
                       umbral_kw: float = 2.0) -> dict:
    """
    Calcula el analisis completo de picos criticos.

    Args:
        analysis:  ElectricityAnalysis con hourly_records validados
        umbral_kw: Umbral configurable por el usuario (default: 2.0 kW)

    Returns:
        Diccionario con todos los calculos listos para los graficos
    """
    records = analysis.hourly_records

    if not records:
        print("ERROR: No hay registros para analizar picos.")
        return {}

    print(f"Iniciando analisis de picos criticos (umbral: {umbral_kw} kW)...")

    # Filtrar registros que superan el umbral
    picos = [r for r in records if r.consumption_kwh > umbral_kw]
    total_picos = len(picos)
    total_horas = len(records)

    print(f"  Horas sobre umbral: {total_picos} de {total_horas}")

    if not picos:
        print("  No hay picos por encima del umbral.")
        return {
            'umbral_kw':    umbral_kw,
            'total_picos':  0,
            'kpis':         {},
            'top10':        [],
            'by_month':     {},
            'by_franja':    {},
            'heatmap':      {},
            'by_day_type':  {},
            'by_period':    {},
        }

    # ----------------------------------------------------------------
    # KPIs PRINCIPALES
    # ----------------------------------------------------------------

    pico_maximo = max(picos, key=lambda r: r.consumption_kwh)

    # Mes con mas picos
    picos_por_mes = defaultdict(int)
    for r in picos:
        picos_por_mes[r.month_name] += 1
    mes_mas_picos = max(picos_por_mes, key=picos_por_mes.get)

    # Franja horaria mas repetida
    picos_por_franja = defaultdict(int)
    for r in picos:
        picos_por_franja[_franja_horaria(r.timestamp.hour)] += 1
    franja_mas_repetida = max(picos_por_franja, key=picos_por_franja.get)

    # Hora exacta mas repetida
    picos_por_hora = defaultdict(int)
    for r in picos:
        picos_por_hora[r.timestamp.hour] += 1
    hora_mas_repetida = max(picos_por_hora, key=picos_por_hora.get)

    kpis = {
        'total_horas_sobre_umbral': total_picos,
        'pct_sobre_umbral':         _round2((total_picos / total_horas) * 100),
        'pico_maximo_kwh':          _round4(pico_maximo.consumption_kwh),
        'pico_maximo_fecha':        str(pico_maximo.timestamp),
        'pico_maximo_mes':          pico_maximo.month_name,
        'mes_mas_picos':            mes_mas_picos,
        'picos_en_mes_mas':         picos_por_mes[mes_mas_picos],
        'franja_mas_repetida':      franja_mas_repetida,
        'hora_mas_repetida':        f"{hora_mas_repetida:02d}:00",
    }

    print(f"  Pico maximo: {kpis['pico_maximo_kwh']} kW ({kpis['pico_maximo_fecha']})")
    print(f"  Mes con mas picos: {mes_mas_picos} ({kpis['picos_en_mes_mas']} horas)")
    print(f"  Franja mas repetida: {franja_mas_repetida}")

    # ----------------------------------------------------------------
    # TOP 10 PICOS MAS ALTOS (tabla interactiva)
    # ----------------------------------------------------------------

    top10 = sorted(picos, key=lambda r: r.consumption_kwh, reverse=True)[:10]
    top10_data = [
        {
            'ranking':          i + 1,
            'fecha':            r.timestamp.strftime('%d/%m/%Y'),
            'hora':             f"{r.timestamp.hour:02d}:00",
            'dia_semana':       r.day_of_week.capitalize(),
            'mes':              r.month_name.capitalize(),
            'kwh':              _round4(r.consumption_kwh),
            'exceso_kwh':       _round4(r.consumption_kwh - umbral_kw),
            'es_festivo':       'Si' if r.is_holiday else 'No',
            'es_finde':         'Si' if r.is_weekend else 'No',
            'periodo_potencia': r.power_period.value,
            'periodo_energia':  r.energy_period.value,
            'franja':           _franja_horaria(r.timestamp.hour),
        }
        for i, r in enumerate(top10)
    ]

    # ----------------------------------------------------------------
    # EVOLUCION MENSUAL DE PICOS
    # ----------------------------------------------------------------

    by_month_count = defaultdict(int)
    by_month_max   = defaultdict(float)
    by_month_sum   = defaultdict(float)

    for r in picos:
        by_month_count[r.month_name] += 1
        by_month_sum[r.month_name]   += r.consumption_kwh
        if r.consumption_kwh > by_month_max[r.month_name]:
            by_month_max[r.month_name] = r.consumption_kwh

    by_month = {
        mes: {
            'num_picos':  by_month_count[mes],
            'max_kwh':    _round4(by_month_max[mes]),
            'avg_kwh':    _round4(by_month_sum[mes] / by_month_count[mes]),
            'month_num':  MESES_ORDEN.index(mes) + 1 if mes in MESES_ORDEN else 99
        }
        for mes in by_month_count
    }
    by_month = dict(sorted(by_month.items(), key=lambda x: x[1]['month_num']))

    # ----------------------------------------------------------------
    # DISTRIBUCION POR FRANJA HORARIA
    # ----------------------------------------------------------------

    franjas_orden = [
        'Madrugada (0h-6h)',
        'Manana (6h-12h)',
        'Tarde (12h-18h)',
        'Noche (18h-24h)'
    ]

    by_franja = {
        franja: {
            'num_picos':  picos_por_franja.get(franja, 0),
            'pct':        _round2((picos_por_franja.get(franja, 0) / total_picos) * 100)
        }
        for franja in franjas_orden
    }

    # Distribucion por hora exacta (0-23)
    by_hora_exacta = {
        hora: {
            'num_picos': picos_por_hora.get(hora, 0),
            'pct':       _round2((picos_por_hora.get(hora, 0) / total_picos) * 100)
        }
        for hora in range(24)
    }

    # ----------------------------------------------------------------
    # MAPA DE CALOR: MES x HORA
    # ----------------------------------------------------------------

    heatmap_count = defaultdict(int)
    for r in picos:
        clave = (r.month_name, r.timestamp.hour)
        heatmap_count[clave] += 1

    meses_presentes = sorted(
        {r.month_name for r in picos},
        key=lambda m: MESES_ORDEN.index(m) if m in MESES_ORDEN else 99
    )

    heatmap = {
        'meses': meses_presentes,
        'horas': list(range(24)),
        'valores': {}
    }
    for mes in meses_presentes:
        heatmap['valores'][mes] = {}
        for hora in range(24):
            heatmap['valores'][mes][hora] = heatmap_count.get((mes, hora), 0)

    # ----------------------------------------------------------------
    # LABORABLE VS FIN DE SEMANA
    # ----------------------------------------------------------------

    lab   = [r for r in picos if not r.is_weekend and not r.is_holiday]
    finde = [r for r in picos if r.is_weekend or r.is_holiday]

    by_day_type = {
        'laborable': {
            'num_picos': len(lab),
            'pct':       _round2((len(lab) / total_picos) * 100),
            'max_kwh':   _round4(max(r.consumption_kwh for r in lab)) if lab else 0.0,
        },
        'fin_de_semana': {
            'num_picos': len(finde),
            'pct':       _round2((len(finde) / total_picos) * 100),
            'max_kwh':   _round4(max(r.consumption_kwh for r in finde)) if finde else 0.0,
        }
    }

    # ----------------------------------------------------------------
    # POR PERIODO DE POTENCIA P1/P2
    # ----------------------------------------------------------------

    from src.models.internal_data_model import PowerPeriod

    p1_picos = [r for r in picos if r.power_period == PowerPeriod.P1]
    p2_picos = [r for r in picos if r.power_period == PowerPeriod.P2]

    by_period = {
        'P1': {
            'num_picos': len(p1_picos),
            'pct':       _round2((len(p1_picos) / total_picos) * 100),
            'max_kwh':   _round4(max(r.consumption_kwh for r in p1_picos)) if p1_picos else 0.0,
        },
        'P2': {
            'num_picos': len(p2_picos),
            'pct':       _round2((len(p2_picos) / total_picos) * 100),
            'max_kwh':   _round4(max(r.consumption_kwh for r in p2_picos)) if p2_picos else 0.0,
        }
    }

    print(f"  P1: {by_period['P1']['num_picos']} picos | P2: {by_period['P2']['num_picos']} picos")
    print(f"  Laborable: {by_day_type['laborable']['num_picos']} | Finde: {by_day_type['fin_de_semana']['num_picos']}")
    print("Analisis de picos completado.")

    return {
        'umbral_kw':    umbral_kw,
        'total_picos':  total_picos,
        'kpis':         kpis,
        'top10':        top10_data,
        'by_month':     by_month,
        'by_franja':    by_franja,
        'by_hora':      by_hora_exacta,
        'heatmap':      heatmap,
        'by_day_type':  by_day_type,
        'by_period':    by_period,
    }
