# =============================================================================
# src/analysis/peaks_engine.py
# Motor de análisis de picos críticos
# Compatible con 2.0TD + 3.0TD
# =============================================================================

from collections import defaultdict

from src.models.internal_data_model import (
    ElectricityAnalysis,
    ContractType,
)


# =============================================================================
# HELPERS
# =============================================================================

def _round2(val: float) -> float:
    return round(val, 2)


def _get_period_order(contract_type: ContractType):
    if contract_type == ContractType.TD_3_0:
        return ["P1", "P2", "P3", "P4", "P5", "P6"]
    return ["P1", "P3"]


def _get_month_short(month_name: str) -> str:
    text = str(month_name).strip().lower()
    return text[:3]


def _get_franja(hour: int) -> str:
    if 0 <= hour < 8:
        return "00-08"
    if 8 <= hour < 12:
        return "08-12"
    if 12 <= hour < 16:
        return "12-16"
    if 16 <= hour < 20:
        return "16-20"
    return "20-24"


# =============================================================================
# FUNCION PRINCIPAL
# =============================================================================

def run_peaks_analysis(
    analysis: ElectricityAnalysis,
    umbral_kw: float = 2.0,
) -> ElectricityAnalysis:
    records = analysis.hourly_records
    contract_type = analysis.client.contract_type

    if not records:
        print("ERROR: No hay registros horarios para analizar.")
        return analysis

    print("Iniciando análisis de picos...")
    print(f"  Umbral configurado: {umbral_kw} kW")

    # ----------------------------------------------------------------
    # REGISTROS SOBRE UMBRAL
    # ----------------------------------------------------------------

    peaks = [r for r in records if r.consumption_kwh > umbral_kw]
    total_peaks = len(peaks)
    pct_peaks = _round2((total_peaks / len(records)) * 100) if records else 0.0

    print(f"  Horas sobre umbral: {total_peaks}")
    print(f"  Porcentaje:         {pct_peaks}%")

    # ----------------------------------------------------------------
    # TOP 10 PICOS
    # ----------------------------------------------------------------

    top10 = sorted(
        peaks,
        key=lambda r: r.consumption_kwh,
        reverse=True
    )[:10]

    top10_list = [
        {
            "timestamp": str(r.timestamp),
            "fecha": str(r.timestamp.date()),
            "hora": r.hour,
            "month_name": r.month_name,
            "day_of_week": r.day_of_week,
            "consumption_kwh": _round2(r.consumption_kwh),
            "exceso_kwh": _round2(r.consumption_kwh - umbral_kw),
            "power_period": r.power_period.value,
            "energy_period": r.energy_period.value,
            "is_weekend": r.is_weekend,
            "is_holiday": r.is_holiday,
        }
        for r in top10
    ]

    # ----------------------------------------------------------------
    # POR MES
    # ----------------------------------------------------------------

    by_month_sum = defaultdict(float)
    by_month_count = defaultdict(int)
    by_month_max = defaultdict(float)
    month_num_map = {}

    for r in peaks:
        mes = r.month_name
        by_month_sum[mes] += r.consumption_kwh
        by_month_count[mes] += 1
        by_month_max[mes] = max(by_month_max[mes], r.consumption_kwh)
        month_num_map[mes] = r.month

    by_month = {
        mes: {
            "num_picos": by_month_count[mes],
            "total_kwh": _round2(by_month_sum[mes]),
            "avg_kwh": _round2(by_month_sum[mes] / by_month_count[mes]) if by_month_count[mes] > 0 else 0.0,
            "max_kw": _round2(by_month_max[mes]),
            "month_num": month_num_map[mes],
        }
        for mes in by_month_count
    }
    by_month = dict(sorted(by_month.items(), key=lambda x: x[1]["month_num"]))

    # ----------------------------------------------------------------
    # POR FRANJA
    # ----------------------------------------------------------------

    by_franja_sum = defaultdict(float)
    by_franja_count = defaultdict(int)

    for r in peaks:
        franja = _get_franja(r.hour)
        by_franja_sum[franja] += r.consumption_kwh
        by_franja_count[franja] += 1

    franja_order = ["00-08", "08-12", "12-16", "16-20", "20-24"]

    by_franja = {
        franja: {
            "num_picos": by_franja_count[franja],
            "total_kwh": _round2(by_franja_sum[franja]),
            "avg_kwh": _round2(by_franja_sum[franja] / by_franja_count[franja]) if by_franja_count[franja] > 0 else 0.0,
        }
        for franja in franja_order
        if franja in by_franja_count
    }

    # ----------------------------------------------------------------
    # POR HORA
    # ----------------------------------------------------------------

    by_hour_sum = defaultdict(float)
    by_hour_count = defaultdict(int)

    for r in peaks:
        by_hour_sum[r.hour] += r.consumption_kwh
        by_hour_count[r.hour] += 1

    by_hour = {
        hour: {
            "num_picos": by_hour_count[hour],
            "total_kwh": _round2(by_hour_sum[hour]),
            "avg_kwh": _round2(by_hour_sum[hour] / by_hour_count[hour]) if by_hour_count[hour] > 0 else 0.0,
        }
        for hour in sorted(by_hour_count.keys())
    }

    # ----------------------------------------------------------------
    # HEATMAP MES x HORA
    # ----------------------------------------------------------------

    heatmap_sum = defaultdict(float)
    heatmap_count = defaultdict(int)

    for r in peaks:
        mes = _get_month_short(r.month_name)
        clave = (mes, r.hour)
        heatmap_sum[clave] += r.consumption_kwh
        heatmap_count[clave] += 1

    meses_presentes = []
    for r in peaks:
        mes = _get_month_short(r.month_name)
        if mes not in meses_presentes:
            meses_presentes.append(mes)

    # Mantener orden cronológico por número de mes
    month_order_map = {}
    for r in peaks:
        month_order_map[_get_month_short(r.month_name)] = r.month
    meses_presentes = sorted(meses_presentes, key=lambda m: month_order_map.get(m, 99))

    heatmap = {
        "meses": meses_presentes,
        "horas": list(range(24)),
        "valores": {}
    }

    for mes in meses_presentes:
        heatmap["valores"][mes] = {}
        for hora in range(24):
            clave = (mes, hora)
            if clave in heatmap_sum:
                heatmap["valores"][mes][hora] = _round2(heatmap_sum[clave] / heatmap_count[clave])
            else:
                heatmap["valores"][mes][hora] = None

    # ----------------------------------------------------------------
    # POR TIPO DE DIA
    # ----------------------------------------------------------------

    laborable = [r for r in peaks if not r.is_weekend and not r.is_holiday]
    fin_semana = [r for r in peaks if r.is_weekend or r.is_holiday]

    by_day_type = {
        "laborable": {
            "num_picos": len(laborable),
            "total_kwh": _round2(sum(r.consumption_kwh for r in laborable)),
            "avg_kwh": _round2(sum(r.consumption_kwh for r in laborable) / len(laborable)) if laborable else 0.0,
            "pct_of_total": _round2((len(laborable) / total_peaks) * 100) if total_peaks > 0 else 0.0,
        },
        "fin_de_semana": {
            "num_picos": len(fin_semana),
            "total_kwh": _round2(sum(r.consumption_kwh for r in fin_semana)),
            "avg_kwh": _round2(sum(r.consumption_kwh for r in fin_semana) / len(fin_semana)) if fin_semana else 0.0,
            "pct_of_total": _round2((len(fin_semana) / total_peaks) * 100) if total_peaks > 0 else 0.0,
        }
    }

    # ----------------------------------------------------------------
    # POR PERIODO DE POTENCIA
    # ----------------------------------------------------------------

    period_order = _get_period_order(contract_type)

    by_period_sum = defaultdict(float)
    by_period_count = defaultdict(int)

    for r in peaks:
        p = r.power_period.value
        by_period_sum[p] += r.consumption_kwh
        by_period_count[p] += 1

    by_period = {
        p: {
            "num_picos": by_period_count[p],
            "total_kwh": _round2(by_period_sum[p]),
            "avg_kwh": _round2(by_period_sum[p] / by_period_count[p]) if by_period_count[p] > 0 else 0.0,
            "pct_of_total": _round2((by_period_count[p] / total_peaks) * 100) if total_peaks > 0 else 0.0,
        }
        for p in period_order
    }

    print("  Picos por periodo:")
    for p in period_order:
        print(f"    {p}: {by_period[p]['num_picos']} horas ({by_period[p]['pct_of_total']}%)")

    # ----------------------------------------------------------------
    # GUARDAR EN analysis
    # ----------------------------------------------------------------

    peaks_analysis = {
        "umbral_kw": umbral_kw,
        "total_peaks": total_peaks,
        "pct_peaks": pct_peaks,
        "top10": top10_list,
        "by_month": by_month,
        "by_franja": by_franja,
        "by_hour": by_hour,
        "heatmap": heatmap,
        "by_day_type": by_day_type,
        "by_period": by_period,
        "contract_type": contract_type.value,
    }

    analysis.peaks_analysis = peaks_analysis

    print("Análisis de picos completado.")
    return analysis
