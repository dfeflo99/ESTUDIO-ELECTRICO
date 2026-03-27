# =============================================================================
# src/analysis/power_engine.py
# Motor de analisis de potencia electrica
# Compatible con 2.0TD + 3.0TD
# =============================================================================

from collections import defaultdict
import numpy as np

from src.models.internal_data_model import (
    ElectricityAnalysis,
    PowerAnalysis,
    ContractedPowers,
    PowerPeriod,
    ContractType,
)


# =============================================================================
# HELPERS
# =============================================================================

def _round2(val: float) -> float:
    return round(val, 2)

def _round4(val: float) -> float:
    return round(val, 4)


# Potencias comerciales 2.0TD
POTENCIAS_COMERCIALES_2_0 = [
    2.3, 3.45, 4.6, 5.75, 6.9, 8.05, 9.2, 10.35, 11.5, 14.49
]


def potencia_comercial_optima_2_0(kw: float) -> float:
    for p in POTENCIAS_COMERCIALES_2_0:
        if p >= kw:
            return p
    return POTENCIAS_COMERCIALES_2_0[-1]


def potencia_optima_generica(kw: float, contract_type: ContractType) -> float:
    """
    En 2.0TD usamos potencias comerciales cerradas.
    En 3.0TD, por ahora devolvemos el valor redondeado a 2 decimales.
    """
    if contract_type == ContractType.TD_2_0:
        return potencia_comercial_optima_2_0(kw)
    return _round2(kw)


def _get_month_short(month_text: str) -> str:
    text = str(month_text).strip().lower()
    return text[:3]


def _get_official_periods(contract_type: ContractType):
    if contract_type == ContractType.TD_3_0:
        return ["P1", "P2", "P3", "P4", "P5", "P6"]
    # 2.0TD en tu proyecto: potencia P1 y P3
    return ["P1", "P3"]


def _get_record_period_value(record) -> str:
    try:
        return record.power_period.value
    except Exception:
        return str(record.power_period)


# =============================================================================
# BLOQUE 1 — KPIs DESDE CSV OFICIAL DE POTENCIAS MAXIMAS
# =============================================================================

def _calculate_kpis_from_official(monthly_max_power: list, contract_type: ContractType) -> dict:
    if not monthly_max_power:
        return {
            "max_real_kw": 0.0,
            "max_by_month": {},
            "max_periods_kw": {},
            "max_punta_kw": 0.0,
            "max_valle_kw": 0.0,
        }

    official_periods = _get_official_periods(contract_type)

    # Pot.Max global
    pot_max_records = [r for r in monthly_max_power if r.period == "Pot.Max"]
    max_real_kw = _round4(max(r.max_kw for r in pot_max_records)) if pot_max_records else 0.0

    # Maximos por periodo oficial
    max_periods_kw = {}
    for period in official_periods:
        period_records = [r for r in monthly_max_power if r.period == period]
        max_periods_kw[period] = _round4(max(r.max_kw for r in period_records)) if period_records else 0.0

    # Estructura mensual para gráficos
    max_by_month = {}
    for r in monthly_max_power:
        mes = _get_month_short(r.month)
        if mes not in max_by_month:
            max_by_month[mes] = {
                "month_num": r.month_num,
                "year": r.year,
                "Pot.Max": 0.0,
            }
            for p in official_periods:
                max_by_month[mes][p] = 0.0

        max_by_month[mes][r.period] = _round4(r.max_kw)

    max_by_month = dict(sorted(max_by_month.items(), key=lambda x: x[1]["month_num"]))

    # Alias para compatibilidad con charts viejos 2.0TD
    # chart_monthly_official_peaks hoy espera Punta / Valle / Pot.Max
    if contract_type == ContractType.TD_2_0:
        for mes in max_by_month:
            max_by_month[mes]["Punta"] = max_by_month[mes].get("P1", 0.0)
            max_by_month[mes]["Valle"] = max_by_month[mes].get("P3", 0.0)

        max_punta_kw = max_periods_kw.get("P1", 0.0)
        max_valle_kw = max_periods_kw.get("P3", 0.0)
    else:
        # En 3.0TD dejamos alias aproximados para no romper componentes viejos
        for mes in max_by_month:
            max_by_month[mes]["Punta"] = max_by_month[mes].get("P1", 0.0)
            max_by_month[mes]["Valle"] = max_by_month[mes].get("P6", 0.0)

        max_punta_kw = max_periods_kw.get("P1", 0.0)
        max_valle_kw = max_periods_kw.get("P6", 0.0)

    return {
        "max_real_kw": max_real_kw,
        "max_by_month": max_by_month,
        "max_periods_kw": max_periods_kw,
        "max_punta_kw": max_punta_kw,
        "max_valle_kw": max_valle_kw,
    }


# =============================================================================
# BLOQUE 2 — RECOMENDACION DESDE CSV OFICIAL
# =============================================================================

def _calculate_recommendation_from_official(
    monthly_max_power: list,
    contract_type: ContractType,
    contracted: ContractedPowers,
) -> dict:
    official_periods = _get_official_periods(contract_type)

    max_periods = {}
    recommended_periods = {}
    has_excess = False
    has_deficit = False

    for period in official_periods:
        period_records = [r for r in monthly_max_power if r.period == period]
        max_kw = max((r.max_kw for r in period_records), default=0.0)
        max_periods[period] = _round4(max_kw)

        recommended = potencia_optima_generica(max_kw * 1.10, contract_type)
        recommended_periods[period] = recommended

        contracted_kw = getattr(contracted, period.lower(), 0.0) or 0.0

        if contracted_kw > 0 and max_kw > contracted_kw:
            has_deficit = True

        if contracted_kw > recommended * 1.10 and recommended > 0:
            has_excess = True

    observations = []

    if contract_type == ContractType.TD_2_0:
        rec_txt = f"P1={recommended_periods.get('P1', 0)}kW / P3={recommended_periods.get('P3', 0)}kW"
    else:
        rec_txt = " / ".join([f"{p}={recommended_periods.get(p, 0)}kW" for p in official_periods])

    if has_excess:
        observations.append(
            f"Tienes potencia contratada de mas. Podrias considerar {rec_txt}."
        )
    if has_deficit:
        observations.append(
            "Has superado la potencia contratada en algun momento. "
            "Esto puede generar penalizaciones o indicar falta de margen."
        )
    if not has_excess and not has_deficit:
        observations.append(
            "Tu potencia contratada parece adecuada a tu perfil de consumo real."
        )

    return {
        "recommended_periods": recommended_periods,
        "max_periods": max_periods,
        "has_excess": has_excess,
        "has_deficit": has_deficit,
        "observations": observations,
    }


# =============================================================================
# BLOQUE 3 — DISTRIBUCION TEMPORAL DESDE CSV DE CONSUMO
# =============================================================================

def _calculate_distribution_from_consumption(records: list, umbral_kw: float) -> dict:
    potencias = [r.consumption_kwh for r in records]

    if not potencias:
        return {
            "avg_power_kw": 0.0,
            "p99_desde_consumo": 0.0,
            "max_desde_consumo": 0.0,
            "load_factor": 0.0,
            "horas_sobre_umbral": 0,
            "pct_sobre_umbral": 0.0,
            "daily_max_power": {},
            "heatmap_matrix": {"horas": list(range(24)), "dias": list(range(1, 32)), "valores": {}},
            "power_ranking": [],
            "records_sobre_umbral": [],
        }

    avg_power_kw = _round4(sum(potencias) / len(potencias))
    p99_desde_consumo = _round4(float(np.percentile(potencias, 99)))
    max_desde_consumo = _round4(max(potencias))
    load_factor = _round4(avg_power_kw / max_desde_consumo) if max_desde_consumo > 0 else 0.0

    horas_sobre_umbral = sum(1 for p in potencias if p > umbral_kw)
    pct_sobre_umbral = _round2((horas_sobre_umbral / len(potencias)) * 100)

    # Potencia maxima diaria
    daily_max = defaultdict(float)
    daily_meta = defaultdict(dict)

    for r in records:
        fecha = r.timestamp.date()
        if r.consumption_kwh > daily_max[fecha]:
            daily_max[fecha] = r.consumption_kwh
            daily_meta[fecha] = {
                "month_name": r.month_name,
                "day_of_week": r.day_of_week,
                "is_weekend": r.is_weekend,
                "is_holiday": r.is_holiday,
            }

    daily_max_power = {
        str(fecha): {
            "max_kw": _round4(daily_max[fecha]),
            **daily_meta[fecha]
        }
        for fecha in sorted(daily_max.keys())
    }

    # Heatmap hora x día
    heatmap_sum = defaultdict(float)
    heatmap_count = defaultdict(int)

    for r in records:
        clave = (r.hour, r.day_of_month)
        heatmap_sum[clave] += r.consumption_kwh
        heatmap_count[clave] += 1

    heatmap_matrix = {
        "horas": list(range(0, 24)),
        "dias": list(range(1, 32)),
        "valores": {}
    }

    for hora in range(24):
        heatmap_matrix["valores"][hora] = {}
        for dia in range(1, 32):
            clave = (hora, dia)
            if clave in heatmap_sum:
                heatmap_matrix["valores"][hora][dia] = _round4(
                    heatmap_sum[clave] / heatmap_count[clave]
                )
            else:
                heatmap_matrix["valores"][hora][dia] = None

    power_ranking = sorted([_round4(p) for p in potencias], reverse=True)

    records_sobre_umbral = [
        {
            "timestamp": str(r.timestamp),
            "month_name": r.month_name,
            "day_of_month": r.day_of_month,
            "hour": r.hour,
            "consumption_kwh": _round4(r.consumption_kwh),
            "exceso_kwh": _round4(r.consumption_kwh - umbral_kw),
            "is_weekend": r.is_weekend,
            "is_holiday": r.is_holiday,
            "power_period": r.power_period.value,
            "energy_period": r.energy_period.value,
        }
        for r in records if r.consumption_kwh > umbral_kw
    ]

    return {
        "avg_power_kw": avg_power_kw,
        "p99_desde_consumo": p99_desde_consumo,
        "max_desde_consumo": max_desde_consumo,
        "load_factor": load_factor,
        "horas_sobre_umbral": horas_sobre_umbral,
        "pct_sobre_umbral": pct_sobre_umbral,
        "daily_max_power": daily_max_power,
        "heatmap_matrix": heatmap_matrix,
        "power_ranking": power_ranking,
        "records_sobre_umbral": records_sobre_umbral,
    }


# =============================================================================
# BLOQUE 4 — EXCESOS SOBRE POTENCIA CONTRATADA
# =============================================================================

def _calculate_excesses_by_period(records: list, contracted: ContractedPowers, contract_type: ContractType) -> dict:
    official_periods = _get_official_periods(contract_type)

    result = {
        "hours": {p: 0 for p in ["P1", "P2", "P3", "P4", "P5", "P6"]},
        "records": {p: [] for p in ["P1", "P2", "P3", "P4", "P5", "P6"]},
    }

    for r in records:
        period = _get_record_period_value(r)
        if period not in official_periods:
            continue

        contracted_kw = getattr(contracted, period.lower(), 0.0) or 0.0
        if contracted_kw <= 0:
            continue

        if r.consumption_kwh > contracted_kw:
            result["hours"][period] += 1
            result["records"][period].append({
                "timestamp": str(r.timestamp),
                "hour": r.hour,
                "period": period,
                "consumption_kwh": _round4(r.consumption_kwh),
                "contracted_kw": _round4(contracted_kw),
                "exceso_kw": _round4(r.consumption_kwh - contracted_kw),
            })

    return result


# =============================================================================
# BLOQUE 5 — INTERPRETACION DEL PERFIL
# =============================================================================

def _interpret_profile(avg_power_kw: float, p99_kw: float, max_real_kw: float) -> dict:
    ratio = _round2(p99_kw / avg_power_kw) if avg_power_kw > 0 else 0.0

    if ratio < 2.0:
        tipo = "estable"
        descripcion = (
            f"Tu perfil de consumo es bastante uniforme. "
            f"El P99 ({p99_kw} kW) es solo {ratio}x el promedio "
            f"({avg_power_kw} kW). El pico real registrado fue {max_real_kw} kW."
        )
    elif ratio < 4.0:
        tipo = "moderadamente variable"
        descripcion = (
            f"Tu perfil tiene cierta variabilidad. "
            f"El P99 ({p99_kw} kW) es {ratio}x el promedio "
            f"({avg_power_kw} kW). Pico real: {max_real_kw} kW."
        )
    else:
        tipo = "muy variable"
        descripcion = (
            f"Tu perfil es muy irregular con picos destacados. "
            f"El P99 ({p99_kw} kW) es {ratio}x el promedio "
            f"({avg_power_kw} kW). Pico real registrado: {max_real_kw} kW."
        )

    return {"tipo": tipo, "descripcion": descripcion, "ratio": ratio}


# =============================================================================
# FUNCION PRINCIPAL
# =============================================================================

def run_power_analysis(
    analysis: ElectricityAnalysis,
    contracted_p1: float = None,
    contracted_p2: float = None,
    contracted_p3: float = None,
    contracted_p4: float = None,
    contracted_p5: float = None,
    contracted_p6: float = None,
    umbral_kw: float = 2.0,
) -> ElectricityAnalysis:
    records = analysis.hourly_records
    monthly_max_power = analysis.monthly_max_power
    contract_type = analysis.client.contract_type

    if not records:
        print("ERROR: No hay registros horarios para analizar.")
        return analysis

    print("Iniciando analisis de potencia...")
    print(f"  Umbral configurado: {umbral_kw} kW")

    # ----------------------------------------------------------------
    # Potencias contratadas
    # ----------------------------------------------------------------

    base_contract = analysis.contract.contracted_powers if analysis.contract else None

    def _pick(name, explicit):
        if explicit is not None:
            return explicit
        if base_contract is not None:
            return getattr(base_contract, name, 0.0) or 0.0
        return 0.0

    cp1 = _pick("p1", contracted_p1)
    cp2 = _pick("p2", contracted_p2)
    cp3 = _pick("p3", contracted_p3)
    cp4 = _pick("p4", contracted_p4)
    cp5 = _pick("p5", contracted_p5)
    cp6 = _pick("p6", contracted_p6)

    contracted = ContractedPowers(
        p1=cp1, p2=cp2, p3=cp3, p4=cp4, p5=cp5, p6=cp6
    )

    # ----------------------------------------------------------------
    # KPIs oficiales
    # ----------------------------------------------------------------

    kpis_oficiales = _calculate_kpis_from_official(monthly_max_power, contract_type)
    max_real_kw = kpis_oficiales.get("max_real_kw", 0.0)
    max_by_month = kpis_oficiales.get("max_by_month", {})
    max_periods_kw = kpis_oficiales.get("max_periods_kw", {})
    max_punta_kw = kpis_oficiales.get("max_punta_kw", 0.0)
    max_valle_kw = kpis_oficiales.get("max_valle_kw", 0.0)

    print(f"  Maximo real (CSV oficial): {max_real_kw} kW")
    print(f"  Maximo Punta(alias):       {max_punta_kw} kW")
    print(f"  Maximo Valle(alias):       {max_valle_kw} kW")

    # ----------------------------------------------------------------
    # Recomendacion
    # ----------------------------------------------------------------

    rec = _calculate_recommendation_from_official(
        monthly_max_power=monthly_max_power,
        contract_type=contract_type,
        contracted=contracted,
    )

    recommended_periods = rec["recommended_periods"]
    print("  Recomendacion por periodo:")
    for p, v in recommended_periods.items():
        print(f"    {p}: {v} kW")

    # ----------------------------------------------------------------
    # Distribucion temporal desde consumo
    # ----------------------------------------------------------------

    dist = _calculate_distribution_from_consumption(records, umbral_kw)

    print(f"  Factor de carga:           {dist['load_factor']}")
    print(f"  P99 (desde consumo):       {dist['p99_desde_consumo']} kW")
    print(f"  Horas sobre {umbral_kw}kW: {dist['horas_sobre_umbral']}")
    print(f"  Porcentaje sobre umbral:   {dist['pct_sobre_umbral']}%")

    # ----------------------------------------------------------------
    # Excesos sobre contratada
    # ----------------------------------------------------------------

    excess = _calculate_excesses_by_period(records, contracted, contract_type)

    # ----------------------------------------------------------------
    # Perfil
    # ----------------------------------------------------------------

    perfil = _interpret_profile(
        dist["avg_power_kw"],
        dist["p99_desde_consumo"],
        max_real_kw
    )

    print(f"  Perfil: {perfil['tipo']}")

    # ----------------------------------------------------------------
    # Construir PowerAnalysis
    # ----------------------------------------------------------------

    power_analysis = PowerAnalysis(
        max_power_kw=max_real_kw,
        p99_power_kw=dist["p99_desde_consumo"],
        load_factor=dist["load_factor"],
        hours_exceeds_2kw=dist["horas_sobre_umbral"],
        pct_exceeds_2kw=dist["pct_sobre_umbral"],

        daily_max_power=dist["daily_max_power"],
        hourly_power_heatmap=dist["heatmap_matrix"],
        power_ranking=dist["power_ranking"],

        records_exceeding_2kw=dist["records_sobre_umbral"],

        contracted_powers=contracted,

        # Compatibilidad:
        # - en 2.0TD, hours_exceeds_p2 almacena el 2º periodo funcional (P3)
        # - en 3.0TD, hours_exceeds_p2 es realmente P2
        hours_exceeds_p1=excess["hours"].get("P1", 0),
        hours_exceeds_p2=excess["hours"].get("P2" if contract_type == ContractType.TD_3_0 else "P3", 0),

        records_exceeding_p1=excess["records"].get("P1", []),
        records_exceeding_p2=excess["records"].get("P2" if contract_type == ContractType.TD_3_0 else "P3", []),

        recommended_p1_kw=recommended_periods.get("P1", 0.0),
        recommended_p2_kw=recommended_periods.get("P2" if contract_type == ContractType.TD_3_0 else "P3", 0.0),

        has_excess_contracted=rec["has_excess"],
        has_deficit_contracted=rec["has_deficit"],
        observations=rec["observations"],

        hours_exceeds_p3=excess["hours"].get("P3", 0),
        hours_exceeds_p4=excess["hours"].get("P4", 0),
        hours_exceeds_p5=excess["hours"].get("P5", 0),
        hours_exceeds_p6=excess["hours"].get("P6", 0),

        records_exceeding_p3=excess["records"].get("P3", []),
        records_exceeding_p4=excess["records"].get("P4", []),
        records_exceeding_p5=excess["records"].get("P5", []),
        records_exceeding_p6=excess["records"].get("P6", []),

        recommended_p3_kw=recommended_periods.get("P3", 0.0),
        recommended_p4_kw=recommended_periods.get("P4", 0.0),
        recommended_p5_kw=recommended_periods.get("P5", 0.0),
        recommended_p6_kw=recommended_periods.get("P6", 0.0),
    )

    # Extras útiles para tus charts y notebook actuales
    power_analysis.perfil_tipo = perfil["tipo"]
    power_analysis.perfil_descripcion = perfil["descripcion"]
    power_analysis.avg_power_kw = dist["avg_power_kw"]
    power_analysis.umbral_kw = umbral_kw
    power_analysis.max_punta_kw = max_punta_kw
    power_analysis.max_valle_kw = max_valle_kw
    power_analysis.max_by_month = max_by_month
    power_analysis.max_periods_kw = max_periods_kw
    power_analysis.contract_type = contract_type.value

    if contract_type == ContractType.TD_3_0:
        power_analysis.nota_metodologia = (
            "Los graficos de distribucion horaria muestran la potencia media por hora "
            "(derivada de la curva de consumo). Los maximos por periodo y Pot.Max "
            "se basan en el CSV oficial de potencias maximas de la distribuidora."
        )
    else:
        power_analysis.nota_metodologia = (
            "Los graficos de distribucion horaria muestran la potencia media por hora "
            "(calculada a partir de tu curva de consumo). Los maximos y la "
            "recomendacion usan los picos reales registrados por la distribuidora."
        )

    analysis.power_analysis = power_analysis

    print("Analisis de potencia completado.")
    return analysis
