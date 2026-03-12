# =============================================================================
# src/ingestion/excel_loader.py
# Lector de los CSVs de consumo y potencia máxima demandada
# Versión: 1.0
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
# =============================================================================

import pandas as pd
import holidays
from datetime import datetime, time
from typing import Optional

# Importamos el modelo interno
import sys
sys.path.append('..')  # Ajustar según estructura en Colab
from src.models.internal_data_model import (
    ElectricityAnalysis,
    ClientProfile,
    ContractInfo,
    ContractedPowers,
    HourlyRecord,
    MonthlyMaxPower,
    EnergyPeriod,
    PowerPeriod,
    DataSource,
    ClientType,
    ContractType
)


# =============================================================================
# MAPA DE PROVINCIAS → CÓDIGO DE COMUNIDAD AUTÓNOMA
# Necesario para la librería `holidays`
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
# FUNCIÓN 1 — CARGAR FESTIVOS
# =============================================================================

def load_holidays(province: str, years: list) -> set:
    """
    Carga el conjunto de fechas festivas (nacionales + autonómicas)
    para una provincia y un rango de años dado.

    Args:
        province: Nombre de la provincia del cliente (ej: "Madrid")
        years:    Lista de años a cubrir (ej: [2024, 2025])

    Returns:
        Set de objetos date con todos los días festivos
    """
    region = PROVINCE_TO_REGION.get(province, "MD")  # Madrid por defecto
    festivos = set()
    for year in years:
        festivos.update(holidays.Spain(prov=region, years=year).keys())
    return festivos


# =============================================================================
# FUNCIÓN 2 — ASIGNAR PERIODO DE ENERGÍA (P1/P2/P3)
# Tarifa 2.0TD
# =============================================================================

def get_energy_period(dt: datetime, festivos: set) -> EnergyPeriod:
    """
    Determina el periodo de energía (P1/P2/P3) para un timestamp dado.

    Reglas tarifa 2.0TD:
        P3 Valle:  Sábados, domingos, festivos (todo el día)
                   Lunes-Viernes: horas 0-8 (00:00-07:59)
        P1 Punta:  Lunes-Viernes (no festivos): horas 10-14 y 18-22 (10:00-13:59 y 18:00-21:59)
        P2 Llano:  Resto (Lunes-Viernes no festivos: 8-10, 14-18, 22-24)

    Args:
        dt:        Timestamp del registro (ya con hora ajustada, ej: 00:00 para hora 1)
        festivos:  Set de fechas festivas

    Returns:
        EnergyPeriod (P1, P2 o P3)
    """
    hora = dt.hour
    es_festivo = dt.date() in festivos
    es_fin_semana = dt.weekday() >= 5  # 5=sábado, 6=domingo

    # Días especiales → todo P3
    if es_fin_semana or es_festivo:
        return EnergyPeriod.P3

    # Días laborables
    if hora < 8:
        return EnergyPeriod.P3
    elif (10 <= hora < 14) or (18 <= hora < 22):
        return EnergyPeriod.P1
    else:
        return EnergyPeriod.P2


# =============================================================================
# FUNCIÓN 3 — ASIGNAR PERIODO DE POTENCIA (P1/P2)
# Tarifa 2.0TD
# =============================================================================

def get_power_period(dt: datetime, festivos: set) -> PowerPeriod:
    """
    Determina el periodo de potencia (P1/P2) para un timestamp dado.

    Reglas tarifa 2.0TD:
        P2: Sábados, domingos, festivos (todo el día)
            Lunes-Viernes: horas 0-8 (00:00-07:59)
        P1: Lunes-Viernes (no festivos): horas 8-24 (08:00-23:59)

    Args:
        dt:        Timestamp del registro
        festivos:  Set de fechas festivas

    Returns:
        PowerPeriod (P1 o P2)
    """
    hora = dt.hour
    es_festivo = dt.date() in festivos
    es_fin_semana = dt.weekday() >= 5

    if es_fin_semana or es_festivo or hora < 8:
        return PowerPeriod.P2
    else:
        return PowerPeriod.P1


# =============================================================================
# FUNCIÓN 4 — LEER CSV DE CONSUMO
# =============================================================================

def load_consumption_csv(filepath: str, festivos: set) -> list:
    """
    Lee el CSV de consumo horario y devuelve una lista de HourlyRecord.

    Formato esperado del CSV:
        CUPS ; Fecha ; Hora ; Consumo ; ;
        ES003140... ; 01/01/2025 ; 1 ; 0,089 ; ;

    Args:
        filepath:  Ruta al CSV de consumo
        festivos:  Set de fechas festivas (ya calculadas)

    Returns:
        Lista de HourlyRecord ordenada por timestamp
    """
    # --- Leer CSV ---
    df = pd.read_csv(
        filepath,
        sep=';',
        decimal=',',
        encoding='utf-8',
        skipinitialspace=True
    )

    # --- Limpiar columnas (eliminar espacios y columnas vacías) ---
    df.columns = df.columns.str.strip()
    df = df.loc[:, ~df.columns.str.startswith('Unnamed')]  # Elimina columnas vacías

    # --- Renombrar columnas para mayor claridad ---
    df = df.rename(columns={
        'CUPS':    'cups',
        'Fecha':   'fecha',
        'Hora':    'hora',
        'Consumo': 'consumo_kwh'
    })

    # --- Validaciones básicas ---
    required_cols = ['cups', 'fecha', 'hora', 'consumo_kwh']
    for col in required_cols:
        if col not in df.columns:
            raise ValueError(f"Columna '{col}' no encontrada en el CSV de consumo.")

    # --- Parsear fechas ---
    df['fecha'] = pd.to_datetime(df['fecha'], format='%d/%m/%Y')

    # --- Ajustar hora: Hora 1 = 00:00, Hora 24 = 23:00 ---
    df['hora_ajustada'] = df['hora'] - 1

    # --- Construir timestamp completo ---
    df['timestamp'] = df['fecha'] + pd.to_timedelta(df['hora_ajustada'], unit='h')

    # --- Eliminar filas con consumo nulo ---
    df = df.dropna(subset=['consumo_kwh'])
    df['consumo_kwh'] = df['consumo_kwh'].astype(float)

    # --- Nombres de días y meses en español ---
    dias_semana = {0: 'lunes', 1: 'martes', 2: 'miércoles', 3: 'jueves',
                   4: 'viernes', 5: 'sábado', 6: 'domingo'}
    meses = {1: 'enero', 2: 'febrero', 3: 'marzo', 4: 'abril',
             5: 'mayo', 6: 'junio', 7: 'julio', 8: 'agosto',
             9: 'septiembre', 10: 'octubre', 11: 'noviembre', 12: 'diciembre'}

    # --- Construir lista de HourlyRecord ---
    records = []
    for _, row in df.iterrows():
        ts = row['timestamp'].to_pydatetime()
        es_fin_semana = ts.weekday() >= 5
        es_festivo = ts.date() in festivos

        record = HourlyRecord(
            timestamp       = ts,
            hour            = int(row['hora']),
            day_of_month    = ts.day,
            day_of_week     = dias_semana[ts.weekday()],
            day_of_week_num = ts.weekday(),
            month           = ts.month,
            month_name      = meses[ts.month],
            is_weekend      = es_fin_semana,
            is_holiday      = es_festivo,
            consumption_kwh = round(float(row['consumo_kwh']), 4),
            energy_period   = get_energy_period(ts, festivos),
            power_period    = get_power_period(ts, festivos),
            exceeds_2kw     = float(row['consumo_kwh']) > 2.0
        )
        records.append(record)

    # Ordenar por timestamp
    records.sort(key=lambda x: x.timestamp)
    print(f"✅ CSV de consumo cargado: {len(records)} registros")
    return records


# =============================================================================
# FUNCIÓN 5 — LEER CSV DE POTENCIA MÁXIMA
# =============================================================================

def load_max_power_csv(filepath: str) -> list:
    """
    Lee el CSV de potencia máxima demandada y devuelve una lista de MonthlyMaxPower.

    Formato esperado del CSV:
        CUPS ; Mes/Ano ; Periodo ; kW ; Fecha ; Hora
        ES003140... ; ene-25 ; Punta ; 2,792 ; 22/01/2025 ; 21:30

    Args:
        filepath:  Ruta al CSV de potencia máxima

    Returns:
        Lista de MonthlyMaxPower
    """
    # --- Leer CSV ---
    df = pd.read_csv(
        filepath,
        sep=';',
        decimal=',',
        encoding='utf-8',
        skipinitialspace=True
    )

    # --- Limpiar columnas ---
    df.columns = df.columns.str.strip()

    # --- Renombrar columnas ---
    df = df.rename(columns={
        'CUPS':    'cups',
        'Mes/Ano': 'mes_ano',
        'Periodo': 'periodo',
        'kW':      'max_kw',
        'Fecha':   'fecha',
        'Hora':    'hora'
    })

    # --- Validaciones ---
    required_cols = ['cups', 'mes_ano', 'periodo', 'max_kw', 'fecha', 'hora']
    for col in required_cols:
        if col not in df.columns:
            raise ValueError(f"Columna '{col}' no encontrada en el CSV de potencia.")

    # --- Mapa de nombres de mes a número ---
    mes_map = {
        'ene': 1, 'feb': 2, 'mar': 3, 'abr': 4,
        'may': 5, 'jun': 6, 'jul': 7, 'ago': 8,
        'sep': 9, 'oct': 10, 'nov': 11, 'dic': 12
    }

    # --- Construir lista de MonthlyMaxPower ---
    max_power_records = []
    for _, row in df.iterrows():
        # Parsear mes y año desde formato "ene-25"
        partes = str(row['mes_ano']).split('-')
        mes_str = partes[0].lower()
        anio = 2000 + int(partes[1])
        mes_num = mes_map.get(mes_str, 1)

        # Construir datetime completo (fecha + hora)
        fecha_hora_str = f"{row['fecha']} {row['hora']}"
        try:
            fecha_hora = datetime.strptime(fecha_hora_str, '%d/%m/%Y %H:%M')
        except ValueError:
            fecha_hora = datetime.strptime(row['fecha'], '%d/%m/%Y')

        record = MonthlyMaxPower(
            month     = str(row['mes_ano']),
            month_num = mes_num,
            year      = anio,
            period    = str(row['periodo']),
            max_kw    = round(float(row['max_kw']), 4),
            date      = fecha_hora
        )
        max_power_records.append(record)

    print(f"✅ CSV de potencia máxima cargado: {len(max_power_records)} registros")
    return max_power_records


# =============================================================================
# FUNCIÓN PRINCIPAL — construye el objeto ElectricityAnalysis completo
# =============================================================================

def load_from_csv(
    consumption_filepath: str,
    max_power_filepath: str,
    client: ClientProfile,
    contract: Optional[ContractInfo] = None
) -> ElectricityAnalysis:
    """
    Función principal del loader. Lee los dos CSVs y devuelve
    un objeto ElectricityAnalysis listo para los motores de análisis.

    Args:
        consumption_filepath:  Ruta al CSV de consumo (ESTUDIO 2.0.csv)
        max_power_filepath:    Ruta al CSV de potencia máxima
        client:                Perfil del cliente (tipo, contrato, provincia)
        contract:              Datos del contrato (opcional)

    Returns:
        ElectricityAnalysis con hourly_records y monthly_max_power rellenos
    """
    print("🔄 Iniciando carga de datos...")

    # 1. Calcular años presentes en los datos para cargar festivos
    #    Leemos solo la columna de fechas para ser eficientes
    df_fechas = pd.read_csv(consumption_filepath, sep=';', usecols=[1],
                             header=0, encoding='utf-8')
    df_fechas.columns = ['fecha']
    df_fechas['fecha'] = pd.to_datetime(df_fechas['fecha'], format='%d/%m/%Y', errors='coerce')
    years = df_fechas['fecha'].dt.year.dropna().unique().tolist()
    years = [int(y) for y in years]

    # 2. Cargar festivos para la provincia del cliente
    print(f"📅 Cargando festivos para {client.province} — años: {years}")
    festivos = load_holidays(client.province, years)
    print(f"   {len(festivos)} días festivos encontrados")

    # 3. Leer CSV de consumo
    hourly_records = load_consumption_csv(consumption_filepath, festivos)

    # 4. Leer CSV de potencia máxima
    monthly_max_power = load_max_power_csv(max_power_filepath)

    # 5. Construir y devolver el objeto principal
    analysis = ElectricityAnalysis(
        client            = client,
        contract          = contract,
        hourly_records    = hourly_records,
        monthly_max_power = monthly_max_power,
        data_source       = DataSource.CSV,
        is_complete       = False
    )

    print(f"✅ ElectricityAnalysis creado correctamente")
    print(f"   Registros horarios:        {len(hourly_records)}")
    print(f"   Registros potencia máxima: {len(monthly_max_power)}")
    return analysis
