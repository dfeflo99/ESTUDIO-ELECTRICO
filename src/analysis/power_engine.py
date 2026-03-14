# =============================================================================
# src/analysis/power_engine.py
# Motor de analisis de potencia electrica
# Version: 1.2
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

POTENCIAS_COMERCIALES = [
    2.3, 3.45, 4.6, 5.75, 6.9, 8.05, 9.2, 10.35, 11.5, 14.49
]

def potencia_comercial_optima(kw: float) -> float:
    for p in POTENCIAS_COMERCIALES:
        if p >= kw:
            return p
    return POTENCIAS_COMERCIALES[-1]


# =============================================================================
# BLOQUE 1 — KPIs DESDE CSV OFICIAL
# =============================================================================

def _calculate_kpis_from_official(monthly_max_power: list) -> dict:
    if not monthly_max_power:
        return {}

    pot_max_records = [r for r in monthly_max_power if r.period == 'Pot.Max']
    punta_records   = [r for r in monthly_max_power if r.period == 'Punta']
    valle_records   = [r for r in monthly_max_power if r.period == 'Valle']

    max_real_kw  = _round4(max(r.max_kw for r in pot_max_records)) if pot_max_records else 0.0
    max_punta_kw = _round4(max(r.max_kw for r in punta_records))   if punta_records   else 0.0
    max_valle_kw = _round4(max(r.max_kw for r in valle_records))   if valle_records   else 0.0

    max_by_month = {}
    for r in monthly_max_power:
        mes = r.month[:3].lower()
        if mes not in max_by_month:
            max_by_month[mes] = {'Punta': 0.0, 'Valle': 0.0, 'Pot.Max': 0.0,
                                 'month_num': r.month_num, 'year': r.year}
        max_by_month[mes][r.period] = _round4(r.max_kw)

    max_by_month = dict(sorted(
        max_by_month.items(), key=lambda x: x[1]['month_num']
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
    potencias = [r.consumption_kwh for r in records]

    avg_power_kw      = _round4(sum(potencias) / len(potencias))
    p99_desde_consumo = _round4(float(np.percentile(potencias, 99)))
    max_desde_consumo = _round4(max(potencias))
    load_factor       = _round4(avg_power_kw / max_desde_consumo) if max_desde_consumo > 0 else 0.0

    horas_sobre_umbral = sum(1 for p in potencias if p > umbral_kw)
    pct_sobre_umbral   = _round2((horas_sobre_umbral / len(potencias)) * 100)

    daily_max  = defaultdict(float)
    daily_meta = defaultdict(dict)

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

    power_ranking = sorted(potencias, reverse=True)

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


# ===========================================
