"""
calculators/aportaciones.py
Calcula las aportaciones mensuales al IMSS (RCV) para un trabajador.

Lógica:
  - Cuota retiro (2%): siempre fija, la paga el patrón
  - Cuota trabajador (1.125%): fija
  - Cuota cesantía y vejez: varía por año Y por bracket salarial (2do/3er transitorio)
  - Cuota social: aportación del gobierno, solo para SBC <= 1 UMA mensual
  - Salario máximo cotizable: 25 UMAs mensuales
"""

from config import (
    CUOTAS_FIJAS,
    CUOTAS_CESANTIA_VEJEZ,
    CUOTA_CESANTIA_VEJEZ_FINAL,
    FACTOR_SALARIO_MAXIMO_COTIZABLE,
)
from data_fetchers.uma import get_uma_mensual


# ─────────────────────────────────────────────────────────────────────────────
# HELPERS
# ─────────────────────────────────────────────────────────────────────────────

def salario_cotizable(sbc_mensual: float, anio: int) -> float:
    """
    Retorna el SBC efectivo para cotizar al IMSS (topado a 25 UMAs mensuales).
    """
    uma_mensual = get_uma_mensual(anio)
    tope = FACTOR_SALARIO_MAXIMO_COTIZABLE * uma_mensual
    return min(sbc_mensual, tope)


def get_bracket_cesantia(sbc_mensual: float, anio: int) -> str:
    """
    Determina el bracket salarial para la cuota de cesantía y vejez.
    Los brackets están definidos en múltiplos de UMA mensual.

    Returns:
        Key del bracket (ej: "1SM", "1.01-1.50", "4.01+")
    """
    uma_mensual = get_uma_mensual(anio)
    uma_diaria  = uma_mensual / 30.4  # aprox días mes

    # El bracket "1SM" se define como hasta 1 salario mínimo (≈ 1 UMA en 2016+)
    # En la práctica, para LSS se usa la UMA como referencia desde 2017
    ratio = sbc_mensual / uma_mensual if uma_mensual > 0 else 0

    if ratio <= 1.0:
        return "1SM"
    elif ratio <= 1.50:
        return "1.01-1.50"
    elif ratio <= 2.00:
        return "1.51-2.00"
    elif ratio <= 2.50:
        return "2.01-2.50"
    elif ratio <= 3.00:
        return "2.51-3.00"
    elif ratio <= 3.50:
        return "3.01-3.50"
    elif ratio <= 4.00:
        return "3.51-4.00"
    else:
        return "4.01+"


def get_tasa_cesantia_vejez(sbc_mensual: float, anio: int) -> float:
    """
    Retorna la tasa patronal de cesantía y vejez según el año y bracket salarial.
    Para años fuera del período de transición (> 2030), usa la tasa final.
    """
    bracket = get_bracket_cesantia(sbc_mensual, anio)

    if anio in CUOTAS_CESANTIA_VEJEZ:
        return CUOTAS_CESANTIA_VEJEZ[anio][bracket]
    elif anio > 2030:
        return CUOTA_CESANTIA_VEJEZ_FINAL[bracket]
    else:
        # Año anterior a la tabla (pre-2023): tasa fija histórica
        return 0.0315


def cuota_social(sbc_mensual: float, anio: int) -> float:
    """
    Calcula la cuota social que aporta el gobierno.
    Solo aplica cuando el SBC es <= 1 UMA mensual.
    El monto es fijo por UMA y se actualiza anualmente.

    Referencia: Art. 168 LSS — cuota social = 5.5% de 1 SMGDF de 1997
    actualizado por inflación. En la práctica el Excel lo muestra como 0
    para SBC > 1 UMA, y un monto pequeño para SBC ≤ 1 UMA.
    """
    uma_mensual = get_uma_mensual(anio)
    if sbc_mensual > uma_mensual:
        return 0.0

    # Cuota social base 1997 actualizada (aprox 5.5% de 1 SM 1997 × factores INPC)
    # En el Excel fuente aparece como 0 para el caso de análisis (SBC=30,000)
    # Para SBC <= 1 UMA, estimamos como 11.9% del SBC (aprox histórico)
    return sbc_mensual * 0.119


# ─────────────────────────────────────────────────────────────────────────────
# FUNCIÓN PRINCIPAL
# ─────────────────────────────────────────────────────────────────────────────

def calcular_aportaciones(sbc_mensual: float, anio: int) -> dict:
    """
    Calcula el desglose completo de aportaciones mensuales al RCV-IMSS.

    Args:
        sbc_mensual: Salario Base de Cotización mensual (pesos corrientes)
        anio:        Año de cálculo

    Returns:
        {
          "sbc_original":        float,  # SBC ingresado
          "sbc_cotizable":       float,  # SBC topado a 25 UMAs
          "uma_mensual":         float,
          "bracket":             str,    # Bracket salarial
          "tasa_retiro":         float,  # 2% (patrón)
          "tasa_trabajador":     float,  # 1.125% (trabajador)
          "tasa_cesantia_vejez": float,  # Variable por año y bracket
          "tasa_total_patronal": float,  # retiro + cesantia
          "tasa_total":          float,  # todas las cuotas
          "cuota_retiro":        float,  # $
          "cuota_trabajador":    float,  # $
          "cuota_cesantia_vejez":float,  # $
          "cuota_social":        float,  # $ (gobierno)
          "aportacion_total":    float,  # $ total al AFORE
          "aportacion_patronal": float,  # $ patrón (retiro + cesantia)
        }
    """
    sbc_cot   = salario_cotizable(sbc_mensual, anio)
    uma_mens  = get_uma_mensual(anio)
    bracket   = get_bracket_cesantia(sbc_cot, anio)

    tasa_retiro   = CUOTAS_FIJAS["retiro"]           # 2%
    tasa_trab     = CUOTAS_FIJAS["trabajador"]       # 1.125%
    tasa_ces_vej  = get_tasa_cesantia_vejez(sbc_cot, anio)

    cuota_ret     = sbc_cot * tasa_retiro
    cuota_trab    = sbc_cot * tasa_trab
    cuota_ces_vej = sbc_cot * tasa_ces_vej
    cuota_soc     = cuota_social(sbc_mensual, anio)

    aportacion_patronal = cuota_ret + cuota_ces_vej
    aportacion_total    = aportacion_patronal + cuota_trab + cuota_soc

    return {
        "sbc_original":         sbc_mensual,
        "sbc_cotizable":        sbc_cot,
        "uma_mensual":          uma_mens,
        "bracket":              bracket,
        "tasa_retiro":          tasa_retiro,
        "tasa_trabajador":      tasa_trab,
        "tasa_cesantia_vejez":  tasa_ces_vej,
        "tasa_total_patronal":  tasa_retiro + tasa_ces_vej,
        "tasa_total":           tasa_retiro + tasa_trab + tasa_ces_vej,
        "cuota_retiro":         cuota_ret,
        "cuota_trabajador":     cuota_trab,
        "cuota_cesantia_vejez": cuota_ces_vej,
        "cuota_social":         cuota_soc,
        "aportacion_patronal":  aportacion_patronal,
        "aportacion_total":     aportacion_total,
    }


def aportacion_mensual_total(sbc_mensual: float, anio: int) -> float:
    """Atajo: retorna solo el monto total mensual que entra al AFORE."""
    return calcular_aportaciones(sbc_mensual, anio)["aportacion_total"]


def proyectar_sbc(sbc_base: float, anio_base: int, anio_objetivo: int,
                  tasa_crecimiento: float) -> float:
    """
    Proyecta el SBC de un año base a un año objetivo
    usando una tasa de crecimiento anual compuesta.

    Args:
        sbc_base:         SBC en el año base (pesos corrientes)
        anio_base:        Año del SBC base
        anio_objetivo:    Año al que se quiere proyectar
        tasa_crecimiento: Tasa anual de crecimiento (ej: 0.062 = 6.2%)

    Returns:
        SBC proyectado en pesos corrientes del año objetivo
    """
    annos = anio_objetivo - anio_base
    if annos <= 0:
        return sbc_base
    return sbc_base * (1 + tasa_crecimiento) ** annos
