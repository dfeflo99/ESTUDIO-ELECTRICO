# =============================================================================
# src/analysis/optimization_engine.py
# Motor de optimizacion de potencia contratada
# Version: 1.1
#
# Pagina 4 del informe: Optimizacion de potencia contratada
#
# CRITERIO:
#   No se da una "recomendacion automatica" unica.
#   Se presentan dos "opciones sugeridas" con su explicacion:
#     - Opcion equilibrada: primera potencia comercial que supera el P95
#       del consumo horario con un 5% de margen
#     - Opcion segura: primera potencia comercial que supera el maximo
#       real del CSV oficial
#   El cliente decide con informacion completa.
#
# Nota: No incluye calculos economicos (euros).
# =============================================================================

from collections import defaultdict
import numpy as np

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
    if horas_exceso == 0:
        return 'Ninguno'
    pct = (horas_exceso / total_horas) * 100
    if pct < 0.1:
        return 'Muy bajo'
    elif pct < 0.5:
        return 'Bajo'
    elif pct < 1.0:
        return 'Moderado'
    else:
        return 'Alto'

def _primera_potencia_comercial_sobre(kw: float) -> float:
    """Devuelve la primera potencia comercial estrictamente superior al valor dado."""
    for p in POTENCIAS_COMERCIALES:
        if p >= kw:
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

    # Separar por periodo de potencia
    records_p1 = [r for r in records if r.power_period == PowerPeriod.P1]
    records_p2 = [r for r in records if r.power_period == PowerPeriod.P2]

    potencias_p1 = [r.consumption_kwh for r in records_p1]
    potencias_p2 = [r.consumption_kwh for r in records_p2]

    # ----------------------------------------------------------------
    # MAXIMOS REALES DESDE CSV OFICIAL
    # ----------------------------------------------------------------

    punta_records = [r for r in monthly_max_power if r.period == 'Punta']
    valle_records = [r for r in monthly_max_power if r.period == 'Valle']

    max_real_p1 = _round4(max(r.max_kw for r in punta_records)) if punta_records else _round4(max(potencias_p1)) if potencias_p1 else 0.0
    max_real_p2 = _round4(max(r.max_kw for r in valle_records)) if valle_records else _round4(max(potencias_p2)) if potencias_p2 else 0.0

    # ----------------------------------------------------------------
    # P95 DESDE CSV DE CONSUMO HORARIO
    # ----------------------------------------------------------------

    p95_p1 = _round4(float(np.percentile(potencias_p1, 95))) if potencias_p1 else 0.0
    p95_p2 = _round4(float(np.percentile(potencias_p2, 95))) if potencias_p2 else 0.0

    # ----------------------------------------------------------------
    # DOS OPCIONES SUGERIDAS (no recomendacion automatica)
    # ----------------------------------------------------------------

    MARGEN_EQUILIBRADA = 1.05  # 5% sobre P95

    # Opcion equilibrada: cubre P95 con 5% de margen
    equilibrada_p1 = _primera_potencia_comercial_sobre(p95_p1 * MARGEN_EQUILIBRADA)
    equilibrada_p2 = _primera_potencia_comercial_sobre(p95_p2 * MARGEN_EQUILIBRADA)

    # Opcion segura: cubre el maximo real registrado
    segura_p1 = _primera_potencia_comercial_sobre(max_real_p1)
    segura_p2 = _primera_potencia_comercial_sobre(max_real_p2)

    # Horas de exceso para cada opcion
    def horas_exceso(potencias, umbral):
        return sum(1 for v in potencias if v > umbral) if umbral > 0 else 0

    horas_exceso_actual_p1      = horas_exceso(potencias_p1, contracted_p1)
    horas_exceso_actual_p2      = horas_exceso(potencias_p2, contracted_p2)
    horas_exceso_equilibrada_p1 = horas_exceso(potencias_p1, equilibrada_p1)
    horas_exceso_equilibrada_p2 = horas_exceso(potencias_p2, equilibrada_p2)
    horas_exceso_segura_p1      = horas_exceso(potencias_p1, segura_p1)
    horas_exceso_segura_p2      = horas_exceso(potencias_p2, segura_p2)

    print(f"  P95 consumo P1: {p95_p1} kW | Maximo real P1: {max_real_p1} kW")
    print(f"  P95 consumo P2: {p95_p2} kW | Maximo real P2: {max_real_p2} kW")
    print(f"  Opcion equilibrada P1: {equilibrada_p1} kW ({horas_exceso_equilibrada_p1}h exceso)")
    print(f"  Opcion segura P1:      {segura_p1} kW ({horas_exceso_segura_p1}h exceso)")

    opciones_sugeridas = {
        'equilibrada': {
            'p1':               equilibrada_p1,
            'p2':               equilibrada_p2,
            'horas_exceso_p1':  horas_exceso_equilibrada_p1,
            'horas_exceso_p2':  horas_exceso_equilibrada_p2,
            'riesgo_p1':        _nivel_riesgo(horas_exceso_equilibrada_p1, total_horas),
            'riesgo_p2':        _nivel_riesgo(horas_exceso_equilibrada_p2, total_horas),
            'titulo':           'Opcion equilibrada',
            'descripcion':      (
                f"Cubre el 95% de las horas de uso habitual con un margen del 5%. "
                f"Pueden producirse excesos puntuales en momentos de coincidencia "
                f"de varios electrodomesticos, pero son poco frecuentes. "
                f"Es la opcion mas economica con un riesgo aceptable."
            ),
            'base_calculo':     f"P95 consumo horario P1: {p95_p1} kW",
        },
        'segura': {
            'p1':               segura_p1,
            'p2':               segura_p2,
            'horas_exceso_p1':  horas_exceso_segura_p1,
            'horas_exceso_p2':  horas_exceso_segura_p2,
            'riesgo_p1':        _nivel_riesgo(horas_exceso_segura_p1, total_horas),
            'riesgo_p2':        _nivel_riesgo(horas_exceso_segura_p2, total_horas),
            'titulo':           'Opcion segura',
            'descripcion':      (
                f"Cubre absolutamente todos los picos registrados, incluidos "
                f"los mas excepcionales. Sin riesgo de excesos. "
                f"Adecuada si quieres total tranquilidad o si usas habitualmente "
                f"varios electrodomesticos de alta potencia a la vez."
            ),
            'base_calculo':     f"Maximo real registrado P1: {max_real_p1} kW",
        }
    }

    # ----------------------------------------------------------------
    # KPIs
    # ----------------------------------------------------------------

    kpis = {
        'contracted_p1':        contracted_p1,
        'contracted_p2':        contracted_p2,
        'horas_exceso_p1':      horas_exceso_actual_p1,
        'horas_exceso_p2':      horas_exceso_actual_p2,
        'pct_exceso_p1':        _round2((horas_exceso_actual_p1 / len(records_p1)) * 100) if records_p1 else 0.0,
        'pct_exceso_p2':        _round2((horas_exceso_actual_p2 / len(records_p2)) * 100) if records_p2 else 0.0,
        'max_real_p1':          max_real_p1,
        'max_real_p2':          max_real_p2,
        'p95_p1':               p95_p1,
        'p95_p2':               p95_p2,
        'tiene_exceso':         horas_exceso_actual_p1 > 0 or horas_exceso_actual_p2 > 0,
    }

    # ----------------------------------------------------------------
    # CURVA DE HORAS SUPERADAS VS POTENCIA
    # ----------------------------------------------------------------

    curva_p1 = []
    curva_p2 = []

    for pot in POTENCIAS_COMERCIALES:
        h_p1 = horas_exceso(potencias_p1, pot)
        h_p2 = horas_exceso(potencias_p2, pot)

        curva_p1.append({
            'potencia':         pot,
            'horas_exceso':     h_p1,
            'pct_exceso':       _round2((h_p1 / len(records_p1)) * 100) if records_p1 else 0.0,
            'es_actual':        pot == contracted_p1,
            'es_equilibrada':   pot == equilibrada_p1,
            'es_segura':        pot == segura_p1,
        })

        curva_p2.append({
            'potencia':         pot,
            'horas_exceso':     h_p2,
            'pct_exceso':       _round2((h_p2 / len(records_p2)) * 100) if records_p2 else 0.0,
            'es_actual':        pot == contracted_p2,
            'es_equilibrada':   pot == equilibrada_p2,
            'es_segura':        pot == segura_p2,
        })

    # ----------------------------------------------------------------
    # TABLA COMPARATIVA DE OPCIONES
    # ----------------------------------------------------------------

    def build_tabla(curva, max_real, p95):
        return [
            {
                'potencia':       entry['potencia'],
                'horas_exceso':   entry['horas_exceso'],
                'pct_exceso':     entry['pct_exceso'],
                'riesgo':         _nivel_riesgo(entry['horas_exceso'], total_horas),
                'margen_kw':      _round4(entry['potencia'] - max_real),
                'es_actual':      entry['es_actual'],
                'es_equilibrada': entry['es_equilibrada'],
                'es_segura':      entry['es_segura'],
            }
            for entry in curva
        ]

    tabla_p1 = build_tabla(curva_p1, max_real_p1, p95_p1)
    tabla_p2 = build_tabla(curva_p2, max_real_p2, p95_p2)

    print("Analisis de optimizacion completado.")

    return {
        'contracted_p1':      contracted_p1,
        'contracted_p2':      contracted_p2,
        'kpis':               kpis,
        'opciones_sugeridas': opciones_sugeridas,
        'curva_p1':           curva_p1,
        'curva_p2':           curva_p2,
        'tabla_p1':           tabla_p1,
        'tabla_p2':           tabla_p2,
        'potencias_comerciales': POTENCIAS_COMERCIALES,
    }
