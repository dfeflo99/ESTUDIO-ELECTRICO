# =============================================================================
# src/analysis/consumption_engine.py
# Motor de analisis de consumo electrico
# Version: 1.0
#
# Pagina 1 del informe: Perfil de consumo general
#
# Calcula:
#   - KPIs principales
#   - Agregaciones para graficos
#   - Desglose por periodo P1/P2/P3
#   - Laborable vs fin de semana
#   - Por temporada (verano/invierno)
#   - Porcentaje de consumo nocturno
# =============================================================================

from dataclasses import dataclass, field
from typing import Optional
from collections import defaultdict

import sys
sys.path.append('..')
from src.models.internal_data_model import (
    ElectricityAnalysis,
    ConsumptionSummary,
    PeriodConsumptionSummary,
    EnergyPeriod
)


# =============================================================================
# HELPERS
# =============================================================================

def _round2(val: float) -> float:
    return round(val, 2)

def _get_season(month: int) -> str:
    """
    Clasifica el mes en temporada.
        Verano:    junio, julio, agosto, septiembre
        Invierno:  diciembre, enero, febrero, marzo
        Entretiempo: abril, mayo, octubre, noviembre
    """
    if month in [6, 7, 8, 9]:
        return 'verano'
    elif month in [12, 1, 2, 3]:
        return 'invierno'
    else:
        return 'entretiempo'

# Orden natural de los meses para graficos
MONTH_ORDER = {
    'enero': 1, 'febrero': 2, 'marzo': 3, 'abril': 4,
    'mayo': 5, 'junio': 6, 'julio': 7, 'agosto': 8,
    'septiembre': 9, 'octubre': 10, 'noviembre': 11, 'diciembre': 12
}

# Orden natural de los dias para graficos
DAY_ORDER = {
    'lunes': 0, 'martes': 1, 'miercoles': 2, 'jueves': 3,
    'viernes': 4, 'sabado': 5, 'domingo': 6
}


# =============================================================================
# MOTOR PRINCIPAL
# =============================================================================

def run_consumption_analysis(analysis: ElectricityAnalysis) -> ElectricityAnalysis:
    """
    Funcion principal del motor de consumo.
    Toma el ElectricityAnalysis con hourly_records ya validados
    y rellena el campo consumption_summary con todos los calculos.

    Args:
        analysis: ElectricityAnalysis con hourly_records validados

    Returns:
        ElectricityAnalysis con consumption_summary relleno

    Ejemplo de uso:
        analysis = run_consumption_analysis(analysis)
        summary  = analysis.consumption_summary
        print(summary.total_kwh)
    """
    records = analysis.hourly_records

    if not records:
        print("ERROR: No hay registros horarios para analizar.")
        return analysis

    print("Iniciando analisis de consumo...")

    # ----------------------------------------------------------------
    # KPIs PRINCIPALES
    # ----------------------------------------------------------------

    total_kwh   = _round2(sum(r.consumption_kwh for r in records))
    total_dias  = len({r.timestamp.date() for r in records})
    total_horas = len(records)

    avg_daily_kwh  = _round2(total_kwh / total_dias) if total_dias > 0 else 0.0
    avg_hourly_kwh = _round2(total_kwh / total_horas) if total_horas > 0 else 0.0

    date_from = min(r.timestamp for r in records)
    date_to   = max(r.timestamp for r in records)

    print(f"  Consumo total:          {total_kwh} kWh")
    print(f"  Promedio diario:        {avg_daily_kwh} kWh")
    print(f"  Promedio por hora:      {avg_hourly_kwh} kWh")
    print(f"  Periodo:                {date_from.date()} a {date_to.date()}")

    # ----------------------------------------------------------------
    # AGREGACION POR MES (suma de kWh por mes)
    # ----------------------------------------------------------------

    by_month_sum   = defaultdict(float)
    by_month_count = defaultdict(int)

    for r in records:
        by_month_sum[r.month_name]   += r.consumption_kwh
        by_month_count[r.month_name] += 1

    by_month = {
        mes: {
            'total_kwh':    _round2(by_month_sum[mes]),
            'avg_kwh':      _round2(by_month_sum[mes] / by_month_count[mes]),
            'num_horas':    by_month_count[mes],
            'month_num':    MONTH_ORDER.get(mes, 0)
        }
        for mes in by_month_sum
    }
    # Ordenar por numero de mes
    by_month = dict(sorted(by_month.items(), key=lambda x: x[1]['month_num']))

    # ----------------------------------------------------------------
    # AGREGACION POR HORA (promedio de kWh por hora del dia 0-23)
    # ----------------------------------------------------------------

    by_hour_sum   = defaultdict(float)
    by_hour_count = defaultdict(int)

    for r in records:
        hora_real = r.timestamp.hour  # 0-23
        by_hour_sum[hora_real]   += r.consumption_kwh
        by_hour_count[hora_real] += 1

    by_hour = {
        hora: {
            'avg_kwh':   _round2(by_hour_sum[hora] / by_hour_count[hora]),
            'total_kwh': _round2(by_hour_sum[hora]),
            'num_dias':  by_hour_count[hora]
        }
        for hora in sorted(by_hour_sum.keys())
    }

    # ----------------------------------------------------------------
    # AGREGACION POR DIA DE LA SEMANA (suma y promedio)
    # ----------------------------------------------------------------

    by_dow_sum   = defaultdict(float)
    by_dow_count = defaultdict(int)

    for r in records:
        dia = r.day_of_week
        by_dow_sum[dia]   += r.consumption_kwh
        by_dow_count[dia] += 1

    by_day_of_week = {
        dia: {
            'total_kwh': _round2(by_dow_sum[dia]),
            'avg_kwh':   _round2(by_dow_sum[dia] / by_dow_count[dia]),
            'num_horas': by_dow_count[dia],
            'day_num':   DAY_ORDER.get(dia, 0)
        }
        for dia in by_dow_sum
    }
    by_day_of_week = dict(sorted(
        by_day_of_week.items(), key=lambda x: x[1]['day_num']
    ))

    # ----------------------------------------------------------------
    # AGREGACION POR DIA DEL MES (promedio del dia 1-31)
    # ----------------------------------------------------------------

    by_dom_sum   = defaultdict(float)
    by_dom_count = defaultdict(int)

    for r in records:
        by_dom_sum[r.day_of_month]   += r.consumption_kwh
        by_dom_count[r.day_of_month] += 1

    by_day_of_month = {
        dia: {
            'avg_kwh':   _round2(by_dom_sum[dia] / by_dom_count[dia]),
            'total_kwh': _round2(by_dom_sum[dia])
        }
        for dia in sorted(by_dom_sum.keys())
    }

    # ----------------------------------------------------------------
    # AGREGACION POR HORA Y FECHA (para grafico detallado)
    # Formato: { 'YYYY-MM-DD HH:00': kwh }
    # ----------------------------------------------------------------

    by_hour_and_date = {
        r.timestamp.strftime('%Y-%m-%d %H:00'): _round2(r.consumption_kwh)
        for r in records
    }

    # ----------------------------------------------------------------
    # DESGLOSE POR PERIODO ENERGETICO P1/P2/P3
    # ----------------------------------------------------------------

    period_sums   = defaultdict(float)
    period_counts = defaultdict(int)

    for r in records:
        period_sums[r.energy_period]   += r.consumption_kwh
        period_counts[r.energy_period] += 1

    by_energy_period = {}
    for period in [EnergyPeriod.P1, EnergyPeriod.P2, EnergyPeriod.P3]:
        kwh   = period_sums.get(period, 0.0)
        count = period_counts.get(period, 0)
        by_energy_period[period.value] = PeriodConsumptionSummary(
            period           = period,
            total_kwh        = _round2(kwh),
            avg_kwh_per_hour = _round2(kwh / count) if count > 0 else 0.0,
            pct_of_total     = _round2((kwh / total_kwh) * 100) if total_kwh > 0 else 0.0
        )

    print(f"  P1 Punta:  {by_energy_period['P1'].total_kwh} kWh "
          f"({by_energy_period['P1'].pct_of_total}%)")
    print(f"  P2 Llano:  {by_energy_period['P2'].total_kwh} kWh "
          f"({by_energy_period['P2'].pct_of_total}%)")
    print(f"  P3 Valle:  {by_energy_period['P3'].total_kwh} kWh "
          f"({by_energy_period['P3'].pct_of_total}%)")

    # ----------------------------------------------------------------
    # LABORABLE VS FIN DE SEMANA
    # ----------------------------------------------------------------

    lab_kwh = sum(r.consumption_kwh for r in records
                  if not r.is_weekend and not r.is_holiday)
    fds_kwh = sum(r.consumption_kwh for r in records
                  if r.is_weekend or r.is_holiday)

    lab_horas = sum(1 for r in records if not r.is_weekend and not r.is_holiday)
    fds_horas = sum(1 for r in records if r.is_weekend or r.is_holiday)

    by_day_type = {
        'laborable': {
            'total_kwh':    _round2(lab_kwh),
            'avg_kwh':      _round2(lab_kwh / lab_horas) if lab_horas > 0 else 0.0,
            'num_horas':    lab_horas,
            'pct_of_total': _round2((lab_kwh / total_kwh) * 100) if total_kwh > 0 else 0.0
        },
        'fin_de_semana': {
            'total_kwh':    _round2(fds_kwh),
            'avg_kwh':      _round2(fds_kwh / fds_horas) if fds_horas > 0 else 0.0,
            'num_horas':    fds_horas,
            'pct_of_total': _round2((fds_kwh / total_kwh) * 100) if total_kwh > 0 else 0.0
        }
    }

    print(f"  Laborable:       {by_day_type['laborable']['total_kwh']} kWh "
          f"({by_day_type['laborable']['pct_of_total']}%)")
    print(f"  Fin de semana:   {by_day_type['fin_de_semana']['total_kwh']} kWh "
          f"({by_day_type['fin_de_semana']['pct_of_total']}%)")

    # ----------------------------------------------------------------
    # POR TEMPORADA
    # ----------------------------------------------------------------

    season_sums   = defaultdict(float)
    season_counts = defaultdict(int)

    for r in records:
        season = _get_season(r.month)
        season_sums[season]   += r.consumption_kwh
        season_counts[season] += 1

    by_season = {
        season: {
            'total_kwh':    _round2(season_sums[season]),
            'avg_kwh':      _round2(season_sums[season] / season_counts[season])
                            if season_counts[season] > 0 else 0.0,
            'num_horas':    season_counts[season],
            'pct_of_total': _round2((season_sums[season] / total_kwh) * 100)
                            if total_kwh > 0 else 0.0
        }
        for season in ['verano', 'invierno', 'entretiempo']
        if season in season_sums
    }

    # ----------------------------------------------------------------
    # CONSUMO NOCTURNO (horas 0-7)
    # ----------------------------------------------------------------

    nocturno_kwh   = sum(r.consumption_kwh for r in records
                         if r.timestamp.hour < 8)
    nocturno_horas = sum(1 for r in records if r.timestamp.hour < 8)
    pct_nocturno   = _round2((nocturno_kwh / total_kwh) * 100) if total_kwh > 0 else 0.0

    nocturno = {
        'total_kwh':    _round2(nocturno_kwh),
        'avg_kwh':      _round2(nocturno_kwh / nocturno_horas)
                        if nocturno_horas > 0 else 0.0,
        'pct_of_total': pct_nocturno
    }

    print(f"  Consumo nocturno (0h-8h): {nocturno['total_kwh']} kWh "
          f"({nocturno['pct_of_total']}%)")

    # ----------------------------------------------------------------
    # CONSTRUIR ConsumptionSummary
    # ----------------------------------------------------------------

    summary = ConsumptionSummary(
        # KPIs
        total_kwh          = total_kwh,
        avg_daily_kwh      = avg_daily_kwh,
        avg_hourly_kwh     = avg_hourly_kwh,

        # Rango temporal
        date_from          = date_from,
        date_to            = date_to,
        total_days         = total_dias,

        # Agregaciones para graficos
        by_month           = by_month,
        by_hour            = by_hour,
        by_day_of_week     = by_day_of_week,
        by_day_of_month    = by_day_of_month,
        by_hour_and_date   = by_hour_and_date,

        # Periodos
        by_energy_period   = by_energy_period,
    )

    # Anadir campos extra al summary (no estan en el dataclass base,
    # los adjuntamos dinamicamente para no romper compatibilidad)
    summary.by_day_type  = by_day_type
    summary.by_season    = by_season
    summary.nocturno     = nocturno

    # Guardar en el objeto principal
    analysis.consumption_summary = summary

    print("Analisis de consumo completado.")
    return analysis
