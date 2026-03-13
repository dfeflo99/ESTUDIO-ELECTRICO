# =============================================================================
# src/analysis/power_engine.py
# Motor de analisis de potencia electrica
# Version: 1.1
#
# Pagina 2 del informe: Perfil de potencia real
#
# CRITERIO DE FUENTES:
#   CSV de consumo horario   -> distribucion temporal (heatmap, dia a dia,
#                               ranking, factor de carga, horas sobre umbral)
#   CSV potencias maximas    -> KPIs de pico real, comparativa con potencia
#                               contratada y recomendacion optima
#
# NOTA PARA EL USUARIO:
#   Los graficos de distribucion muestran potencia MEDIA por hora.
#   Los KPIs de maximo y la recomendacion usan los picos REALES
#   registrados por la distribuidora.
# =============================================================================

from dataclasses import dataclass, field
from typing import Optional
from collections import defaultdict
import numpy as np

import sys
sys.path.append('..')
from src.models.internal_data_model import (
    ElectricityAnalysis,
    PowerAnalysis,
    ContractedPowers,
    PowerPeriod
)


# =============================================================================
# HELPERS
# =============================================================================

def _round2(val: float) -> float:
    return round(val, 2)

def _round4(val: float) -> float:
    return round(val, 4)

# Potencias comerciales disponibles en 2.0TD (kW)
POTENCIAS_COMERCIALES = [
    2.3, 3.45, 4.6, 5.75, 6.9, 8.05, 9.2, 10.35, 11.5, 14.49
]

def potencia_comercial_optima(kw: float) -> float:
    """Devuelve la potencia comercial mas baja que cubre el valor dado."""
    for p in POTENCIAS_COMERCIALES:
        if p >= kw:
            return p
    return POTENCIAS_COMERCIALES[-1]


# =============================================================================
# BLOQUE 1 — KPIs DESDE CSV OFICIAL DE POTENCIAS MAXIMAS
# =============================================================================

def _calculate_kpis_from_official(monthly_max_power: list) -> dict:
    """
    Calcula los KPIs de potencia real usando el CSV oficial
    de potencias maximas de la distribuidora.

    Usa el tipo 'Pot.Max' que es el pico absoluto registrado cada mes.
    Tambien extrae el maximo de Punta y Valle por separado.

    Returns:
        Dict con max_real_kw, max_punta_kw, max_valle_kw,
        max_by_month (para grafico de barras)
    """
    if not monthly_max_power:
        return {}

    pot_max_records = [r for r in monthly_max_power if r.period == 'Pot.Max']
    punta_records   = [r for r in monthly_max_power if r.period == 'Punta']
    valle_records   = [r for r in monthly_max_power if r.period == 'Valle']

    max_real_kw  = _round4(max(r.max_kw for r in pot_max_records)) if pot_max_records else 0.0
    max_punta_kw = _round4(max(r.max_kw for r in punta_records))   if punta_records   else 0.0
    max_valle_kw = _round4(max(r.max_kw for r in valle_records))   if valle_records   else 0.0

    # Para grafico de barras por mes
    meses_orden = ['ene', 'feb', 'mar', 'abr', 'may', 'jun',
                   'jul', 'ago', 'sep', 'oct', 'nov', 'dic']

    max_by_month = {}
    for r in monthly_max_power:
        mes = r.month[:3].lower()
        if mes not in max_by_month:
            max_by_month[mes] = {'Punta': 0.0, 'Valle': 0.0, 'Pot.Max': 0.0,
                                 'month_num': r.month_num, 'year': r.year}
        max_by_month[mes][r.period] = _round4(r.max_kw)

    max_by_month = dict(sorted(
        max_by_month.items(),
        key=lambda x: x[1]['month_num']
    ))

    return {
        'max_real_kw':  max_real_kw,
        'max_punta_kw': max_punta_kw,
        'max_valle_kw': max_valle_kw,
        'max_by_month': max_by_month,
    }


# =============================================================================
# BLOQUE 2 — RECOMENDACION DESDE CSV OFICIAL
# =============================================================================

def _calculate_recommendation_from_official(monthly_max_power: list,
                                             contracted_p1: float,
                                             contracted_p2: float) -> dict:
    """
    Calcula la recomendacion de potencia optima usando los picos
    reales del CSV oficial + margen de seguridad del 10%.

    En 2.0TD:
        P1 contratada se compara con picos de Punta
        P2 contratada se compara con picos de Valle
    """
    punta_records = [r for r in monthly_max_power if r.period == 'Punta']
    valle_records = [r for r in monthly_max_power if r.period == 'Valle']

    max_punta = max(r.max_kw for r in punta_records) if punta_records else 0.0
    max_valle = max(r.max_kw for r in valle_records) if valle_records else 0.0

    MARGEN = 1.10
    recommended_p1 = potencia_comercial_optima(max_punta * MARGEN)
    recommended_p2 = potencia_comercial_optima(max_valle * MARGEN)

    has_excess  = (contracted_p1 > recommended_p1 * 1.1 or
                   contracted_p2 > recommended_p2 * 1.1)
    has_deficit = (contracted_p1 > 0 and max_punta > contracted_p1 or
                   contracted_p2 > 0 and max_valle > contracted_p2)

    observations = []
    if has_excess:
        observations.append(
            f"Tienes potencia contratada de mas. Podrias considerar "
            f"P1={recommended_p1}kW / P2={recommended_p2}kW y ahorrar "
            f"en el termino fijo de potencia."
        )
    if has_deficit:
        observations.append(
            f"Has superado la potencia contratada en algun momento. "
            f"Esto puede generar penalizaciones en la factura."
        )
    if not has_excess and not has_deficit:
        observations.append(
            f"Tu potencia contratada parece adecuada a tu perfil de consumo real."
        )

    return {
        'recommended_p1':   recommended_p1,
        'recommended_p2':   recommended_p2,
        'has_excess':       has_excess,
        'has_deficit':      has_deficit,
        'observations':     observations,
        'max_punta_real':   _round4(max_punta),
        'max_valle_real':   _round4(max_valle),
    }


# =============================================================================
# BLOQUE 3 — DISTRIBUCION TEMPORAL DESDE CSV DE CONSUMO
# =============================================================================

def _calculate_distribution_from_consumption(records: list,
                                              umbral_kw: float) -> dict:
    """
    Calcula la distribucion temporal de potencia usando el CSV de consumo.
    Recuerda: kWh/hora = potencia MEDIA en esa hora, no el pico instantaneo.

    Args:
        records:   Lista de HourlyRecord
        umbral_kw: Umbral configurable por el usuario (por defecto 2.0 kW)

    Returns:
        Dict con daily_max, heatmap_matrix, power_ranking,
        factor_carga, horas_sobre_umbral, pct_sobre_umbral,
        avg_power_kw, p99_desde_consumo
    """
    potencias = [r.consumption_kwh for r in records]

    # KPIs desde consumo (aproximados)
    avg_power_kw      = _round4(sum(potencias) / len(potencias))
    p99_desde_consumo = _round4(float(np.percentile(potencias, 99)))
    max_desde_consumo = _round4(max(potencias))
    load_factor       = _round4(avg_power_kw / max_desde_consumo) if max_desde_consumo > 0 else 0.0

    # Horas sobre umbral (variable)
    horas_sobre_umbral = sum(1 for p in potencias if p > umbral_kw)
    pct_sobre_umbral   = _round2((horas_sobre_umbral / len(potencias)) * 100)

    # Potencia maxima dia a dia
    daily_max     = defaultdict(float)
    daily_meta    = defaultdict(dict)

    for r in records:
        fecha = r.timestamp.date()
        if r.consumption_kwh > daily_max[fecha]:
            daily_max[fecha] = r.consumption_kwh
            daily_meta[fecha] = {
                'month_name':  r.month_name,
                'day_of_week': r.day_of_week,
                'is_weekend':  r.is_weekend,
                'is_holiday':  r.is_holiday,
            }

    daily_max_power = {
        str(fecha): {
            'max_kw': _round4(daily_max[fecha]),
            **daily_meta[fecha]
        }
        for fecha in sorted(daily_max.keys())
    }

    # Heatmap hora x dia del mes (potencia media)
    heatmap_sum   = defaultdict(float)
    heatmap_count = defaultdict(int)

    for r in records:
        clave = (r.timestamp.hour, r.day_of_month)
        heatmap_sum[clave]   += r.consumption_kwh
        heatmap_count[clave] += 1

    heatmap_matrix = {
        'horas': list(range(0, 24)),
        'dias':  list(range(1, 32)),
        'valores': {}
    }
    for hora in range(24):
        heatmap_matrix['valores'][hora] = {}
        for dia in range(1, 32):
            clave = (hora, dia)
            if clave in heatmap_sum:
                heatmap_matrix['valores'][hora][dia] = _round4(
                    heatmap_sum[clave] / heatmap_count[clave]
                )
            else:
                heatmap_matrix['valores'][hora][dia] = None

    # Curva de ranking
    power_ranking = sorted(potencias, reverse=True)

    # Registros sobre umbral
    records_sobre_umbral = [
        {
            'timestamp':       str(r.timestamp),
            'month_name':      r.month_name,
            'day_of_month':    r.day_of_month,
            'hour':            r.timestamp.hour,
            'consumption_kwh': _round4(r.consumption_kwh),
            'exceso_kwh':      _round4(r.consumption_kwh - umbral_kw),
            'is_weekend':      r.is_weekend,
            'is_holiday':      r.is_holiday,
            'power_period':    r.power_period.value,
            'energy_period':   r.energy_period.value,
        }
        for r in records if r.consumption_kwh > umbral_kw
    ]

    # Excesos sobre potencia contratada (desde consumo, aproximado)
    records_exceso_p1 = []
    records_exceso_p2 = []
    horas_exceso_p1   = 0
    horas_exceso_p2   = 0

    return {
        'avg_power_kw':         avg_power_kw,
        'p99_desde_consumo':    p99_desde_consumo,
        'max_desde_consumo':    max_desde_consumo,
        'load_factor':          load_factor,
        'horas_sobre_umbral':   horas_sobre_umbral,
        'pct_sobre_umbral':     pct_sobre_umbral,
        'daily_max_power':      daily_max_power,
        'heatmap_matrix':       heatmap_matrix,
        'power_ranking':        power_ranking,
        'records_sobre_umbral': records_sobre_umbral,
    }


# =============================================================================
# BLOQUE 4 — INTERPRETACION AUTOMATICA DEL PERFIL
# =============================================================================

def _interpret_profile(avg_power_kw: float, p99_kw: float,
                        max_real_kw: float) -> dict:
    """
    Interpreta automaticamente el perfil de consumo como
    estable, moderadamente variable o muy variable.
    """
    ratio = _round2(p99_kw / avg_power_kw) if avg_power_kw > 0 else 0.0

    if ratio < 2.0:
        tipo = "estable"
        descripcion = (
            f"Tu perfil de consumo es bastante uniforme. "
            f"El P99 ({p99_kw} kW) es solo {ratio}x el promedio "
            f"({avg_power_kw} kW), lo que indica pocos picos extremos. "
            f"El pico real registrado por tu distribuidora fue {max_real_kw} kW."
        )
    elif ratio < 4.0:
        tipo = "moderadamente variable"
        descripcion = (
            f"Tu perfil tiene cierta variabilidad. "
            f"El P99 ({p99_kw} kW) es {ratio}x el promedio "
            f"({avg_power_kw} kW). Hay momentos de mayor demanda pero "
            f"no son extremos. Pico real: {max_real_kw} kW."
        )
    else:
        tipo = "muy variable"
        descripcion = (
            f"Tu perfil es muy irregular con picos destacados. "
            f"El P99 ({p99_kw} kW) es {ratio}x el promedio "
            f"({avg_power_kw} kW). Revisa los momentos de mayor consumo. "
            f"Pico real registrado: {max_real_kw} kW."
        )

    return {'tipo': tipo, 'descripcion': descripcion, 'ratio': ratio}


# =============================================================================
# FUNCION PRINCIPAL
# =============================================================================

def run_power_analysis(analysis: ElectricityAnalysis,
                       contracted_p1: float = None,
                       contracted_p2: float = None,
                       umbral_kw: float = 2.0) -> ElectricityAnalysis:
    """
    Funcion principal del motor de potencia.

    Args:
        analysis:      ElectricityAnalysis con hourly_records validados
        contracted_p1: Potencia contratada P1 en kW
        contracted_p2: Potencia contratada P2 en kW
        umbral_kw:     Umbral configurable por el usuario (default: 2.0 kW)
                       Este valor sera interactivo en el dashboard

    Returns:
        ElectricityAnalysis con power_analysis relleno
    """
    records            = analysis.hourly_records
    monthly_max_power  = analysis.monthly_max_power

    if not records:
        print("ERROR: No hay registros horarios para analizar.")
        return analysis

    print("Iniciando analisis de potencia...")
    print(f"  Umbral configurado: {umbral_kw} kW")

    # Obtener potencias contratadas
    if contracted_p1 is None and analysis.contract:
        contracted_p1 = analysis.contract.contracted_powers.p1
    if contracted_p2 is None and analysis.contract:
        contracted_p2 = analysis.contract.contracted_powers.p2
    contracted_p1 = contracted_p1 or 0.0
    contracted_p2 = contracted_p2 or 0.0

    # ---- BLOQUE 1: KPIs desde CSV oficial ----
    kpis_oficiales = _calculate_kpis_from_official(monthly_max_power)
    max_real_kw    = kpis_oficiales.get('max_real_kw', 0.0)
    max_punta_kw   = kpis_oficiales.get('max_punta_kw', 0.0)
    max_valle_kw   = kpis_oficiales.get('max_valle_kw', 0.0)
    max_by_month   = kpis_oficiales.get('max_by_month', {})

    print(f"  Maximo real (CSV oficial): {max_real_kw} kW")
    print(f"  Maximo Punta:              {max_punta_kw} kW")
    print(f"  Maximo Valle:              {max_valle_kw} kW")

    # ---- BLOQUE 2: Recomendacion desde CSV oficial ----
    rec = _calculate_recommendation_from_official(
        monthly_max_power, contracted_p1, contracted_p2
    )

    print(f"  Potencia recomendada P1:   {rec['recommended_p1']} kW")
    print(f"  Potencia recomendada P2:   {rec['recommended_p2']} kW")

    # ---- BLOQUE 3: Distribucion temporal desde CSV consumo ----
    dist = _calculate_distribution_from_consumption(records, umbral_kw)

    print(f"  Factor de carga:           {dist['load_factor']}")
    print(f"  P99 (desde consumo):       {dist['p99_desde_consumo']} kW")
    print(f"  Horas sobre {umbral_kw}kW:       {dist['horas_sobre_umbral']}")
    print(f"  Porcentaje sobre umbral:   {dist['pct_sobre_umbral']}%")

    # ---- BLOQUE 4: Interpretacion del perfil ----
    perfil = _interpret_profile(
        dist['avg_power_kw'],
        dist['p99_desde_consumo'],
        max_real_kw
    )

    print(f"  Perfil: {perfil['tipo']}")

    # ---- CONSTRUIR PowerAnalysis ----
    contracted = ContractedPowers(p1=contracted_p1, p2=contracted_p2)

    power_analysis = PowerAnalysis(
        # KPIs principales (desde CSV oficial)
        max_power_kw            = max_real_kw,
        p99_power_kw            = dist['p99_desde_consumo'],
        load_factor             = dist['load_factor'],
        hours_exceeds_2kw       = dist['horas_sobre_umbral'],
        pct_exceeds_2kw         = dist['pct_sobre_umbral'],

        # Graficos (desde CSV consumo)
        daily_max_power         = dist['daily_max_power'],
        hourly_power_heatmap    = dist['heatmap_matrix'],
        power_ranking           = dist['power_ranking'],

        # Picos criticos
        records_exceeding_2kw   = dist['records_sobre_umbral'],

        # Potencia contratada y excesos
        contracted_powers       = contracted,
        hours_exceeds_p1        = 0,
        hours_exceeds_p2        = 0,
        records_exceeding_p1    = [],
        records_exceeding_p2    = [],

        # Recomendacion (desde CSV oficial)
        recommended_p1_kw       = rec['recommended_p1'],
        recommended_p2_kw       = rec['recommended_p2'],
        has_excess_contracted   = rec['has_excess'],
        has_deficit_contracted  = rec['has_deficit'],
        observations            = rec['observations'],
    )

    # Campos extra
    power_analysis.perfil_tipo          = perfil['tipo']
    power_analysis.perfil_descripcion   = perfil['descripcion']
    power_analysis.avg_power_kw         = dist['avg_power_kw']
    power_analysis.umbral_kw            = umbral_kw
    power_analysis.max_punta_kw         = max_punta_kw
    power_analysis.max_valle_kw         = max_valle_kw
    power_analysis.max_by_month         = max_by_month

    # Nota explicativa para mostrar al usuario
    power_analysis.nota_metodologia = (
        "Los graficos de distribucion horaria muestran la potencia MEDIA por hora "
        "(calculada a partir de tu curva de consumo). "
        "Los KPIs de potencia maxima y la recomendacion de potencia contratada "
        "se basan en los picos REALES registrados por tu distribuidora."
    )

    analysis.power_analysis = power_analysis

    print("Analisis de potencia completado.")
    return analysis
