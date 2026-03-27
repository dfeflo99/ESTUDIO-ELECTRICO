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

MESES_ES_CAT = {
    "ene": 1, "enero": 1, "gen": 1, "gener": 1,
    "feb": 2, "febrero": 2, "febrer": 2,
    "mar": 3, "marzo": 3, "març": 3, "marc": 3,
    "abr": 4, "abril": 4,
    "may": 5, "mayo": 5, "maig": 5,
    "jun": 6, "junio": 6, "juny": 6,
    "jul": 7, "julio": 7, "juliol": 7,
    "ago": 8, "agosto": 8, "agost": 8,
    "sep": 9, "sept": 9, "septiembre": 9, "set": 9, "setembre": 9,
    "oct": 10, "octubre": 10,
    "nov": 11, "noviembre": 11, "novembre": 11,
    "dic": 12, "diciembre": 12, "des": 12, "desembre": 12,
}


# =============================================================================
# HELPERS
# =============================================================================

def read_csv_flexible(filepath: str, nrows: Optional[int] = None) -> pd.DataFrame:
    """
    Lee CSV con separador ';' y tolerancia a utf-8 / latin-1.
    """
    for enc in ("utf-8", "latin-1"):
        try:
            return pd.read_csv(
                filepath,
                sep=";",
                dtype=str,
                encoding=enc,
                on_bad_lines="skip",
                nrows=nrows,
            )
        except UnicodeDecodeError:
            continue
    return pd.read_csv(
        filepath,
        sep=";",
        dtype=str,
        encoding="utf-8",
        on_bad_lines="skip",
        nrows=nrows,
    )


def clean_columns(df: pd.DataFrame) -> pd.DataFrame:
    df = df.copy()
    df.columns = [str(c).strip() for c in df.columns]
    df = df.loc[:, ~pd.Series(df.columns).str.startswith("Unnamed").values]
    return df


def get_spain_holidays(province: Optional[str] = None, years: Optional[List[int]] = None):
    """
    Festivos España.
    """
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

    # decimal con coma
    text = text.replace(",", ".")
    try:
        return float(text)
    except Exception:
        return default


def safe_int(value, default: int = 0) -> int:
    if pd.isna(value):
        return default

    text = str(value).strip()
    if text == "":
        return default

    text = text.replace(",", ".")
    try:
        return int(float(text))
    except Exception:
        return default


def month_name_es(month: int) -> str:
    names = {
        1: "enero", 2: "febrero", 3: "marzo", 4: "abril",
        5: "mayo", 6: "junio", 7: "julio", 8: "agosto",
        9: "septiembre", 10: "octubre", 11: "noviembre", 12: "diciembre"
    }
    return names.get(month, "")


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
    Soporta:
    - 02/2024
    - 02-2024
    - 2024-02
    - ene-25
    - feb-24
    - marzo-2025
    - març-24
    """
    raw = str(text).strip().lower()
    if not raw or raw == "nan":
        return None, None

    # Caso texto mes-año
    m = re.match(r"^([a-zà-ÿ]+)[\-/ ]+(\d{2,4})$", raw)
    if m:
        mes_txt = m.group(1)
        year_txt = m.group(2)

        month_num = MESES_ES_CAT.get(mes_txt)
        if month_num is None:
            return None, None

        year = int(year_txt)
        if year < 100:
            year += 2000

        return month_num, year

    # Caso numérico
    nums = re.findall(r"\d+", raw)
    if len(nums) >= 2:
        a, b = nums[0], nums[1]

        # mes-año
        if len(b) in (2, 4):
            month_num = int(a)
            year = int(b)
            if year < 100:
                year += 2000
            if 1 <= month_num <= 12:
                return month_num, year

        # año-mes
        if len(a) == 4:
            year = int(a)
            month_num = int(b)
            if 1 <= month_num <= 12:
                return month_num, year

    return None, None


def detect_csv_type(filepath: str) -> str:
    """
    Detecta tipo por columnas, no por nombre de archivo.
    """
    df = clean_columns(read_csv_flexible(filepath, nrows=5))
    cols = set(df.columns)

    if {"CUPS", "Fecha", "Hora", "AE_kWh"}.issubset(cols):
        return "consumption_3_0"

    if {"CUPS", "Mes/Any", "Periode", "kW", "Data", "Hora"}.issubset(cols):
        return "power_3_0"

    if {"CUPS", "Fecha", "Hora", "Consumo"}.issubset(cols):
        return "consumption_2_0"

    if {"CUPS", "Mes/Ano", "Periodo", "kW", "Fecha", "Hora"}.issubset(cols):
        return "power_2_0"

    raise ValueError(
        f"No se pudo detectar el tipo de CSV en: {os.path.basename(filepath)} | columnas={list(df.columns)}"
    )


# =============================================================================
# NORMALIZACIÓN DE HORAS
# =============================================================================

def normalize_hour_2_0(hour_raw: int) -> int:
    """
    2.0TD:
    - habitual 1..24
    - 1 = 00:00-00:59
    - 24 = 23:00-23:59
    - si viniera 0, lo tratamos como 00:00-00:59 también
    Internamente devolvemos 0..23
    """
    if hour_raw <= 0:
        return 0
    if hour_raw >= 24:
        return 23
    return hour_raw - 1


def normalize_hour_3_0(hour_raw: int) -> int:
    """
    3.0TD:
    - habitual 0..24
    - 0 = 00:00-00:59
    - 24 se trata como 23
    Internamente devolvemos 0..23
    """
    if hour_raw <= 0:
        return 0
    if hour_raw >= 24:
        return 23
    return hour_raw


# =============================================================================
# PERIODOS 2.0TD
# =============================================================================

def get_energy_period_2_0(dt: datetime, is_holiday: bool) -> EnergyPeriod:
    """
    2.0TD energía:
    - P1: lun-vie 10-14 y 18-22
    - P2: lun-vie resto horas laborables
    - P3: noches + fines de semana + festivos
    """
    wd = dt.weekday()
    h = dt.hour

    if is_holiday or wd >= 5:
        return EnergyPeriod.P3

    if (10 <= h < 14) or (18 <= h < 22):
        return EnergyPeriod.P1

    if 0 <= h < 8:
        return EnergyPeriod.P3

    return EnergyPeriod.P2


def get_power_period_2_0(dt: datetime, is_holiday: bool) -> PowerPeriod:
    """
    En tu proyecto:
    2.0TD potencia = P1 y P3
    - P1: laborables 8-24
    - P3: resto
    """
    wd = dt.weekday()
    h = dt.hour

    if is_holiday or wd >= 5 or h < 8:
        return PowerPeriod.P3

    return PowerPeriod.P1


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
    """
    Regla fijada contigo:
    - sábados, domingos y festivos: P6 24h
    - laborables:
      ALTA     -> P1/P2/P6
      MED_ALTA -> P2/P3/P6
      MEDIA    -> P3/P4/P6
      BAJA     -> P4/P5/P6
    """
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
    """
    Para registros horarios derivados del CSV de consumo 3.0TD,
    alineamos power_period con la misma lógica horaria.
    """
    ep = get_energy_period_3_0(dt, is_holiday)
    return PowerPeriod(ep.value)


# =============================================================================
# PARSEOS DE PERIODO
# =============================================================================

def parse_period_2_0(period_text: str) -> str:
    text = str(period_text).strip().lower()

    if text == "punta":
        return "P1"
    if text == "valle":
        return "P3"
    if text in ("pot.max", "pot max", "potmax"):
        return "Pot.Max"

    return str(period_text).strip()


def parse_period_3_0(period_text: str) -> str:
    text = str(period_text).strip().upper()

    if text in {"P1", "P2", "P3", "P4", "P5", "P6"}:
        return text
    if text in {"POT.MAX", "POT MAX", "POTMAX"}:
        return "Pot.Max"

    return str(period_text).strip()


# =============================================================================
# LOADERS CONSUMO
# =============================================================================

def load_consumption_csv_2_0(filepath: str, client: ClientProfile) -> List[HourlyRecord]:
    df = clean_columns(read_csv_flexible(filepath))

    years = sorted(
        pd.to_datetime(df["Fecha"], format="%d/%m/%Y", errors="coerce")
        .dropna()
        .dt.year.unique()
        .tolist()
    )
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

            records.append(
                HourlyRecord(
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
            )
        except Exception as e:
            print(f"[WARN] Error procesando fila consumo 2.0TD: {e}")

    return records


def load_consumption_csv_3_0(filepath: str, client: ClientProfile) -> List[HourlyRecord]:
    df = clean_columns(read_csv_flexible(filepath))

    years = sorted(
        pd.to_datetime(df["Fecha"], format="%d/%m/%Y", errors="coerce")
        .dropna()
        .dt.year.unique()
        .tolist()
    )
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
            ae_autocons = safe_float(row.get("AE_AUTOCONS_KWh", row.get("AE_AUTOCONS_kWh")))
            r1 = safe_float(row.get("R1_kVARh"))
            r2 = safe_float(row.get("R2_kVARh"))
            r3 = safe_float(row.get("R3_kVARh"))
            r4 = safe_float(row.get("R4_kVARh"))

            real_est = str(row.get("REAL/ESTIMADO", "")).strip().upper()
            is_estimated = True if real_est == "E" else False if real_est == "R" else None

            records.append(
                HourlyRecord(
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
            )
        except Exception as e:
            print(f"[WARN] Error procesando fila consumo 3.0TD: {e}")

    return records


# =============================================================================
# LOADERS POTENCIA
# =============================================================================

def load_power_csv_2_0(filepath: str) -> List[MonthlyMaxPower]:
    df = clean_columns(read_csv_flexible(filepath))
    records = []

    for _, row in df.iterrows():
        try:
            month_num, year = extract_month_year(row.get("Mes/Ano", ""))

            dt_date = parse_date_flexible(row.get("Fecha", ""))
            if month_num is None or year is None:
                if dt_date is not None:
                    month_num = dt_date.month
                    year = dt_date.year
                else:
                    raise ValueError(f"No se pudo interpretar Mes/Ano='{row.get('Mes/Ano', '')}'")

            period = parse_period_2_0(row.get("Periodo", ""))
            max_kw = safe_float(row.get("kW"))

            hour_text = str(row.get("Hora", "")).strip()
            if ":" in hour_text:
                try:
                    hh, mm = hour_text.split(":")
                    hour = min(max(int(hh), 0), 23)
                    minute = min(max(int(mm), 0), 59)
                except Exception:
                    hour = 0
                    minute = 0
            else:
                hour_raw = safe_int(row.get("Hora", 0), default=0)
                hour = normalize_hour_2_0(hour_raw)
                minute = 0

            if dt_date is not None:
                dt = datetime(dt_date.year, dt_date.month, dt_date.day, hour, minute)
            else:
                dt = datetime(year, month_num, 1, hour, minute)

            records.append(
                MonthlyMaxPower(
                    month=str(row.get("Mes/Ano", "")),
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
    df = clean_columns(read_csv_flexible(filepath))
    records = []

    for _, row in df.iterrows():
        try:
            month_num, year = extract_month_year(row.get("Mes/Any", ""))

            dt_date = parse_date_flexible(row.get("Data", ""))
            if month_num is None or year is None:
                if dt_date is not None:
                    month_num = dt_date.month
                    year = dt_date.year
                else:
                    raise ValueError(f"No se pudo interpretar Mes/Any='{row.get('Mes/Any', '')}'")

            period = parse_period_3_0(row.get("Periode", ""))
            max_kw = safe_float(row.get("kW"))

            hour_text = str(row.get("Hora", "")).strip()
            if ":" in hour_text:
                try:
                    hh, mm = hour_text.split(":")
                    hour = min(max(int(hh), 0), 23)
                    minute = min(max(int(mm), 0), 59)
                except Exception:
                    hour = 0
                    minute = 0
            else:
                hour_raw = safe_int(row.get("Hora", 0), default=0)
                hour = normalize_hour_3_0(hour_raw)
                minute = 0

            if dt_date is not None:
                dt = datetime(dt_date.year, dt_date.month, dt_date.day, hour, minute)
            else:
                dt = datetime(year, month_num, 1, hour, minute)

            records.append(
                MonthlyMaxPower(
                    month=str(row.get("Mes/Any", "")),
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

def load_from_csv(
    filepaths: List[str],
    client: ClientProfile,
    contract: Optional[ContractInfo] = None
) -> ElectricityAnalysis:
    hourly_records: List[HourlyRecord] = []
    monthly_max_power: List[MonthlyMaxPower] = []
    detected_types: List[Tuple[str, str]] = []

    for filepath in filepaths:
        csv_type = detect_csv_type(filepath)
        detected_types.append((os.path.basename(filepath), csv_type))

        if csv_type == "consumption_2_0":
            hourly_records.extend(load_consumption_csv_2_0(filepath, client))
        elif csv_type == "power_2_0":
            monthly_max_power.extend(load_power_csv_2_0(filepath))
        elif csv_type == "consumption_3_0":
            hourly_records.extend(load_consumption_csv_3_0(filepath, client))
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
