# =============================================================================
# src/analysis/optimization_engine.py
# Motor de optimizacion de potencia contratada
# Version: 2.0
#
# Pagina 4 del informe: Optimizacion de potencia contratada
#
# CRITERIO:
#   Cruce del CSV oficial de potencias maximas con el CSV de consumo horario.
#   Para cada mes y periodo se analiza si el pico oficial fue puntual
#   o si hay un patron recurrente de horas altas.
#
#   Umbral de patron: 75% del pico oficial del mes
#   - Pocas horas sobre ese umbral -> puntual
#   - Muchas horas sobre ese umbral -> recurrente
#
#   Opciones sugeridas:
#   - Equilibrada: basada en la mediana de picos mensuales + 10%
#   - Segura: basada en el maximo absoluto registrado
# =============================================================================

from collections import defaultdict
import numpy as np

import sys
sys.path.append('..')
from src.models.internal_data_model import (
    ElectricityAnalysis,
    PowerPeriod
)

POTENCIAS_COMERCIALES = [2.3, 3.45, 4.6, 5.75, 6.9, 8.05, 9.2, 10.35, 11.5, 14.49]

MESES_NOMBRE = {
    'ene': 'enero', 'feb': 'febrero', 'mar': 'marzo', 'abr': 'abril',
    'may': 'mayo',  'jun': 'junio',   'jul': 'julio', 'ago': 'agosto',
    'sep': 'septiembre', 'oct': 'octubre', 'nov': 'noviembre', 'dic': 'diciembre'
}

MESES_ORDEN = [
    'enero', 'febrero', 'marzo', 'abril', 'mayo', 'junio',
    'julio', 'agosto', 'septiembre', 'octubre', 'noviembre', 'diciembre'
]

def _round4(val):
    return round(val, 4)

def _round2(val):
    return round(val, 2)

def _primera_potencia_comercial_sobre(kw):
    for p in POTENCIAS_COMERCIALES:
        if p >= kw:
            return p
    return POTENCIAS_COMERCIALES[-1]

def _nivel_riesgo(horas_exceso, total_horas):
    if horas_exceso == 0:
        return 'Ninguno'
    pct = (horas_exceso / total_horas) * 100
    if pct < 0.1:   return 'Muy bajo'
    elif pct < 0.5: return 'Bajo'
    elif pct < 1.0: return 'Moderado'
    else:           return 'Alto'

def _clasificar_patron(horas_sobre_umbral):
    """
    Clasifica si un pico mensual es puntual o recurrente
    segun cuantas horas del mes superaron el 75% del pico oficial.
    """
    if horas_sobre_umbral == 0:
        return 'sin datos'
    elif horas_sobre_umbral <= 2:
        return 'puntual'
    elif horas_sobre_umbral <= 6:
        return 'ocasional'
    else:
        return 'recurrente'


# =============================================================================
# BLOQUE 1 — CRUCE CSV OFICIAL + CSV CONSUMO
# =============================================================================

def _cross_analysis(records: list, monthly_max_power: list) -> dict:
    """
    Para cada mes y periodo del CSV oficial, analiza cuantas horas
    del CSV de consumo superaron el 75% del pico oficial.

    Returns:
        Dict con el analisis por mes y periodo
    """
    # Agrupar registros de consumo por mes y periodo de potencia
    consumo_por_mes_p1 = defaultdict(list)  # {month_name: [kwh, kwh, ...]}
    consumo_por_mes_p2 = defaultdict(list)

    for r in records:
        if r.power_period == PowerPeriod.P1:
            consumo_por_mes_p1[r.month_name].append(r.consumption_kwh)
        else:
            consumo_por_mes_p2[r.month_name].append(r.consumption_kwh)

    # Agrupar CSV oficial por mes
    oficial_por_mes = defaultdict(dict)
    for r in monthly_max_power:
        mes_corto = r.month[:3].lower()
        mes_nombre = MESES_NOMBRE.get(mes_corto, mes_corto)
        oficial_por_mes[mes_nombre][r.period] = {
            'max_kw': r.max_kw,
            'fecha':  r.date,
        }

    # Cruce
    analisis_por_mes = {}

    for mes in sorted(oficial_por_mes.keys(),
                      key=lambda m: MESES_ORDEN.index(m) if m in MESES_ORDEN else 99):

        datos_mes = oficial_por_mes[mes]
        analisis_mes = {}

        # Analisis Punta (P1)
        if 'Punta' in datos_mes:
            pico_punta = datos_mes['Punta']['max_kw']
            umbral_75  = pico_punta * 0.75
            horas_p1   = consumo_por_mes_p1.get(mes, [])
            horas_sobre = sum(1 for v in horas_p1 if v >= umbral_75)
            patron      = _clasificar_patron(horas_sobre)

            analisis_mes['punta'] = {
                'pico_oficial':     _round4(pico_punta),
                'fecha_pico':       datos_mes['Punta']['fecha'].strftime('%d/%m/%Y %H:%M'),
                'umbral_75pct':     _round4(umbral_75),
                'horas_sobre_umbral': horas_sobre,
                'total_horas_p1':   len(horas_p1),
                'patron':           patron,
                'descripcion':      _descripcion_patron(patron, horas_sobre, pico_punta, 'Punta'),
            }

        # Analisis Valle (P2)
        if 'Valle' in datos_mes:
            pico_valle = datos_mes['Valle']['max_kw']
            umbral_75  = pico_valle * 0.75
            horas_p2   = consumo_por_mes_p2.get(mes, [])
            horas_sobre = sum(1 for v in horas_p2 if v >= umbral_75)
            patron      = _clasificar_patron(horas_sobre)

            analisis_mes['valle'] = {
                'pico_oficial':     _round4(pico_valle),
                'fecha_pico':       datos_mes['Valle']['fecha'].strftime('%d/%m/%Y %H:%M'),
                'umbral_75pct':     _round4(umbral_75),
                'horas_sobre_umbral': horas_sobre,
                'total_horas_p2':   len(horas_p2),
                'patron':           patron,
                'descripcion':      _descripcion_patron(patron, horas_sobre, pico_valle, 'Valle'),
            }

        analisis_por_mes[mes] = analisis_mes

    return analisis_por_mes


def _descripcion_patron(patron, horas, pico, periodo):
    """Genera texto explicativo del patron detectado."""
    if patron == 'puntual':
        return (
            f"El pico de {pico} kW en {periodo} fue un evento puntual — "
            f"solo {horas} hora(s) superaron el 75% de ese valor. "
            f"Bajo riesgo de que se repita con frecuencia."
        )
    elif patron == 'ocasional':
        return (
            f"El pico de {pico} kW en {periodo} no fue unico — "
            f"{horas} horas superaron el 75% de ese valor. "
            f"Riesgo moderado de excesos si se baja la potencia."
        )
    elif patron == 'recurrente':
        return (
            f"El pico de {pico} kW en {periodo} forma parte de un patron recurrente — "
            f"{horas} horas superaron el 75% de ese valor. "
            f"Alto riesgo si se contrata una potencia inferior."
        )
    else:
        return "Sin datos suficientes para clasificar el patron."


# =============================================================================
# FUNCION PRINCIPAL
# =============================================================================

def run_optimization_analysis(analysis: ElectricityAnalysis,
                               contracted_p1: float = None,
                               contracted_p2: float = None) -> dict:
    """
    Calcula el analisis completo de optimizacion cruzando
    el CSV oficial con el CSV de consumo horario.
    """
    records           = analysis.hourly_records
    monthly_max_power = analysis.monthly_max_power

    if not records or not monthly_max_power:
        print("ERROR: Faltan datos para el analisis.")
        return {}

    if contracted_p1 is None and analysis.contract:
        contracted_p1 = analysis.contract.contracted_powers.p1
    if contracted_p2 is None and analysis.contract:
        contracted_p2 = analysis.contract.contracted_powers.p2
    contracted_p1 = contracted_p1 or 0.0
    contracted_p2 = contracted_p2 or 0.0

    print(f"Iniciando analisis de optimizacion (cruce de CSVs)...")
    print(f"  Potencia contratada: P1={contracted_p1} kW / P2={contracted_p2} kW")

    total_horas = len(records)

    # Separar por periodo
    records_p1 = [r for r in records if r.power_period == PowerPeriod.P1]
    records_p2 = [r for r in records if r.power_period == PowerPeriod.P2]
    potencias_p1 = [r.consumption_kwh for r in records_p1]
    potencias_p2 = [r.consumption_kwh for r in records_p2]

    # Maximos del CSV oficial
    punta_records = [r for r in monthly_max_power if r.period == 'Punta']
    valle_records = [r for r in monthly_max_power if r.period == 'Valle']

    picos_punta = [r.max_kw for r in punta_records]
    picos_valle = [r.max_kw for r in valle_records]

    max_real_p1    = _round4(max(picos_punta)) if picos_punta else 0.0
    max_real_p2    = _round4(max(picos_valle)) if picos_valle else 0.0
    mediana_p1     = _round4(float(np.median(picos_punta))) if picos_punta else 0.0
    mediana_p2     = _round4(float(np.median(picos_valle))) if picos_valle else 0.0

    # ----------------------------------------------------------------
    # CRUCE CSV OFICIAL + CSV CONSUMO
    # ----------------------------------------------------------------

    analisis_por_mes = _cross_analysis(records, monthly_max_power)

    # Resumen del patron global
    todos_patrones_punta = [
        analisis_por_mes[m]['punta']['patron']
        for m in analisis_por_mes
        if 'punta' in analisis_por_mes[m]
    ]
    todos_patrones_valle = [
        analisis_por_mes[m]['valle']['patron']
        for m in analisis_por_mes
        if 'valle' in analisis_por_mes[m]
    ]

    patron_global_p1 = 'recurrente' if todos_patrones_punta.count('recurrente') > len(todos_patrones_punta) / 2 else \
                       'ocasional'  if todos_patrones_punta.count('ocasional')  > 0 else 'puntual'
    patron_global_p2 = 'recurrente' if todos_patrones_valle.count('recurrente') > len(todos_patrones_valle) / 2 else \
                       'ocasional'  if todos_patrones_valle.count('ocasional')  > 0 else 'puntual'

    print(f"  Patron global P1 (Punta): {patron_global_p1}")
    print(f"  Patron global P2 (Valle): {patron_global_p2}")

    # ----------------------------------------------------------------
    # OPCIONES SUGERIDAS
    # ----------------------------------------------------------------

    # Equilibrada: basada en la mediana de picos + 10%
    equilibrada_p1 = _primera_potencia_comercial_sobre(mediana_p1 * 1.10)
    equilibrada_p2 = _primera_potencia_comercial_sobre(mediana_p2 * 1.10)

    # Segura: basada en el maximo absoluto
    segura_p1 = _primera_potencia_comercial_sobre(max_real_p1)
    segura_p2 = _primera_potencia_comercial_sobre(max_real_p2)

    def horas_exceso(potencias, umbral):
        return sum(1 for v in potencias if v > umbral) if umbral > 0 else 0

    opciones_sugeridas = {
        'equilibrada': {
            'p1':               equilibrada_p1,
            'p2':               equilibrada_p2,
            'horas_exceso_p1':  horas_exceso(potencias_p1, equilibrada_p1),
            'horas_exceso_p2':  horas_exceso(potencias_p2, equilibrada_p2),
            'titulo':           'Opcion equilibrada',
            'descripcion':      (
                f"Basada en la mediana de los picos mensuales de Punta "
                f"({mediana_p1} kW) con un margen del 10%. "
                f"Adecuada cuando los picos son mayormente puntuales u ocasionales. "
                f"Puede haber algun exceso en meses con picos excepcionales."
            ),
            'base_calculo':     f"Mediana picos Punta: {mediana_p1} kW",
        },
        'segura': {
            'p1':               segura_p1,
            'p2':               segura_p2,
            'horas_exceso_p1':  horas_exceso(potencias_p1, segura_p1),
            'horas_exceso_p2':  horas_exceso(potencias_p2, segura_p2),
            'titulo':           'Opcion segura',
            'descripcion':      (
                f"Basada en el maximo absoluto registrado de Punta "
                f"({max_real_p1} kW). Cubre absolutamente todos los picos "
                f"incluyendo los mas excepcionales. Sin riesgo de excesos."
            ),
            'base_calculo':     f"Maximo absoluto Punta: {max_real_p1} kW",
        }
    }

    # ----------------------------------------------------------------
    # KPIs
    # ----------------------------------------------------------------

    horas_exceso_actual_p1 = horas_exceso(potencias_p1, contracted_p1)
    horas_exceso_actual_p2 = horas_exceso(potencias_p2, contracted_p2)

    kpis = {
        'contracted_p1':        contracted_p1,
        'contracted_p2':        contracted_p2,
        'max_real_p1':          max_real_p1,
        'max_real_p2':          max_real_p2,
        'mediana_p1':           mediana_p1,
        'mediana_p2':           mediana_p2,
        'horas_exceso_p1':      horas_exceso_actual_p1,
        'horas_exceso_p2':      horas_exceso_actual_p2,
        'pct_exceso_p1':        _round2((horas_exceso_actual_p1 / len(records_p1)) * 100) if records_p1 else 0.0,
        'pct_exceso_p2':        _round2((horas_exceso_actual_p2 / len(records_p2)) * 100) if records_p2 else 0.0,
        'patron_global_p1':     patron_global_p1,
        'patron_global_p2':     patron_global_p2,
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
            'potencia':       pot,
            'horas_exceso':   h_p1,
            'pct_exceso':     _round2((h_p1 / len(records_p1)) * 100) if records_p1 else 0.0,
            'es_actual':      pot == contracted_p1,
            'es_equilibrada': pot == equilibrada_p1,
            'es_segura':      pot == segura_p1,
        })

        curva_p2.append({
            'potencia':       pot,
            'horas_exceso':   h_p2,
            'pct_exceso':     _round2((h_p2 / len(records_p2)) * 100) if records_p2 else 0.0,
            'es_actual':      pot == contracted_p2,
            'es_equilibrada': pot == equilibrada_p2,
            'es_segura':      pot == segura_p2,
        })

    # ----------------------------------------------------------------
    # TABLA COMPARATIVA
    # ----------------------------------------------------------------

    def build_tabla(curva, max_real):
        return [
            {
                'potencia':       e['potencia'],
                'horas_exceso':   e['horas_exceso'],
                'pct_exceso':     e['pct_exceso'],
                'riesgo':         _nivel_riesgo(e['horas_exceso'], total_horas),
                'margen_kw':      _round4(e['potencia'] - max_real),
                'es_actual':      e['es_actual'],
                'es_equilibrada': e['es_equilibrada'],
                'es_segura':      e['es_segura'],
            }
            for e in curva
        ]

    print("Analisis de optimizacion completado.")

    return {
        'contracted_p1':      contracted_p1,
        'contracted_p2':      contracted_p2,
        'kpis':               kpis,
        'analisis_por_mes':   analisis_por_mes,
        'opciones_sugeridas': opciones_sugeridas,
        'curva_p1':           curva_p1,
        'curva_p2':           curva_p2,
        'tabla_p1':           build_tabla(curva_p1, max_real_p1),
        'tabla_p2':           build_tabla(curva_p2, max_real_p2),
        'potencias_comerciales': POTENCIAS_COMERCIALES,
    }
