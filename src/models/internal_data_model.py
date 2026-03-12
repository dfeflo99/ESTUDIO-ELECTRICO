# =============================================================================
# src/models/internal_data_model.py
# Modelo interno central del sistema de análisis eléctrico
# Versión: 1.0
# =============================================================================

from dataclasses import dataclass, field
from datetime import datetime
from typing import Optional
from enum import Enum


# =============================================================================
# ENUMS
# =============================================================================

class ClientType(Enum):
    DOMESTIC = "domestic"       # Hogar
    BUSINESS = "business"       # Pyme

class ContractType(Enum):
    TD_2_0 = "2.0TD"            # Doméstico — hasta 15kW
    TD_3_0 = "3.0TD"            # Pyme — más de 15kW

class DataSource(Enum):
    CSV    = "csv"              # Datos cargados desde CSV
    OCR    = "ocr"              # Datos extraídos de factura por OCR
    MANUAL = "manual"           # Datos introducidos manualmente por el usuario

class EnergyPeriod(Enum):
    """
    Periodos para el coste de ENERGÍA (consumo) en tarifa 2.0TD.
    Dependen de hora, día de la semana y festivos.
    - P1 Punta:  Lunes-Viernes 10h-14h y 18h-22h
    - P2 Llano:  Lunes-Viernes 8h-10h, 14h-18h, 22h-24h
    - P3 Valle:  Lunes-Viernes 0h-8h + sábados, domingos y festivos (todo el día)
    """
    P1 = "P1"   # Punta
    P2 = "P2"   # Llano
    P3 = "P3"   # Valle

class PowerPeriod(Enum):
    """
    Periodos para el coste de POTENCIA (maxímetro) en tarifa 2.0TD.
    - P1: Lunes-Viernes 8h-24h (no festivos)
    - P2: Lunes-Viernes 0h-8h + sábados, domingos y festivos (todo el día)
    Nota: los festivos dependen de la provincia del cliente.
    Se calculan usando la librería `holidays` con la comunidad autónoma correspondiente.
    """
    P1 = "P1"
    P2 = "P2"


# =============================================================================
# BLOQUE 1 — PERFIL DEL CLIENTE
# =============================================================================

@dataclass
class ClientProfile:
    client_type:   ClientType
    contract_type: ContractType
    province:      str              # Provincia (determina festivos autonómicos)
    name:          Optional[str] = None
    email:         Optional[str] = None


# =============================================================================
# BLOQUE 2 — INFORMACIÓN DEL CONTRATO
# =============================================================================

@dataclass
class ContractedPowers:
    """Potencias contratadas por periodo (en kW). En 2.0TD son 2 periodos."""
    p1: float                       # kW contratados en P1
    p2: float                       # kW contratados en P2

@dataclass
class ContractInfo:
    cups:              Optional[str]            # Código universal del punto de suministro
    distributor:       Optional[str]            # Distribuidora (Iberdrola, Endesa...)
    marketer:          Optional[str]            # Comercializadora actual
    contracted_powers: ContractedPowers
    meter_rental:      Optional[float] = None   # Alquiler del contador (€/mes)


# =============================================================================
# BLOQUE 3 — REGISTRO HORARIO (unidad básica de datos)
# =============================================================================

@dataclass
class HourlyRecord:
    """
    Un registro de consumo por hora.
    Es la unidad mínima de datos del sistema.
    Todos los análisis y gráficos se construyen a partir de estos registros.
    """
    # Identificación temporal
    timestamp:        datetime          # Fecha y hora exacta
    hour:             int               # Hora del día (1-24)
    day_of_month:     int               # Día del mes (1-31)
    day_of_week:      str               # Nombre del día (lunes, martes...)
    day_of_week_num:  int               # Número del día (0=lunes, 6=domingo)
    month:            int               # Número del mes (1-12)
    month_name:       str               # Nombre del mes (enero, febrero...)
    is_weekend:       bool              # True si es sábado o domingo
    is_holiday:       bool              # True si es festivo (nacional o autonómico)

    # Consumo
    consumption_kwh:  float             # Consumo en kWh (AE_kWh en Power BI)

    # Periodos (calculados a partir de timestamp + festivos)
    energy_period:    EnergyPeriod      # P1/P2/P3 — para coste de energía
    power_period:     PowerPeriod       # P1/P2    — para coste de potencia

    # Flags de análisis
    exceeds_2kw:      bool = False      # True si consumption_kwh > 2 (Supera_2kW_flag)


# =============================================================================
# BLOQUE 4 — DATOS DE POTENCIA MÁXIMA (del CSV de potencia)
# =============================================================================

@dataclass
class MonthlyMaxPower:
    """
    Potencia máxima registrada por periodo y mes.
    Viene del CSV 'Potencia máxima demandada'.
    """
    month:          str             # Formato "ene-25", "feb-25"...
    month_num:      int             # Número del mes
    year:           int
    period:         str             # "Punta", "Valle", "Pot.Max"
    max_kw:         float           # Potencia máxima registrada (kW)
    date:           datetime        # Fecha y hora exacta del pico


# =============================================================================
# BLOQUE 5 — RESÚMENES DE CONSUMO (para gráficos y KPIs)
# =============================================================================

@dataclass
class PeriodConsumptionSummary:
    """Resumen de consumo por periodo energético."""
    period:             EnergyPeriod
    total_kwh:          float
    avg_kwh_per_hour:   float
    pct_of_total:       float           # % del consumo total

@dataclass
class ConsumptionSummary:
    """
    Resumen global del consumo.
    Alimenta los KPIs y gráficos de la página 'Perfil de consumo general'.
    """
    # KPIs principales
    total_kwh:              float       # Consumo Total
    avg_daily_kwh:          float       # Consumo_Promedio_Diario
    avg_hourly_kwh:         float       # Consumo_Promedio_Hora

    # Rango temporal
    date_from:              datetime
    date_to:                datetime
    total_days:             int

    # Agregaciones para gráficos
    by_month:               dict        # {mes: total_kwh} → gráfico por mes
    by_hour:                dict        # {hora: total_kwh} → gráfico por hora
    by_day_of_week:         dict        # {dia: total_kwh} → gráfico por día semana
    by_day_of_month:        dict        # {dia_mes: total_kwh} → gráfico por día mes
    by_hour_and_date:       dict        # {fecha+hora: kwh} → gráfico detallado

    # Por periodo energético
    by_energy_period:       dict        # {"P1": PeriodConsumptionSummary, ...}


# =============================================================================
# BLOQUE 6 — ANÁLISIS DE POTENCIA (para gráficos y KPIs de potencia)
# =============================================================================

@dataclass
class PowerAnalysis:
    """
    Resultado del análisis de potencia real y contratada.
    Alimenta la página 'Perfil de potencia real' y 'Optimización de potencia contratada'.
    """
    # KPIs principales
    max_power_kw:               float       # Máx. de Potencia
    p99_power_kw:               float       # P99 (percentil 99 de potencia)
    load_factor:                float       # Factor_Carga = AVERAGE / MAX
    hours_exceeds_2kw:          int         # Horas_Supera_2kW
    pct_exceeds_2kw:            float       # Porcentaje_Supera_2kW

    # Potencia diaria (para gráfico línea día a día)
    daily_max_power:            dict        # {fecha: max_kw} → gráfico potencia diaria

    # Heatmap hora x día del mes (para tabla con colores)
    hourly_power_heatmap:       dict        # {(hora, dia_mes): kwh}

    # Ranking de potencia (para curva de ranking)
    power_ranking:              list        # Lista ordenada de mayor a menor potencia

    # Registros que superan 2kW (para tabla 'Análisis de picos críticos')
    records_exceeding_2kw:      list        # Lista de HourlyRecord con exceeds_2kw=True

    # Potencias contratadas actuales (interactivo — puede cambiar)
    contracted_powers:          ContractedPowers

    # Excesos sobre potencia contratada
    hours_exceeds_p1:           int         # Horas_Supera_P1_Contratada
    hours_exceeds_p2:           int         # Horas_Supera_P2_Contratada
    records_exceeding_p1:       list        # Registros con Exceso_P1 > 0
    records_exceeding_p2:       list        # Registros con Exceso_P2 > 0

    # Recomendación del sistema
    recommended_p1_kw:          float       # Potencia P1 recomendada
    recommended_p2_kw:          float       # Potencia P2 recomendada
    has_excess_contracted:      bool        # Tiene potencia contratada de más
    has_deficit_contracted:     bool        # Ha tenido excesos (maxímetro disparado)
    observations:               list        # Textos explicativos para el usuario


# =============================================================================
# BLOQUE 7 — SIMULACIÓN DE COSTES (para página de costes y comparativa)
# =============================================================================

@dataclass
class CostSimulation:
    """
    Simulación del coste con una tarifa concreta.
    Puede usarse para la tarifa actual o para comparar con otras ofertas.
    Los precios de energía vienen del Excel de comercializadoras o de ESIOS (PVPC).
    """
    # Identificación de la oferta
    marketer_name:          str
    offer_name:             str
    is_indexed:             bool        # True si es tarifa indexada (PVPC o similar)

    # Precios de energía (€/kWh por periodo)
    price_p1_kwh:           float
    price_p2_kwh:           float
    price_p3_kwh:           float

    # Precios de potencia (€/kW/día por periodo)
    price_power_p1_day:     float
    price_power_p2_day:     float

    # Costes calculados
    energy_cost:            float       # Coste_Energia
    power_cost:             float       # Coste_Potencia
    meter_rental:           float       # Alquiler_Contador
    electric_tax:           float       # Impuesto_Electrico (5,11273% sobre subtotal)
    vat:                    float       # IVA (21%)
    tax_base:               float       # Base_Imponible
    total_simulated_cost:   float       # Coste_Total_Simulado

    # Para comparativa
    saving_vs_current:      float       # Ahorro respecto a tarifa actual (€)
    saving_pct:             float       # Ahorro en porcentaje


@dataclass
class ComparisonReport:
    """Comparativa de todas las ofertas disponibles."""
    current_cost:           Optional[float]     # Coste real de la última factura
    simulations:            list                # Lista de CostSimulation ordenada por ahorro
    best_offer:             Optional[str]       # Nombre de la mejor oferta


# =============================================================================
# MODELO PRINCIPAL — punto de entrada y salida de todos los motores
# =============================================================================

@dataclass
class ElectricityAnalysis:
    """
    Modelo interno central.

    TODOS los caminos de entrada generan este objeto:
        CSV  → excel_loader.py    → ElectricityAnalysis
        OCR  → invoice_ocr.py     → ElectricityAnalysis
        Form → manual_input.py    → ElectricityAnalysis

    TODOS los motores trabajan sobre este objeto:
        consumption_engine.py → rellena consumption_summary
        power_engine.py       → rellena power_analysis
        comparator.py         → rellena comparison_report
    """
    # Datos de entrada (obligatorios)
    client:             ClientProfile
    contract:           Optional[ContractInfo]
    hourly_records:     list                    # Lista de HourlyRecord
    monthly_max_power:  list                    # Lista de MonthlyMaxPower

    # Resultados de los motores (se rellenan progresivamente)
    consumption_summary:    Optional[ConsumptionSummary]    = None
    power_analysis:         Optional[PowerAnalysis]         = None
    comparison_report:      Optional[ComparisonReport]      = None

    # Metadatos
    data_source:    DataSource  = DataSource.CSV
    created_at:     datetime    = field(default_factory=datetime.now)
    is_complete:    bool        = False     # True cuando todos los análisis están hechos
