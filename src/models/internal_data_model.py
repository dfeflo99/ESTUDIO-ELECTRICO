# =============================================================================
# src/models/internal_data_model.py
# Modelo interno central del sistema de análisis eléctrico
# Versión: 2.0
# Compatible con 2.0TD + 3.0TD
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
    Periodos de energía.
    2.0TD usa normalmente P1/P2/P3.
    3.0TD usa P1/P2/P3/P4/P5/P6.
    """
    P1 = "P1"
    P2 = "P2"
    P3 = "P3"
    P4 = "P4"
    P5 = "P5"
    P6 = "P6"


class PowerPeriod(Enum):
    """
    Periodos de potencia.
    2.0TD usa normalmente P1/P2.
    3.0TD usa P1/P2/P3/P4/P5/P6.
    """
    P1 = "P1"
    P2 = "P2"
    P3 = "P3"
    P4 = "P4"
    P5 = "P5"
    P6 = "P6"


# =============================================================================
# BLOQUE 1 — PERFIL DEL CLIENTE
# =============================================================================

@dataclass
class ClientProfile:
    client_type:   ClientType
    contract_type: ContractType
    province:      str
    name:          Optional[str] = None
    email:         Optional[str] = None


# =============================================================================
# BLOQUE 2 — INFORMACIÓN DEL CONTRATO
# =============================================================================

@dataclass
class ContractedPowers:
    """
    Potencias contratadas por periodo (kW).

    Compatibilidad:
    - 2.0TD: usa p1 y p2
    - 3.0TD: usa p1..p6
    """
    p1: float = 0.0
    p2: float = 0.0
    p3: float = 0.0
    p4: float = 0.0
    p5: float = 0.0
    p6: float = 0.0

    def as_dict(self) -> dict:
        return {
            "P1": self.p1,
            "P2": self.p2,
            "P3": self.p3,
            "P4": self.p4,
            "P5": self.p5,
            "P6": self.p6,
        }

    def active_periods(self, contract_type: Optional[ContractType] = None) -> dict:
        if contract_type == ContractType.TD_2_0:
            return {"P1": self.p1, "P2": self.p2}
        if contract_type == ContractType.TD_3_0:
            return self.as_dict()

        # Si no se indica contrato, devolvemos solo los periodos con valor > 0
        data = self.as_dict()
        activos = {k: v for k, v in data.items() if v not in (None, 0)}
        return activos if activos else {"P1": self.p1, "P2": self.p2}


@dataclass
class ContractInfo:
    cups:              Optional[str]
    distributor:       Optional[str]
    marketer:          Optional[str]
    contracted_powers: ContractedPowers
    meter_rental:      Optional[float] = None


# =============================================================================
# BLOQUE 3 — REGISTRO HORARIO
# =============================================================================

@dataclass
class HourlyRecord:
    """
    Registro horario base del sistema.

    Compatibilidad:
    - 2.0TD:
        * hora origen habitual: 1-24
        * consumo principal: consumption_kwh
        * periodos: energía P1/P2/P3, potencia P1/P2
    - 3.0TD:
        * hora origen habitual: 0-23
        * si aparece 24 se normalizará en el loader
        * energía P1..P6
        * potencia P1..P6
        * campos extra opcionales: exportación, autoconsumo, reactiva, estimado
    """
    # Identificación temporal
    timestamp:        datetime
    hour:             int               # Hora normalizada para análisis (0-23)
    day_of_month:     int
    day_of_week:      str
    day_of_week_num:  int               # 0=lunes, 6=domingo
    month:            int
    month_name:       str
    is_weekend:       bool
    is_holiday:       bool

    # Consumo principal
    consumption_kwh:  float             # Energía activa importada

    # Periodos calculados
    energy_period:    EnergyPeriod
    power_period:     PowerPeriod

    # Flags de análisis
    exceeds_2kw:      bool = False

    # Metadatos opcionales del CSV
    source_hour_raw:          Optional[int] = None   # Hora original tal como venía en el CSV
    is_estimated:            Optional[bool] = None   # REAL/ESTIMADO -> True si estimado
    real_or_estimated:       Optional[str] = None    # "R" / "E"

    # Campos opcionales 3.0TD
    export_kwh:              float = 0.0            # AS_KWh
    self_consumption_kwh:    float = 0.0            # AE_AUTOCONS_kWh
    reactive_r1_kvarh:       float = 0.0
    reactive_r2_kvarh:       float = 0.0
    reactive_r3_kvarh:       float = 0.0
    reactive_r4_kvarh:       float = 0.0


# =============================================================================
# BLOQUE 4 — POTENCIA MÁXIMA MENSUAL
# =============================================================================

@dataclass
class MonthlyMaxPower:
    """
    Potencia máxima registrada por periodo y mes.

    Compatibilidad:
    - 2.0TD: period puede venir como "Punta", "Valle", "Pot.Max"
    - 3.0TD: period puede venir como "P1".."P6" o "Pot.Max"
    """
    month:          str
    month_num:      int
    year:           int
    period:         str
    max_kw:         float
    date:           datetime


# =============================================================================
# BLOQUE 5 — RESÚMENES DE CONSUMO
# =============================================================================

@dataclass
class PeriodConsumptionSummary:
    period:             EnergyPeriod
    total_kwh:          float
    avg_kwh_per_hour:   float
    pct_of_total:       float


@dataclass
class ConsumptionSummary:
    # KPIs principales
    total_kwh:              float
    avg_daily_kwh:          float
    avg_hourly_kwh:         float

    # Rango temporal
    date_from:              datetime
    date_to:                datetime
    total_days:             int

    # Agregaciones para gráficos
    by_month:               dict
    by_hour:                dict
    by_day_of_week:         dict
    by_day_of_month:        dict
    by_hour_and_date:       dict

    # Por periodo energético
    by_energy_period:       dict


# =============================================================================
# BLOQUE 6 — ANÁLISIS DE POTENCIA
# =============================================================================

@dataclass
class PowerAnalysis:
    # KPIs principales
    max_power_kw:               float
    p99_power_kw:               float
    load_factor:                float
    hours_exceeds_2kw:          int
    pct_exceeds_2kw:            float

    # Potencia diaria
    daily_max_power:            dict

    # Heatmap hora x día
    hourly_power_heatmap:       dict

    # Ranking
    power_ranking:              list

    # Registros que superan umbral
    records_exceeding_2kw:      list

    # Potencias contratadas actuales
    contracted_powers:          ContractedPowers

    # Excesos sobre potencia contratada
    hours_exceeds_p1:           int
    hours_exceeds_p2:           int
    records_exceeding_p1:       list
    records_exceeding_p2:       list

    # Recomendación del sistema
    recommended_p1_kw:          float
    recommended_p2_kw:          float
    has_excess_contracted:      bool
    has_deficit_contracted:     bool
    observations:               list

    # Campos extra opcionales para futuro 3.0TD
    hours_exceeds_p3:           int = 0
    hours_exceeds_p4:           int = 0
    hours_exceeds_p5:           int = 0
    hours_exceeds_p6:           int = 0
    records_exceeding_p3:       list = field(default_factory=list)
    records_exceeding_p4:       list = field(default_factory=list)
    records_exceeding_p5:       list = field(default_factory=list)
    records_exceeding_p6:       list = field(default_factory=list)
    recommended_p3_kw:          float = 0.0
    recommended_p4_kw:          float = 0.0
    recommended_p5_kw:          float = 0.0
    recommended_p6_kw:          float = 0.0


# =============================================================================
# BLOQUE 7 — SIMULACIÓN DE COSTES
# =============================================================================

@dataclass
class CostSimulation:
    # Identificación de la oferta
    marketer_name:          str
    offer_name:             str
    is_indexed:             bool

    # Precios de energía (€/kWh por periodo)
    price_p1_kwh:           float
    price_p2_kwh:           float
    price_p3_kwh:           float
    price_p4_kwh:           float = 0.0
    price_p5_kwh:           float = 0.0
    price_p6_kwh:           float = 0.0

    # Precios de potencia (€/kW/día por periodo)
    price_power_p1_day:     float = 0.0
    price_power_p2_day:     float = 0.0
    price_power_p3_day:     float = 0.0
    price_power_p4_day:     float = 0.0
    price_power_p5_day:     float = 0.0
    price_power_p6_day:     float = 0.0

    # Costes calculados
    energy_cost:            float = 0.0
    power_cost:             float = 0.0
    meter_rental:           float = 0.0
    electric_tax:           float = 0.0
    vat:                    float = 0.0
    tax_base:               float = 0.0
    total_simulated_cost:   float = 0.0

    # Para comparativa
    saving_vs_current:      float = 0.0
    saving_pct:             float = 0.0


@dataclass
class ComparisonReport:
    current_cost:           Optional[float]
    simulations:            list
    best_offer:             Optional[str]


# =============================================================================
# MODELO PRINCIPAL
# =============================================================================

@dataclass
class ElectricityAnalysis:
    """
    Modelo interno central del sistema.

    CSV  -> excel_loader.py  -> ElectricityAnalysis
    OCR  -> invoice_ocr.py   -> ElectricityAnalysis
    Form -> manual_input.py  -> ElectricityAnalysis
    """
    # Datos de entrada
    client:             ClientProfile
    contract:           Optional[ContractInfo]
    hourly_records:     list
    monthly_max_power:  list

    # Resultados de motores
    consumption_summary:    Optional[ConsumptionSummary] = None
    power_analysis:         Optional[PowerAnalysis] = None
    comparison_report:      Optional[ComparisonReport] = None

    # Metadatos
    data_source:    DataSource = DataSource.CSV
    created_at:     datetime = field(default_factory=datetime.now)
    is_complete:    bool = False
