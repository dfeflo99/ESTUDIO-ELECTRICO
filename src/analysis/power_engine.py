# =============================================================================
# src/analysis/power_engine.py
# Motor de analisis de potencia electrica
# Version: 1.0
#
# Pagina 2 del informe: Perfil de potencia real
#
# Calcula:
#   - KPIs: maximo, P99, factor de carga, horas sobre umbral, % sobre umbral
#   - Potencia maxima dia a dia
#   - Heatmap hora x dia del mes
#   - Curva de ranking de potencia
#   - Interpretacion automatica del perfil (estable / variable)
#
# Fuente de datos:
#   - hourly_records del CSV de consumo (kWh/hora = kW medio en esa hora)
#   - monthly_max_power del CSV oficial de potencias maximas
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
# HELPER
# =============================================================================

def _round2(val: float) -> float:
    return round(val, 2)

def _round4(val: float) -> float:
    return round(val, 4)


# =============================================================================
# MOTOR PRINCIPAL
# =============================================================================

def run_power_analysis(analysis: ElectricityAnalysis,
                       contracted_p1: float = None,
                       contracted_p2: float = None) -> ElectricityAnalysis:
    """
    Funcion principal del motor de potencia.
    Toma el ElectricityAnalysis con hourly_records validados
    y rellena el campo power_analysis con todos los calculos.

    Args:
        analysis:      ElectricityAnalysis con hourly_records validados
        contracted_p1: Potencia contratada P1 en kW (opcional)
                       Si no se pasa se intenta obtener del contrato
        contracted_p2: Potencia contratada P2 en kW (opcional)

    Returns:
        ElectricityAnalysis con power_analysis relleno
    """
    records = analysis.hourly_records

    if not records:
        print("ERROR: No hay registros horarios para analizar.")
        return analysis

    print("Iniciando analisis de potencia...")

    # Obtener potencias contratadas
    if contracted_p1 is None and analysis.contract:
        contracted_p1 = analysis.contract.contracted_powers.p1
    if contracted_p2 is None and analysis.contract:
        contracted_p2 = analysis.contract.contracted_powers.p2

    # Si no hay contrato usar valores por defecto para el analisis
    contracted_p1 = contracted_p1 or 0.0
    contracted_p2 = contracted_p2 or 0.0

    # Lista de potencias horarias (kWh/hora = kW medio en esa hora)
    potencias = [r.consumption_kwh for r in records]

    # ----------------------------------------------------------------
    # KPIs PRINCIPALES (siempre año completo)
    # ----------------------------------------------------------------

    max_power_kw    = _round4(max(potencias))
    avg_power_kw    = _round4(sum(potencias) / len(potencias))
    p99_power_kw    = _round4(float(np.percentile(potencias, 99)))
    load_factor     = _round4(avg_power_kw / max_power_kw) if max_power_kw > 0 else 0.0

    # Umbral configurable (por defecto 2kW para 2.0TD)
    UMBRAL_KW = 2.0
    horas_sobre_umbral = sum(1 for p in potencias if p > UMBRAL_KW)
    pct_sobre_umbral   = _round2((horas_sobre_umbral / len(potencias)) * 100)

    print(f"  Maximo de potencia:     {max_power_kw} kW")
    print(f"  P99:                    {p99_power_kw} kW")
    print(f"  Factor de carga:        {load_factor}")
    print(f"  Horas sobre {UMBRAL_KW}kW:      {horas_sobre_umbral}")
    print(f"  Porcentaje sobre umbral:{pct_sobre_umbral}%")

    # ----------------------------------------------------------------
    # INTERPRETACION AUTOMATICA DEL PERFIL
    # Compara P99 con el promedio para determinar si es estable o variable
    # ----------------------------------------------------------------

    ratio_variabilidad = _round2(p99_power_kw / avg_power_kw) if avg_power_kw > 0 else 0.0

    if ratio_variabilidad < 2.0:
        perfil_tipo        = "estable"
        perfil_descripcion = (
            f"Tu consumo es bastante uniforme a lo largo del dia. "
            f"El P99 ({p99_power_kw} kW) es {ratio_variabilidad}x el promedio "
            f"({avg_power_kw} kW), lo que indica pocos picos extremos."
        )
    elif ratio_variabilidad < 4.0:
        perfil_tipo        = "moderadamente variable"
        perfil_descripcion = (
            f"Tu consumo tiene cierta variabilidad. "
            f"El P99 ({p99_power_kw} kW) es {ratio_variabilidad}x el promedio "
            f"({avg_power_kw} kW). Hay momentos de mayor demanda pero no son extremos."
        )
    else:
        perfil_tipo        = "muy variable"
        perfil_descripcion = (
            f"Tu consumo es muy irregular con picos destacados. "
            f"El P99 ({p99_power_kw} kW) es {ratio_variabilidad}x el promedio "
            f"({avg_power_kw} kW). Revisa los momentos de mayor consumo."
        )

    print(f"  Perfil: {perfil_tipo}")

    # ----------------------------------------------------------------
    # POTENCIA MAXIMA DIA A DIA
    # Para cada dia cogemos el maximo de todos sus registros horarios
    # ----------------------------------------------------------------

    daily_max = defaultdict(float)
    daily_records = defaultdict(list)

    for r in records:
        fecha = r.timestamp.date()
        if r.consumption_kwh > daily_max[fecha]:
            daily_max[fecha] = r.consumption_kwh
        daily_records[fecha].append(r)

    daily_max_power = {
        str(fecha): {
            'max_kw':       _round4(daily_max[fecha]),
            'month_name':   list(daily_records[fecha])[0].month_name,
            'day_of_week':  list(daily_records[fecha])[0].day_of_week,
            'is_weekend':   list(daily_records[fecha])[0].is_weekend,
            'is_holiday':   list(daily_records[fecha])[0].is_holiday,
        }
        for fecha in sorted(daily_max.keys())
    }

    # ----------------------------------------------------------------
    # HEATMAP HORA x DIA DEL MES
    # Matriz de 24 horas x 31 dias con la potencia media
    # ----------------------------------------------------------------

    heatmap_sum   = defaultdict(float)
    heatmap_count = defaultdict(int)

    for r in records:
        clave = (r.timestamp.hour, r.day_of_month)
        heatmap_sum[clave]   += r.consumption_kwh
        heatmap_count[clave] += 1

    # Calcular promedio para cada celda (hora, dia_mes)
    hourly_power_heatmap = {
        f"{hora}_{dia}": _round4(heatmap_sum[(hora, dia)] / heatmap_count[(hora, dia)])
        for (hora, dia) in heatmap_sum
    }

    # Tambien guardamos estructura matricial para Plotly
    # horas 0-23 x dias 1-31
    heatmap_matrix = {
        'horas':    list(range(0, 24)),
        'dias':     list(range(1, 32)),
        'valores':  {}   # {hora: {dia: valor}}
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

    # ----------------------------------------------------------------
    # CURVA DE RANKING DE POTENCIA
    # Lista ordenada de mayor a menor para la curva de duracion
    # ----------------------------------------------------------------

    power_ranking = sorted(potencias, reverse=True)

    # ----------------------------------------------------------------
    # REGISTROS QUE SUPERAN EL UMBRAL
    # ----------------------------------------------------------------

    records_sobre_umbral = [
        {
            'timestamp':      str(r.timestamp),
            'month_name':     r.month_name,
            'day_of_month':   r.day_of_month,
            'hour':           r.timestamp.hour,
            'consumption_kwh':_round4(r.consumption_kwh),
            'exceso_kwh':     _round4(r.consumption_kwh - UMBRAL_KW),
            'is_weekend':     r.is_weekend,
            'is_holiday':     r.is_holiday,
            'power_period':   r.power_period.value,
            'energy_period':  r.energy_period.value,
        }
        for r in records if r.consumption_kwh > UMBRAL_KW
    ]

    # ----------------------------------------------------------------
    # EXCESOS SOBRE POTENCIA CONTRATADA (si se conoce)
    # ----------------------------------------------------------------

    records_exceso_p1 = []
    records_exceso_p2 = []
    horas_exceso_p1   = 0
    horas_exceso_p2   = 0

    if contracted_p1 > 0 or contracted_p2 > 0:
        for r in records:
            if r.power_period == PowerPeriod.P1 and contracted_p1 > 0:
                if r.consumption_kwh > contracted_p1:
                    exceso = _round4(r.consumption_kwh - contracted_p1)
                    records_exceso_p1.append({
                        'timestamp':      str(r.timestamp),
                        'month_name':     r.month_name,
                        'day_of_month':   r.day_of_month,
                        'hour':           r.timestamp.hour,
                        'consumption_kwh':_round4(r.consumption_kwh),
                        'exceso_kwh':     exceso,
                    })
                    horas_exceso_p1 += 1

            elif r.power_period == PowerPeriod.P2 and contracted_p2 > 0:
                if r.consumption_kwh > contracted_p2:
                    exceso = _round4(r.consumption_kwh - contracted_p2)
                    records_exceso_p2.append({
                        'timestamp':      str(r.timestamp),
                        'month_name':     r.month_name,
                        'day_of_month':   r.day_of_month,
                        'hour':           r.timestamp.hour,
                        'consumption_kwh':_round4(r.consumption_kwh),
                        'exceso_kwh':     exceso,
                    })
                    horas_exceso_p2 += 1

        print(f"  Horas exceso P1 ({contracted_p1}kW): {horas_exceso_p1}")
        print(f"  Horas exceso P2 ({contracted_p2}kW): {horas_exceso_p2}")

    # ----------------------------------------------------------------
    # RECOMENDACION DE POTENCIA OPTIMA
    # Basada en P99 con un margen de seguridad del 10%
    # ----------------------------------------------------------------

    # Calcular P99 por periodo de potencia
    potencias_p1 = [r.consumption_kwh for r in records
                    if r.power_period == PowerPeriod.P1]
    potencias_p2 = [r.consumption_kwh for r in records
                    if r.power_period == PowerPeriod.P2]

    p99_p1 = _round4(float(np.percentile(potencias_p1, 99))) if potencias_p1 else 0.0
    p99_p2 = _round4(float(np.percentile(potencias_p2, 99))) if potencias_p2 else 0.0

    MARGEN_SEGURIDAD = 1.10  # 10% de margen
    recommended_p1 = _round2(p99_p1 * MARGEN_SEGURIDAD)
    recommended_p2 = _round2(p99_p2 * MARGEN_SEGURIDAD)

    # Redondear a potencias comerciales disponibles (2.3, 3.45, 4.6, 5.75, 6.9, 8.05, 9.2, 10.35, 11.5, 14.49)
    POTENCIAS_COMERCIALES = [2.3, 3.45, 4.6, 5.75, 6.9, 8.05, 9.2, 10.35, 11.5, 14.49]

    def potencia_comercial_optima(kw: float) -> float:
        for p in POTENCIAS_COMERCIALES:
            if p >= kw:
                return p
        return POTENCIAS_COMERCIALES[-1]

    recommended_p1_comercial = potencia_comercial_optima(recommended_p1)
    recommended_p2_comercial = potencia_comercial_optima(recommended_p2)

    has_excess  = (contracted_p1 > recommended_p1_comercial * 1.1 or
                   contracted_p2 > recommended_p2_comercial * 1.1)
    has_deficit = horas_exceso_p1 > 0 or horas_exceso_p2 > 0

    observations = []
    if has_excess:
        observations.append(
            f"Parece que tienes potencia contratada de mas. "
            f"Podrias considerar bajar a P1={recommended_p1_comercial}kW / "
            f"P2={recommended_p2_comercial}kW y ahorrar en el termino fijo."
        )
    if has_deficit:
        observations.append(
            f"Has superado la potencia contratada en {horas_exceso_p1} horas en P1 "
            f"y {horas_exceso_p2} horas en P2. Esto puede generar penalizaciones."
        )
    if not has_excess and not has_deficit:
        observations.append(
            f"Tu potencia contratada parece adecuada a tu perfil de consumo."
        )

    print(f"  Potencia recomendada P1: {recommended_p1_comercial} kW")
    print(f"  Potencia recomendada P2: {recommended_p2_comercial} kW")

    # ----------------------------------------------------------------
    # CONSTRUIR PowerAnalysis
    # ----------------------------------------------------------------

    contracted = ContractedPowers(p1=contracted_p1, p2=contracted_p2)

    power_analysis = PowerAnalysis(
        # KPIs
        max_power_kw            = max_power_kw,
        p99_power_kw            = p99_power_kw,
        load_factor             = load_factor,
        hours_exceeds_2kw       = horas_sobre_umbral,
        pct_exceeds_2kw         = pct_sobre_umbral,

        # Graficos
        daily_max_power         = daily_max_power,
        hourly_power_heatmap    = heatmap_matrix,
        power_ranking           = power_ranking,

        # Picos criticos
        records_exceeding_2kw   = records_sobre_umbral,

        # Potencia contratada y excesos
        contracted_powers       = contracted,
        hours_exceeds_p1        = horas_exceso_p1,
        hours_exceeds_p2        = horas_exceso_p2,
        records_exceeding_p1    = records_exceso_p1,
        records_exceeding_p2    = records_exceso_p2,

        # Recomendacion
        recommended_p1_kw       = recommended_p1_comercial,
        recommended_p2_kw       = recommended_p2_comercial,
        has_excess_contracted   = has_excess,
        has_deficit_contracted  = has_deficit,
        observations            = observations,
    )

    # Añadir campos extra
    power_analysis.perfil_tipo         = perfil_tipo
    power_analysis.perfil_descripcion  = perfil_descripcion
    power_analysis.avg_power_kw        = avg_power_kw
    power_analysis.umbral_kw           = UMBRAL_KW

    analysis.power_analysis = power_analysis

    print("Analisis de potencia completado.")
    return analysis
