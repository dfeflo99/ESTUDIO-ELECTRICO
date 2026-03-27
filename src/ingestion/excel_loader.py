# =============================================================================
# src/ingestion/excel_loader.py
# Carga y parseo de CSVs de distribuidora
# Compatible con 2.0TD + 3.0TD
# =============================================================================

from __future__ import annotations

import os
import re
from datetime import datetime
from typing import List, Optional, Tuple

import pandas as pd
import holidays

from src.models.internal_data_model import (
    ElectricityAnalysis,
    ClientProfile,
    ContractInfo,
    HourlyRecord,
    MonthlyMaxPower,
    DataSource,
    EnergyPeriod,
    PowerPeriod,
    ContractType,
)


# =============================================================================
# CONFIG
# =============================================================================

SPAIN_HOLIDAYS_CACHE = {}


# =============================================================================
# HELPERS
# =============================================================================

def get_spain_holidays(province: Optional[str] = None, years: Optional[List[int]] = None):
    key = (province, tuple(sorted(years)) if years else None)
    if key not in SPAIN_HOLIDAYS_CACHE:
        if years:
            SPAIN_HOLIDAYS_CACHE[key] = holidays.Spain(years=years)
        else:
            SPAIN_HOLIDAYS_CACHE[key] = holidays.Spain()
    return SPAIN_HOLIDAYS_CACHE[key]


def safe_float(value, default: float = 0.0) -> float:
    if pd.isna(value):
        return default

    text = str(value).strip()
    if text == "":
        return default

    text = text.replace(",", ".")
    try:
        return float(text)
    except Exception:
        return default


def safe_int(value, default: int = 0) -> int:
    if pd.isna(value):
        return default
    try:
        return int(float(str(value).strip().replace(",", ".")))
    except Exception:
        return default


def normalize_hour_2_0(hour_raw: int) -> int:
    if hour_raw <= 0:
        return 0
    if hour_raw == 24:
        return 23
    return hour_raw - 1


def normalize_hour_3_0(hour_raw: int) -> int:
    if hour_raw < 0:
        return 0
    if hour_raw >= 24:
        return 23
    return hour_raw


def month_name_es(month: int) -> str:
    names = {
        1: "enero", 2: "febrero", 3: "marzo", 4: "abril",
        5: "mayo", 6: "junio", 7: "julio", 8: "agosto",
        9: "septiembre", 10: "octubre", 11: "noviembre", 12: "diciembre"
    }
    return names.get(month, "")


def detect_csv_type(filepath: str) -> str:
    df = pd.read_csv(filepath, sep=";", nrows=5, dtype=str, encoding="utf-8", on_bad_lines="skip")
    cols = [c.strip() for c in df.columns]

    if "AE_kWh" in cols:
        return "consumption_3_0"

    if "Periode" in cols and "Mes/Any" in cols and "kW" in cols:
        return "power_3_0"

    if {"CUPS", "Fecha", "Hora", "Consumo"}.issubset(set(cols)):
        return "consumption_2_0"

    if "Periodo" in cols and "Mes/Ano" in cols and "kW" in cols:
        return "power_2_0"

    raise ValueError(f"No se pudo detectar el tipo de CSV en: {os.path.basename(filepath)}")


def parse_date_flexible(date_str: str) -> Optional[datetime]:
    text = str(date_str).strip()
    if not text or text.lower() == "nan":
        return None

    for fmt in ("%d/%m/%Y", "%d-%m-%Y", "%Y-%m-%d", "%d/%m/%y", "%d-%m-%y"):
        try:
            return datetime.strptime(text, fmt)
        except Exception:
            pass
    return None


def extract_month_year(text: str) -> Tuple[Optional[int], Optional[int]]:
    """
    Intenta sacar mes y año desde cadenas tipo:
    - 02/2024
    - 02-2024
    - 2/2024
    - 2-2024
    - 2024-02
    - 2024/02
    """
    raw = str(text).strip()
    if not raw or raw.lower() == "nan":
        return None, None

    nums = re.findall(r"\d+", raw)
    if len(nums) < 2:
        return None, None

    a, b = nums[0], nums[1]

    # Caso mes-año
    if len(b) == 4:
        month_num = int(a)
        year = int(b)
        if 1 <= month_num <= 12:
            return month_num, year

    # Caso año-mes
    if len(a) == 4:
        year = int(a)
        month_num = int(b)
        if 1 <= month_num <= 12:
            return month_num, year

    return None, None


# =============================================================================
# PERIODOS 2.0TD
# =============================================================================

def get_energy_period_2_0(dt: datetime, is_holiday: bool) -> EnergyPeriod:
    wd = dt.weekday()
    h = dt.hour

    if is_holiday or wd >= 5:
        return EnergyPeriod.P3

    if (10 <= h < 14) or (18 <= h < 22):
        return EnergyPeriod.P1

    return EnergyPeriod.P2


def get_power_period_2_0(dt: datetime, is_holiday: bool) -> PowerPeriod:
    wd = dt.weekday()
    h = dt.hour

    if is_holiday or wd >= 5:
        return PowerPeriod.P2

    if 8 <= h < 24:
        return PowerPeriod.P1

    return PowerPeriod.P2


# =============================================================================
# PERIODOS 3.0TD
# =============================================================================

def get_3_0_season(month: int) -> str:
    if month in (1, 2, 7, 12):
        return "ALTA"
    if month in (3, 11):
        return "MED_ALTA"
    if month in (6, 8, 9):
        return "MEDIA"
    return "BAJA"


def get_energy_period_3_0(dt: datetime, is_holiday: bool) -> EnergyPeriod:
    wd = dt.weekday()
    h = dt.hour

    if is_holiday or wd >= 5:
        return EnergyPeriod.P6

    season = get_3_0_season(dt.month)

    if 0 <= h < 8:
        return EnergyPeriod.P6

    if h == 8:
        if season == "ALTA":
            return EnergyPeriod.P2
        if season == "MED_ALTA":
            return EnergyPeriod.P3
        if season == "MEDIA":
            return EnergyPeriod.P4
        return EnergyPeriod.P5

    if 9 <= h < 14:
        if season == "ALTA":
            return EnergyPeriod.P1
        if season == "MED_ALTA":
            return EnergyPeriod.P2
        if season == "MEDIA":
            return EnergyPeriod.P3
        return EnergyPeriod.P4

    if 14 <= h < 18:
        if season == "ALTA":
            return EnergyPeriod.P2
        if season == "MED_ALTA":
            return EnergyPeriod.P3
        if season == "MEDIA":
            return EnergyPeriod.P4
        return EnergyPeriod.P5

    if 18 <= h < 22:
        if season == "ALTA":
            return EnergyPeriod.P1
        if season == "MED_ALTA":
            return EnergyPeriod.P2
        if season == "MEDIA":
            return EnergyPeriod.P3
        return EnergyPeriod.P4

    if 22 <= h < 24:
        if season == "ALTA":
            return EnergyPeriod.P2
        if season == "MED_ALTA":
            return EnergyPeriod.P3
        if season == "MEDIA":
            return EnergyPeriod.P4
        return EnergyPeriod.P5

    return EnergyPeriod.P6


def get_power_period_3_0(dt: datetime, is_holiday: bool) -> PowerPeriod:
    ep = get_energy_period_3_0(dt, is_holiday)
    return PowerPeriod(ep.value)


# =============================================================================
# LOADERS CONSUMO
# =============================================================================

def load_consumption_csv_2_0(filepath: str, client: ClientProfile) -> List[HourlyRecord]:
    df = pd.read_csv(
        filepath,
        sep=";",
        decimal=",",
        dtype=str,
        encoding="utf-8",
        on_bad_lines="skip"
    )

    years = sorted(pd.to_datetime(df["Fecha"], format="%d/%m/%Y", errors="coerce").dropna().dt.year.unique().tolist())
    es_holidays = get_spain_holidays(client.province, years=years)

    records = []

    for _, row in df.iterrows():
        try:
            date = datetime.strptime(str(row["Fecha"]).strip(), "%d/%m/%Y")
            hour_raw = safe_int(row["Hora"])
            hour = normalize_hour_2_0(hour_raw)
            dt = datetime(date.year, date.month, date.day, hour, 0)

            is_holiday = dt.date() in es_holidays
            energy_period = get_energy_period_2_0(dt, is_holiday)
            power_period = get_power_period_2_0(dt, is_holiday)
            consumption = safe_float(row["Consumo"])

            record = HourlyRecord(
                timestamp=dt,
                hour=hour,
                day_of_month=dt.day,
                day_of_week=dt.strftime("%A").lower(),
                day_of_week_num=dt.weekday(),
                month=dt.month,
                month_name=month_name_es(dt.month),
                is_weekend=dt.weekday() >= 5,
                is_holiday=is_holiday,
                consumption_kwh=consumption,
                energy_period=energy_period,
                power_period=power_period,
                exceeds_2kw=consumption > 2.0,
                source_hour_raw=hour_raw,
            )
            records.append(record)

        except Exception as e:
            print(f"[WARN] Error procesando fila consumo 2.0TD: {e}")

    return records


def load_consumption_csv_3_0(filepath: str, client: ClientProfile) -> List[HourlyRecord]:
    df = pd.read_csv(
        filepath,
        sep=";",
        dtype=str,
        encoding="utf-8",
        on_bad_lines="skip"
    )

    years = sorted(pd.to_datetime(df["Fecha"], format="%d/%m/%Y", errors="coerce").dropna().dt.year.unique().tolist())
    es_holidays = get_spain_holidays(client.province, years=years)

    records = []

    for _, row in df.iterrows():
        try:
            date = datetime.strptime(str(row["Fecha"]).strip(), "%d/%m/%Y")
            hour_raw = safe_int(row["Hora"])
            hour = normalize_hour_3_0(hour_raw)
            dt = datetime(date.year, date.month, date.day, hour, 0)

            is_holiday = dt.date() in es_holidays
            energy_period = get_energy_period_3_0(dt, is_holiday)
            power_period = get_power_period_3_0(dt, is_holiday)

            ae_kwh = safe_float(row.get("AE_kWh"))
            as_kwh = safe_float(row.get("AS_KWh"))
            ae_autocons = safe_float(row.get("AE_AUTOCONS_kWh"))
            r1 = safe_float(row.get("R1_kVARh"))
            r2 = safe_float(row.get("R2_kVARh"))
            r3 = safe_float(row.get("R3_kVARh"))
            r4 = safe_float(row.get("R4_kVARh"))

            real_est = str(row.get("REAL/ESTIMADO", "")).strip().upper()
            is_estimated = True if real_est == "E" else False if real_est == "R" else None

            record = HourlyRecord(
                timestamp=dt,
                hour=hour,
                day_of_month=dt.day,
                day_of_week=dt.strftime("%A").lower(),
                day_of_week_num=dt.weekday(),
                month=dt.month,
                month_name=month_name_es(dt.month),
                is_weekend=dt.weekday() >= 5,
                is_holiday=is_holiday,
                consumption_kwh=ae_kwh,
                energy_period=energy_period,
                power_period=power_period,
                exceeds_2kw=ae_kwh > 2.0,
                source_hour_raw=hour_raw,
                is_estimated=is_estimated,
                real_or_estimated=real_est if real_est else None,
                export_kwh=as_kwh,
                self_consumption_kwh=ae_autocons,
                reactive_r1_kvarh=r1,
                reactive_r2_kvarh=r2,
                reactive_r3_kvarh=r3,
                reactive_r4_kvarh=r4,
            )
            records.append(record)

        except Exception as e:
            print(f"[WARN] Error procesando fila consumo 3.0TD: {e}")

    return records


# =============================================================================
# LOADERS POTENCIA
# =============================================================================

def parse_period_2_0(period_text: str) -> str:
    text = str(period_text).strip()
    low = text.lower()

    if low in ("punta", "p1"):
        return "Punta"
    if low in ("valle", "p2"):
        return "Valle"
    if low in ("pot.max", "pot max", "potmax"):
        return "Pot.Max"

    return text


def parse_period_3_0(period_text: str) -> str:
    text = str(period_text).strip().upper()
    if text in {"P1", "P2", "P3", "P4", "P5", "P6"}:
        return text
    if text in {"POT.MAX", "POT MAX", "POTMAX"}:
        return "Pot.Max"
    return text


def load_power_csv_2_0(filepath: str) -> List[MonthlyMaxPower]:
    df = pd.read_csv(
        filepath,
        sep=";",
        dtype=str,
        encoding="utf-8",
        on_bad_lines="skip"
    )

    records = []

    for _, row in df.iterrows():
        try:
            month_num, year = extract_month_year(row.get("Mes/Ano", ""))

            date_str = str(row.get("Fecha", "")).strip()
            dt_date = parse_date_flexible(date_str)

            if month_num is None or year is None:
                if dt_date is not None:
                    month_num = dt_date.month
                    year = dt_date.year
                else:
                    raise ValueError(f"No se pudo interpretar Mes/Ano='{row.get('Mes/Ano', '')}'")

            period = parse_period_2_0(row["Periodo"])
            max_kw = safe_float(row["kW"])

            hour_raw = safe_int(row.get("Hora", 0), default=0)
            hour = normalize_hour_2_0(hour_raw)

            if dt_date is not None:
                dt = datetime(dt_date.year, dt_date.month, dt_date.day, hour, 0)
            else:
                dt = datetime(year, month_num, 1, hour, 0)

            records.append(
                MonthlyMaxPower(
                    month=f"{month_num:02d}/{year}",
                    month_num=month_num,
                    year=year,
                    period=period,
                    max_kw=max_kw,
                    date=dt,
                )
            )
        except Exception as e:
            print(f"[WARN] Error procesando fila potencia 2.0TD: {e}")

    return records


def load_power_csv_3_0(filepath: str) -> List[MonthlyMaxPower]:
    df = pd.read_csv(
        filepath,
        sep=";",
        dtype=str,
        encoding="utf-8",
        on_bad_lines="skip"
    )

    records = []

    for _, row in df.iterrows():
        try:
            month_num, year = extract_month_year(row.get("Mes/Any", ""))

            date_str = str(row.get("Data", "")).strip()
            dt_date = parse_date_flexible(date_str)

            if month_num is None or year is None:
                if dt_date is not None:
                    month_num = dt_date.month
                    year = dt_date.year
                else:
                    raise ValueError(f"No se pudo interpretar Mes/Any='{row.get('Mes/Any', '')}'")

            period = parse_period_3_0(row["Periode"])
            max_kw = safe_float(row["kW"])

            hour_raw = safe_int(row.get("Hora", 0), default=0)
            hour = normalize_hour_3_0(hour_raw)

            if dt_date is not None:
                dt = datetime(dt_date.year, dt_date.month, dt_date.day, hour, 0)
            else:
                dt = datetime(year, month_num, 1, hour, 0)

            records.append(
                MonthlyMaxPower(
                    month=f"{month_num:02d}/{year}",
                    month_num=month_num,
                    year=year,
                    period=period,
                    max_kw=max_kw,
                    date=dt,
                )
            )
        except Exception as e:
            print(f"[WARN] Error procesando fila potencia 3.0TD: {e}")

    return records


# =============================================================================
# API PRINCIPAL
# =============================================================================

def load_from_csv(filepaths: List[str], client: ClientProfile, contract: Optional[ContractInfo] = None) -> ElectricityAnalysis:
    hourly_records: List[HourlyRecord] = []
    monthly_max_power: List[MonthlyMaxPower] = []

    detected_types: List[Tuple[str, str]] = []

    for filepath in filepaths:
        csv_type = detect_csv_type(filepath)
        detected_types.append((os.path.basename(filepath), csv_type))

        if csv_type == "consumption_2_0":
            hourly_records.extend(load_consumption_csv_2_0(filepath, client))

        elif csv_type == "consumption_3_0":
            hourly_records.extend(load_consumption_csv_3_0(filepath, client))

        elif csv_type == "power_2_0":
            monthly_max_power.extend(load_power_csv_2_0(filepath))

        elif csv_type == "power_3_0":
            monthly_max_power.extend(load_power_csv_3_0(filepath))

    inferred_contract = client.contract_type
    if inferred_contract is None:
        if any(t[1].endswith("3_0") for t in detected_types):
            inferred_contract = ContractType.TD_3_0
        else:
            inferred_contract = ContractType.TD_2_0

    client_final = ClientProfile(
        client_type=client.client_type,
        contract_type=inferred_contract,
        province=client.province,
        name=client.name,
        email=client.email,
    )

    return ElectricityAnalysis(
        client=client_final,
        contract=contract,
        hourly_records=hourly_records,
        monthly_max_power=monthly_max_power,
        data_source=DataSource.CSV,
        is_complete=(len(hourly_records) > 0 or len(monthly_max_power) > 0),
    )
