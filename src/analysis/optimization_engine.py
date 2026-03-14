# =============================================================================
# src/analysis/optimization_engine.py
# Motor de optimizacion de potencia contratada
# Version: 1.0
#
# Pagina 4 del informe: Optimizacion de potencia contratada
#
# Calcula:
#   - KPIs: potencia actual, recomendada, horas exceso P1/P2
#   - Curva de horas superadas para cada potencia comercial
#   - Tabla comparativa de opciones con nivel de riesgo
#
# Nota: No incluye calculos economicos (euros).
#       El apartado economico se tratara en el estudio de factura.
# =============================================================================

from collections import defaultdict
from typing import Optional

import sys
sys.path.append('..')
from src.models.internal_data_model import (
    ElectricityAnalysis,
    PowerPeriod
)

# Potencias comerciales disponibles en 2.0TD (kW)
POTENCIAS_COMERCIALES = [2.3, 3.45, 4.6, 5.75, 6.9, 8.05, 9.2, 10.35, 11.5, 14.49]

def _round4(val: float) -> float:
    return round(val, 4)

def _round2(val: float) -> float:
    return round(val, 2)

def _nivel_riesgo(horas_exceso: int, total_horas: int) -> str:
    """
    Clasifica el nivel de riesgo segun el porcentaje de horas con exceso.
        Seguro:    0 horas de exceso
        Bajo:      < 0.1% de las horas
        Moderado:  0.1% - 0.5%
        Alto:      > 0.5%
    """
    if horas_exceso == 0:
        return 'Seguro'
    pct = (horas_exceso / total_horas) * 100
    if pct < 0.1:
        return 'Bajo'
    elif pct < 0.5:
        return 'Moderado'
    else:
        return 'Alto'

def _potencia_recomendada_comercial(max_real: float) -> float:
    """Devuelve la potencia comercial minima que cubre el maximo real + 10%."""
    objetivo = max_real * 1.10
    for p in POTENCIAS_COMERCIALES:
        if p >= objetivo:
            return p
    return POTENCIAS_COMERCIALES[-1]


# =============================================================================
# FUNCION PRINCIPAL
# =============================================================================

def run_optimization_analysis(analysis: ElectricityAnalysis,
                               contracted_p1: float = None,
                               contracted_p2: float = None) -> dict:
    """
    Calcula el analisis completo de optimizacion de potencia contratada.

    Args:
        analysis:      ElectricityAnalysis con hourly_records y monthly_max_power
        contracted_p1: Potencia contratada P1 actual en kW
        contracted_p2: Potencia contratada P2 actual en kW

    Returns:
        Diccionario con todos los calculos listos para los graficos
    """
    records           = analysis.hourly_records
    monthly_max_power = analysis.monthly_max_power

    if not records:
        print("ERROR: No hay registros para analizar.")
        return {}

    # Obtener potencias contratadas
    if contracted_p1 is None and analysis.contract:
        contracted_p1 = analysis.contract.contracted_powers.p1
    if contracted_p2 is None and analysis.contract:
        contracted_p2 = analysis.contract.contracted_powers.p2
    contracted_p1 = contracted_p1 or 0.0
    contracted_p2 = contracted_p2 or 0.0

    print(f"Iniciando analisis de optimizacion...")
    print(f"  Potencia contratada actual: P1={contracted_p1} kW / P2={contracted_p2} kW")

    total_horas = len(records)

    # Separar registros por periodo de potencia
    records_p1 = [r for r in records if r.power_period == PowerPeriod.P1]
    records_p2 = [r for r in records if r.power_period == PowerPeriod.P2]

    potencias_p1 = [r.consumption_kwh for r in records_p1]
    potencias_p2 = [r.consumption_kwh for r in records_p2]

    # Maximos reales desde CSV oficial
    punta_records = [r for r in monthly_max_power if r.period == 'Punta']
    valle_records = [r for r in monthly_max_power if r.period == 'Valle']

    max_real_p1 = _round4(max(r.max_kw for r in punta_records)) if punta_records else _round4(max(potencias_p1)) if potencias_p1 else 0.0
    max_real_p2 = _round4(max(r.max_kw for r in valle_records)) if valle_records else _round4(max(potencias_p2)) if potencias_p2 else 0.0

    # Potencias recomendadas
    recommended_p1 = _potencia_recomendada_comercial(max_real_p1)
    recommended_p2 = _potencia_recomendada_comercial(max_real_p2)

    # Horas de exceso con la potencia actual
    horas_exceso_p1_actual = sum(1 for v in potencias_p1 if v > contracted_p1) if contracted_p1 > 0 else 0
    horas_exceso_p2_actual = sum(1 for v in potencias_p2 if v > contracted_p2) if contracted_p2 > 0 else 0

    print(f"  Maximo real P1 (Punta): {max_real_p1} kW")
    print(f"  Maximo real P2 (Valle): {max_real_p2} kW")
    print(f"  Recomendada P1: {recommended_p1} kW")
    print(f"  Recomendada P2: {recommended_p2} kW")
    print(f"  Horas exceso P1 actual: {horas_exceso_p1_actual}")
    print(f"  Horas exceso P2 actual: {horas_exceso_p2_actual}")

    # ----------------------------------------------------------------
    # KPIs
    # ----------------------------------------------------------------

    kpis = {
        'contracted_p1':        contracted_p1,
        'contracted_p2':        contracted_p2,
        'recommended_p1':       recommended_p1,
        'recommended_p2':       recommended_p2,
        'max_real_p1':          max_real_p1,
        'max_real_p2':          max_real_p2,
        'horas_exceso_p1':      horas_exceso_p1_actual,
        'horas_exceso_p2':      horas_exceso_p2_actual,
        'pct_exceso_p1':        _round2((horas_exceso_p1_actual / len(records_p1)) * 100) if records_p1 else 0.0,
        'pct_exceso_p2':        _round2((horas_exceso_p2_actual / len(records_p2)) * 100) if records_p2 else 0.0,
        'tiene_exceso':         horas_exceso_p1_actual > 0 or horas_exceso_p2_actual > 0,
        'tiene_sobredimension': contracted_p1 > recommended_p1 * 1.1 or contracted_p2 > recommended_p2 * 1.1,
    }

    # ----------------------------------------------------------------
    # CURVA DE HORAS SUPERADAS VS POTENCIA (P1 y P2)
    # Para cada potencia comercial calcula cuantas horas se superarian
    # ----------------------------------------------------------------

    curva_p1 = []
    curva_p2 = []

    for pot in POTENCIAS_COMERCIALES:
        horas_sup_p1 = sum(1 for v in potencias_p1 if v > pot)
        horas_sup_p2 = sum(1 for v in potencias_p2 if v > pot)

        curva_p1.append({
            'potencia':     pot,
            'horas_exceso': horas_sup_p1,
            'pct_exceso':   _round2((horas_sup_p1 / len(records_p1)) * 100) if records_p1 else 0.0,
            'es_actual':    pot == contracted_p1,
            'es_recomendada': pot == recommended_p1,
        })

        curva_p2.append({
            'potencia':     pot,
            'horas_exceso': horas_sup_p2,
            'pct_exceso':   _round2((horas_sup_p2 / len(records_p2)) * 100) if records_p2 else 0.0,
            'es_actual':    pot == contracted_p2,
            'es_recomendada': pot == recommended_p2,
        })

    # ----------------------------------------------------------------
    # TABLA COMPARATIVA DE OPCIONES
    # ----------------------------------------------------------------

    tabla_opciones_p1 = [
        {
            'potencia':         pot,
            'horas_exceso':     entry['horas_exceso'],
            'pct_exceso':       entry['pct_exceso'],
            'riesgo':           _nivel_riesgo(entry['horas_exceso'], total_horas),
            'es_actual':        pot == contracted_p1,
            'es_recomendada':   pot == recommended_p1,
            'margen_kw':        _round4(pot - max_real_p1),
        }
        for pot, entry in zip(POTENCIAS_COMERCIALES, curva_p1)
    ]

    tabla_opciones_p2 = [
        {
            'potencia':         pot,
            'horas_exceso':     entry['horas_exceso'],
            'pct_exceso':       entry['pct_exceso'],
            'riesgo':           _nivel_riesgo(entry['horas_exceso'], total_horas),
            'es_actual':        pot == contracted_p2,
            'es_recomendada':   pot == recommended_p2,
            'margen_kw':        _round4(pot - max_real_p2),
        }
        for pot, entry in zip(POTENCIAS_COMERCIALES, curva_p2)
    ]

    # ----------------------------------------------------------------
    # EXCESOS DETALLADOS CON POTENCIA ACTUAL
    # ----------------------------------------------------------------

    excesos_p1 = [
        {
            'timestamp':    str(r.timestamp),
            'fecha':        r.timestamp.strftime('%d/%m/%Y'),
            'hora':         f"{r.timestamp.hour:02d}:00",
            'dia_semana':   r.day_of_week.capitalize(),
            'mes':          r.month_name.capitalize(),
            'kwh':          _round4(r.consumption_kwh),
            'exceso_kwh':   _round4(r.consumption_kwh - contracted_p1),
        }
        for r in records_p1 if r.consumption_kwh > contracted_p1 and contracted_p1 > 0
    ]

    excesos_p2 = [
        {
            'timestamp':    str(r.timestamp),
            'fecha':        r.timestamp.strftime('%d/%m/%Y'),
            'hora':         f"{r.timestamp.hour:02d}:00",
            'dia_semana':   r.day_of_week.capitalize(),
            'mes':          r.month_name.capitalize(),
            'kwh':          _round4(r.consumption_kwh),
            'exceso_kwh':   _round4(r.consumption_kwh - contracted_p2),
        }
        for r in records_p2 if r.consumption_kwh > contracted_p2 and contracted_p2 > 0
    ]

    print("Analisis de optimizacion completado.")

    return {
        'contracted_p1':      contracted_p1,
        'contracted_p2':      contracted_p2,
        'kpis':               kpis,
        'curva_p1':           curva_p1,
        'curva_p2':           curva_p2,
        'tabla_opciones_p1':  tabla_opciones_p1,
        'tabla_opciones_p2':  tabla_opciones_p2,
        'excesos_p1':         excesos_p1,
        'excesos_p2':         excesos_p2,
        'potencias_comerciales': POTENCIAS_COMERCIALES,
    }
