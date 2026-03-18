"""
calculators/pension.py
Calcula la pensión bajo los distintos esquemas de la LSS 1997.

Esquemas:
  1. RCV (Retiro, Cesantía y Vejez): pensión financiada con saldo del AFORE
     mediante una anualidad vitalicia (renta vitalicia) o retiro programado.

  2. PMG (Pensión Mínima Garantizada, Art. 170 LSS):
     El Estado garantiza un mínimo si el saldo del AFORE no alcanza.
     El monto depende del SBC promedio, edad y semanas cotizadas.

  3. 4to Transitorio: para trabajadores que cotizaron antes del 1ro julio 1997,
     pueden elegir entre el régimen 1973 o el 1997.

La pensión final es: max(RCV, PMG) si aplica PMG; de lo contrario solo RCV.
"""

import sys, os
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from datetime import date
from typing import Optional

from config import (
    SEMANAS_MINIMAS_RCV,
    SEMANAS_4TO_TRANSITORIO,
    SEMANAS_4TO_TRANSITORIO_FINAL,
    PMG_BASE_2025,
    TASA_INTERES_TECNICO,
)
from data_fetchers.uma    import get_uma_mensual
from calculators.anualidades import (
    pension_desde_saldo,
    saldo_requerido_para_pension,
    get_ax,
    ax_conjunto,
)


# ─────────────────────────────────────────────────────────────────────────────
# HELPERS
# ─────────────────────────────────────────────────────────────────────────────

def semanas_requeridas(anio_retiro: int, cotizo_antes_1997: bool = False) -> int:
    """
    Semanas mínimas para pensionarse.
    - Post-1997: siempre 1,000 (SEMANAS_4TO_TRANSITORIO_FINAL).
    - Pre-1997:  esquema transitorio 2021-2030 (4to Transitorio), luego 1,000.
    """
    if cotizo_antes_1997 and anio_retiro in SEMANAS_4TO_TRANSITORIO:
        return SEMANAS_4TO_TRANSITORIO[anio_retiro]
    return SEMANAS_4TO_TRANSITORIO_FINAL


def cumple_requisitos(semanas_cotizadas: int, anio_retiro: int,
                      cotizo_antes_1997: bool = False) -> bool:
    """Verifica si el trabajador cumple el mínimo de semanas para pensionarse."""
    return semanas_cotizadas >= semanas_requeridas(anio_retiro, cotizo_antes_1997)


def _bracket_pmg(sbc_mensual: float, uma_mensual: float) -> Optional[str]:
    """Determina el bracket salarial para la PMG."""
    ratio = sbc_mensual / uma_mensual if uma_mensual > 0 else 0
    if ratio < 1.0:
        return "1SM-1.99UMA"   # menor a 1 UMA, aplica bracket mínimo
    elif ratio < 2.0:
        return "1SM-1.99UMA"
    elif ratio < 3.0:
        return "2-2.99UMA"
    elif ratio < 4.0:
        return "3-3.99UMA"
    elif ratio < 5.0:
        return "4-4.99UMA"
    else:
        return None            # > 5 UMAs no aplica PMG


def _semanas_pmg_key(semanas: int) -> int:
    """Encuentra la clave de semanas más cercana (por abajo) en la tabla PMG."""
    claves = sorted([1000, 1025, 1050, 1075, 1100, 1125, 1150, 1175, 1200, 1225, 1250])
    for c in reversed(claves):
        if semanas >= c:
            return c
    return 1000  # mínimo


# ─────────────────────────────────────────────────────────────────────────────
# PMG — PENSIÓN MÍNIMA GARANTIZADA
# ─────────────────────────────────────────────────────────────────────────────

def calcular_pmg(
    sbc_promedio:      float,
    edad_retiro:       int,
    semanas_cotizadas: int,
    anio_retiro:       int,
    anio_referencia:   int  = 2025,
    cotizo_antes_1997: bool = False,
) -> dict:
    """
    Calcula la Pensión Mínima Garantizada (Art. 170 LSS reforma 2020).

    La PMG se expresa en pesos de 2025 y se actualiza con INPC al año de retiro.
    Se estima la actualización INPC usando el crecimiento de la UMA.

    Args:
        sbc_promedio:      SBC promedio de toda la vida laboral (pesos del anio_retiro)
        edad_retiro:       Edad al momento del retiro (60–65)
        semanas_cotizadas: Semanas totales cotizadas al IMSS
        anio_retiro:       Año en que se pensiona
        anio_referencia:   Año base de la tabla PMG (2025)

    Returns:
        {
          "aplica":         bool,
          "monto_mensual":  float,   # pesos del año de retiro
          "bracket":        str,
          "semanas_key":    int,
          "factor_actualizacion": float,
        }
    """
    uma_retiro = get_uma_mensual(anio_retiro)
    uma_ref    = get_uma_mensual(anio_referencia)

    bracket = _bracket_pmg(sbc_promedio, uma_retiro)

    # Verificar si aplica PMG
    edad_ok    = 60 <= edad_retiro <= 65
    semanas_ok = semanas_cotizadas >= semanas_requeridas(anio_retiro, cotizo_antes_1997)

    if not edad_ok or not semanas_ok or bracket is None:
        return {
            "aplica":               False,
            "monto_mensual":        0.0,
            "bracket":              bracket or "N/A",
            "semanas_key":          semanas_cotizadas,
            "factor_actualizacion": 0.0,
            "razon_no_aplica": (
                "edad fuera de rango (60-65)" if not edad_ok
                else f"semanas insuficientes ({semanas_cotizadas} < {semanas_requeridas(anio_retiro, cotizo_antes_1997)})"
                if not semanas_ok
                else "SBC supera 5 UMAs"
            ),
        }

    tabla_bracket = PMG_BASE_2025.get(bracket, {})
    tabla_edad    = tabla_bracket.get(edad_retiro, {})

    if not tabla_edad:
        return {"aplica": False, "monto_mensual": 0.0, "bracket": bracket,
                "semanas_key": semanas_cotizadas, "factor_actualizacion": 0.0}

    semanas_key  = _semanas_pmg_key(semanas_cotizadas)
    monto_base   = tabla_edad.get(semanas_key, 0.0)

    # Actualizar con crecimiento UMA (proxy INPC)
    factor_act   = (uma_retiro / uma_ref) if uma_ref > 0 else 1.0
    monto_actual = monto_base * factor_act

    return {
        "aplica":               True,
        "monto_mensual":        monto_actual,
        "monto_base_2025":      monto_base,
        "bracket":              bracket,
        "semanas_key":          semanas_key,
        "factor_actualizacion": factor_act,
    }


# ─────────────────────────────────────────────────────────────────────────────
# RCV — PENSIÓN POR SALDO AFORE
# ─────────────────────────────────────────────────────────────────────────────

def calcular_pension_rcv(
    saldo_afore:       float,
    genero:            int,
    edad_retiro:       int,
    semanas_cotizadas: int,
    anio_retiro:       int,
    casado:            int   = 0,
    genero_conyuge:    int   = 0,
    edad_conyuge:      int   = 0,
    tasa_interes:      float = TASA_INTERES_TECNICO,
    cotizo_antes_1997: bool  = False,
) -> dict:
    """
    Calcula la pensión mensual que otorga el saldo acumulado en el AFORE
    mediante una renta vitalicia.

    Args:
        saldo_afore:       Saldo al momento del retiro (pesos corrientes)
        genero:            0 = Hombre, 1 = Mujer
        edad_retiro:       Edad al pensionarse
        semanas_cotizadas: Total de semanas cotizadas
        anio_retiro:       Año de retiro
        casado:            1 = tiene cónyuge con pensión de viudez
        genero_conyuge:    Género del cónyuge
        edad_conyuge:      Edad del cónyuge
        tasa_interes:      Tasa técnica actuarial

    Returns:
        {
          "cumple_requisitos": bool,
          "semanas_requeridas":int,
          "pension_mensual":   float,
          "pension_anual":     float,
          "ax_utilizado":      float,
          "tipo":              str,   # "renta_vitalicia" o "retiro_programado"
        }
    """
    requisitos_ok = cumple_requisitos(semanas_cotizadas, anio_retiro, cotizo_antes_1997)

    # Elegir anualidad: conjunta si está casado, individual si no
    if casado == 1 and edad_conyuge > 0:
        ax = ax_conjunto(
            genero_titular  = genero,
            edad_titular    = edad_retiro,
            genero_conyuge  = genero_conyuge,
            edad_conyuge    = edad_conyuge,
            fraccion_viudez = 0.9,
            tasa_interes    = tasa_interes,
        )
        tipo = "renta_vitalicia_conjunta"
    else:
        ax   = get_ax(genero, edad_retiro, tasa_interes, mensual=True)
        tipo = "renta_vitalicia"

    if ax > 0:
        pension_anual   = saldo_afore / ax
        pension_mensual = pension_anual / 12
    else:
        pension_anual   = 0.0
        pension_mensual = 0.0

    return {
        "cumple_requisitos":  requisitos_ok,
        "semanas_requeridas": semanas_requeridas(anio_retiro, cotizo_antes_1997),
        "pension_mensual":    pension_mensual,
        "pension_anual":      pension_anual,
        "ax_utilizado":       ax,
        "tipo":               tipo,
        "saldo_afore":        saldo_afore,
    }


# ─────────────────────────────────────────────────────────────────────────────
# CÁLCULO INTEGRAL
# ─────────────────────────────────────────────────────────────────────────────

def calcular_pension_total(
    saldo_afore:       float,
    sbc_promedio:      float,
    genero:            int,
    edad_retiro:       int,
    semanas_cotizadas: int,
    anio_retiro:       int,
    casado:            int   = 0,
    genero_conyuge:    int   = 0,
    edad_conyuge:      int   = 0,
    tasa_interes:      float = TASA_INTERES_TECNICO,
    cotizo_antes_1997: bool  = False,
) -> dict:
    """
    Calcula la pensión definitiva considerando RCV y PMG.
    La pensión final es el máximo entre ambas.

    Returns:
        {
          "pension_rcv":       dict,   # resultado calcular_pension_rcv
          "pension_pmg":       dict,   # resultado calcular_pmg
          "pension_final":     float,  # mensual en pesos corrientes
          "fuente_pension":    str,    # "RCV" o "PMG"
          "deficit_saldo":     float,  # saldo adicional que pagaría el Estado (PMG)
          "saldo_requerido_pmg": float,# saldo para financiar PMG sin subsidio
          "tasa_reemplazo":    float,  # pension_final / sbc_promedio
          "cumple_para_pensionarse": bool,
        }
    """
    rcv = calcular_pension_rcv(
        saldo_afore       = saldo_afore,
        genero            = genero,
        edad_retiro       = edad_retiro,
        semanas_cotizadas = semanas_cotizadas,
        anio_retiro       = anio_retiro,
        casado            = casado,
        genero_conyuge    = genero_conyuge,
        edad_conyuge      = edad_conyuge,
        tasa_interes      = tasa_interes,
        cotizo_antes_1997 = cotizo_antes_1997,
    )

    pmg = calcular_pmg(
        sbc_promedio      = sbc_promedio,
        edad_retiro       = edad_retiro,
        semanas_cotizadas = semanas_cotizadas,
        anio_retiro       = anio_retiro,
        cotizo_antes_1997 = cotizo_antes_1997,
    )

    pension_rcv_mens = rcv["pension_mensual"]
    pension_pmg_mens = pmg["monto_mensual"] if pmg["aplica"] else 0.0

    # La pensión final: si RCV > PMG el AFORE la financia completamente.
    # Si RCV < PMG, el Estado completa la diferencia hasta el mínimo garantizado.
    if pmg["aplica"] and pension_pmg_mens > pension_rcv_mens:
        pension_final  = pension_pmg_mens
        fuente         = "PMG"
        # Saldo que requeriría el Estado para cubrir la diferencia
        ax             = rcv["ax_utilizado"]
        deficit_saldo  = (pension_pmg_mens - pension_rcv_mens) * 12 * ax
    else:
        pension_final  = pension_rcv_mens
        fuente         = "RCV"
        deficit_saldo  = 0.0

    # Saldo hipotético necesario para financiar la PMG sin subsidio
    saldo_req_pmg = (
        saldo_requerido_para_pension(pension_pmg_mens, genero, edad_retiro, tasa_interes)
        if pmg["aplica"] else 0.0
    )

    tasa_reemplazo = pension_final / sbc_promedio if sbc_promedio > 0 else 0.0

    cumple = rcv["cumple_requisitos"]

    return {
        "pension_rcv":             rcv,
        "pension_pmg":             pmg,
        "pension_final":           pension_final,
        "fuente_pension":          fuente,
        "deficit_saldo":           deficit_saldo,
        "saldo_requerido_pmg":     saldo_req_pmg,
        "tasa_reemplazo":          tasa_reemplazo,
        "cumple_para_pensionarse": cumple,
    }


def calcular_pension_desde_trabajador(trabajador, resultado_saldo: dict) -> dict:
    """
    Wrapper: recibe el objeto Trabajador y el resultado de proyectar_saldo
    y retorna el cálculo completo de pensión.
    """
    saldo_fin       = resultado_saldo["saldo_final"]
    semanas_tot     = resultado_saldo["semanas_totales"]
    detalle         = resultado_saldo["detalle_anual"]

    # SBC promedio de la vida laboral (usando el promedio de la proyección)
    if detalle:
        sbc_promedio = sum(d["sbc_cotizable"] for d in detalle) / len(detalle)
    else:
        sbc_promedio = trabajador.sbc_mensual

    return calcular_pension_total(
        saldo_afore       = saldo_fin,
        sbc_promedio      = sbc_promedio,
        genero            = trabajador.genero,
        edad_retiro       = trabajador.edad_retiro_deseada,
        semanas_cotizadas = semanas_tot,
        anio_retiro       = trabajador.anno_retiro,
        casado            = trabajador.casado,
        genero_conyuge    = trabajador.genero_conyuge,
        edad_conyuge      = trabajador.edad_conyuge,
        cotizo_antes_1997 = bool(trabajador.cotizo_antes_1997),
    )
