# =============================================================================
# src/analysis/optimization_engine.py
# Motor de optimizacion de potencia contratada
# Version: 3.0
#
# Pagina 4: Optimizacion de potencia contratada
#
# El cliente debe entender claramente:
#   1. Con mi potencia actual tengo X excesos al año
#   2. Si subo a 3.45 kW los excesos desaparecen (o se reducen)
#   3. Mis picos de ciertos meses son excepcionales
# =============================================================================

from collections import defaultdict
import numpy as np

import sys
sys.path.append('..')
from src.models.internal_data_model import ElectricityAnalysis, PowerPeriod

POTENCIAS_COMERCIALES = [2.3, 3.45, 4.6, 5.75, 6.9, 8.05, 9.2, 10.35, 11.5, 14.49]

MESES_NOMBRE = {
    'ene': 'enero', 'feb': 'febrero', 'mar': 'marzo', 'abr': 'abril',
    'may': 'mayo', 'jun': 'junio', 'jul': 'julio', 'ago': 'agosto',
    'sep': 'septiembre', 'oct': 'octubre', 'nov': 'noviembre', 'dic': 'diciembre'
}

MESES_ORDEN = [
    'enero', 'febrero', 'marzo', 'abril', 'mayo', 'junio',
    'julio', 'agosto', 'septiembre', 'octubre', 'noviembre', 'diciembre'
]

def _round4(val): return round(val, 4)
def _round2(val): return round(val, 2)

def _primera_potencia_sobre(kw):
    for p in POTENCIAS_COMERCIALES:
        if p >= kw:
            return p
    return POTENCIAS_COMERCIALES[-1]


def run_optimization_analysis(analysis: ElectricityAnalysis,
                               contracted_p1: float = None,
                               contracted_p2: float = None) -> dict:
    """
    Calcula el analisis de optimizacion de potencia.
    Usa el CSV oficial para los picos reales y el CSV de consumo
    para calcular excesos con la potencia actual.
    """
    records           = analysis.hourly_records
    monthly_max_power = analysis.monthly_max_power

    if not records or not monthly_max_power:
        print("ERROR: Faltan datos.")
        return {}

    if contracted_p1 is None and analysis.contract:
        contracted_p1 = analysis.contract.contracted_powers.p1
    if contracted_p2 is None and analysis.contract:
        contracted_p2 = analysis.contract.contracted_powers.p2
    contracted_p1 = contracted_p1 or 0.0
    contracted_p2 = contracted_p2 or 0.0

    print(f"Iniciando analisis de optimizacion...")
    print(f"  Potencia actual: P1={contracted_p1} kW / P2={contracted_p2} kW")

    # Registros por periodo
    records_p1 = [r for r in records if r.power_period == PowerPeriod.P1]
    records_p2 = [r for r in records if r.power_period == PowerPeriod.P2]
    potencias_p1 = [r.consumption_kwh for r in records_p1]
    potencias_p2 = [r.consumption_kwh for r in records_p2]

    # ----------------------------------------------------------------
    # PICOS OFICIALES POR MES (del CSV oficial)
    # ----------------------------------------------------------------

    picos_por_mes = {}
    for r in monthly_max_power:
        mes_corto  = r.month[:3].lower()
        mes_nombre = MESES_NOMBRE.get(mes_corto, mes_corto)
        if mes_nombre not in picos_por_mes:
            picos_por_mes[mes_nombre] = {}
        picos_por_mes[mes_nombre][r.period] = _round4(r.max_kw)

    # Ordenar meses
    meses_ordenados = sorted(
        picos_por_mes.keys(),
        key=lambda m: MESES_ORDEN.index(m) if m in MESES_ORDEN else 99
    )

    # ----------------------------------------------------------------
    # PICOS MENSUALES VS POTENCIA CONTRATADA
    # ----------------------------------------------------------------

    picos_mensuales = []
    for mes in meses_ordenados:
        datos = picos_por_mes[mes]
        pico_punta = datos.get('Punta', 0)
        pico_valle = datos.get('Valle', 0)
        pico_max   = datos.get('Pot.Max', max(pico_punta, pico_valle))

        supera_p1 = pico_punta > contracted_p1 if contracted_p1 > 0 else False
        supera_p2 = pico_valle > contracted_p2 if contracted_p2 > 0 else False

        picos_mensuales.append({
            'mes':          mes,
            'pico_punta':   pico_punta,
            'pico_valle':   pico_valle,
            'pico_max':     pico_max,
            'supera_p1':    supera_p1,
            'supera_p2':    supera_p2,
            'exceso_p1':    _round4(pico_punta - contracted_p1) if supera_p1 else 0.0,
            'exceso_p2':    _round4(pico_valle - contracted_p2) if supera_p2 else 0.0,
        })

    # ----------------------------------------------------------------
    # KPIs
    # ----------------------------------------------------------------

    meses_con_exceso_p1 = [p for p in picos_mensuales if p['supera_p1']]
    meses_con_exceso_p2 = [p for p in picos_mensuales if p['supera_p2']]
    mes_max_exceso_p1   = max(meses_con_exceso_p1, key=lambda x: x['exceso_p1'])['mes'] if meses_con_exceso_p1 else None
    mes_max_exceso_p2   = max(meses_con_exceso_p2, key=lambda x: x['exceso_p2'])['mes'] if meses_con_exceso_p2 else None

    max_pico_punta = max((p['pico_punta'] for p in picos_mensuales), default=0)
    max_pico_valle = max((p['pico_valle'] for p in picos_mensuales), default=0)

    # Excesos desde CSV consumo (para horas exactas)
    horas_exceso_p1 = sum(1 for v in potencias_p1 if v > contracted_p1) if contracted_p1 > 0 else 0
    horas_exceso_p2 = sum(1 for v in potencias_p2 if v > contracted_p2) if contracted_p2 > 0 else 0

    kpis = {
        'contracted_p1':        contracted_p1,
        'contracted_p2':        contracted_p2,
        'horas_exceso_p1':      horas_exceso_p1,
        'horas_exceso_p2':      horas_exceso_p2,
        'meses_exceso_p1':      len(meses_con_exceso_p1),
        'meses_exceso_p2':      len(meses_con_exceso_p2),
        'mes_max_exceso_p1':    mes_max_exceso_p1,
        'mes_max_exceso_p2':    mes_max_exceso_p2,
        'max_pico_punta':       max_pico_punta,
        'max_pico_valle':       max_pico_valle,
        'tiene_exceso':         horas_exceso_p1 > 0 or horas_exceso_p2 > 0,
    }

    print(f"  Meses con exceso P1: {len(meses_con_exceso_p1)}")
    print(f"  Meses con exceso P2: {len(meses_con_exceso_p2)}")
    print(f"  Horas exceso P1: {horas_exceso_p1} | Horas exceso P2: {horas_exceso_p2}")

    # ----------------------------------------------------------------
    # TABLA DE MESES CON EXCESO
    # ----------------------------------------------------------------

    tabla_excesos = []
    for p in picos_mensuales:
        if p['supera_p1'] or p['supera_p2']:
            tabla_excesos.append({
                'mes':        p['mes'].capitalize(),
                'pico_punta': f"{p['pico_punta']} kW",
                'exceso_p1':  f"+{p['exceso_p1']} kW" if p['supera_p1'] else '—',
                'pico_valle': f"{p['pico_valle']} kW",
                'exceso_p2':  f"+{p['exceso_p2']} kW" if p['supera_p2'] else '—',
                'supera_p1':  p['supera_p1'],
                'supera_p2':  p['supera_p2'],
            })

    # ----------------------------------------------------------------
    # OPCIONES SUGERIDAS — solo 3.45 y 4.6
    # ----------------------------------------------------------------

    def horas_exceso_con(potencias, umbral):
        return sum(1 for v in potencias if v > umbral)

    def meses_exceso_con(picos, umbral_campo, umbral_val):
        return sum(1 for p in picos if p[umbral_campo] > umbral_val)

    opciones_sugeridas = {
        'equilibrada': {
            'p1':               3.45,
            'p2':               3.45,
            'horas_exceso_p1':  horas_exceso_con(potencias_p1, 3.45),
            'horas_exceso_p2':  horas_exceso_con(potencias_p2, 3.45),
            'meses_exceso_p1':  meses_exceso_con(picos_mensuales, 'pico_punta', 3.45),
            'meses_exceso_p2':  meses_exceso_con(picos_mensuales, 'pico_valle', 3.45),
            'titulo':           '3.45 kW — Opcion equilibrada',
            'descripcion':      (
                "Cubre la gran mayoria de situaciones habituales. "
                "Pueden producirse excesos en momentos muy puntuales "
                "donde coincidan varios electrodomesticos de alta potencia. "
                "Es la opcion mas economica con un riesgo bajo."
            ),
        },
        'segura': {
            'p1':               4.6,
            'p2':               4.6,
            'horas_exceso_p1':  horas_exceso_con(potencias_p1, 4.6),
            'horas_exceso_p2':  horas_exceso_con(potencias_p2, 4.6),
            'meses_exceso_p1':  meses_exceso_con(picos_mensuales, 'pico_punta', 4.6),
            'meses_exceso_p2':  meses_exceso_con(picos_mensuales, 'pico_valle', 4.6),
            'titulo':           '4.6 kW — Opcion segura',
            'descripcion':      (
                "Cubre absolutamente todos los picos registrados "
                "incluyendo los mas excepcionales. "
                "Sin ningun riesgo de excesos. "
                "Adecuada si quieres total tranquilidad."
            ),
        }
    }

    print(f"  Opcion 3.45 kW — Horas exceso P1: {opciones_sugeridas['equilibrada']['horas_exceso_p1']}")
    print(f"  Opcion 4.6 kW  — Horas exceso P1: {opciones_sugeridas['segura']['horas_exceso_p1']}")
    print("Analisis de optimizacion completado.")

    return {
        'contracted_p1':      contracted_p1,
        'contracted_p2':      contracted_p2,
        'kpis':               kpis,
        'picos_mensuales':    picos_mensuales,
        'tabla_excesos':      tabla_excesos,
        'opciones_sugeridas': opciones_sugeridas,
    }
