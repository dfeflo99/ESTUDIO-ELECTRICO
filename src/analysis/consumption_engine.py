# =============================================================================
# src/analysis/consumption_engine.py
# Motor de análisis de consumo eléctrico
# Compatible con 2.0TD + 3.0TD
# =============================================================================

from collections import defaultdict

from src.models.internal_data_model import (
    ElectricityAnalysis,
    ConsumptionSummary,
    PeriodConsumptionSummary,
    EnergyPeriod,
    ContractType,
)


# =============================================================================
# HELPERS
# =============================================================================

def _round2(val: float) -> float:
    return round(val, 2)


def _normalize_day_name(day_name: str) -> str:
    """
    Normaliza nombres de día para ordenar bien aunque vengan con o sin tilde.
    """
    if not day_name:
        return ""

    text = str(day_name).strip().lower()
    mapping = {
        "lunes": "lunes",
        "martes": "martes",
        "miércoles": "miercoles",
        "miercoles": "miercoles",
        "jueves": "jueves",
        "viernes": "viernes",
        "sábado": "sabado",
        "sabado": "sabado",
        "domingo": "domingo",
    }
    return mapping.get(text, text)


def _get_climatic_season(month: int) -> str:
    """
    Temporada climática, para mantener compatibilidad con tus gráficos actuales.
    """
    if month in [6, 7, 8, 9]:
        return "verano"
    elif month in [12, 1, 2, 3]:
        return "invierno"
    else:
        return "entretiempo"


def _get_tariff_season_3_0(month: int) -> str:
    """
    Temporada tarifaria 3.0TD.
    """
    if month in (1, 2, 7, 12):
        return "alta"
    if month in (3, 11):
        return "med_alta"
    if month in (6, 8, 9):
        return "media"
    return "baja"


def _get_energy_period_order(contract_type: ContractType):
    """
    Orden de periodos a mostrar según tarifa.
    """
    if contract_type == ContractType.TD_3_0:
        return [
            EnergyPeriod.P1,
            EnergyPeriod.P2,
            EnergyPeriod.P3,
            EnergyPeriod.P4,
            EnergyPeriod.P5,
            EnergyPeriod.P6,
        ]

    # 2.0TD por defecto
    return [
        EnergyPeriod.P1,
        EnergyPeriod.P2,
        EnergyPeriod.P3,
    ]


MONTH_ORDER = {
    "enero": 1, "febrero": 2, "marzo": 3, "abril": 4,
    "mayo": 5, "junio": 6, "julio": 7, "agosto": 8,
    "septiembre": 9, "octubre": 10, "noviembre": 11, "diciembre": 12
}

DAY_ORDER = {
    "lunes": 0,
    "martes": 1,
    "miercoles": 2,
    "jueves": 3,
    "viernes": 4,
    "sabado": 5,
    "domingo": 6,
}


# =============================================================================
# MOTOR PRINCIPAL
# =============================================================================

def run_consumption_analysis(analysis: ElectricityAnalysis) -> ElectricityAnalysis:
    records = analysis.hourly_records

    if not records:
        print("ERROR: No hay registros horarios para analizar.")
        return analysis

    contract_type = analysis.client.contract_type

    print("Iniciando análisis de consumo...")

    # ----------------------------------------------------------------
    # KPIs PRINCIPALES
    # ----------------------------------------------------------------

    total_kwh = _round2(sum(r.consumption_kwh for r in records))
    total_days = len({r.timestamp.date() for r in records})
    total_hours = len(records)

    avg_daily_kwh = _round2(total_kwh / total_days) if total_days > 0 else 0.0
    avg_hourly_kwh = _round2(total_kwh / total_hours) if total_hours > 0 else 0.0

    date_from = min(r.timestamp for r in records)
    date_to = max(r.timestamp for r in records)

    print(f"  Consumo total:     {total_kwh} kWh")
    print(f"  Promedio diario:   {avg_daily_kwh} kWh")
    print(f"  Promedio horario:  {avg_hourly_kwh} kWh")
    print(f"  Periodo:           {date_from.date()} a {date_to.date()}")

    # ----------------------------------------------------------------
    # AGREGACIÓN POR MES
    # ----------------------------------------------------------------

    by_month_sum = defaultdict(float)
    by_month_count = defaultdict(int)

    for r in records:
        by_month_sum[r.month_name] += r.consumption_kwh
        by_month_count[r.month_name] += 1

    by_month = {
        month: {
            "total_kwh": _round2(by_month_sum[month]),
            "avg_kwh": _round2(by_month_sum[month] / by_month_count[month]),
            "num_horas": by_month_count[month],
            "month_num": MONTH_ORDER.get(month, 0),
        }
        for month in by_month_sum
    }
    by_month = dict(sorted(by_month.items(), key=lambda x: x[1]["month_num"]))

    # ----------------------------------------------------------------
    # AGREGACIÓN POR HORA
    # ----------------------------------------------------------------

    by_hour_sum = defaultdict(float)
    by_hour_count = defaultdict(int)

    for r in records:
        by_hour_sum[r.hour] += r.consumption_kwh
        by_hour_count[r.hour] += 1

    by_hour = {
        hour: {
            "avg_kwh": _round2(by_hour_sum[hour] / by_hour_count[hour]),
            "total_kwh": _round2(by_hour_sum[hour]),
            "num_dias": by_hour_count[hour],
        }
        for hour in sorted(by_hour_sum.keys())
    }

    # ----------------------------------------------------------------
    # AGREGACIÓN POR DÍA DE LA SEMANA
    # ----------------------------------------------------------------

    by_dow_sum = defaultdict(float)
    by_dow_count = defaultdict(int)

    for r in records:
        day = _normalize_day_name(r.day_of_week)
        by_dow_sum[day] += r.consumption_kwh
        by_dow_count[day] += 1

    by_day_of_week = {
        day: {
            "total_kwh": _round2(by_dow_sum[day]),
            "avg_kwh": _round2(by_dow_sum[day] / by_dow_count[day]),
            "num_horas": by_dow_count[day],
            "day_num": DAY_ORDER.get(day, 99),
        }
        for day in by_dow_sum
    }
    by_day_of_week = dict(sorted(by_day_of_week.items(), key=lambda x: x[1]["day_num"]))

    # ----------------------------------------------------------------
    # AGREGACIÓN POR DÍA DEL MES
    # ----------------------------------------------------------------

    by_dom_sum = defaultdict(float)
    by_dom_count = defaultdict(int)

    for r in records:
        by_dom_sum[r.day_of_month] += r.consumption_kwh
        by_dom_count[r.day_of_month] += 1

    by_day_of_month = {
        day: {
            "avg_kwh": _round2(by_dom_sum[day] / by_dom_count[day]),
            "total_kwh": _round2(by_dom_sum[day]),
        }
        for day in sorted(by_dom_sum.keys())
    }

    # ----------------------------------------------------------------
    # AGREGACIÓN POR HORA Y FECHA
    # ----------------------------------------------------------------

    by_hour_and_date = {
        r.timestamp.strftime("%Y-%m-%d %H:00"): _round2(r.consumption_kwh)
        for r in records
    }

    # ----------------------------------------------------------------
    # DESGLOSE POR PERIODO ENERGÉTICO
    # 2.0TD -> P1/P2/P3
    # 3.0TD -> P1/P2/P3/P4/P5/P6
    # ----------------------------------------------------------------

    period_sums = defaultdict(float)
    period_counts = defaultdict(int)

    for r in records:
        period_sums[r.energy_period] += r.consumption_kwh
        period_counts[r.energy_period] += 1

    by_energy_period = {}
    ordered_periods = _get_energy_period_order(contract_type)

    for period in ordered_periods:
        kwh = period_sums.get(period, 0.0)
        count = period_counts.get(period, 0)

        by_energy_period[period.value] = PeriodConsumptionSummary(
            period=period,
            total_kwh=_round2(kwh),
            avg_kwh_per_hour=_round2(kwh / count) if count > 0 else 0.0,
            pct_of_total=_round2((kwh / total_kwh) * 100) if total_kwh > 0 else 0.0,
        )

    print("  Consumo por periodo:")
    for period in ordered_periods:
        p = by_energy_period[period.value]
        print(f"    {period.value}: {p.total_kwh} kWh ({p.pct_of_total}%)")

    # ----------------------------------------------------------------
    # LABORABLE VS FIN DE SEMANA / FESTIVO
    # ----------------------------------------------------------------

    laborable_kwh = sum(
        r.consumption_kwh for r in records
        if not r.is_weekend and not r.is_holiday
    )
    fin_semana_kwh = sum(
        r.consumption_kwh for r in records
        if r.is_weekend or r.is_holiday
    )

    laborable_hours = sum(
        1 for r in records if not r.is_weekend and not r.is_holiday
    )
    fin_semana_hours = sum(
        1 for r in records if r.is_weekend or r.is_holiday
    )

    by_day_type = {
        "laborable": {
            "total_kwh": _round2(laborable_kwh),
            "avg_kwh": _round2(laborable_kwh / laborable_hours) if laborable_hours > 0 else 0.0,
            "num_horas": laborable_hours,
            "pct_of_total": _round2((laborable_kwh / total_kwh) * 100) if total_kwh > 0 else 0.0,
        },
        "fin_de_semana": {
            "total_kwh": _round2(fin_semana_kwh),
            "avg_kwh": _round2(fin_semana_kwh / fin_semana_hours) if fin_semana_hours > 0 else 0.0,
            "num_horas": fin_semana_hours,
            "pct_of_total": _round2((fin_semana_kwh / total_kwh) * 100) if total_kwh > 0 else 0.0,
        },
    }

    print(f"  Laborable:      {by_day_type['laborable']['total_kwh']} kWh ({by_day_type['laborable']['pct_of_total']}%)")
    print(f"  Fin de semana:  {by_day_type['fin_de_semana']['total_kwh']} kWh ({by_day_type['fin_de_semana']['pct_of_total']}%)")

    # ----------------------------------------------------------------
    # TEMPORADA CLIMÁTICA (compatibilidad con gráficos actuales)
    # ----------------------------------------------------------------

    season_sums = defaultdict(float)
    season_counts = defaultdict(int)

    for r in records:
        season = _get_climatic_season(r.month)
        season_sums[season] += r.consumption_kwh
        season_counts[season] += 1

    by_season = {
        season: {
            "total_kwh": _round2(season_sums[season]),
            "avg_kwh": _round2(season_sums[season] / season_counts[season]) if season_counts[season] > 0 else 0.0,
            "num_horas": season_counts[season],
            "pct_of_total": _round2((season_sums[season] / total_kwh) * 100) if total_kwh > 0 else 0.0,
        }
        for season in ["verano", "invierno", "entretiempo"]
        if season in season_sums
    }

    # ----------------------------------------------------------------
    # TEMPORADA TARIFARIA 3.0TD
    # ----------------------------------------------------------------

    by_tariff_season = {}

    if contract_type == ContractType.TD_3_0:
        tariff_sums = defaultdict(float)
        tariff_counts = defaultdict(int)

        for r in records:
            season = _get_tariff_season_3_0(r.month)
            tariff_sums[season] += r.consumption_kwh
            tariff_counts[season] += 1

        for season in ["alta", "med_alta", "media", "baja"]:
            if season in tariff_sums:
                by_tariff_season[season] = {
                    "total_kwh": _round2(tariff_sums[season]),
                    "avg_kwh": _round2(tariff_sums[season] / tariff_counts[season]) if tariff_counts[season] > 0 else 0.0,
                    "num_horas": tariff_counts[season],
                    "pct_of_total": _round2((tariff_sums[season] / total_kwh) * 100) if total_kwh > 0 else 0.0,
                }

    # ----------------------------------------------------------------
    # CONSUMO NOCTURNO (0h-7h)
    # ----------------------------------------------------------------

    nocturno_kwh = sum(r.consumption_kwh for r in records if r.hour < 8)
    nocturno_hours = sum(1 for r in records if r.hour < 8)

    nocturno = {
        "total_kwh": _round2(nocturno_kwh),
        "avg_kwh": _round2(nocturno_kwh / nocturno_hours) if nocturno_hours > 0 else 0.0,
        "pct_of_total": _round2((nocturno_kwh / total_kwh) * 100) if total_kwh > 0 else 0.0,
    }

    print(f"  Consumo nocturno (0h-8h): {nocturno['total_kwh']} kWh ({nocturno['pct_of_total']}%)")

    # ----------------------------------------------------------------
    # CAMPOS EXTRA 3.0TD: importación / exportación / autoconsumo
    # ----------------------------------------------------------------

    total_export_kwh = _round2(sum(getattr(r, "export_kwh", 0.0) for r in records))
    total_self_consumption_kwh = _round2(sum(getattr(r, "self_consumption_kwh", 0.0) for r in records))
    estimated_hours = sum(1 for r in records if getattr(r, "is_estimated", None) is True)
    real_hours = sum(1 for r in records if getattr(r, "is_estimated", None) is False)

    extra_3_0 = {
        "total_export_kwh": total_export_kwh,
        "total_self_consumption_kwh": total_self_consumption_kwh,
        "estimated_hours": estimated_hours,
        "real_hours": real_hours,
    }

    # ----------------------------------------------------------------
    # CONSTRUIR SUMMARY
    # ----------------------------------------------------------------

    summary = ConsumptionSummary(
        total_kwh=total_kwh,
        avg_daily_kwh=avg_daily_kwh,
        avg_hourly_kwh=avg_hourly_kwh,
        date_from=date_from,
        date_to=date_to,
        total_days=total_days,
        by_month=by_month,
        by_hour=by_hour,
        by_day_of_week=by_day_of_week,
        by_day_of_month=by_day_of_month,
        by_hour_and_date=by_hour_and_date,
        by_energy_period=by_energy_period,
    )

    # Compatibilidad con el resto de tu proyecto
    summary.by_day_type = by_day_type
    summary.by_season = by_season
    summary.nocturno = nocturno

    # Campos nuevos útiles
    summary.by_tariff_season = by_tariff_season
    summary.extra_3_0 = extra_3_0

    analysis.consumption_summary = summary

    print("Análisis de consumo completado.")
    return analysis
