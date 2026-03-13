# =============================================================================
# src/validation/validator.py
# Validacion y normalizacion del objeto ElectricityAnalysis
# Version: 1.0
#
# Reglas generales:
#   - Si el sistema PUEDE corregir automaticamente -> lo corrige y avisa
#   - Si el sistema NO PUEDE corregir             -> avisa y continua
#   - Horas faltantes                             -> se dejan vacias y se avisa
# =============================================================================

from dataclasses import dataclass, field
from typing import Optional
from datetime import datetime, timedelta

import sys
sys.path.append('..')
from src.models.internal_data_model import ElectricityAnalysis, HourlyRecord


# =============================================================================
# RESULTADO DE LA VALIDACION
# =============================================================================

@dataclass
class ValidationResult:
    """
    Resultado completo de la validacion.
    Contiene el analisis corregido y todos los avisos generados.
    """
    is_valid:   bool
    analysis:   Optional[ElectricityAnalysis] = None

    # Correcciones aplicadas automaticamente
    corrections: list = field(default_factory=list)

    # Avisos - problemas detectados pero no bloqueantes
    warnings:    list = field(default_factory=list)

    # Errores - problemas que impiden continuar
    errors:      list = field(default_factory=list)

    def print_report(self):
        print("\n" + "="*60)
        print("INFORME DE VALIDACION")
        print("="*60)

        if self.corrections:
            print(f"\n CORRECCIONES APLICADAS ({len(self.corrections)}):")
            for c in self.corrections:
                print(f"   - {c}")

        if self.warnings:
            print(f"\n AVISOS ({len(self.warnings)}):")
            for w in self.warnings:
                print(f"   - {w}")

        if self.errors:
            print(f"\n ERRORES ({len(self.errors)}):")
            for e in self.errors:
                print(f"   - {e}")

        estado = "VALIDO - puede continuar" if self.is_valid else "NO VALIDO - revisar errores"
        print(f"\n{estado}")
        print("="*60)


# =============================================================================
# VALIDACIONES DEL CSV DE CONSUMO
# =============================================================================

def validate_consumption(records: list, result: ValidationResult) -> list:
    """
    Valida y corrige la lista de registros horarios de consumo.

    Comprobaciones:
        1. Consumo negativo          -> corrige a 0 y avisa
        2. Consumo anormalmente alto -> avisa (no corrige)
        3. Timestamps duplicados     -> elimina duplicados y avisa
        4. Horas faltantes           -> avisa, no rellena
    """
    if not records:
        result.errors.append("El CSV de consumo esta vacio.")
        return records

    # 1. Consumo negativo -> corregir a 0
    negativos = 0
    for r in records:
        if r.consumption_kwh < 0:
            r.consumption_kwh = 0.0
            negativos += 1

    if negativos > 0:
        result.corrections.append(
            f"{negativos} registros con consumo negativo corregidos a 0 kWh."
        )

    # 2. Consumo anormalmente alto -> avisar (umbral: 10 kWh/hora para hogar 2.0TD)
    UMBRAL_ALTO = 10.0
    altos = [r for r in records if r.consumption_kwh > UMBRAL_ALTO]
    if altos:
        result.warnings.append(
            f"{len(altos)} registros con consumo superior a {UMBRAL_ALTO} kWh/hora. "
            f"Maximo encontrado: {max(r.consumption_kwh for r in altos):.3f} kWh. "
            f"Revisa si son correctos."
        )

    # 3. Timestamps duplicados -> eliminar y avisar
    timestamps_vistos = {}
    records_limpios = []
    duplicados = 0

    for r in records:
        ts = r.timestamp
        if ts in timestamps_vistos:
            duplicados += 1
        else:
            timestamps_vistos[ts] = True
            records_limpios.append(r)

    if duplicados > 0:
        result.corrections.append(
            f"{duplicados} registros duplicados eliminados del CSV de consumo."
        )
        records = records_limpios

    # 4. Horas faltantes -> avisar (no rellenar)
    if len(records) >= 2:
        records_ord = sorted(records, key=lambda x: x.timestamp)
        ts_inicio = records_ord[0].timestamp
        ts_fin    = records_ord[-1].timestamp
        horas_esperadas = int((ts_fin - ts_inicio).total_seconds() / 3600) + 1
        horas_reales    = len(records_ord)
        horas_faltantes = horas_esperadas - horas_reales

        if horas_faltantes > 0:
            ts_set = {r.timestamp for r in records_ord}
            faltantes = []
            ts_actual = ts_inicio
            while ts_actual <= ts_fin:
                if ts_actual not in ts_set:
                    faltantes.append(ts_actual)
                ts_actual += timedelta(hours=1)

            muestra = ', '.join(str(f) for f in faltantes[:5])
            sufijo = f" (y {len(faltantes)-5} mas)" if len(faltantes) > 5 else ""
            result.warnings.append(
                f"{horas_faltantes} horas faltantes en el CSV de consumo. "
                f"Primeras: {muestra}{sufijo}. "
                f"Los calculos se haran con los datos disponibles."
            )
        elif horas_faltantes == 0:
            result.corrections.append(
                f"Secuencia horaria completa: {horas_reales} horas "
                f"del {ts_inicio.date()} al {ts_fin.date()}."
            )
        else:
            result.warnings.append(
                f"Mas registros de los esperados ({horas_reales} vs "
                f"{horas_esperadas} esperados). Revisa el archivo."
            )

    return records


# =============================================================================
# VALIDACIONES DEL CSV DE POTENCIA MAXIMA
# =============================================================================

def validate_max_power(monthly_max_power: list, result: ValidationResult) -> list:
    """
    Valida y corrige la lista de registros de potencia maxima mensual.

    Comprobaciones:
        1. Potencia negativa o nula    -> avisa
        2. Periodos desconocidos       -> avisa
        3. Meses duplicados            -> elimina duplicados y avisa
        4. Potencia anormalmente alta  -> avisa (umbral: 15 kW para 2.0TD)
    """
    if not monthly_max_power:
        result.warnings.append(
            "El CSV de potencia maxima esta vacio. "
            "No se podra hacer el analisis de potencia contratada."
        )
        return monthly_max_power

    PERIODOS_VALIDOS = {'Punta', 'Valle', 'Pot.Max'}
    UMBRAL_POTENCIA  = 15.0  # kW maximo esperado en contrato 2.0TD

    # 1. Potencia negativa o nula
    negativos = [r for r in monthly_max_power if r.max_kw <= 0]
    if negativos:
        result.warnings.append(
            f"{len(negativos)} registros de potencia con valor nulo o negativo. "
            f"Revisa el CSV de potencia maxima."
        )

    # 2. Periodos desconocidos
    desconocidos = [r for r in monthly_max_power if r.period not in PERIODOS_VALIDOS]
    if desconocidos:
        periodos_encontrados = list({r.period for r in desconocidos})
        result.warnings.append(
            f"{len(desconocidos)} registros con periodo desconocido: {periodos_encontrados}. "
            f"Periodos validos: {list(PERIODOS_VALIDOS)}."
        )

    # 3. Duplicados (mismo mes + mismo periodo)
    vistos = {}
    limpios = []
    duplicados = 0

    for r in monthly_max_power:
        clave = (r.month, r.period)
        if clave in vistos:
            duplicados += 1
        else:
            vistos[clave] = True
            limpios.append(r)

    if duplicados > 0:
        result.corrections.append(
            f"{duplicados} registros duplicados eliminados del CSV de potencia maxima."
        )
        monthly_max_power = limpios

    # 4. Potencia anormalmente alta
    altos = [r for r in monthly_max_power if r.max_kw > UMBRAL_POTENCIA]
    if altos:
        result.warnings.append(
            f"{len(altos)} registros de potencia maxima superan {UMBRAL_POTENCIA} kW. "
            f"Maximo encontrado: {max(r.max_kw for r in altos):.3f} kW. "
            f"Verifica si el contrato es realmente 2.0TD."
        )

    return monthly_max_power


# =============================================================================
# FUNCION PRINCIPAL
# =============================================================================

def validate(analysis: ElectricityAnalysis) -> ValidationResult:
    """
    Funcion principal de validacion.
    Recibe el ElectricityAnalysis tal como sale del loader
    y devuelve un ValidationResult con el analisis corregido.

    Ejemplo de uso:
        result = validate(analysis)
        result.print_report()

        if result.is_valid:
            analysis_limpio = result.analysis
            # continuar con los motores de analisis
    """
    print("Iniciando validacion de datos...")
    result = ValidationResult(is_valid=True, analysis=analysis)

    # Validar consumo horario
    analysis.hourly_records = validate_consumption(
        analysis.hourly_records, result
    )

    # Validar potencia maxima
    analysis.monthly_max_power = validate_max_power(
        analysis.monthly_max_power, result
    )

    # Si hay errores criticos -> marcar como no valido
    if result.errors:
        result.is_valid = False

    result.analysis = analysis
    print(f"Validacion completada.")
    return result
