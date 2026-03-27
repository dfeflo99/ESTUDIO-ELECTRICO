# =============================================================================
# src/analysis/optimization_engine.py
# Motor de optimizacion de potencia contratada
# Compatible con 2.0TD + 3.0TD
# =============================================================================

from collections import defaultdict

from src.models.internal_data_model import (
    ElectricityAnalysis,
    ContractType,
)

# =============================================================================
# CONFIG
# =============================================================================

POTENCIAS_COMERCIALES_2_0 = [2.3, 3.45, 4.6, 5.75, 6.9, 8.05, 9.2, 10.35, 11.5, 14.49]

MESES_NOMBRE = {
    'ene': 'enero', 'feb': 'febrero', 'mar': 'marzo', 'abr': 'abril',
    'may': 'mayo', 'jun': 'junio', 'jul': 'julio', 'ago': 'agosto',
    'sep': 'septiembre', 'oct': 'octubre', 'nov': 'noviembre', 'dic': 'diciembre'
}

MESES_ORDEN = [
    'enero', 'febrero', 'marzo', 'abril', 'mayo', 'junio',
    'julio', 'agosto', 'septiembre', 'octubre', 'noviembre', 'diciembre'
]


# =============================================================================
# HELPERS
# =============================================================================

def _round4(val):
    return round(val, 4)

def _round2(val):
    return round(val, 2)


def _get_period_order(contract_type: ContractType):
    if contract_type == ContractType.TD_3_0:
        return ["P1", "P2", "P3", "P4", "P5", "P6"]
    return ["P1", "P3"]


def _get_month_name(month_text: str) -> str:
    """
    Convierte:
    - ene-25 -> enero
    - feb-24 -> febrero
    - 02-2024 -> feb (si viniera algo raro, mantiene aproximacion)
    """
    text = str(month_text).strip().lower()
    corto = text[:3]
    return MESES_NOMBRE.get(corto, corto)


def _get_contracted_periods(
    analysis: ElectricityAnalysis,
    contract_type: ContractType,
    contracted_p1=None,
    contracted_p2=None,
    contracted_p3=None,
    contracted_p4=None,
    contracted_p5=None,
    contracted_p6=None,
):
    base = analysis.contract.contracted_powers if analysis.contract else None

    def pick(attr, explicit):
        if explicit is not None:
            return float(explicit)
        if base is not None:
            return float(getattr(base, attr, 0.0) or 0.0)
        return 0.0

    contracted = {
        "P1": pick("p1", contracted_p1),
        "P2": pick("p2", contracted_p2),
        "P3": pick("p3", contracted_p3),
        "P4": pick("p4", contracted_p4),
        "P5": pick("p5", contracted_p5),
        "P6": pick("p6", contracted_p6),
    }

    if contract_type == ContractType.TD_2_0:
        # En tu proyecto 2.0TD usa P1 y P3
        if contracted_p2 is not None and contracted["P3"] == 0.0:
            contracted["P3"] = float(contracted_p2)
        return {"P1": contracted["P1"], "P3": contracted["P3"]}

    return {p: contracted[p] for p in ["P1", "P2", "P3", "P4", "P5", "P6"]}


def _primera_potencia_sobre_2_0(kw):
    for p in POTENCIAS_COMERCIALES_2_0:
        if p >= kw:
            return p
    return POTENCIAS_COMERCIALES_2_0[-1]


def _potencia_objetivo(kw: float, contract_type: ContractType):
    if contract_type == ContractType.TD_2_0:
        return _primera_potencia_sobre_2_0(kw)
    return _round2(kw)


def _hours_excess_with(records, periodo: str, umbral: float) -> int:
    return sum(
        1 for r in records
        if r.power_period.value == periodo and r.consumption_kwh > umbral
    )


def _max_monthly_official_by_period(monthly_max_power: list, period: str) -> float:
    vals = [r.max_kw for r in monthly_max_power if r.period == period]
    return _round4(max(vals)) if vals else 0.0


def _build_monthly_peaks(monthly_max_power: list, contract_type: ContractType, contracted: dict):
    """
    Construye:
    - lista mensual ordenada
    - compatibilidad con charts antiguos (pico_punta / pico_valle)
    - detalle completo por periodos
    """
    period_order = _get_period_order(contract_type)

    # Agrupar por mes
    picos_por_mes = {}
    month_num_by_mes = {}

    for r in monthly_max_power:
        mes_nombre = _get_month_name(r.month)
        if mes_nombre not in picos_por_mes:
            picos_por_mes[mes_nombre] = {}
            month_num_by_mes[mes_nombre] = r.month_num
        picos_por_mes[mes_nombre][r.period] = _round4(r.max_kw)

    meses_ordenados = sorted(
        picos_por_mes.keys(),
        key=lambda m: month_num_by_mes.get(m, 99)
    )

    picos_mensuales = []
    for mes in meses_ordenados:
        datos = picos_por_mes[mes]

        row = {
            "mes": mes,
            "month_num": month_num_by_mes.get(mes, 99),
            "pot_max": datos.get("Pot.Max", 0.0),
            "periodos": {},
        }

        for p in period_order:
            pico = _round4(datos.get(p, 0.0))
            contratado = _round4(contracted.get(p, 0.0))
            supera = (contratado > 0 and pico > contratado)
            exceso = _round4(pico - contratado) if supera else 0.0

            row["periodos"][p] = {
                "pico_kw": pico,
                "contracted_kw": contratado,
                "supera": supera,
                "exceso_kw": exceso,
            }

        # Alias para compatibilidad con charts viejos:
        # - 2.0TD: punta=P1, valle=P3
        # - 3.0TD: punta=P1, valle=P6 (solo como alias visual temporal)
        if contract_type == ContractType.TD_2_0:
            alias_2 = "P3"
        else:
            alias_2 = "P6"

        row["pico_punta"] = row["periodos"].get("P1", {}).get("pico_kw", 0.0)
        row["pico_valle"] = row["periodos"].get(alias_2, {}).get("pico_kw", 0.0)
        row["supera_p1"] = row["periodos"].get("P1", {}).get("supera", False)
        row["supera_p2"] = row["periodos"].get(alias_2, {}).get("supera", False)
        row["exceso_p1"] = row["periodos"].get("P1", {}).get("exceso_kw", 0.0)
        row["exceso_p2"] = row["periodos"].get(alias_2, {}).get("exceso_kw", 0.0)

        picos_mensuales.append(row)

    return picos_mensuales


def _build_excess_table(picos_mensuales: list, contract_type: ContractType):
    tabla = []

    if contract_type == ContractType.TD_2_0:
        alias_2 = "P3"
        alias_2_label = "P3"
    else:
        alias_2 = "P6"
        alias_2_label = "P6"

    for p in picos_mensuales:
        if p["supera_p1"] or p["supera_p2"]:
            row = {
                "mes": p["mes"].capitalize(),
                "pico_punta": f"{p['pico_punta']} kW",
                "exceso_p1": f"+{p['exceso_p1']} kW" if p["supera_p1"] else "—",
                "pico_valle": f"{p['pico_valle']} kW",
                "exceso_p2": f"+{p['exceso_p2']} kW" if p["supera_p2"] else "—",
                "supera_p1": p["supera_p1"],
                "supera_p2": p["supera_p2"],
                "alias_periodo_2": alias_2_label,
            }
            tabla.append(row)

    # Tabla completa extra para futuro 3.0TD
    tabla_full = []
    for p in picos_mensuales:
        for periodo, info in p["periodos"].items():
            if info["supera"]:
                tabla_full.append({
                    "mes": p["mes"].capitalize(),
                    "periodo": periodo,
                    "pico_kw": info["pico_kw"],
                    "contracted_kw": info["contracted_kw"],
                    "exceso_kw": info["exceso_kw"],
                })

    return tabla, tabla_full


def _build_suggested_options(
    analysis: ElectricityAnalysis,
    contract_type: ContractType,
    contracted: dict,
    picos_mensuales: list,
):
    period_order = _get_period_order(contract_type)
    records = analysis.hourly_records

    max_by_period = {}
    for p in period_order:
        vals = [m["periodos"][p]["pico_kw"] for m in picos_mensuales if p in m["periodos"]]
        max_by_period[p] = _round4(max(vals)) if vals else 0.0

    # Equilibrada = 90% del maximo
    # Segura      = 100% del maximo
    eq = {}
    sg = {}

    for p in period_order:
        eq[p] = _potencia_objetivo(max_by_period[p] * 0.90, contract_type)
        sg[p] = _potencia_objetivo(max_by_period[p], contract_type)

        # Si coinciden en 2.0TD, intentamos bajar una escalon la equilibrada
        if contract_type == ContractType.TD_2_0 and eq[p] == sg[p]:
            idx = POTENCIAS_COMERCIALES_2_0.index(sg[p]) if sg[p] in POTENCIAS_COMERCIALES_2_0 else 0
            eq[p] = POTENCIAS_COMERCIALES_2_0[max(0, idx - 1)]

    def meses_exceso_con(picos, periodo, umbral):
        return sum(1 for m in picos if m["periodos"].get(periodo, {}).get("pico_kw", 0.0) > umbral)

    opciones = {
        "equilibrada": {
            "periodos": {},
            "titulo": "Opcion equilibrada",
            "descripcion": (
                "Cubre la gran mayoria de situaciones habituales "
                "(aprox. 90% del pico maximo registrado por periodo). "
                "Es la opcion mas economica con un riesgo bajo de excesos puntuales."
            ),
        },
        "segura": {
            "periodos": {},
            "titulo": "Opcion segura",
            "descripcion": (
                "Cubre el 100% de los picos maximos registrados por periodo. "
                "Es la opcion con menor riesgo de excesos."
            ),
        }
    }

    for p in period_order:
        eq_kw = eq[p]
        sg_kw = sg[p]

        opciones["equilibrada"]["periodos"][p] = {
            "kw": eq_kw,
            "horas_exceso": _hours_excess_with(records, p, eq_kw),
            "meses_exceso": meses_exceso_con(picos_mensuales, p, eq_kw),
        }
        opciones["segura"]["periodos"][p] = {
            "kw": sg_kw,
            "horas_exceso": _hours_excess_with(records, p, sg_kw),
            "meses_exceso": meses_exceso_con(picos_mensuales, p, sg_kw),
        }

    # Alias para compatibilidad con charts viejos
    alias_2 = "P3" if contract_type == ContractType.TD_2_0 else "P6"

    opciones["equilibrada"]["p1"] = opciones["equilibrada"]["periodos"].get("P1", {}).get("kw", 0.0)
    opciones["equilibrada"]["p2"] = opciones["equilibrada"]["periodos"].get(alias_2, {}).get("kw", 0.0)
    opciones["equilibrada"]["horas_exceso_p1"] = opciones["equilibrada"]["periodos"].get("P1", {}).get("horas_exceso", 0)
    opciones["equilibrada"]["horas_exceso_p2"] = opciones["equilibrada"]["periodos"].get(alias_2, {}).get("horas_exceso", 0)
    opciones["equilibrada"]["meses_exceso_p1"] = opciones["equilibrada"]["periodos"].get("P1", {}).get("meses_exceso", 0)
    opciones["equilibrada"]["meses_exceso_p2"] = opciones["equilibrada"]["periodos"].get(alias_2, {}).get("meses_exceso", 0)
    opciones["equilibrada"]["titulo"] = (
        f"P1={opciones['equilibrada']['p1']} kW"
        + (f" / {alias_2}={opciones['equilibrada']['p2']} kW" if alias_2 in period_order else "")
        + " — Opcion equilibrada"
    )

    opciones["segura"]["p1"] = opciones["segura"]["periodos"].get("P1", {}).get("kw", 0.0)
    opciones["segura"]["p2"] = opciones["segura"]["periodos"].get(alias_2, {}).get("kw", 0.0)
    opciones["segura"]["horas_exceso_p1"] = opciones["segura"]["periodos"].get("P1", {}).get("horas_exceso", 0)
    opciones["segura"]["horas_exceso_p2"] = opciones["segura"]["periodos"].get(alias_2, {}).get("horas_exceso", 0)
    opciones["segura"]["meses_exceso_p1"] = opciones["segura"]["periodos"].get("P1", {}).get("meses_exceso", 0)
    opciones["segura"]["meses_exceso_p2"] = opciones["segura"]["periodos"].get(alias_2, {}).get("meses_exceso", 0)
    opciones["segura"]["titulo"] = (
        f"P1={opciones['segura']['p1']} kW"
        + (f" / {alias_2}={opciones['segura']['p2']} kW" if alias_2 in period_order else "")
        + " — Opcion segura"
    )

    return opciones, max_by_period


# =============================================================================
# FUNCION PRINCIPAL
# =============================================================================

def run_optimization_analysis(
    analysis: ElectricityAnalysis,
    contracted_p1: float = None,
    contracted_p2: float = None,
    contracted_p3: float = None,
    contracted_p4: float = None,
    contracted_p5: float = None,
    contracted_p6: float = None,
) -> dict:
    """
    Analiza optimizacion de potencia contratada.
    - 2.0TD: P1/P3
    - 3.0TD: P1..P6
    """

    records = analysis.hourly_records
    monthly_max_power = analysis.monthly_max_power
    contract_type = analysis.client.contract_type

    if not records or not monthly_max_power:
        print("ERROR: Faltan datos.")
        return {}

    contracted = _get_contracted_periods(
        analysis=analysis,
        contract_type=contract_type,
        contracted_p1=contracted_p1,
        contracted_p2=contracted_p2,
        contracted_p3=contracted_p3,
        contracted_p4=contracted_p4,
        contracted_p5=contracted_p5,
        contracted_p6=contracted_p6,
    )

    print("Iniciando analisis de optimizacion...")
    print(f"  Tipo contrato: {contract_type.value}")
    print(f"  Potencias actuales: {contracted}")

    # ----------------------------------------------------------------
    # PICOS OFICIALES POR MES
    # ----------------------------------------------------------------

    picos_mensuales = _build_monthly_peaks(
        monthly_max_power=monthly_max_power,
        contract_type=contract_type,
        contracted=contracted,
    )

    # ----------------------------------------------------------------
    # TABLAS DE EXCESOS
    # ----------------------------------------------------------------

    tabla_excesos, tabla_excesos_full = _build_excess_table(
        picos_mensuales=picos_mensuales,
        contract_type=contract_type,
    )

    # ----------------------------------------------------------------
    # OPCIONES SUGERIDAS
    # ----------------------------------------------------------------

    opciones_sugeridas, max_by_period = _build_suggested_options(
        analysis=analysis,
        contract_type=contract_type,
        contracted=contracted,
        picos_mensuales=picos_mensuales,
    )

    # ----------------------------------------------------------------
    # KPIs
    # ----------------------------------------------------------------

    meses_exceso_por_periodo = {}
    for p in _get_period_order(contract_type):
        meses_exceso_por_periodo[p] = sum(
            1 for m in picos_mensuales if m["periodos"].get(p, {}).get("supera", False)
        )

    alias_2 = "P3" if contract_type == ContractType.TD_2_0 else "P6"

    tiene_exceso = any(v > 0 for v in meses_exceso_por_periodo.values())

    mes_max_exceso_p1 = ""
    mayor_exceso_p1 = -1
    for m in picos_mensuales:
        ex = m["periodos"].get("P1", {}).get("exceso_kw", 0.0)
        if ex > mayor_exceso_p1:
            mayor_exceso_p1 = ex
            mes_max_exceso_p1 = m["mes"]

    mes_max_exceso_p2 = ""
    mayor_exceso_p2 = -1
    for m in picos_mensuales:
        ex = m["periodos"].get(alias_2, {}).get("exceso_kw", 0.0)
        if ex > mayor_exceso_p2:
            mayor_exceso_p2 = ex
            mes_max_exceso_p2 = m["mes"]

    kpis = {
        "contract_type": contract_type.value,
        "contracted_periods": contracted,

        # Compatibilidad con charts viejos
        "contracted_p1": contracted.get("P1", 0.0),
        "contracted_p2": contracted.get(alias_2, 0.0),

        "meses_exceso_p1": meses_exceso_por_periodo.get("P1", 0),
        "meses_exceso_p2": meses_exceso_por_periodo.get(alias_2, 0),
        "max_pico_punta": max_by_period.get("P1", 0.0),
        "max_pico_valle": max_by_period.get(alias_2, 0.0),

        "meses_exceso_por_periodo": meses_exceso_por_periodo,
        "max_picos_por_periodo": max_by_period,

        "tiene_exceso": tiene_exceso,
        "mes_max_exceso_p1": mes_max_exceso_p1,
        "mes_max_exceso_p2": mes_max_exceso_p2,
    }

    print(f"  Meses con exceso P1: {kpis['meses_exceso_p1']}")
    print(f"  Meses con exceso alias 2: {kpis['meses_exceso_p2']}")
    print("  Maximos por periodo:")
    for p, v in max_by_period.items():
        print(f"    {p}: {v} kW")

    # ----------------------------------------------------------------
    # RESULTADO FINAL
    # ----------------------------------------------------------------

    result = {
        "contract_type": contract_type.value,
        "contracted_p1": contracted.get("P1", 0.0),
        "contracted_p2": contracted.get(alias_2, 0.0),
        "contracted_periods": contracted,
        "kpis": kpis,
        "picos_mensuales": picos_mensuales,
        "tabla_excesos": tabla_excesos,
        "tabla_excesos_full": tabla_excesos_full,
        "opciones_sugeridas": opciones_sugeridas,
        "alias_periodo_2": alias_2,
    }

    analysis.optimization_analysis = result

    print("Analisis de optimizacion completado.")
    return result
