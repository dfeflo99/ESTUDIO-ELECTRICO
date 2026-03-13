# =============================================================================
# src/ingestion/excel_loader.py
# Lector de los CSVs de consumo y potencia máxima demandada
# Versión: 1.1 — detección automática de archivos por columnas
#
# CSVs esperados:
#   - Consumo:          CUPS ; Fecha ; Hora ; Consumo ; ;
#   - Potencia máxima:  CUPS ; Mes/Ano ; Periodo ; kW ; Fecha ; Hora
#
# Notas importantes:
#   - Separador: punto y coma (;)
#   - Decimal: coma (,)
#   - Hora: 1-24 donde Hora 1 = 00:00-01:00 (se resta 1 para construir timestamp)
#   - Festivos: calculados con librería `holidays` según provincia del cliente
#   - El nombre del archivo NO importa — se detecta por sus columnas
# =============================================================================

import pandas as pd
import holidays
from datetime import datetime
from typing import Optional

import sys
sys.path.append('..')
from src.models.internal_data_model import (
    ElectricityAnalysis, ClientProfile, ContractInfo, ContractedPowers,
    HourlyRecord, MonthlyMaxPower, EnergyPeriod, PowerPeriod,
    DataSource, ClientType, ContractType
)


# =============================================================================
# MAPA DE PROVINCIAS → CÓDIGO DE COMUNIDAD AUTÓNOMA
# =============================================================================

PROVINCE_TO_REGION = {
    "Álava": "PV", "Albacete": "CM", "Alicante": "VC", "Almería": "AN",
    "Asturias": "AS", "Ávila": "CL", "Badajoz": "EX", "Barcelona": "CT",
    "Burgos": "CL", "Cáceres": "EX", "Cádiz": "AN", "Cantabria": "CB",
    "Castellón": "VC", "Ciudad Real": "CM", "Córdoba": "AN", "Cuenca": "CM",
    "Girona": "CT", "Granada": "AN", "Guadalajara": "CM", "Guipúzcoa": "PV",
    "Huelva": "AN", "Huesca": "AR", "Islas Baleares": "IB", "Jaén": "AN",
    "La Coruña": "GA", "La Rioja": "RI", "Las Palmas": "CN", "León": "CL",
    "Lleida": "CT", "Lugo": "GA", "Madrid": "MD", "Málaga": "AN",
    "Murcia": "MC", "Navarra": "NC", "Ourense": "GA", "Palencia": "CL",
    "Pontevedra": "GA", "Salamanca": "CL", "Santa Cruz de Tenerife": "CN",
    "Segovia": "CL", "Sevilla": "AN", "Soria": "CL", "Tarragona": "CT",
    "Teruel": "AR", "Toledo": "CM", "Valencia": "VC", "Valladolid": "CL",
    "Vizcaya": "PV", "Zamora": "CL", "Zaragoza": "AR", "Ceuta": "CE",
    "Melilla": "ML"
}


# =============================================================================
# FUNCIÓN 1 — DETECCIÓN AUTOMÁTICA DEL TIPO DE CSV
# =============================================================================

def detect_csv_type(filepath: str) -> str:
    """
    Detecta si un CSV es de consumo o de potencia máxima
    mirando sus columnas, no su nombre.

    Returns:
        'consumo' o 'potencia'
    """
    try:
        df = pd.read_csv(filepath, sep=';', nrows=1, encoding='utf-8')
    except UnicodeDecodeError:
        df = pd.read_csv(filepath, sep=';', nrows=1, encoding='latin-1')

    cols = [c.strip() for c in df.columns]

    if 'Consumo' in cols and 'Hora' in cols and 'Fecha' in cols:
        return 'consumo'
    elif 'kW' in cols and 'Periodo' in cols and 'Mes/Ano' in cols:
        return 'potencia'
    else:
        raise ValueError(
            f"No se puede detectar el tipo de CSV.\n"
            f"Columnas encontradas: {cols}\n"
            f"Esperadas para consumo:  ['CUPS', 'Fecha', 'Hora', 'Consumo']\n"
            f"Esperadas para potencia: ['CUPS', 'Mes/Ano', 'Periodo', 'kW', 'Fecha', 'Hora']"
        )


def detect_and_assign_files(filepaths: list) -> dict:
    """
    Recibe una lista de rutas CSV con cualquier nombre
    y devuelve un diccionario asignando cada archivo a su tipo.

    Returns:
        {'consumo': '/ruta/archivo1.csv', 'potencia': '/ruta/archivo2.csv'}
    """
    result = {}
    for filepath in filepaths:
        tipo = detect_csv_type(filepath)
        if tipo in result:
            raise ValueError(
                f"Se han detectado dos archivos del mismo tipo '{tipo}'.\n"
                f"Sube un archivo de consumo y uno de potencia máxima."
            )
        result[tipo] = filepath

    if 'consumo' not in result:
        raise ValueError("No se detectó archivo de consumo. "
                         "Sube el Excel de consumo horario.")
    if 'potencia' not in result:
        raise ValueError("No se detectó archivo de potencia máxima. "
                         "Sube el Excel de potencias máximas.")

    print(f"✅ Archivos detectados:")
    print(f"   Consumo:  {result['consumo']}")
    print(f"   Potencia: {result['potencia']}")
    return result


# =============================================================================
# FUNCIÓN 2 — CARGAR FESTIVOS
# =============================================================================

def load_holidays(province: str, years: list) -> set:
    """
    Carga festivos nacionales + autonómicos para una provincia y años dados.
    """
    region = PROVINCE_TO_REGION.get(province, "MD")
    festivos = set()
    for year in years:
        festivos.update(holidays.Spain(prov=region, years=year).keys())
    return festivos


# =============================================================================
# FUNCIÓN 3 — PERIODO DE ENERGÍA (P1/P2/P3) — Tarifa 2.0TD
# =============================================================================

def get_energy_period(dt: datetime, festivos: set) -> EnergyPeriod:
    """
    P3 Valle:  Fines de semana, festivos y laborables 0h-8h
    P1 Punta:  Laborables 10h-14h y 18h-22h
    P2 Llano:  Resto de laborables
    """
    hora = dt.hour
    if dt.weekday() >= 5 or dt.date() in festivos:
        return EnergyPeriod.P3
    if hora < 8:
        return EnergyPeriod.P3
    elif (10 <= hora < 14) or (18 <= hora < 22):
        return EnergyPeriod.P1
    else:
        return EnergyPeriod.P2


# =============================================================================
# FUNCIÓN 4 — PERIODO DE POTENCIA (P1/P2) — Tarifa 2.0TD
# =============================================================================

def get_power_period(dt: datetime, festivos: set) -> PowerPeriod:
    """
    P2: Fines de semana, festivos y laborables 0h-8h
    P1: Laborables 8h-24h
    """
    hora = dt.hour
    if dt.weekday() >= 5 or dt.date() in festivos or hora < 8:
        return PowerPeriod.P2
    else:
        return PowerPeriod.P1


# =============================================================================
# FUNCIÓN 5 — LEER CSV DE CONSUMO
# =============================================================================

def load_consumption_csv(filepath: str, festivos: set) -> list:
    """
    Lee el CSV de consumo horario y devuelve lista de HourlyRecord.
    """
    try:
        df = pd.read_csv(filepath, sep=';', decimal=',',
                         encoding='utf-8', skipinitialspace=True)
    except UnicodeDecodeError:
        df = pd.read_csv(filepath, sep=';', decimal=',',
                         encoding='latin-1', skipinitialspace=True)

    df.columns = df.columns.str.strip()
    df = df.loc[:, ~df.columns.str.startswith('Unnamed')]
    df = df.rename(columns={'CUPS': 'cups', 'Fecha': 'fecha',
                             'Hora': 'hora', 'Consumo': 'consumo_kwh'})

    for col in ['cups', 'fecha', 'hora', 'consumo_kwh']:
        if col not in df.columns:
            raise ValueError(f"Columna '{col}' no encontrada en CSV de consumo.")

    df['fecha'] = pd.to_datetime(df['fecha'], format='%d/%m/%Y')
    df['hora_ajustada'] = df['hora'] - 1
    df['timestamp'] = df['fecha'] + pd.to_timedelta(df['hora_ajustada'], unit='h')
    df = df.dropna(subset=['consumo_kwh'])
    df['consumo_kwh'] = df['consumo_kwh'].astype(float)

    dias_semana = {0: 'lunes', 1: 'martes', 2: 'miércoles', 3: 'jueves',
                   4: 'viernes', 5: 'sábado', 6: 'domingo'}
    meses = {1: 'enero', 2: 'febrero', 3: 'marzo', 4: 'abril', 5: 'mayo',
             6: 'junio', 7: 'julio', 8: 'agosto', 9: 'septiembre',
             10: 'octubre', 11: 'noviembre', 12: 'diciembre'}

    records = []
    for _, row in df.iterrows():
        ts = row['timestamp'].to_pydatetime()
        record = HourlyRecord(
            timestamp       = ts,
            hour            = int(row['hora']),
            day_of_month    = ts.day,
            day_of_week     = dias_semana[ts.weekday()],
            day_of_week_num = ts.weekday(),
            month           = ts.month,
            month_name      = meses[ts.month],
            is_weekend      = ts.weekday() >= 5,
            is_holiday      = ts.date() in festivos,
            consumption_kwh = round(float(row['consumo_kwh']), 4),
            energy_period   = get_energy_period(ts, festivos),
            power_period    = get_power_period(ts, festivos),
            exceeds_2kw     = float(row['consumo_kwh']) > 2.0
        )
        records.append(record)

    records.sort(key=lambda x: x.timestamp)
    print(f"✅ CSV de consumo cargado: {len(records)} registros")
    return records


# =============================================================================
# FUNCIÓN 6 — LEER CSV DE POTENCIA MÁXIMA
# =============================================================================

def load_max_power_csv(filepath: str) -> list:
    """
    Lee el CSV de potencia máxima y devuelve lista de MonthlyMaxPower.
    """
    try:
        df = pd.read_csv(filepath, sep=';', decimal=',',
                         encoding='utf-8', skipinitialspace=True)
    except UnicodeDecodeError:
        df = pd.read_csv(filepath, sep=';', decimal=',',
                         encoding='latin-1', skipinitialspace=True)

    df.columns = df.columns.str.strip()
    df = df.rename(columns={'CUPS': 'cups', 'Mes/Ano': 'mes_ano',
                             'Periodo': 'periodo', 'kW': 'max_kw',
                             'Fecha': 'fecha', 'Hora': 'hora'})

    for col in ['cups', 'mes_ano', 'periodo', 'max_kw', 'fecha', 'hora']:
        if col not in df.columns:
            raise ValueError(f"Columna '{col}' no encontrada en CSV de potencia.")

    mes_map = {'ene': 1, 'feb': 2, 'mar': 3, 'abr': 4, 'may': 5, 'jun': 6,
               'jul': 7, 'ago': 8, 'sep': 9, 'oct': 10, 'nov': 11, 'dic': 12}

    records = []
    for _, row in df.iterrows():
        partes = str(row['mes_ano']).split('-')
        mes_str = partes[0].lower()
        anio = 2000 + int(partes[1])
        mes_num = mes_map.get(mes_str, 1)

        try:
            fecha_hora = datetime.strptime(f"{row['fecha']} {row['hora']}",
                                           '%d/%m/%Y %H:%M')
        except ValueError:
            fecha_hora = datetime.strptime(row['fecha'], '%d/%m/%Y')

        records.append(MonthlyMaxPower(
            month=str(row['mes_ano']), month_num=mes_num, year=anio,
            period=str(row['periodo']), max_kw=round(float(row['max_kw']), 4),
            date=fecha_hora
        ))

    print(f"✅ CSV de potencia máxima cargado: {len(records)} registros")
    return records


# =============================================================================
# FUNCIÓN PRINCIPAL
# =============================================================================

def load_from_csv(
    filepaths: list,
    client: ClientProfile,
    contract: Optional[ContractInfo] = None
) -> ElectricityAnalysis:
    """
    Función principal. Acepta archivos con CUALQUIER nombre,
    los detecta automáticamente y devuelve un ElectricityAnalysis completo.

    Args:
        filepaths: Lista de rutas a los CSVs subidos por el usuario
        client:    Perfil del cliente
        contract:  Datos del contrato (opcional)

    Ejemplo:
        analysis = load_from_csv(
            filepaths = ['archivo1.csv', 'archivo2.csv'],
            client    = ClientProfile(
                client_type   = ClientType.DOMESTIC,
                contract_type = ContractType.TD_2_0,
                province      = "Madrid"
            )
        )
    """
    print("🔄 Iniciando carga de datos...")

    # 1. Detectar archivos automáticamente
    archivos = detect_and_assign_files(filepaths)

    # 2. Extraer años para cargar festivos correctos
    df_fechas = pd.read_csv(archivos['consumo'], sep=';', usecols=[1], header=0)
    df_fechas.columns = ['fecha']
    df_fechas['fecha'] = pd.to_datetime(df_fechas['fecha'],
                                         format='%d/%m/%Y', errors='coerce')
    years = [int(y) for y in df_fechas['fecha'].dt.year.dropna().unique()]

    # 3. Cargar festivos
    print(f"📅 Cargando festivos para {client.province} — años: {years}")
    festivos = load_holidays(client.province, years)
    print(f"   {len(festivos)} días festivos encontrados")

    # 4. Leer datos
    hourly_records    = load_consumption_csv(archivos['consumo'], festivos)
    monthly_max_power = load_max_power_csv(archivos['potencia'])

    # 5. Construir objeto principal
    analysis = ElectricityAnalysis(
        client            = client,
        contract          = contract,
        hourly_records    = hourly_records,
        monthly_max_power = monthly_max_power,
        data_source       = DataSource.CSV,
        is_complete       = False
    )

    print(f"\n✅ ElectricityAnalysis creado correctamente")
    print(f"   Registros horarios:        {len(hourly_records)}")
    print(f"   Registros potencia máxima: {len(monthly_max_power)}")
    return analysis
