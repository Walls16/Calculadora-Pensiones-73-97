"""
calculators/anualidades.py
Calcula anualidades vitalicias contingentes usando tablas de conmutación actuariales.

Tablas de conmutación:
  Dx  = lx × vˣ          donde v = 1/(1+i)
  Nx  = Σ Dx  (desde x hasta ω)
  äx  = Nx / Dx          (anualidad anticipada vitalicia)
  äx(m) = äx - (m-1)/(2m)  (corrección por pagos fraccionados m veces al año)

La anualidad äx es el valor presente de $1 pagado al inicio de cada año
mientras el beneficiario esté vivo, descontado a la tasa técnica i.

äx(12) representa pagos mensuales (m=12).
"""

from config import TASA_INTERES_TECNICO, EDAD_MAXIMA, PAGOS_POR_ANIO
from data_fetchers.tablas_vida import get_lx, get_qx


# ─────────────────────────────────────────────────────────────────────────────
# TABLAS DE CONMUTACIÓN
# ─────────────────────────────────────────────────────────────────────────────

def calcular_tablas_conmutacion(
    genero: int,
    tasa_interes: float = TASA_INTERES_TECNICO,
    edad_inicio:  int   = 0,
) -> dict[int, dict]:
    """
    Calcula las tablas de conmutación actuariales para un género dado.

    Args:
        genero:       0 = Hombre, 1 = Mujer
        tasa_interes: Tasa de interés técnico anual (default 2.34% CNSF)
        edad_inicio:  Edad desde la que se calcula la cohorte

    Returns:
        dict {edad: {"lx", "dx", "Vx", "Dx", "Nx", "ax", "ax_m"}}
    """
    v   = 1.0 / (1.0 + tasa_interes)    # Factor de descuento
    lx  = get_lx(genero, edad_inicio)   # {edad: lx}

    # ── Paso 1: calcular Dx para todas las edades ──────────────────────────
    Dx: dict[int, float] = {}
    for edad in range(edad_inicio, EDAD_MAXIMA + 1):
        Vx        = v ** (edad - edad_inicio)
        Dx[edad]  = lx.get(edad, 0.0) * Vx

    # ── Paso 2: calcular Nx (suma acumulada de Dx de x hasta ω) ───────────
    # Se calcula de mayor a menor para eficiencia
    Nx: dict[int, float] = {}
    acum = 0.0
    for edad in range(EDAD_MAXIMA, edad_inicio - 1, -1):
        acum    += Dx.get(edad, 0.0)
        Nx[edad] = acum

    # ── Paso 3: calcular äx y äx(m) ───────────────────────────────────────
    m = PAGOS_POR_ANIO   # 12 para pagos mensuales

    tablas: dict[int, dict] = {}
    for edad in range(edad_inicio, EDAD_MAXIMA + 1):
        lx_val = lx.get(edad, 0.0)
        qx_val = get_qx(genero, edad)
        Vx_val = v ** (edad - edad_inicio)
        Dx_val = Dx.get(edad, 0.0)
        Nx_val = Nx.get(edad, 0.0)

        if Dx_val > 0:
            ax_val   = Nx_val / Dx_val                    # anualidad anual
            ax_m_val = ax_val - (m - 1) / (2 * m)        # corrección mensual
        else:
            ax_val   = 0.0
            ax_m_val = 0.0

        tablas[edad] = {
            "lx":    lx_val,
            "qx":    qx_val,
            "dx":    lx_val * qx_val,
            "Vx":    Vx_val,
            "Dx":    Dx_val,
            "Nx":    Nx_val,
            "ax":    max(ax_val, 0.0),
            "ax_m":  max(ax_m_val, 0.0),
        }

    return tablas


# ─────────────────────────────────────────────────────────────────────────────
# API PÚBLICA
# ─────────────────────────────────────────────────────────────────────────────

def get_ax(
    genero:       int,
    edad:         int,
    tasa_interes: float = TASA_INTERES_TECNICO,
    mensual:      bool  = True,
) -> float:
    """
    Retorna la anualidad vitalicia äx para un género y edad dados.

    Args:
        genero:       0 = Hombre, 1 = Mujer
        edad:         Edad al momento de iniciar la pensión
        tasa_interes: Tasa de interés técnico (default CNSF 2.34%)
        mensual:      Si True, retorna äx(12); si False, retorna äx anual

    Returns:
        Valor de la anualidad (ej: 16.5 significa $16.50 de valor presente por $1 de pensión anual)
    """
    tablas = calcular_tablas_conmutacion(genero, tasa_interes)
    edad   = max(0, min(edad, EDAD_MAXIMA))
    fila   = tablas.get(edad, {})
    return fila.get("ax_m" if mensual else "ax", 0.0)


def pension_desde_saldo(
    saldo:        float,
    genero:       int,
    edad:         int,
    tasa_interes: float = TASA_INTERES_TECNICO,
    frecuencia:   str   = "mensual",
) -> float:
    """
    Calcula la pensión mensual (o anual) que puede pagar un saldo dado
    mediante una anualidad vitalicia.

    Fórmula: pensión_anual = saldo / äx(12)
             pensión_mensual = pensión_anual / 12

    Args:
        saldo:        Saldo acumulado en el AFORE (pesos)
        genero:       0 = Hombre, 1 = Mujer
        edad:         Edad al retiro
        tasa_interes: Tasa de interés técnico
        frecuencia:   "mensual" o "anual"

    Returns:
        Monto de pensión en pesos
    """
    ax_m = get_ax(genero, edad, tasa_interes, mensual=True)

    if ax_m <= 0:
        return 0.0

    # äx(12) es el valor presente de $1 de pensión ANUAL pagada mensualmente
    # Entonces: pensión_anual = saldo / äx(12)
    pension_anual   = saldo / ax_m
    pension_mensual = pension_anual / 12

    return pension_mensual if frecuencia == "mensual" else pension_anual


def saldo_requerido_para_pension(
    pension_mensual_deseada: float,
    genero:                  int,
    edad:                    int,
    tasa_interes:            float = TASA_INTERES_TECNICO,
) -> float:
    """
    Calcula el saldo necesario para financiar una pensión mensual dada.

    Args:
        pension_mensual_deseada: Monto mensual deseado (pesos)
        genero:                  0 = Hombre, 1 = Mujer
        edad:                    Edad al retiro
        tasa_interes:            Tasa de interés técnico

    Returns:
        Saldo necesario en pesos
    """
    ax_m = get_ax(genero, edad, tasa_interes, mensual=True)
    return pension_mensual_deseada * 12 * ax_m


def ax_conjunto(
    genero_titular:  int,
    edad_titular:    int,
    genero_conyuge:  int,
    edad_conyuge:    int,
    fraccion_viudez: float = 0.9,
    tasa_interes:    float = TASA_INTERES_TECNICO,
) -> float:
    """
    Calcula la anualidad conjunta para titular + cónyuge (pensión de viudez).

    äxy = äx + äy - äxy  (donde äxy es la anualidad del último sobreviviente)

    Aproximación usando independencia de vidas:
      äxy(conjunta) = fraccion_viudez × äy  (simplificación para LSS)

    En realidad LSS paga el 90% de la pensión al cónyuge sobreviviente.
    Por simplificación usamos:
      äxy = äx + fraccion_viudez × äy × (Dx(y)/Dx(x))   [aproximación]

    Args:
        genero_titular:  Género del pensionado titular
        edad_titular:    Edad del titular al retiro
        genero_conyuge:  Género del cónyuge
        edad_conyuge:    Edad del cónyuge al retiro
        fraccion_viudez: Porcentaje de pensión al cónyuge sobreviviente (90% LSS)
        tasa_interes:    Tasa técnica

    Returns:
        Factor de anualidad conjunta
    """
    ax_titular  = get_ax(genero_titular, edad_titular, tasa_interes)
    ax_conyuge  = get_ax(genero_conyuge, edad_conyuge, tasa_interes)

    # Tabla de conmutación para ambos
    tablas_t = calcular_tablas_conmutacion(genero_titular, tasa_interes)
    tablas_c = calcular_tablas_conmutacion(genero_conyuge, tasa_interes)

    Dx_t = tablas_t.get(edad_titular, {}).get("Dx", 1.0)
    Dx_c = tablas_c.get(edad_conyuge, {}).get("Dx", 1.0)

    if Dx_t <= 0:
        return ax_titular

    # Corrección por diferencia de edades entre titular y cónyuge
    factor_conyuge = (Dx_c / Dx_t) if Dx_t > 0 else 1.0

    # La pensión conjunta es la pensión del titular + la pensión de viudez
    # descontada al valor presente relativo al titular
    ax_conjunto_val = ax_titular + fraccion_viudez * ax_conyuge * factor_conyuge
    return ax_conjunto_val / 12   # convertir a base mensual equivalente
